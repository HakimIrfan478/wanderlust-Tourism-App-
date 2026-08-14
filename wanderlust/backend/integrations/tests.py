"""Tests for the two external-API integrations.

Every provider call is mocked. These tests exist mainly to prove the graceful
degradation the report's risk register promises: a provider outage must not
propagate to the client as an error.
"""
import json
from unittest.mock import patch

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings

from destinations.models import Destination

from . import countries, weather

WEATHER_PAYLOAD = {
    "timezone": "Europe/Athens",
    "current": {
        "temperature_2m": 24.5,
        "relative_humidity_2m": 60,
        "weather_code": 0,
        "wind_speed_10m": 12.0,
    },
    "daily": {
        "time": ["2026-08-03", "2026-08-04"],
        "weather_code": [0, 61],
        "temperature_2m_max": [28.0, 25.0],
        "temperature_2m_min": [20.0, 18.0],
        "precipitation_probability_max": [0, 40],
    },
}

# countries.dev shape (the keyless default provider).
COUNTRY_PAYLOAD = {
    "name": "Greece",
    "nativeName": "Ελλάδα",
    "alpha2Code": "GR",
    "capital": "Athens",
    "currencies": [{"code": "EUR", "name": "Euro", "symbol": "€"}],
    "languages": [{"name": "Greek", "iso639_1": "el"}],
    "region": "Europe",
    "subregion": "Southern Europe",
    "population": 10400000,
    "timezones": ["UTC+02:00"],
    "flags": {"png": "https://flagcdn.com/w320/gr.png"},
    "flag": "🇬🇷",
    "area": 131990,
    "callingCodes": ["30"],
}

# REST Countries v5 shape, used when an API key is configured.
RESTCOUNTRIES_PAYLOAD = {
    "objects": [
        {
            "name": {"common": "Greece", "official": "Hellenic Republic"},
            "capital": ["Athens"],
            "currencies": {"EUR": {"name": "Euro", "symbol": "€"}},
            "languages": {"ell": "Greek"},
            "region": "Europe",
            "subregion": "Southern Europe",
            "population": 10400000,
            "timezones": ["UTC+02:00"],
            "flags": {"png": "https://flagcdn.com/w320/gr.png"},
            "cca2": "GR",
        }
    ]
}

# What the deprecated v3.1 endpoint now returns: HTTP 200 with an error body.
DEPRECATED_PAYLOAD = {
    "success": False,
    "data": None,
    "errors": [{"message": "This API version has been deprecated."}],
}


class FakeResponse:
    """Stand-in for a requests.Response.

    Exposes both `.json()` and `.content`, because the country module parses
    raw bytes to sidestep the provider's missing charset header.
    """

    def __init__(self, payload, status=200, raw=None):
        self._payload = payload
        self.status_code = status
        self._raw = raw

    @property
    def content(self):
        if self._raw is not None:
            return self._raw
        return json.dumps(self._payload).encode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self):
        return self._payload


class WeatherTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch("integrations.weather.requests.get")
    def test_successful_call_is_shaped_for_the_app(self, mock_get):
        mock_get.return_value = FakeResponse(WEATHER_PAYLOAD)
        result = weather.get_weather(36.39, 25.46)
        self.assertTrue(result["available"])
        self.assertEqual(result["current"]["temperature_c"], 24.5)
        self.assertEqual(result["current"]["condition"], "Clear sky")
        self.assertEqual(result["current"]["icon"], "sunny")
        self.assertEqual(len(result["forecast"]), 2)
        self.assertEqual(result["forecast"][1]["condition"], "Slight rain")
        self.assertEqual(result["forecast"][1]["icon"], "rain")

    @patch("integrations.weather.requests.get")
    def test_second_call_is_served_from_cache(self, mock_get):
        mock_get.return_value = FakeResponse(WEATHER_PAYLOAD)
        weather.get_weather(36.39, 25.46)
        second = weather.get_weather(36.39, 25.46)
        self.assertTrue(second["cached"])
        self.assertEqual(mock_get.call_count, 1)

    @patch("integrations.weather.requests.get", side_effect=requests.ConnectionError("down"))
    def test_provider_outage_degrades_instead_of_raising(self, _mock_get):
        result = weather.get_weather(36.39, 25.46)
        self.assertFalse(result["available"])
        self.assertEqual(result["forecast"], [])
        self.assertIn("could not be reached", result["detail"])

    @patch("integrations.weather.requests.get")
    def test_short_daily_series_does_not_crash(self, mock_get):
        payload = {
            "current": {},
            "daily": {"time": ["2026-08-03", "2026-08-04"], "weather_code": [0]},
        }
        mock_get.return_value = FakeResponse(payload)
        result = weather.get_weather(1.0, 1.0)
        self.assertEqual(len(result["forecast"]), 2)
        self.assertIsNone(result["forecast"][1]["temp_max_c"])

    def test_invalid_coordinates_are_reported(self):
        result = weather.get_weather("not-a-number", 1.0)
        self.assertFalse(result["available"])


class CountryTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_provider_defaults_to_the_keyless_one(self):
        with override_settings(COUNTRY_API_PROVIDER="auto", RESTCOUNTRIES_API_KEY=""):
            self.assertEqual(countries.active_provider(), countries.PROVIDER_COUNTRIES_DEV)

    def test_provider_switches_to_restcountries_when_a_key_is_set(self):
        with override_settings(COUNTRY_API_PROVIDER="auto", RESTCOUNTRIES_API_KEY="abc123"):
            self.assertEqual(countries.active_provider(), countries.PROVIDER_RESTCOUNTRIES)

    @patch("integrations.countries.requests.get")
    def test_successful_call_is_shaped_for_the_app(self, mock_get):
        mock_get.return_value = FakeResponse(COUNTRY_PAYLOAD)
        result = countries.get_country_info("GR")
        self.assertTrue(result["available"])
        self.assertEqual(result["name"], "Greece")
        self.assertEqual(result["capital"], "Athens")
        self.assertEqual(result["currencies"][0]["code"], "EUR")
        self.assertEqual(result["languages"], ["Greek"])
        self.assertEqual(result["country_code"], "GR")

    @override_settings(COUNTRY_API_PROVIDER="restcountries", RESTCOUNTRIES_API_KEY="k")
    @patch("integrations.countries.requests.get")
    def test_restcountries_v5_shape_normalises_to_the_same_result(self, mock_get):
        mock_get.return_value = FakeResponse(RESTCOUNTRIES_PAYLOAD)
        result = countries.get_country_info("GR")
        # Different provider, different payload shape, identical output.
        self.assertTrue(result["available"])
        self.assertEqual(result["name"], "Greece")
        self.assertEqual(result["official_name"], "Hellenic Republic")
        self.assertEqual(result["capital"], "Athens")
        self.assertEqual(result["currencies"][0]["code"], "EUR")
        self.assertEqual(result["languages"], ["Greek"])

    @override_settings(COUNTRY_API_PROVIDER="restcountries", RESTCOUNTRIES_API_KEY="k")
    @patch("integrations.countries.requests.get")
    def test_api_key_is_sent_as_a_bearer_token(self, mock_get):
        mock_get.return_value = FakeResponse(RESTCOUNTRIES_PAYLOAD)
        countries.get_country_info("GR")
        headers = mock_get.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer k")

    @patch("integrations.countries.requests.get")
    def test_deprecated_provider_envelope_is_not_treated_as_success(self, mock_get):
        # The old REST Countries endpoint answers 200 with an error body. A
        # naive client reports "available" with every field empty; this must
        # be recognised as a failure instead.
        mock_get.return_value = FakeResponse(DEPRECATED_PAYLOAD)
        result = countries.get_country_info("GR")
        self.assertFalse(result["available"])
        self.assertIn("deprecated", result["detail"].lower())

    @patch("integrations.countries.requests.get")
    def test_non_ascii_names_survive_a_missing_charset_header(self, mock_get):
        # The provider serves UTF-8 without declaring it, so anything that
        # relies on requests' encoding guess turns "Ελλάδα" into mojibake.
        payload = dict(COUNTRY_PAYLOAD, nativeName="Ελλάδα")
        mock_get.return_value = FakeResponse(
            payload, raw=json.dumps(payload, ensure_ascii=False).encode("utf-8")
        )
        result = countries.get_country_info("GR")
        self.assertEqual(result["official_name"], "Ελλάδα")

    @patch("integrations.countries.requests.get")
    def test_payload_without_a_name_is_rejected(self, mock_get):
        mock_get.return_value = FakeResponse({"region": "Europe"})
        result = countries.get_country_info("GR")
        self.assertFalse(result["available"])

    @patch("integrations.countries.requests.get")
    def test_list_response_is_normalised_to_a_dict(self, mock_get):
        mock_get.return_value = FakeResponse([COUNTRY_PAYLOAD])
        result = countries.get_country_info("gr")
        self.assertEqual(result["name"], "Greece")

    @patch("integrations.countries.requests.get")
    def test_response_is_cached(self, mock_get):
        mock_get.return_value = FakeResponse(COUNTRY_PAYLOAD)
        countries.get_country_info("GR")
        countries.get_country_info("GR")
        self.assertEqual(mock_get.call_count, 1)

    @patch("integrations.countries.requests.get", side_effect=requests.Timeout("slow"))
    def test_timeout_degrades_gracefully(self, _mock_get):
        result = countries.get_country_info("GR")
        self.assertFalse(result["available"])

    @patch("integrations.countries.requests.get")
    def test_unauthorised_v5_request_degrades_gracefully(self, mock_get):
        with override_settings(COUNTRY_API_PROVIDER="restcountries", RESTCOUNTRIES_API_KEY=""):
            mock_get.return_value = FakeResponse({"errors": [{"code": "authKeyMissing"}]}, status=401)
            result = countries.get_country_info("GR")
        self.assertFalse(result["available"])

    def test_malformed_code_is_rejected_without_a_network_call(self):
        result = countries.get_country_info("GREECE")
        self.assertFalse(result["available"])
        self.assertIn("two-letter", result["detail"])


class IntegrationApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.destination = Destination.objects.create(
            name="Santorini",
            country="Greece",
            country_code="GR",
            category="beach",
            short_description="Islands.",
            description="Islands and sunsets.",
            tags=["sunsets"],
            latitude=36.39,
            longitude=25.46,
            average_cost_per_day_usd=150,
        )

    @patch("integrations.weather.requests.get")
    def test_weather_endpoint_by_destination(self, mock_get):
        mock_get.return_value = FakeResponse(WEATHER_PAYLOAD)
        response = self.client.get(
            f"/api/integrations/weather/?destination={self.destination.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["available"])

    def test_weather_endpoint_without_parameters_is_a_400(self):
        self.assertEqual(self.client.get("/api/integrations/weather/").status_code, 400)

    def test_weather_endpoint_for_a_missing_destination_is_a_404(self):
        response = self.client.get("/api/integrations/weather/?destination=99999")
        self.assertEqual(response.status_code, 404)

    @patch("integrations.weather.requests.get", side_effect=requests.ConnectionError("down"))
    def test_provider_outage_is_still_a_200(self, _mock_get):
        # The app renders the rest of the destination screen regardless, so a
        # provider problem must not surface as an HTTP error.
        response = self.client.get(
            f"/api/integrations/weather/?destination={self.destination.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["available"])

    @patch("integrations.countries.requests.get")
    def test_country_endpoint_by_destination(self, mock_get):
        mock_get.return_value = FakeResponse(COUNTRY_PAYLOAD)
        response = self.client.get(
            f"/api/integrations/country/?destination={self.destination.id}"
        )
        self.assertEqual(response.json()["capital"], "Athens")

    @patch("integrations.countries.requests.get")
    @patch("integrations.weather.requests.get")
    def test_context_endpoint_returns_both_in_one_request(self, mock_weather, mock_country):
        mock_weather.return_value = FakeResponse(WEATHER_PAYLOAD)
        mock_country.return_value = FakeResponse(COUNTRY_PAYLOAD)
        response = self.client.get(
            f"/api/integrations/context/?destination={self.destination.id}"
        )
        body = response.json()
        self.assertTrue(body["weather"]["available"])
        self.assertTrue(body["country"]["available"])

    def test_context_endpoint_requires_a_destination(self):
        self.assertEqual(self.client.get("/api/integrations/context/").status_code, 400)
