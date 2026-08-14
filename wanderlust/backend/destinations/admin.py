from django.contrib import admin
from django.utils.html import format_html

from .models import Destination, Review


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "country",
        "category",
        "average_cost_per_day_usd",
        "has_embedding",
        "preview",
    )
    list_filter = ("category", "country")
    search_fields = ("name", "country", "city", "description")
    readonly_fields = ("embedding_model", "embedding_computed_at", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "country", "country_code", "city", "category")}),
        ("Content", {"fields": ("short_description", "description", "tags", "best_season")}),
        ("Location", {"fields": ("latitude", "longitude")}),
        ("Media", {"fields": ("image_url", "image_attribution", "wikipedia_title")}),
        ("Cost", {"fields": ("average_cost_per_day_usd",)}),
        (
            "Recommender cache",
            {
                "classes": ("collapse",),
                "description": (
                    "Written by the semantic backend. Clearing the embedding "
                    "forces it to be recomputed on the next recommendation."
                ),
                "fields": ("embedding", "embedding_model", "embedding_computed_at"),
            },
        ),
        ("Timestamps", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )

    @admin.display(boolean=True, description="Embedded")
    def has_embedding(self, obj):
        return bool(obj.embedding)

    @admin.display(description="Image")
    def preview(self, obj):
        if not obj.image_url:
            return "—"
        return format_html(
            '<img src="{}" style="height:40px;border-radius:4px" />', obj.image_url
        )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("destination", "author", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("destination__name", "author__username", "comment")
    autocomplete_fields = ("destination",)
