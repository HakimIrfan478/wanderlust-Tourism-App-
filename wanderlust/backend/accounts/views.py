from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from destinations.models import Destination
from destinations.serializers import DestinationListSerializer

from .serializers import RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    """GET and PATCH the currently authenticated user's profile."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ToggleFavoriteView(APIView):
    """POST /api/auth/favorites/<destination_id>/ — add or remove a saved place."""

    permission_classes = [IsAuthenticated]

    def post(self, request, destination_id):
        destination = get_object_or_404(Destination, pk=destination_id)
        user = request.user
        if user.favorites.filter(pk=destination_id).exists():
            user.favorites.remove(destination)
            favorited = False
        else:
            user.favorites.add(destination)
            favorited = True
        return Response(
            {
                "destination": destination_id,
                "favorited": favorited,
                "favorite_count": user.favorites.count(),
            },
            status=status.HTTP_200_OK,
        )


class FavoritesListView(generics.ListAPIView):
    """GET /api/auth/favorites/ — the user's saved destinations, in full.

    Returning whole objects here means the profile screen does not have to
    download the entire catalogue and filter it client-side.
    """

    serializer_class = DestinationListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        # order_by is explicit: an aggregate annotation drops Meta.ordering.
        return self.request.user.favorites.annotate(
            avg_rating=Avg("reviews__rating"),
            num_reviews=Count("reviews", distinct=True),
        ).order_by("name")
