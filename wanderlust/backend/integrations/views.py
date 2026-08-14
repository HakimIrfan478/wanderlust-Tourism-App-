"""Server-side proxies for the two external APIs.

Both calls are made from the backend rather than the phone, which keeps the
provider contact points in one place, lets responses be cached once for every
user, and means the app never has to handle a third-party outage itself.

These endpoints always return 200 with an ``available`` flag for provider
problems; only a bad request from the client is a 4xx.
"""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from destinations.models import Destination

from . import countries, weather


class WeatherView(APIView):
    """GET /api/integrations/weather/?destination=<id>  or  ?lat=..&lon=.."""

    permission_classes = [AllowAny]

    def get(self, request):
        destination_id = request.query_params.get("destination")
        latitude = request.query_params.get("lat")
        longitude = request.query_params.get("lon")
        days = request.query_params.get("days", 5)

        if destination_id:
            destination = Destination.objects.filter(pk=destination_id).first()
            if destination is None:
                return Response({"detail": "Destination not found."}, status=404)
            latitude, longitude = destination.latitude, destination.longitude

        if latitude is None or longitude is None:
            return Response(
                {"detail": "Provide lat and lon, or a destination id."}, status=400
            )

        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 5

        return Response(weather.get_weather(latitude, longitude, days))


class CountryInfoView(APIView):
    """GET /api/integrations/country/?code=PT  or  ?destination=<id>"""

    permission_classes = [AllowAny]

    def get(self, request):
        code = request.query_params.get("code")
        destination_id = request.query_params.get("destination")

        if not code and destination_id:
            destination = Destination.objects.filter(pk=destination_id).first()
            if destination is None:
                return Response({"detail": "Destination not found."}, status=404)
            code = destination.country_code
            if not code:
                return Response(
                    {
                        "source": "restcountries",
                        "available": False,
                        "detail": "This destination has no country code recorded.",
                    }
                )

        if not code:
            return Response(
                {"detail": "Provide a country 'code' or a destination id."}, status=400
            )

        return Response(countries.get_country_info(code))


class DestinationContextView(APIView):
    """GET /api/integrations/context/?destination=<id>

    Both external calls in one round trip. The destination screen needs weather
    and country facts together, and on a phone connection one request beats two.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        destination_id = request.query_params.get("destination")
        if not destination_id:
            return Response({"detail": "Provide a destination id."}, status=400)

        destination = Destination.objects.filter(pk=destination_id).first()
        if destination is None:
            return Response({"detail": "Destination not found."}, status=404)

        return Response(
            {
                "destination": destination.id,
                "weather": weather.get_weather(
                    destination.latitude, destination.longitude
                ),
                "country": (
                    countries.get_country_info(destination.country_code)
                    if destination.country_code
                    else {
                        "source": "restcountries",
                        "available": False,
                        "detail": "No country code recorded for this destination.",
                    }
                ),
            }
        )
