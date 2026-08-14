from django.db.models import Avg, Count, F, Max, Min, Prefetch, Q
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Destination, Review
from .serializers import (
    DestinationDetailSerializer,
    DestinationListSerializer,
    ReviewSerializer,
)

# Ratings are annotated rather than read per-object so a page of destinations
# costs one query instead of one per card.
RATING_ANNOTATIONS = {
    "avg_rating": Avg("reviews__rating"),
    "num_reviews": Count("reviews", distinct=True),
}

SORT_FIELDS = {
    "name": "name",
    "-name": "-name",
    "cost": "average_cost_per_day_usd",
    "-cost": "-average_cost_per_day_usd",
    "rating": "avg_rating",
    "-rating": "-avg_rating",
    "newest": "-created_at",
}


class DestinationListView(generics.ListAPIView):
    """List destinations.

    Filters: ``?category=``, ``?country=``, ``?search=``, ``?max_cost=``,
    ``?tag=``, ``?ids=1,2,3``. Ordering: ``?sort=`` with any of
    name, -name, cost, -cost, rating, -rating, newest.
    """

    serializer_class = DestinationListSerializer

    def get_queryset(self):
        params = self.request.query_params
        queryset = Destination.objects.annotate(**RATING_ANNOTATIONS)

        if category := params.get("category"):
            queryset = queryset.filter(category=category)
        if country := params.get("country"):
            queryset = queryset.filter(country__icontains=country)
        if tag := params.get("tag"):
            queryset = queryset.filter(tags__icontains=tag)
        if max_cost := params.get("max_cost"):
            if max_cost.isdigit():
                queryset = queryset.filter(average_cost_per_day_usd__lte=int(max_cost))
        if ids := params.get("ids"):
            wanted = [int(v) for v in ids.split(",") if v.strip().isdigit()]
            queryset = queryset.filter(id__in=wanted)
        if search := params.get("search"):
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(city__icontains=search)
                | Q(country__icontains=search)
                | Q(short_description__icontains=search)
                | Q(description__icontains=search)
            )

        # An aggregate annotation drops the model's Meta.ordering, which left
        # the queryset unordered — and an unordered queryset makes paginated
        # pages overlap or skip rows. Ordering is therefore always explicit.
        sort = params.get("sort")
        if sort in ("rating", "-rating"):
            # Explicit nulls_last: SQLite and PostgreSQL disagree about where
            # NULLs sort, and unrated destinations should never top the list.
            field = F("avg_rating")
            ordering = (
                field.desc(nulls_last=True)
                if sort == "-rating"
                else field.asc(nulls_last=True)
            )
            queryset = queryset.order_by(ordering, "name")
        elif sort in SORT_FIELDS:
            queryset = queryset.order_by(SORT_FIELDS[sort], "name")
        else:
            queryset = queryset.order_by("name")
        return queryset


class DestinationDetailView(generics.RetrieveAPIView):
    serializer_class = DestinationDetailSerializer

    def get_queryset(self):
        return (
            Destination.objects.annotate(**RATING_ANNOTATIONS)
            .prefetch_related(
                Prefetch("reviews", queryset=Review.objects.select_related("author"))
            )
            .order_by("name")
        )


class ReviewListCreateView(generics.ListCreateAPIView):
    """List a destination's reviews, or add yours (one per destination)."""

    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return Review.objects.filter(
            destination_id=self.kwargs["destination_id"]
        ).select_related("author")

    def perform_create(self, serializer):
        destination_id = self.kwargs["destination_id"]
        if not Destination.objects.filter(pk=destination_id).exists():
            raise ValidationError("That destination does not exist.")
        if Review.objects.filter(
            destination_id=destination_id, author=self.request.user
        ).exists():
            raise ValidationError("You have already reviewed this destination.")
        serializer.save(author=self.request.user, destination_id=destination_id)


class ReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Edit or delete your own review."""

    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Restricting the queryset (rather than checking in the handler) means
        # someone else's review is a 404, not a 403 that confirms it exists.
        return Review.objects.filter(author=self.request.user)


class CategoryFacetView(APIView):
    """GET /api/destinations/facets/ — counts for the browse filters."""

    permission_classes = [AllowAny]

    def get(self, _request):
        labels = dict(Destination.CATEGORY_CHOICES)
        categories = (
            Destination.objects.values("category")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        countries = (
            Destination.objects.values("country", "country_code")
            .annotate(count=Count("id"))
            .order_by("country")
        )
        costs = Destination.objects.aggregate(
            min=Min("average_cost_per_day_usd"),
            max=Max("average_cost_per_day_usd"),
            mean=Avg("average_cost_per_day_usd"),
        )
        return Response(
            {
                "total": Destination.objects.count(),
                "categories": [
                    {
                        "value": row["category"],
                        "label": labels.get(row["category"], row["category"]),
                        "count": row["count"],
                    }
                    for row in categories
                ],
                "countries": list(countries),
                "cost_per_day_usd": {
                    "min": costs["min"] or 0,
                    "max": costs["max"] or 0,
                    "mean": round(costs["mean"] or 0),
                },
            }
        )
