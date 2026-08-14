from django.urls import path

from .views import CountryInfoView, DestinationContextView, WeatherView

urlpatterns = [
    path("weather/", WeatherView.as_view(), name="weather"),
    path("country/", CountryInfoView.as_view(), name="country-info"),
    path("context/", DestinationContextView.as_view(), name="destination-context"),
]
