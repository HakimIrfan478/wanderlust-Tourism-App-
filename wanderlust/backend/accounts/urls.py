from django.urls import path

from .views import FavoritesListView, MeView, RegisterView, ToggleFavoriteView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("me/", MeView.as_view(), name="me"),
    path("favorites/", FavoritesListView.as_view(), name="favorites"),
    path(
        "favorites/<int:destination_id>/",
        ToggleFavoriteView.as_view(),
        name="toggle-favorite",
    ),
]
