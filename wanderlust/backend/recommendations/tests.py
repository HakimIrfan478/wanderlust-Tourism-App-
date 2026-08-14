"""Tests for the recommendation engine and its API.

The point of these tests is that the two backends stay independently
selectable and that a response never misattributes which model produced it —
the whole comparison rests on that.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from destinations.models import Destination

from . import engine

User = get_user_model()


def make_destination(name, category, description, tags, cost=100):
    return Destination.objects.create(
        name=name,
        country="Testland",
        country_code="TL",
        city=name,
        category=category,
        short_description=description[:120],
        description=description,
        tags=tags,
        latitude=1.0,
        longitude=1.0,
        average_cost_per_day_usd=cost,
        best_season="All year",
    )


class CatalogueMixin:
    def build_catalogue(self):
        make_destination(
            "Sandy Cove",
            "beach",
            "A quiet sandy beach with warm shallow water and excellent fresh seafood.",
            ["beach", "seafood", "quiet"],
            cost=80,
        )
        make_destination(
            "High Ridge",
            "mountain",
            "Steep mountain trails, alpine huts and serious hiking above the tree line.",
            ["hiking", "mountains", "alpine"],
            cost=140,
        )
        make_destination(
            "Old Town",
            "historical",
            "Ancient ruins, classical museums and centuries of layered antiquity.",
            ["ruins", "museums", "history"],
            cost=90,
        )
        make_destination(
            "Neon City",
            "city",
            "A dense modern city of skyscrapers, night markets and late bars.",
            ["nightlife", "city", "food"],
            cost=160,
        )


class ModelNameTests(TestCase):
    def test_aliases_resolve_to_canonical_ids(self):
        for alias in ("semantic", "sbert", "transformer", "sentence-transformer", "MiniLM"):
            self.assertEqual(engine.normalise_model_name(alias), engine.MODEL_SEMANTIC)
        for alias in ("tfidf", "TF-IDF", "baseline", "keyword"):
            self.assertEqual(engine.normalise_model_name(alias), engine.MODEL_TFIDF)

    def test_blank_and_auto_mean_no_preference(self):
        for value in (None, "", "auto", "default"):
            self.assertIsNone(engine.normalise_model_name(value))

    def test_unknown_name_is_passed_through_for_the_caller_to_reject(self):
        self.assertEqual(engine.normalise_model_name("gpt"), "gpt")

    def test_resolve_rejects_an_unknown_model(self):
        with self.assertRaises(ValueError):
            engine.resolve_model("not-a-model")


@override_settings(DISABLE_SEMANTIC_MODEL=True)
class TfidfBackendTests(CatalogueMixin, TestCase):
    def setUp(self):
        engine.reset_caches()
        self.build_catalogue()

    def tearDown(self):
        engine.reset_caches()

    def test_tfidf_is_available_and_semantic_is_not(self):
        self.assertTrue(engine.is_available(engine.MODEL_TFIDF))
        self.assertFalse(engine.is_available(engine.MODEL_SEMANTIC))

    def test_ranking_puts_the_matching_destination_first(self):
        run = engine.recommend(
            "quiet sandy beach with seafood", top_k=3, model=engine.MODEL_TFIDF
        )
        self.assertEqual(run.results[0].destination.name, "Sandy Cove")
        self.assertEqual(run.model, engine.MODEL_TFIDF)

    def test_results_are_ordered_by_descending_score(self):
        run = engine.recommend("mountain hiking", top_k=4, model=engine.MODEL_TFIDF)
        scores = [r.score for r in run.results]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual([r.rank for r in run.results], [1, 2, 3, 4])

    def test_explanations_name_the_shared_keywords(self):
        run = engine.recommend("museums and ruins", top_k=1, model=engine.MODEL_TFIDF)
        result = run.results[0]
        self.assertEqual(result.destination.name, "Old Town")
        self.assertTrue(result.matched_terms)
        self.assertIn("keyword", result.explanation.lower())

    def test_requesting_semantic_falls_back_and_says_so(self):
        run = engine.recommend("beach", top_k=1, model=engine.MODEL_SEMANTIC)
        self.assertEqual(run.model, engine.MODEL_TFIDF)
        self.assertEqual(run.requested_model, engine.MODEL_SEMANTIC)
        self.assertTrue(run.fallback)
        self.assertIn("unavailable", run.note)

    def test_fallback_can_be_refused(self):
        with self.assertRaises(engine.ModelUnavailable):
            engine.recommend(
                "beach", top_k=1, model=engine.MODEL_SEMANTIC, allow_fallback=False
            )

    def test_filtered_candidates_are_scored_against_the_full_corpus(self):
        # Restricting to one category must not change how a term is weighted.
        everything = engine.recommend("beach seafood", top_k=4, model=engine.MODEL_TFIDF)
        beaches_only = engine.recommend(
            "beach seafood",
            Destination.objects.filter(category="beach"),
            top_k=4,
            model=engine.MODEL_TFIDF,
        )
        top_score = next(
            r.score for r in everything.results if r.destination.name == "Sandy Cove"
        )
        self.assertAlmostEqual(beaches_only.results[0].score, top_score, places=6)

    def test_index_refits_when_the_catalogue_changes(self):
        engine.recommend("beach", top_k=1, model=engine.MODEL_TFIDF)
        make_destination(
            "Volcano Isle", "nature", "Black sand volcanic beaches and hot springs.", ["volcano"]
        )
        run = engine.recommend("volcanic hot springs", top_k=1, model=engine.MODEL_TFIDF)
        self.assertEqual(run.results[0].destination.name, "Volcano Isle")

    def test_empty_catalogue_returns_an_empty_run_not_an_error(self):
        Destination.objects.all().delete()
        run = engine.recommend("anything", top_k=5, model=engine.MODEL_TFIDF)
        self.assertEqual(run.results, [])
        self.assertEqual(run.candidate_count, 0)

    def test_nonsense_query_still_returns_a_ranking(self):
        run = engine.recommend("zzzz qqqq", top_k=2, model=engine.MODEL_TFIDF)
        self.assertEqual(len(run.results), 2)
        self.assertEqual(run.results[0].score, 0.0)


@override_settings(DISABLE_SEMANTIC_MODEL=True)
class PersonalizationTests(CatalogueMixin, TestCase):
    def setUp(self):
        engine.reset_caches()
        self.build_catalogue()
        self.user = User.objects.create_user("traveller", password="test-pass-8899")

    def tearDown(self):
        engine.reset_caches()

    def test_anonymous_user_gets_no_boosts(self):
        self.assertEqual(engine.build_personalization(None), {})

    def test_favourites_boost_similar_destinations(self):
        beach = Destination.objects.get(name="Sandy Cove")
        self.user.favorites.add(beach)
        boosts = engine.build_personalization(self.user)
        # The favourite itself is excluded; nothing should be boosted above 1.
        self.assertNotIn(beach.id, boosts)
        self.assertTrue(all(0 < v <= 0.08 for v in boosts.values()))

    def test_boost_is_recorded_separately_from_the_model_score(self):
        ridge = Destination.objects.get(name="High Ridge")
        run = engine.recommend(
            "mountain hiking",
            top_k=1,
            model=engine.MODEL_TFIDF,
            boosts={ridge.id: 0.05},
        )
        result = run.results[0]
        self.assertTrue(run.personalized)
        self.assertAlmostEqual(result.score, result.base_score + 0.05, places=6)

    def test_preferences_alone_produce_boosts(self):
        self.user.travel_preferences = "hiking mountains alpine"
        self.user.save()
        boosts = engine.build_personalization(self.user)
        self.assertIn(Destination.objects.get(name="High Ridge").id, boosts)


@override_settings(DISABLE_SEMANTIC_MODEL=True)
class RecommendationApiTests(CatalogueMixin, TestCase):
    def setUp(self):
        engine.reset_caches()
        self.build_catalogue()

    def tearDown(self):
        engine.reset_caches()

    def test_models_endpoint_reports_availability_and_reasons(self):
        response = self.client.get("/api/recommendations/models/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        by_id = {m["id"]: m for m in body["models"]}
        self.assertTrue(by_id["tfidf"]["available"])
        self.assertFalse(by_id["semantic"]["available"])
        self.assertTrue(by_id["semantic"]["error"])
        self.assertTrue(body["any_available"])

    def test_post_returns_ranked_results_with_model_provenance(self):
        response = self.client.post(
            "/api/recommendations/",
            {"query": "quiet sandy beach", "model": "tfidf", "top_k": 2},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["model"], "tfidf")
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["results"][0]["name"], "Sandy Cove")
        self.assertIn("match_score", body["results"][0])
        self.assertIn("match_percent", body["results"][0])
        self.assertIn("explanation", body["results"][0])

    def test_get_works_the_same_as_post(self):
        response = self.client.get(
            "/api/recommendations/?query=mountain+hiking&model=tfidf&top_k=1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["name"], "High Ridge")

    def test_missing_query_is_a_400_with_guidance(self):
        response = self.client.post(
            "/api/recommendations/", {}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())

    def test_unknown_model_is_rejected(self):
        response = self.client.post(
            "/api/recommendations/",
            {"query": "beach", "model": "gpt-9"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_category_filter_restricts_candidates(self):
        response = self.client.post(
            "/api/recommendations/",
            {"query": "somewhere nice", "model": "tfidf", "category": "beach", "top_k": 5},
            content_type="application/json",
        )
        body = response.json()
        self.assertEqual(body["candidate_count"], 1)
        self.assertEqual(body["results"][0]["category"], "beach")

    def test_max_cost_filter_is_applied(self):
        response = self.client.post(
            "/api/recommendations/",
            {"query": "anywhere", "model": "tfidf", "max_cost": 90, "top_k": 10},
            content_type="application/json",
        )
        costs = [r["average_cost_per_day_usd"] for r in response.json()["results"]]
        self.assertTrue(all(c <= 90 for c in costs))

    def test_top_k_is_clamped_to_the_allowed_range(self):
        response = self.client.post(
            "/api/recommendations/",
            {"query": "beach", "model": "tfidf", "top_k": 500},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_signed_in_user_falls_back_to_saved_preferences(self):
        user = User.objects.create_user("prefs", password="test-pass-8899")
        user.travel_preferences = "ancient ruins and museums"
        user.save()
        self.client.force_login(user)
        response = self.client.post(
            "/api/recommendations/", {"model": "tfidf"}, content_type="application/json"
        )
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["query_from_profile"])
        self.assertEqual(body["results"][0]["name"], "Old Town")

    def test_compare_endpoint_needs_both_models(self):
        response = self.client.post(
            "/api/recommendations/compare/",
            {"query": "beach", "top_k": 3},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        # With the transformer disabled only one model runs, and the endpoint
        # must say so rather than inventing an agreement figure.
        self.assertEqual(body["models_compared"], ["tfidf"])
        self.assertEqual(body["agreement"], {})
        self.assertIn("nothing to compare", body["interpretation"])


class SemanticBackendTests(CatalogueMixin, TestCase):
    """Exercised only when the transformer is actually installed and cached.

    Skipping rather than failing keeps the suite green in CI, where torch is
    not installed; the tests still run locally where the model is present.
    """

    def setUp(self):
        engine.reset_caches()
        if not engine.is_available(engine.MODEL_SEMANTIC):
            self.skipTest("sentence-transformers model not available on this machine")
        self.build_catalogue()

    def tearDown(self):
        engine.reset_caches()

    def test_embeddings_are_cached_and_reused(self):
        engine.ensure_embeddings(Destination.objects.all())
        self.assertEqual(Destination.objects.filter(embedding__isnull=True).count(), 0)
        # A second pass has nothing left to do.
        self.assertEqual(engine.ensure_embeddings(Destination.objects.all()), 0)

    def test_stale_embedding_is_recomputed_when_text_changes(self):
        engine.ensure_embeddings(Destination.objects.all())
        destination = Destination.objects.get(name="Sandy Cove")
        destination.description = "Completely different text about alpine skiing."
        destination.save()
        self.assertEqual(engine.ensure_embeddings(Destination.objects.all()), 1)

    def test_paraphrase_matches_without_shared_keywords(self):
        # "switch off by the ocean" shares no content word with the beach
        # description, so only a semantic model can rank it first.
        run = engine.recommend(
            "somewhere calm to switch off by the ocean",
            top_k=1,
            model=engine.MODEL_SEMANTIC,
            allow_fallback=False,
        )
        self.assertEqual(run.model, engine.MODEL_SEMANTIC)
        self.assertEqual(run.results[0].destination.name, "Sandy Cove")

    def test_compare_runs_both_models_and_reports_agreement(self):
        outcome = engine.compare("quiet beach with seafood", top_k=3)
        self.assertEqual(set(outcome["runs"]), set(engine.ALL_MODELS))
        agreement = outcome["agreement"]
        self.assertIn("overlap_count", agreement)
        self.assertIn("jaccard", agreement)
        self.assertLessEqual(agreement["overlap_count"], 3)

    def test_each_run_reports_its_own_model(self):
        outcome = engine.compare("mountain hiking", top_k=2)
        for name, run in outcome["runs"].items():
            self.assertEqual(run.model, name)
            self.assertFalse(run.fallback)


class ConcurrentModelLoadTests(TestCase):
    """A caller arriving mid-load must wait, not be told the model is missing.

    Regression: the startup warm-up loads the transformer on a background
    thread. The fast path used to key off a flag set *before* the ten-second
    load, so a request landing in that window was told the semantic model was
    unavailable — with no reason attached — and was silently served by the
    baseline while a fallback note claimed the model was missing.
    """

    def setUp(self):
        engine.reset_caches()

    def tearDown(self):
        engine.reset_caches()

    def test_second_caller_waits_for_a_slow_load(self):
        import threading
        import time as timemod

        barrier = threading.Event()
        results = {}

        real_locked = engine._load_semantic_model_locked

        def slow_load():
            barrier.set()
            timemod.sleep(0.4)  # stand in for the real model load
            engine._semantic_state["model"] = "fake-model"
            return "fake-model"

        engine._load_semantic_model_locked = slow_load
        try:
            loader = threading.Thread(
                target=lambda: results.setdefault("loader", engine._load_semantic_model())
            )
            loader.start()
            barrier.wait(timeout=2)  # loader is now inside the slow load
            results["concurrent"] = engine._load_semantic_model()
            loader.join(timeout=5)
        finally:
            engine._load_semantic_model_locked = real_locked

        self.assertEqual(results["loader"], "fake-model")
        self.assertEqual(
            results["concurrent"],
            "fake-model",
            "a caller arriving during the load was told the model was unavailable",
        )

    def test_failed_load_is_not_retried_on_every_call(self):
        calls = []
        real_locked = engine._load_semantic_model_locked

        def failing_load():
            calls.append(1)
            engine._semantic_state["error"] = "boom"
            return None

        engine._load_semantic_model_locked = failing_load
        try:
            self.assertIsNone(engine._load_semantic_model())
            self.assertIsNone(engine._load_semantic_model())
            self.assertIsNone(engine._load_semantic_model())
        finally:
            engine._load_semantic_model_locked = real_locked

        self.assertEqual(len(calls), 1, "a failed load should be attempted once, not per call")

    def test_unavailable_model_always_reports_a_reason(self):
        real_locked = engine._load_semantic_model_locked

        def failing_load():
            engine._semantic_state["error"] = "sentence-transformers not installed"
            return None

        engine._load_semantic_model_locked = failing_load
        try:
            models = engine.available_models()
        finally:
            engine._load_semantic_model_locked = real_locked

        self.assertFalse(models[engine.MODEL_SEMANTIC]["available"])
        self.assertTrue(
            models[engine.MODEL_SEMANTIC]["error"],
            "an unavailable model must say why it is unavailable",
        )


class KendallTauTests(TestCase):
    def test_identical_orders_give_one(self):
        self.assertEqual(engine._kendall_tau_on_shared([1, 2, 3], [1, 2, 3]), 1.0)

    def test_reversed_orders_give_minus_one(self):
        self.assertEqual(engine._kendall_tau_on_shared([1, 2, 3], [3, 2, 1]), -1.0)

    def test_too_few_shared_items_gives_none(self):
        self.assertIsNone(engine._kendall_tau_on_shared([1, 2], [3, 4]))
