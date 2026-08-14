from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user that also stores free-text travel preferences.

    `travel_preferences` is a natural-language description of what the user
    enjoys (e.g. "quiet beaches, local food, hiking, no big crowds").
    The recommendation engine embeds this text to rank destinations.
    """

    bio = models.TextField(blank=True, default="")
    home_country = models.CharField(max_length=80, blank=True, default="")
    travel_preferences = models.TextField(blank=True, default="")
    favorites = models.ManyToManyField(
        "destinations.Destination",
        blank=True,
        related_name="favorited_by",
    )

    def __str__(self):
        return self.username
