"""
Django settings for the Wanderlust tourism management backend.

Database: PostgreSQL when USE_SQLITE=0, otherwise a local SQLite file.
The default shipped in .env is SQLite so the project runs with no database
server to install; switch USE_SQLITE to 0 to use PostgreSQL.

Configuration is read from backend/.env (see .env.example). The loader below
is deliberately dependency-free so the project has one less package to install.
"""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path):
    """Populate os.environ from a KEY=VALUE file.

    Real environment variables always win, so `USE_SQLITE=0 python manage.py ...`
    still overrides the file. Missing file is not an error.
    """
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_dotenv(BASE_DIR / ".env")


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-change-me-in-production")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    # Local apps
    "accounts",
    "destinations",
    "recommendations",
    "integrations",
    "evaluation",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "wanderlust.urls"

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

WSGI_APPLICATION = "wanderlust.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
if env_bool("USE_SQLITE", True):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "wanderlust"),
            "USER": env("DB_USER", "wanderlust"),
            "PASSWORD": env("DB_PASSWORD", "wanderlust"),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
        }
    }

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# DRF + JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # JWT is what the mobile app uses. Session auth is additionally enabled
        # so the DRF browsable API works when logged into /admin/, which makes
        # the API demonstrable from a browser.
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=6),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ---------------------------------------------------------------------------
# CORS (React Native / Expo dev client talks to this API)
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL", True)
CORS_ALLOWED_ORIGINS = [
    o for o in env("CORS_ALLOWED_ORIGINS", "").split(",") if o
]

# ---------------------------------------------------------------------------
# i18n / static
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
# Used to cache the two external API responses (Open-Meteo, REST Countries)
# so a provider outage or rate limit degrades gracefully instead of failing
# the request. In-memory is enough for a single-process dev server; point
# CACHE_BACKEND at Redis/Memcached in production.
CACHES = {
    "default": {
        "BACKEND": env(
            "CACHE_BACKEND", "django.core.cache.backends.locmem.LocMemCache"
        ),
        "LOCATION": env("CACHE_LOCATION", "wanderlust-cache"),
        "TIMEOUT": 60 * 30,
    }
}

WEATHER_CACHE_SECONDS = int(env("WEATHER_CACHE_SECONDS", 60 * 30))  # 30 minutes
COUNTRY_CACHE_SECONDS = int(env("COUNTRY_CACHE_SECONDS", 60 * 60 * 24))  # 24 hours
EXTERNAL_API_TIMEOUT = float(env("EXTERNAL_API_TIMEOUT", 10))

# Country facts provider: "auto" | "countries.dev" | "restcountries".
# REST Countries deprecated its keyless v3.1 API during this project and v5
# requires a key, so the keyless countries.dev is the default. Set a key here
# to switch back to REST Countries without changing any code.
COUNTRY_API_PROVIDER = env("COUNTRY_API_PROVIDER", "auto")
RESTCOUNTRIES_API_KEY = env("RESTCOUNTRIES_API_KEY", "")

# ---------------------------------------------------------------------------
# Recommender configuration
# ---------------------------------------------------------------------------
# The project compares two content-based recommenders over the same catalogue:
#
#   "semantic" -> sentence-transformers bi-encoder (all-MiniLM-L6-v2), the
#                 transformer condition of the experiment.
#   "tfidf"    -> scikit-learn TF-IDF + cosine similarity, the classical
#                 baseline / control condition.
#
# Both are selectable explicitly at request time; RECOMMENDER_DEFAULT_MODEL
# only decides what an unqualified request gets.
EMBEDDING_MODEL_NAME = env("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
RECOMMENDER_DEFAULT_MODEL = env("RECOMMENDER_DEFAULT_MODEL", "semantic")

# Set to 1 to skip loading the transformer entirely (fast test runs, or
# machines where torch will not install). The TF-IDF baseline still works.
DISABLE_SEMANTIC_MODEL = env_bool("DISABLE_SEMANTIC_MODEL", False)

# Load the transformer in a background thread when the server starts, so the
# first user request does not pay the ~10s model load and time out.
RECOMMENDER_WARMUP = env_bool("RECOMMENDER_WARMUP", True)

# Allow the transformer to be loaded from the local HuggingFace cache only,
# so evaluation runs are reproducible and work offline.
HF_OFFLINE_ONLY = env_bool("HF_OFFLINE_ONLY", False)

# Where `manage.py run_evaluation` writes its results.
EVALUATION_OUTPUT_DIR = Path(env("EVALUATION_OUTPUT_DIR", BASE_DIR / "evaluation_results"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.utils.autoreload": {"level": "WARNING", "propagate": False},
    },
}
