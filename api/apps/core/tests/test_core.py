import pytest
from django.urls import reverse

from apps.core.models import AuditLog


@pytest.mark.django_db
def test_health(client):
    r = client.get(reverse("health"))
    assert r.status_code == 200 and r.json() == {"status": "ok"}


@pytest.mark.django_db
def test_audit_log_is_immutable():
    entry = AuditLog.objects.create(action="x", object_type="t", object_id="1")
    entry.reason = "edit"
    with pytest.raises(ValueError):
        entry.save()
    with pytest.raises(ValueError):
        entry.delete()
