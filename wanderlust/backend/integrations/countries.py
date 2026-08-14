"""
Country facts for the destination screen.

Originally this called REST Countries v3.1, which was free and needed no key.
During the project that API was deprecated: requests to /v3.1 now 301-redirect
to a stub that returns ``{"success": false, ...}``, and the replacement v5 API
requires an ``Authorization: Bearer`` key obtained by signing up. That is
exactly the risk the project's risk register anticipated for third-party data
("downtime, rate limits, or changes its terms"), so the provider is now
pluggable rather than hard-coded:

``countries.dev``  (default)
    Keyless, no signup, same field set as the old REST Countries v3.1.

``restcountries``
    REST Countries v5. Selected automatically when RESTCOUNTRIES_API_KEY is
    set, so the original source can be restored without a code change.

Both providers are normalised to one response shape, so nothing downstream —
the serializer, the app, the tests — knows or cares which one answered.
Failures return ``available: False`` instead of raising: country facts are
decoration on the destination screen, never a reason to fail the page.
"""
import json
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

COUNTRIES_DEV_URL = "https://countries.dev/alpha/{code}"
RESTCOUNTRIES_V5_URL = "https://api.restcountries.com/countries/v5/alpha/{code}"

PROVIDER_COUNTRIES_DEV = "countries.dev"
PROVIDER_RESTCOUNTRIES = "restcountries"


def active_provider():
    """Which provider this deployment will use, and why."""
    configured = getattr(settings, "COUNTRY_API_PROVIDER", "auto")
    if configured in (PROVIDER_COUNTRIES_DEV, PROVIDER_RESTCOUNTRIES):
        return configured
    # auto: use REST Countries only if a key is available, since v5 rejects
    # unauthenticated requests with a 401.
    if getattr(settings, "RESTCOUNTRIES_API_KEY", ""):
        return PROVIDER_RESTCOUNTRIES
    return PROVIDER_COUNTRIES_DEV


def _unavailable(code, reason):
    return {
        "source": active_provider(),
        "available": False,
        "detail": reason,
        "country_code": (code or "").upper(),
    }


def get_country_info(country_code: str) -> dict:
    """Travel-relevant facts for an ISO 3166-1 alpha-2 country code."""
    code = (country_code or "").strip()
    if len(code) != 2 or not code.isalpha():
        return _unavailable(code, "Expected a two-letter ISO country code.")

    provider = active_provider()
    key = f"country:{provider}:{code.lower()}"
    cached = cache.get(key)
    if cached is not None:
        return {**cached, "cached": True}

    if provider == PROVIDER_RESTCOUNTRIES:
        url = RESTCOUNTRIES_V5_URL.format(code=code.upper())
        headers = {"Authorization": f"Bearer {settings.RESTCOUNTRIES_API_KEY}"}
    else:
        url = COUNTRIES_DEV_URL.format(code=code.upper())
        headers = {"Accept": "application/json"}

    try:
        response = requests.get(
            url, headers=headers, timeout=settings.EXTERNAL_API_TIMEOUT
        )
        response.raise_for_status()
        # Decode the raw bytes rather than using response.json(): the provider
        # omits a charset in its Content-Type, so requests falls back to
        # guessing, and it guesses wrong often enough to turn "Ελλάδα" into
        # mojibake. JSON is UTF-8 by specification, so parse it as such.
        data = json.loads(response.content)
    except requests.RequestException as exc:
        logger.warning("%s request failed for %s: %s", provider, code, exc)
        return _unavailable(code, "The country information service could not be reached.")
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning("%s returned invalid JSON for %s: %s", provider, code, exc)
        return _unavailable(code, "The country service returned an unreadable response.")

    # v5 wraps results in {"objects": [...]}; some endpoints return a bare list.
    if isinstance(data, dict) and "objects" in data:
        objects = data.get("objects") or []
        data = objects[0] if objects else None
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict) or not data:
        return _unavailable(code, "No country matched that code.")

    # A deprecated provider can answer 200 with an error envelope; treat an
    # explicit failure flag or a missing name as "no usable data".
    if data.get("success") is False:
        message = (data.get("errors") or [{}])[0].get("message", "Provider error.")
        logger.warning("%s reported an error for %s: %s", provider, code, message)
        return _unavailable(code, message)

    result = _shape(data, code, provider)
    if not result["name"]:
        return _unavailable(code, "The country service returned no usable data.")

    cache.set(key, result, settings.COUNTRY_CACHE_SECONDS)
    return {**result, "cached": False}


def _first(value):
    """Providers return capital as either a string or a one-item list."""
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _shape(data: dict, code: str, provider: str) -> dict:
    """Normalise either provider's payload into one response shape."""
    name = data.get("name")
    official = data.get("officialName") or data.get("nativeName")
    if isinstance(name, dict):  # REST Countries nests name.common / name.official
        official = name.get("official") or official
        name = name.get("common")

    currencies = data.get("currencies") or []
    if isinstance(currencies, dict):  # REST Countries keys by currency code
        currencies = [
            {"code": key, "name": info.get("name"), "symbol": info.get("symbol")}
            for key, info in currencies.items()
        ]
    else:
        currencies = [
            {"code": c.get("code"), "name": c.get("name"), "symbol": c.get("symbol")}
            for c in currencies
            if isinstance(c, dict)
        ]

    languages = data.get("languages") or []
    if isinstance(languages, dict):
        languages = list(languages.values())
    else:
        languages = [
            l.get("name") if isinstance(l, dict) else l for l in languages
        ]

    flags = data.get("flags") or {}
    flag_png = flags.get("png") if isinstance(flags, dict) else None

    return {
        "source": provider,
        "available": True,
        "country_code": data.get("alpha2Code") or data.get("cca2") or code.upper(),
        "name": name,
        "official_name": official or name,
        "capital": _first(data.get("capital")),
        "region": data.get("region"),
        "subregion": data.get("subregion"),
        "population": data.get("population"),
        "currencies": [c for c in currencies if c.get("name")],
        "languages": [l for l in languages if l],
        "timezones": data.get("timezones") or [],
        "flag_png": flag_png,
        "flag_emoji": data.get("flag") if isinstance(data.get("flag"), str) else None,
        "area_km2": data.get("area"),
        "calling_code": _first(data.get("callingCodes") or data.get("idd")),
    }
