"""Tests for registration, JWT authentication, the profile and favourites."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from destinations.models import Destination

User = get_user_model()


def make_destination(name):
    return Destination.objects.create(
        name=name,
        country="Testland",
        country_code="TL",
        category="beach",
        short_description=f"{name} short.",
        description=f"{name} long description.",
        tags=["sun"],
        latitude=0.0,
        longitude=0.0,
        average_cost_per_day_usd=100,
    )


class RegistrationTests(TestCase):
    url = "/api/auth/register/"

    def test_registration_creates_a_user_with_a_hashed_password(self):
        response = self.client.post(
            self.url,
            {
                "username": "newuser",
                "email": "new@example.com",
                "password": "a-good-password-42",
                "home_country": "Pakistan",
                "travel_preferences": "quiet beaches and hiking",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="newuser")
        self.assertNotEqual(user.password, "a-good-password-42")
        self.assertTrue(user.check_password("a-good-password-42"))
        self.assertEqual(user.travel_preferences, "quiet beaches and hiking")

    def test_password_is_never_returned(self):
        response = self.client.post(
            self.url,
            {"username": "quiet", "password": "a-good-password-42"},
            content_type="application/json",
        )
        self.assertNotIn("password", response.json())

    def test_short_password_is_rejected(self):
        response = self.client.post(
            self.url,
            {"username": "shorty", "password": "abc"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())

    def test_common_password_is_rejected_by_django_validators(self):
        response = self.client.post(
            self.url,
            {"username": "common", "password": "password123"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user("taken", password="a-good-password-42")
        response = self.client.post(
            self.url,
            {"username": "taken", "password": "a-good-password-42"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(
            "first", email="dupe@example.com", password="a-good-password-42"
        )
        response = self.client.post(
            self.url,
            {
                "username": "second",
                "email": "DUPE@example.com",
                "password": "a-good-password-42",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class JwtAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("jwtuser", password="a-good-password-42")

    def _token(self):
        response = self.client.post(
            "/api/auth/token/",
            {"username": "jwtuser", "password": "a-good-password-42"},
            content_type="application/json",
        )
        return response

    def test_login_returns_access_and_refresh_tokens(self):
        response = self._token()
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        self.assertIn("refresh", response.json())

    def test_wrong_password_is_rejected(self):
        response = self.client.post(
            "/api/auth/token/",
            {"username": "jwtuser", "password": "wrong"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_access_token_authenticates_the_profile_endpoint(self):
        access = self._token().json()["access"]
        response = self.client.get(
            "/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {access}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "jwtuser")

    def test_refresh_token_issues_a_new_access_token(self):
        refresh = self._token().json()["refresh"]
        response = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": refresh},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())

    def test_garbage_token_is_rejected(self):
        response = self.client.get(
            "/api/auth/me/", HTTP_AUTHORIZATION="Bearer not-a-real-token"
        )
        self.assertEqual(response.status_code, 401)

    def test_profile_requires_authentication(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("profile", password="a-good-password-42")
        self.client.force_login(self.user)

    def test_profile_can_be_patched(self):
        response = self.client.patch(
            "/api/auth/me/",
            {"travel_preferences": "mountains and cold weather", "bio": "Hello."},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.travel_preferences, "mountains and cold weather")

    def test_username_is_read_only(self):
        self.client.patch(
            "/api/auth/me/",
            {"username": "hacker"},
            content_type="application/json",
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "profile")

    def test_profile_reports_counts(self):
        body = self.client.get("/api/auth/me/").json()
        self.assertEqual(body["favorite_count"], 0)
        self.assertEqual(body["review_count"], 0)


class FavoritesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("fav", password="a-good-password-42")
        self.destination = make_destination("Fav Bay")
        self.client.force_login(self.user)
        self.url = f"/api/auth/favorites/{self.destination.id}/"

    def test_toggle_adds_then_removes(self):
        first = self.client.post(self.url)
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["favorited"])
        self.assertEqual(self.user.favorites.count(), 1)

        second = self.client.post(self.url)
        self.assertFalse(second.json()["favorited"])
        self.assertEqual(self.user.favorites.count(), 0)

    def test_favourite_list_returns_full_destination_objects(self):
        self.client.post(self.url)
        response = self.client.get("/api/auth/favorites/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["name"], "Fav Bay")
        self.assertTrue(body[0]["is_favorite"])

    def test_favouriting_a_missing_destination_is_a_404(self):
        self.assertEqual(self.client.post("/api/auth/favorites/99999/").status_code, 404)

    def test_favourites_require_authentication(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.url).status_code, 401)
        self.assertEqual(self.client.get("/api/auth/favorites/").status_code, 401)

    def test_destination_list_marks_the_users_favourites(self):
        self.client.post(self.url)
        row = self.client.get("/api/destinations/").json()["results"][0]
        self.assertTrue(row["is_favorite"])
