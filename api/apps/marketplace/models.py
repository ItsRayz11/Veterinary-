from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from apps.core.models import TimeStampedModel

STOCK_STALE_AFTER = timedelta(days=14)
MAX_GLB_BYTES = (
    3 * 1024 * 1024
)  # base64 of this fits the 4 MB request cap and Vercel's 4.5 MB limit


class ApprovalStatus(models.TextChoices):
    PENDING = "pending", "Pending review"
    APPROVED = "approved", "Approved"
    PAUSED = "paused", "Paused"
    REMOVED = "removed", "Removed"


# ---------- retailers and offers ----------


class RetailerKind(models.TextChoices):
    ONLINE = "online", "Online shop"
    OFFLINE = "offline", "Physical store"
    BOTH = "both", "Online and physical"


class Retailer(TimeStampedModel):
    name = models.CharField(max_length=160)
    country = models.ForeignKey("countries.Country", on_delete=models.PROTECT, related_name="+")
    city = models.CharField(max_length=100, blank=True)
    kind = models.CharField(max_length=8, choices=RetailerKind.choices)
    website = models.URLField(blank=True)
    status = models.CharField(
        max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="retailers",
    )  # fmt: skip
    integrates_stock = models.BooleanField(
        default=False, help_text="Retailer syncs stock itself; otherwise staff confirm manually"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StockState(models.TextChoices):
    IN_STOCK = "in_stock", "In stock"
    OUT = "out_of_stock", "Out of stock"
    LIMITED = "limited", "Limited"
    UNKNOWN = "unknown", "Unknown"


class RetailerOffer(TimeStampedModel):
    retailer = models.ForeignKey(Retailer, on_delete=models.CASCADE, related_name="offers")
    pack = models.ForeignKey("pharma.ProductPack", on_delete=models.CASCADE, related_name="+")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    price_observed_on = models.DateField()
    stock_state = models.CharField(
        max_length=14, choices=StockState.choices, default=StockState.UNKNOWN
    )
    stock_checked_at = models.DateTimeField(null=True, blank=True)
    listing_url = models.URLField(blank=True)
    tax_shipping_note = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING
    )
    verified = models.BooleanField(default=False)
    history = HistoricalRecords()

    class Meta:
        ordering = ["amount"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="offer_amount_positive"),
            models.UniqueConstraint(
                fields=["retailer", "pack"], name="one_offer_per_retailer_pack"
            ),
        ]

    def clean(self):
        self.currency = (self.currency or "").upper()
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValidationError("Currency must be a 3-letter ISO 4217 code.")
        if self.listing_url and not self.listing_url.startswith("https://"):
            raise ValidationError("Listing links must use https.")
        if self.stock_state != StockState.UNKNOWN and not self.stock_checked_at:
            raise ValidationError("Record when the stock was checked, or leave it Unknown.")

    @property
    def effective_stock(self) -> str:
        """Never claims stock that was not recently confirmed."""
        if self.stock_state == StockState.UNKNOWN or not self.stock_checked_at:
            return StockState.UNKNOWN
        if timezone.now() - self.stock_checked_at > STOCK_STALE_AFTER:
            return StockState.UNKNOWN
        return self.stock_state


class FxRate(TimeStampedModel):
    """Admin-entered indicative rate. VetRef never fetches or invents exchange rates."""

    currency = models.CharField(max_length=3, unique=True)
    usd_per_unit = models.DecimalField(max_digits=18, decimal_places=8)
    as_of = models.DateTimeField()
    source_note = models.CharField(max_length=200, help_text="Where the rate came from")

    def clean(self):
        self.currency = (self.currency or "").upper()
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValidationError("Currency must be a 3-letter ISO 4217 code.")
        if self.usd_per_unit is not None and self.usd_per_unit <= Decimal("0"):
            raise ValidationError("The rate must be positive.")

    def __str__(self):
        return f"{self.currency} @ {self.as_of:%Y-%m-%d}"


# ---------- 3D catalogs ----------


class Supplier(TimeStampedModel):
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    country = models.ForeignKey(
        "countries.Country", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    website = models.URLField(blank=True)
    status = models.CharField(
        max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING
    )
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="supplier"
    )

    def __str__(self):
        return self.name


def validate_glb(data: bytes) -> None:
    """Structural check of a binary glTF 2.0 file. This is validation, not a malware scan."""
    if len(data) > MAX_GLB_BYTES:
        raise ValidationError(f"The file is larger than {MAX_GLB_BYTES // 1024 // 1024} MB.")
    if len(data) < 20 or data[:4] != b"glTF":
        raise ValidationError("Not a GLB file.")
    version = int.from_bytes(data[4:8], "little")
    length = int.from_bytes(data[8:12], "little")
    if version != 2 or length != len(data):
        raise ValidationError("Unsupported or corrupted GLB (needs glTF 2.0 with a valid length).")
    if data[16:20] != b"JSON":
        raise ValidationError("The GLB's first chunk must be JSON.")


class Catalog3D(TimeStampedModel):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="catalogs")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    collection = models.CharField(max_length=100, blank=True)
    product = models.ForeignKey(
        "pharma.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    asset = models.BinaryField(editable=False, null=True)
    asset_size = models.PositiveIntegerField(default=0, editable=False)
    fallback_image_path = models.CharField(
        max_length=200, blank=True, help_text="Same-site image path, e.g. /images/x.png"
    )
    rights_confirmed = models.BooleanField(
        default=False, help_text="Supplier confirms it owns or may license the asset"
    )
    price_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_currency = models.CharField(max_length=3, blank=True)
    sha256 = models.CharField(max_length=64, blank=True, editable=False)
    scan_status = models.CharField(max_length=10, default="pending", editable=False)
    scan_detail = models.CharField(max_length=300, blank=True, editable=False)
    scanned_at = models.DateTimeField(null=True, blank=True, editable=False)
    status = models.CharField(
        max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING
    )
    reject_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def clean(self):
        if self.fallback_image_path and not (
            self.fallback_image_path.startswith("/") and "//" not in self.fallback_image_path
        ):
            raise ValidationError("The fallback image must be a same-site path starting with /.")
        self.price_currency = (self.price_currency or "").upper()
        if bool(self.price_amount) != bool(self.price_currency):
            raise ValidationError("Give both a price and its currency, or neither.")
        if self.price_amount is not None and self.price_amount <= 0:
            raise ValidationError("The price must be positive.")
        if self.status == ApprovalStatus.APPROVED:
            if not self.rights_confirmed:
                raise ValidationError("Asset rights must be confirmed before approval.")
            if self.asset_size and self.scan_status != "clean":
                raise ValidationError(
                    f"The upload scan result is '{self.scan_status}'; it must be clean to approve."
                )


class PlanKind(models.TextChoices):
    ONE_TIME = "one_time", "One-time catalog purchase"
    SUBSCRIPTION = "subscription", "Supplier subscription"
    LISTING = "listing", "Paid listing"


class CatalogPlan(TimeStampedModel):
    """A commercial plan. Prices are shown, but no payment is taken until payments are enabled."""

    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=12, choices=PlanKind.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    description = models.CharField(max_length=300, blank=True)
    active = models.BooleanField(default=False)

    def clean(self):
        self.currency = (self.currency or "").upper()
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValidationError("Currency must be a 3-letter ISO 4217 code.")

    def __str__(self):
        return self.name


class LeadStatus(models.TextChoices):
    NEW = "new", "New"
    CONTACTED = "contacted", "Contacted"
    CLOSED = "closed", "Closed"


class Lead(TimeStampedModel):
    """A seller or buyer enquiry. This is the only 'purchase' path until payments are approved."""

    name = models.CharField(max_length=120)
    email = models.EmailField()
    company = models.CharField(max_length=160, blank=True)
    plan = models.ForeignKey(CatalogPlan, null=True, blank=True, on_delete=models.SET_NULL)
    catalog = models.ForeignKey(Catalog3D, null=True, blank=True, on_delete=models.SET_NULL)
    message = models.CharField(max_length=1000, blank=True)
    status = models.CharField(max_length=10, choices=LeadStatus.choices, default=LeadStatus.NEW)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} <{self.email}>"
