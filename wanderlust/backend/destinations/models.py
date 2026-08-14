from django.conf import settings
from django.db import models


class Destination(models.Model):
    """A tourist destination.

    ``embedding`` caches the vector the semantic recommender produces for this
    place, so the catalogue is embedded once rather than on every request.
    ``embedding_model`` and ``embedding_computed_at`` record which model wrote
    that vector and when, so the cache can be invalidated when either the
    model or the destination's own text changes. The TF-IDF backend does not
    use these fields — it fits its own index over the live catalogue.

    (At production scale the JSONField would become a pgvector column with an
    ANN index; this is noted as an advanced objective in the report.)
    """

    CATEGORY_CHOICES = [
        ("beach", "Beach"),
        ("mountain", "Mountain"),
        ("city", "City"),
        ("historical", "Historical"),
        ("nature", "Nature & Wildlife"),
        ("adventure", "Adventure"),
        ("cultural", "Cultural"),
    ]

    name = models.CharField(max_length=160)
    country = models.CharField(max_length=80)
    country_code = models.CharField(
        max_length=2, blank=True, default="", help_text="ISO 3166-1 alpha-2"
    )
    city = models.CharField(max_length=120, blank=True, default="")
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="city"
    )
    short_description = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField()
    tags = models.JSONField(
        default=list, blank=True, help_text="List of descriptive tags"
    )
    latitude = models.FloatField()
    longitude = models.FloatField()
    image_url = models.URLField(max_length=500, blank=True, default="")
    image_attribution = models.CharField(max_length=255, blank=True, default="")
    wikipedia_title = models.CharField(
        max_length=160,
        blank=True,
        default="",
        help_text="Wikipedia article title, used to fetch a real photo and credit it.",
    )
    average_cost_per_day_usd = models.PositiveIntegerField(default=0)
    best_season = models.CharField(max_length=120, blank=True, default="")

    embedding = models.JSONField(null=True, blank=True)
    embedding_model = models.CharField(max_length=120, blank=True, default="")
    embedding_computed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["country"]),
        ]

    def __str__(self):
        return f"{self.name}, {self.country}"

    def text_for_embedding(self):
        """Build the text the recommender uses to represent this place."""
        parts = [
            self.name,
            self.city,
            self.country,
            self.get_category_display(),
            self.short_description,
            self.description,
            " ".join(self.tags or []),
            self.best_season,
        ]
        return ". ".join(p for p in parts if p)

    @property
    def rating(self):
        """Mean review score, or None when nobody has reviewed it yet.

        List views annotate ``avg_rating`` so a page of destinations costs one
        query; the aggregate below is only the fallback for objects fetched
        without that annotation.
        """
        if hasattr(self, "avg_rating"):
            return round(self.avg_rating, 2) if self.avg_rating is not None else None
        agg = self.reviews.aggregate(models.Avg("rating"))
        return round(agg["rating__avg"], 2) if agg["rating__avg"] else None

    @property
    def review_count(self):
        if hasattr(self, "num_reviews"):
            return self.num_reviews
        return self.reviews.count()


class Review(models.Model):
    destination = models.ForeignKey(
        Destination, on_delete=models.CASCADE, related_name="reviews"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField()  # 1..5
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("destination", "author")

    def __str__(self):
        return f"{self.author} -> {self.destination} ({self.rating})"
