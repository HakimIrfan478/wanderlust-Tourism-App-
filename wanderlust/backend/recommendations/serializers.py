"""Request validation for the recommendation endpoints."""
from rest_framework import serializers

from destinations.models import Destination

from . import engine

CATEGORY_VALUES = [value for value, _ in Destination.CATEGORY_CHOICES]


class RecommendationRequestSerializer(serializers.Serializer):
    """Validated shape of a recommendation request.

    Accepts the same fields from a JSON body or a query string, so the
    endpoint can be driven from the app and poked at from a browser.
    """

    query = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    category = serializers.ChoiceField(
        choices=CATEGORY_VALUES, required=False, allow_blank=True, allow_null=True
    )
    country = serializers.CharField(required=False, allow_blank=True, max_length=80)
    max_cost = serializers.IntegerField(required=False, min_value=0, allow_null=True)
    top_k = serializers.IntegerField(required=False, default=6, min_value=1, max_value=50)
    model = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    personalize = serializers.BooleanField(required=False, default=False)
    explain = serializers.BooleanField(required=False, default=True)

    def validate_model(self, value):
        if not value:
            return None
        canonical = engine.normalise_model_name(value)
        if canonical is not None and canonical not in engine.ALL_MODELS:
            raise serializers.ValidationError(
                f"Unknown model '{value}'. Choose one of: "
                f"{', '.join(engine.ALL_MODELS)}."
            )
        return canonical

    def candidates(self):
        """The destination queryset this request should rank."""
        data = self.validated_data
        queryset = Destination.objects.all()
        if data.get("category"):
            queryset = queryset.filter(category=data["category"])
        if data.get("country"):
            queryset = queryset.filter(country__icontains=data["country"])
        if data.get("max_cost"):
            queryset = queryset.filter(average_cost_per_day_usd__lte=data["max_cost"])
        return queryset
