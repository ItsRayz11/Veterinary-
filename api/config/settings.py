"""Django settings. All environment-specific values come from env vars (see .env.example)."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY", default="dev-only-insecure-key" if DEBUG else None)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "simple_history",
    "apps.core",
    "apps.accounts",
    "apps.countries",
    "apps.species",
    "apps.units",
    "apps.companies",
    "apps.sources",
    "apps.pharma",
    "apps.clinical",
    "apps.calculators",
    "apps.search",
    "apps.pricing",
    "apps.education",
    "apps.staff",
    "apps.ingestion",
    "apps.opportunities",
    "apps.automation",
    "apps.assistant",
    "apps.monitoring",
    "apps.push",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.StaffMFAMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Postgres (Neon or local) in every real environment. SQLite is only the zero-setup fallback for
# quick local runs; Postgres-only features (pg_trgm, FTS) are added behind feature checks later.
DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{n}"}
    for n in (
        "UserAttributeSimilarityValidator",
        "MinimumLengthValidator",
        "CommonPasswordValidator",
        "NumericPasswordValidator",
    )
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Throttle counters live in the cache. Serverless instances do not share memory, so production
# must use a shared backend, e.g. CACHE_URL=dbcache://django_cache (run `createcachetable`).
CACHES = {"default": env.cache("CACHE_URL", default="locmemcache://")}

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticatedOrReadOnly"],
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.core.throttling.AnonThrottle",
        "apps.core.throttling.UserThrottle",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "apps.core.parsers.ObjectJSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min",
        "user": "600/min",
        "auth": "10/min",
        "submit": "20/hour",
        "assistant": "20/hour",
        "client_error": "30/hour",
        "submit_listing": "20/hour",
        "report": "30/hour",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "apps.core.errors.api_exception_handler",
}
SPECTACULAR_SETTINGS = {"TITLE": "Veterinary Intelligence Platform API", "VERSION": "0.1.0"}

# Optional. Without a key the assistant only lists matching reviewed records.
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
ASSISTANT_MODEL = env("ASSISTANT_MODEL", default="claude-opus-5-5")

# The Django admin lives at /<ADMIN_URL>. A non-default path only reduces automated probing; the
# real protection is authentication and roles. Must end with "/".
ADMIN_URL = env("ADMIN_URL", default="admin/")

# The web app reads the CSRF token from /auth/csrf, never from the cookie, so JavaScript has no
# reason to see the cookie.
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# JSON bodies are small; the largest is a 2 MB CSV import wrapped in JSON.
DATA_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200

# Optional error monitoring for server errors; empty = off. Personal data is never sent.
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    from apps.monitoring import sentry as _sentry

    _sentry.init(
        SENTRY_DSN,
        environment=env("SENTRY_ENVIRONMENT", default="production" if not DEBUG else "development"),
        traces=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
    )

# Two-factor authentication (apps/accounts/mfa.py). Mandatory for staff in production; off by
# default in DEBUG so local development and tests do not need an authenticator app.
REQUIRE_STAFF_MFA = env.bool("REQUIRE_STAFF_MFA", default=not DEBUG)
# A Fernet key: Fernet.generate_key() from the `cryptography` package, urlsafe-base64, 32 bytes.
# Set it before enrolling real users; otherwise the key derives from SECRET_KEY.
MFA_ENCRYPTION_KEY = env("MFA_ENCRYPTION_KEY", default="")

# Per-account sign-in lockout (apps/accounts/lockout.py).
LOGIN_MAX_FAILURES = env.int("LOGIN_MAX_FAILURES", default=8)
LOGIN_LOCK_SECONDS = env.int("LOGIN_LOCK_SECONDS", default=900)

# Shared with the web app (same variable name there). When it matches the X-Web-Proxy-Secret
# header, the API trusts X-Client-IP for per-IP throttling; without it every forwarding header is
# ignored (see apps/core/throttling.py). Set it on both projects in production.
WEB_PROXY_SECRET = env("WEB_PROXY_SECRET", default="")

# Shared secret for scheduler-triggered tasks (/api/v1/cron/<task>/). Empty = endpoint disabled.
CRON_SECRET = env("CRON_SECRET", default="")

SHOW_DEVELOPMENT_DATA = env.bool("SHOW_DEVELOPMENT_DATA", default=DEBUG)
# Catalogue records imported from public lists but not yet reviewed are listed, clearly labelled.
# Clinical data is never affected. Set false to hide them until a reviewer signs off.
SHOW_UNVERIFIED_IMPORTS = env.bool("SHOW_UNVERIFIED_IMPORTS", default=True)

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])
# The web app proxies /api/v1 to this API, so state-changing requests carry the web origin.
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["http://localhost:3000"])

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_HSTS_SECONDS = 31536000
    # Subdomain-wide HSTS and preload are hard to undo, so they are an explicit owner decision
    # (docs/SECURITY.md) rather than a default.
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
    SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
    SILENCED_SYSTEM_CHECKS = [
        c
        for c, on in (
            ("security.W005", SECURE_HSTS_INCLUDE_SUBDOMAINS),
            ("security.W021", SECURE_HSTS_PRELOAD),
        )
        if not on
    ]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"std": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "std"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}

# Web push (optional): generate keys with `manage.py generate_vapid_keys`. Off while unset.
VAPID_PUBLIC_KEY = env("VAPID_PUBLIC_KEY", default="")
VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY", default="")
VAPID_SUBJECT = env("VAPID_SUBJECT", default="mailto:admin@example.com")
