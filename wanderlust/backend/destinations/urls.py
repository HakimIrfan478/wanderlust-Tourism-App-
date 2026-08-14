from django.urls import path

from .views import (
    CategoryFacetView,
    DestinationDetailView,
    DestinationListView,
    ReviewDetailView,
    ReviewListCreateView,
)

urlpatterns = [
    path("", DestinationListView.as_view(), name="destination-list"),
    path("facets/", CategoryFacetView.as_view(), name="destination-facets"),
    path("<int:pk>/", DestinationDetailView.as_view(), name="destination-detail"),
    path(
        "<int:destination_id>/reviews/",
        ReviewListCreateView.as_view(),
        name="destination-reviews",
    ),
    path("reviews/<int:pk>/", ReviewDetailView.as_view(), name="review-detail"),
]
