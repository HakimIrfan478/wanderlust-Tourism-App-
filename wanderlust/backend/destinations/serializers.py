from rest_framework import serializers

from .models import Destination, Review


class ReviewSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "destination",
            "author",
            "author_username",
            "rating",
            "comment",
            "created_at",
        )
        read_only_fields = (
            "id",
            "author",
            "author_username",
            "created_at",
            "destination",
        )

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


class FavoriteMixin(serializers.Serializer):
    """Adds `is_favorite` so list cards can render the heart in one request."""

    is_favorite = serializers.SerializerMethodField()

    def get_is_favorite(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        favorites = self.context.get("favorite_ids")
        if favorites is None:
            favorites = set(request.user.favorites.values_list("id", flat=True))
            self.context["favorite_ids"] = favorites
        return obj.id in favorites


class DestinationListSerializer(FavoriteMixin, serializers.ModelSerializer):
    rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Destination
        fields = (
            "id",
            "name",
            "country",
            "country_code",
            "city",
            "category",
            "short_description",
            "tags",
            "latitude",
            "longitude",
            "image_url",
            "image_attribution",
            "average_cost_per_day_usd",
            "best_season",
            "rating",
            "review_count",
            "is_favorite",
        )


class DestinationDetailSerializer(FavoriteMixin, serializers.ModelSerializer):
    rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)

    class Meta:
        model = Destination
        fields = (
            "id",
            "name",
            "country",
            "country_code",
            "city",
            "category",
            "short_description",
            "description",
            "tags",
            "latitude",
            "longitude",
            "image_url",
            "image_attribution",
            "wikipedia_title",
            "average_cost_per_day_usd",
            "best_season",
            "rating",
            "review_count",
            "is_favorite",
            "reviews",
        )
