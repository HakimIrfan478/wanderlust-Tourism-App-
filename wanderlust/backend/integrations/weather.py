"""
Live weather via the Open-Meteo API (https://open-meteo.com).

Open-Meteo is a real, free weather API that requires no API key, which makes it
usable from anywhere without credentials in the repository. Given a latitude
and longitude (each destination stores its own), this returns current
conditions plus a short daily forecast.

Responses are cached, and every failure path returns a structured
``available: False`` payload rather than raising. The report treats these
integrations as non-critical features, so a provider outage must degrade the
destination screen, never break it.
"""
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes -> human readable
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}

# Rough icon hints so the app can render something sensible without shipping
# its own copy of the WMO code table.
ICON_GROUPS = [
    ({0, 1}, "sunny"),
    ({2, 3}, "cloudy"),
    ({45, 48}, "fog"),
    ({51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}, "rain"),
    ({71, 73, 75, 77, 85, 86}, "snow"),
    ({95, 96, 99}, "storm"),
]


def describe_code(code):
    return WEATHER_CODES.get(code, "Unknown")


def icon_for_code(code):
    for codes, name in ICON_GROUPS:
        if code in codes:
            return name
    return "cloudy"


def _cache_key(latitude, longitude, days):
    # One decimal place is ~11km, which is plenty for a city forecast and
    # gives nearby destinations a shared cache entry.
    return f"weather:{latitude:.1f}:{longitude:.1f}:{days}"


def _unavailable(reason):
    return {
        "source": "open-meteo",
        "available": False,
        "detail": reason,
        "current": None,
        "forecast": [],
    }


def get_weather(latitude: float, longitude: float, days: int = 5) -> dict:
    """Current weather plus an N-day forecast, or an ``available: False`` dict.

    Never raises for a provider problem: callers treat weather as decoration.
    """
    try:
        latitude, longitude = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return _unavailable("Invalid coordinates.")

    days = max(1, min(int(days), 16))
    key = _cache_key(latitude, longitude, days)
    cached = cache.get(key)
    if cached is not None:
        return {**cached, "cached": True}

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
        "precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": days,
    }

    try:
        response = requests.get(
            OPEN_METEO_URL, params=params, timeout=settings.EXTERNAL_API_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.warning("Open-Meteo request failed: %s", exc)
        return _unavailable("The weather service could not be reached.")
    except ValueError as exc:
        logger.warning("Open-Meteo returned invalid JSON: %s", exc)
        return _unavailable("The weather service returned an unreadable response.")

    result = _shape(data)
    cache.set(key, result, settings.WEATHER_CACHE_SECONDS)
    return {**result, "cached": False}


def _shape(data: dict) -> dict:
    """Reduce the provider payload to the fields the app actually renders."""
    current = data.get("current") or {}
    daily = data.get("daily") or {}

    dates = daily.get("time") or []
    codes = daily.get("weather_code") or []
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    rain = daily.get("precipitation_probability_max") or []

    forecast = []
    for index, date in enumerate(dates):
        # Index defensively: the provider can return a short series near the
        # end of its forecast window.
        code = codes[index] if index < len(codes) else None
        forecast.append(
            {
                "date": date,
                "condition": describe_code(code),
                "icon": icon_for_code(code),
                "temp_max_c": highs[index] if index < len(highs) else None,
                "temp_min_c": lows[index] if index < len(lows) else None,
                "precipitation_chance_pct": rain[index] if index < len(rain) else None,
            }
        )

    current_code = current.get("weather_code")
    return {
        "source": "open-meteo",
        "available": True,
        "timezone": data.get("timezone"),
        "current": {
            "temperature_c": current.get("temperature_2m"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "condition": describe_code(current_code),
            "icon": icon_for_code(current_code),
        },
        "forecast": forecast,
    }
