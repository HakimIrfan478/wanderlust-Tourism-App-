"""Tests for the destination catalogue, browsing filters and reviews."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Destination, Review

User = get_user_model()


def make_destination(name, category="beach", country="Testland", cost=100, tags=None):
    return Destination.objects.create(
        name=name,
        country=country,
        country_code="TL",
        city=name,
        category=category,
        short_description=f"{name} short description.",
        description=f"A long description of {name} with plenty of detail.",
        tags=tags or ["sun", "sea"],
        latitude=1.0,
        longitude=2.0,
        average_cost_per_day_usd=cost,
        best_season="All year",
    )


class DestinationModelTests(TestCase):
    def setUp(self):
        self.destination = make_destination("Testville")
        self.user = User.objects.create_user("reviewer", password="test-pass-8899")

    def test_rating_is_none_before_any_review(self):
        self.assertIsNone(self.destination.rating)
        self.assertEqual(self.destination.review_count, 0)

    def test_rating_is_the_mean_of_reviews(self):
        other = User.objects.create_user("second", password="test-pass-8899")
        Review.objects.create(destination=self.destination, author=self.user, rating=5)
        Review.objects.create(destination=self.destination, author=other, rating=2)
        self.assertEqual(self.destination.rating, 3.5)
        self.assertEqual(self.destination.review_count, 2)

    def test_text_for_embedding_includes_the_searchable_fields(self):
        text = self.destination.text_for_embedding()
        for fragment in ("Testville", "Testland", "Beach", "sun"):
            self.assertIn(fragment, text)

    def test_one_review_per_user_per_destination(self):
        Review.objects.create(destination=self.destination, author=self.user, rating=4)
        with self.assertRaises(Exception):
            Review.objects.create(destination=self.destination, author=self.user, rating=2)


class DestinationListApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_destination("Alpha Beach", "beach", "Greece", cost=50, tags=["snorkelling"])
        make_destination("Beta Peak", "mountain", "Nepal", cost=200, tags=["trekking"])
        make_destination("Gamma City", "city", "Japan", cost=150, tags=["nightlife"])

    def test_list_returns_every_destination(self):
        response = self.client.get("/api/destinations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 3)

    def test_default_ordering_is_alphabetical(self):
        # Regression: the rating annotation drops the model's Meta.ordering,
        # which left the list unordered and made paginated pages unstable.
        names = [r["name"] for r in self.client.get("/api/destinations/").json()["results"]]
        self.assertEqual(names, sorted(names))

    def test_filtered_list_is_also_ordered(self):
        names = [
            r["name"]
            for r in self.client.get("/api/destinations/?search=a").json()["results"]
        ]
        self.assertEqual(names, sorted(names))

    def test_filter_by_category(self):
        response = self.client.get("/api/destinations/?category=mountain")
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Beta Peak")

    def test_filter_by_country_is_case_insensitive(self):
        response = self.client.get("/api/destinations/?country=japan")
        self.assertEqual(response.json()["count"], 1)

    def test_search_spans_name_and_description(self):
        response = self.client.get("/api/destinations/?search=Gamma")
        self.assertEqual(response.json()["count"], 1)

    def test_filter_by_max_cost(self):
        response = self.client.get("/api/destinations/?max_cost=150")
        names = {r["name"] for r in response.json()["results"]}
        self.assertEqual(names, {"Alpha Beach", "Gamma City"})

    def test_filter_by_tag(self):
        response = self.client.get("/api/destinations/?tag=trekking")
        self.assertEqual(response.json()["count"], 1)

    def test_sort_by_cost(self):
        response = self.client.get("/api/destinations/?sort=cost")
        costs = [r["average_cost_per_day_usd"] for r in response.json()["results"]]
        self.assertEqual(costs, sorted(costs))

    def test_unrated_destinations_do_not_top_a_rating_sort(self):
        user = User.objects.create_user("rater", password="test-pass-8899")
        rated = Destination.objects.get(name="Beta Peak")
        Review.objects.create(destination=rated, author=user, rating=5)
        response = self.client.get("/api/destinations/?sort=-rating")
        self.assertEqual(response.json()["results"][0]["name"], "Beta Peak")

    def test_ids_filter_selects_specific_rows(self):
        wanted = Destination.objects.get(name="Alpha Beach").id
        response = self.client.get(f"/api/destinations/?ids={wanted}")
        self.assertEqual(response.json()["count"], 1)

    def test_list_includes_rating_and_favourite_flags(self):
        row = self.client.get("/api/destinations/").json()["results"][0]
        self.assertIn("rating", row)
        self.assertIn("review_count", row)
        self.assertFalse(row["is_favorite"])

    def test_facets_report_counts_per_category(self):
        response = self.client.get("/api/destinations/facets/")
        body = response.json()
        self.assertEqual(body["total"], 3)
        self.assertEqual(len(body["categories"]), 3)
        self.assertEqual(body["cost_per_day_usd"]["min"], 50)
        self.assertEqual(body["cost_per_day_usd"]["max"], 200)


class DestinationDetailApiTests(TestCase):
    def setUp(self):
        self.destination = make_destination("Detail Bay")

    def test_detail_returns_the_full_description_and_reviews(self):
        response = self.client.get(f"/api/destinations/{self.destination.id}/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("description", body)
        self.assertEqual(body["reviews"], [])

    def test_missing_destination_is_a_404(self):
        self.assertEqual(self.client.get("/api/destinations/99999/").status_code, 404)


class ReviewApiTests(TestCase):
    def setUp(self):
        self.destination = make_destination("Review Bay")
        self.user = User.objects.create_user("author", password="test-pass-8899")
        self.other = User.objects.create_user("other", password="test-pass-8899")
        self.url = f"/api/destinations/{self.destination.id}/reviews/"

    def test_anonymous_users_can_read_but_not_write(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        response = self.client.post(
            self.url, {"rating": 5}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 401)

    def test_signed_in_user_can_leave_a_review(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {"rating": 5, "comment": "Wonderful."},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["author_username"], "author")

    def test_second_review_from_the_same_user_is_rejected(self):
        self.client.force_login(self.user)
        payload = {"rating": 4, "comment": "Nice."}
        self.client.post(self.url, payload, content_type="application/json")
        response = self.client.post(self.url, payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_rating_must_be_between_one_and_five(self):
        self.client.force_login(self.user)
        for bad in (0, 6, 99):
            response = self.client.post(
                self.url, {"rating": bad}, content_type="application/json"
            )
            self.assertEqual(response.status_code, 400, f"rating {bad} was accepted")

    def test_review_updates_the_destination_rating(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {"rating": 4}, content_type="application/json")
        body = self.client.get(f"/api/destinations/{self.destination.id}/").json()
        self.assertEqual(body["rating"], 4.0)
        self.assertEqual(body["review_count"], 1)

    def test_author_can_edit_their_own_review(self):
        self.client.force_login(self.user)
        created = self.client.post(
            self.url, {"rating": 3}, content_type="application/json"
        ).json()
        response = self.client.patch(
            f"/api/destinations/reviews/{created['id']}/",
            {"rating": 5},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rating"], 5)

    def test_another_users_review_is_not_reachable(self):
        self.client.force_login(self.user)
        created = self.client.post(
            self.url, {"rating": 3}, content_type="application/json"
        ).json()
        self.client.force_login(self.other)
        response = self.client.delete(f"/api/destinations/reviews/{created['id']}/")
        self.assertEqual(response.status_code, 404)

    def test_review_on_a_missing_destination_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/destinations/99999/reviews/",
            {"rating": 5},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
