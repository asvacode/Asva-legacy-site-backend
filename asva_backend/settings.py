import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from django.templatetags.static import static


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me-in-production")

DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

# Comma or whitespace separated. In production set DJANGO_DEBUG=false and list real hostnames.
_raw_hosts = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "").replace(",", " ").split() if h.strip()]
ALLOWED_HOSTS: list[str] = _raw_hosts or ["localhost", "127.0.0.1", os.getenv("RENDER_EXTERNAL_HOSTNAME")]
# So local runserver / curl still work when DJANGO_ALLOWED_HOSTS lists only a public hostname.
for _h in ("localhost", "127.0.0.1"):
    if _h not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_h)
if DEBUG and "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").replace(",", " ").split() if o.strip()]

NEXTJS_ORIGINS = os.getenv("NEXTJS_ORIGINS", "")

# Outbound webhook: Django calls Next.js on-demand revalidation when Content is published.
NEXTJS_WEBHOOK_SECRET = os.getenv("NEXTJS_WEBHOOK_SECRET", "")
NEXTJS_REVALIDATE_URL = os.getenv("NEXTJS_REVALIDATE_URL", "")
# Path sent to Next for each slug, e.g. "/blog/{slug}" or "/{slug}"
NEXTJS_REVALIDATE_PATH_TEMPLATE = os.getenv("NEXTJS_REVALIDATE_PATH_TEMPLATE", "/{slug}")

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "accounts",
    "payments",
    "cms.apps.CmsConfig",
    "phonenumber_field"
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "asva_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "asva_backend.wsgi.application"
ASGI_APPLICATION = "asva_backend.asgi.application"


_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            _database_url,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


STATIC_URL = "static/"
STATICFILES_DIRS = [
    BASE_DIR / "asva_backend" / "static"
]
STATIC_ROOT = BASE_DIR / "staticfiles"

if not DEBUG:
    # Enable the WhiteNoise storage backend, which compresses static files to reduce disk use
    # and renames the files with unique names for each version to support long-term caching
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
}


CORS_ALLOW_CREDENTIALS = True

_nextjs_origins = [o.strip() for o in NEXTJS_ORIGINS.replace(",", " ").split() if o.strip()]
if _nextjs_origins:
    CORS_ALLOWED_ORIGINS = _nextjs_origins
elif DEBUG:
    # Local Next.js dev server; set NEXTJS_ORIGINS in production instead of relying on this.
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://asva-legacy-project-frontend-5wxf.vercel.app",
    ]
else:
    CORS_ALLOW_ALL_ORIGINS = False


UNFOLD = {
    "SITE_TITLE": "ASVA Site Admin",
    "SITE_HEADER": " ",
    "SITE_ICON": {
        "dark": lambda request: static("images/asva-text-dark.svg"),
        "light": lambda request: static('images/asva-text-light.svg')
    },
     "COLORS": {
        "base": {
            "50": "#F8FAFC",
            "100": "#F1F5F9",
            "200": "#E2E8F0",
            "300": "#CBD5E1",
            "400": "#94A3B8",
            "500": "#64748B",
            "600": "#475569",
            "700": "#334155",
            "800": "#1E293B",
            "900": "#0F172A",
            "950": "#020817",
        },
        "primary": {
            "50": "#F0FDF4",
            "100": "#DCFCE7",
            "200": "#BBF7D0",
            "300": "#86EFAC",
            "400": "#4ADE80",
            "500": "#22C55E",
            "600": "#16A34A",
            "700": "#15803D",
            "800": "#166534",
            "900": "#14532D",
            "950": "#052E16",
        },
        "font": {
            "subtle-light": "#64748B",
            "subtle-dark": "#94A3B8",
            "default-light": "#334155",
            "default-dark": "#E2E8F0",
            "important-light": "#020817",
            "important-dark": "#F8FAFC",
        },
    }
}


# django_phonenumber_field settings...
PHONENUMBER_DEFAULT_REGION = "NG"
PHONENUMBER_DEAFULT_FORMAT= "E164"