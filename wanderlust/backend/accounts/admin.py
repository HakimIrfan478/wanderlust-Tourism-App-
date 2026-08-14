from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "home_country", "is_staff", "date_joined")
    search_fields = ("username", "email", "home_country")
    filter_horizontal = ("favorites", "groups", "user_permissions")
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Travel profile",
            {
                "fields": ("bio", "home_country", "travel_preferences", "favorites"),
                "description": (
                    "travel_preferences is free text; the recommender embeds it "
                    "when a signed-in user asks for suggestions without typing a query."
                ),
            },
        ),
    )
