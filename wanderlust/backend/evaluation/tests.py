"""Tests for the ranking metrics and the evaluation runner.

The metric tests use hand-computed expected values rather than comparing
against another implementation, because these numbers end up in the report and
a metric that is subtly wrong would invalidate the whole comparison.
"""
import math

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings

from destinations.models import Destination
from recommendations import engine

from . import metrics, queries, runner


class PrecisionRecallTests(TestCase):
    relevance = {1: 3, 2: 2, 3: 1, 4: 0}

    def test_precision_counts_only_the_top_k(self):
        ranked = [1, 9, 2, 8, 3]
        self.assertEqual(metrics.precision_at_k(ranked, self.relevance, 1), 1.0)
        self.assertAlmostEqual(metrics.precision_at_k(ranked, self.relevance, 3), 2 / 3)
        self.assertAlmostEqual(metrics.precision_at_k(ranked, self.relevance, 5), 3 / 5)

    def test_precision_divides_by_k_not_by_results_returned(self):
        # A model returning one correct result must not score 1.0 at k=5.
        self.assertAlmostEqual(metrics.precision_at_k([1], self.relevance, 5), 0.2)

    def test_threshold_excludes_marginal_grades(self):
        ranked = [3, 1]
        self.assertEqual(
            metrics.precision_at_k(ranked, self.relevance, 1, binary_threshold=2), 0.0
        )
        self.assertEqual(
            metrics.precision_at_k(ranked, self.relevance, 1, binary_threshold=1), 1.0
        )

    def test_recall_is_relative_to_all_relevant_items(self):
        # Three judged items have grade >= 1.
        self.assertAlmostEqual(metrics.recall_at_k([1, 2], self.relevance, 2), 2 / 3)
        self.assertAlmostEqual(metrics.recall_at_k([1, 2, 3], self.relevance, 5), 1.0)

    def test_recall_with_no_relevant_items_is_zero(self):
        self.assertEqual(metrics.recall_at_k([1], {4: 0}, 5), 0.0)


class NdcgTests(TestCase):
    def test_dcg_matches_hand_calculation(self):
        # grades 3 then 1: (2**3-1)/log2(2) + (2**1-1)/log2(3)
        expected = 7 / 1.0 + 1 / math.log2(3)
        self.assertAlmostEqual(
            metrics.dcg_at_k([1, 2], {1: 3, 2: 1}, 2), expected, places=6
        )

    def test_perfect_ranking_scores_one(self):
        relevance = {1: 3, 2: 2, 3: 1}
        self.assertAlmostEqual(metrics.ndcg_at_k([1, 2, 3], relevance, 3), 1.0)

    def test_reversed_ranking_scores_below_one(self):
        relevance = {1: 3, 2: 2, 3: 1}
        self.assertLess(metrics.ndcg_at_k([3, 2, 1], relevance, 3), 1.0)

    def test_ordering_of_grades_matters(self):
        relevance = {1: 3, 2: 1}
        better = metrics.ndcg_at_k([1, 2], relevance, 2)
        worse = metrics.ndcg_at_k([2, 1], relevance, 2)
        self.assertGreater(better, worse)

    def test_no_relevant_items_gives_zero_not_a_crash(self):
        self.assertEqual(metrics.ndcg_at_k([1, 2], {}, 5), 0.0)

    def test_ndcg_is_bounded(self):
        relevance = {1: 3, 2: 2, 3: 1, 4: 3}
        for ranking in ([1, 2, 3, 4], [4, 3, 2, 1], [9, 8, 7], []):
            value = metrics.ndcg_at_k(ranking, relevance, 4)
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)


class RankMetricTests(TestCase):
    def test_reciprocal_rank_uses_first_hit(self):
        self.assertEqual(metrics.reciprocal_rank([9, 8, 1], {1: 3}), 1 / 3)
        self.assertEqual(metrics.reciprocal_rank([1], {1: 3}), 1.0)
        self.assertEqual(metrics.reciprocal_rank([9, 8], {1: 3}), 0.0)

    def test_average_precision_hand_calculation(self):
        # hits at ranks 1 and 3 -> (1/1 + 2/3) / 2
        result = metrics.average_precision([1, 9, 2], {1: 2, 2: 2}, k=3)
        self.assertAlmostEqual(result, (1.0 + 2 / 3) / 2)

    def test_evaluate_ranking_returns_every_metric(self):
        scores = metrics.evaluate_ranking([1, 2], {1: 3, 2: 1}, k_values=(1, 2))
        for name in ("precision@1", "recall@2", "ndcg@1", "ndcg@2", "mrr", "map"):
            self.assertIn(name, scores)


class PairedDifferenceTests(TestCase):
    def test_counts_wins_losses_and_ties(self):
        result = metrics.paired_differences([1.0, 0.5, 0.2], [0.5, 0.5, 0.9])
        self.assertEqual(result["a_wins"], 1)
        self.assertEqual(result["b_wins"], 1)
        self.assertEqual(result["ties"], 1)
        self.assertAlmostEqual(result["mean_difference"], (0.5 + 0.0 - 0.7) / 3, places=4)

    def test_identical_scores_have_no_effect_size(self):
        result = metrics.paired_differences([0.4, 0.4], [0.4, 0.4])
        self.assertEqual(result["mean_difference"], 0.0)
        self.assertIsNone(result["paired_t"])

    def test_mismatched_lengths_return_empty(self):
        self.assertEqual(metrics.paired_differences([1.0], [1.0, 2.0]), {})


class QuerySetTests(TestCase):
    def test_every_query_has_at_least_one_ideal_label(self):
        for spec in queries.LABELLED_QUERIES:
            grades = spec["relevance"].values()
            self.assertTrue(
                any(g == 3 for g in grades),
                f"{spec['id']} has no grade-3 destination, so nDCG cannot reach 1.",
            )

    def test_grades_are_within_the_documented_scale(self):
        for spec in queries.LABELLED_QUERIES:
            for name, grade in spec["relevance"].items():
                self.assertIn(grade, (1, 2, 3), f"{spec['id']}/{name} grade {grade}")

    def test_query_ids_are_unique(self):
        ids = [q["id"] for q in queries.LABELLED_QUERIES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_both_query_types_are_represented(self):
        self.assertEqual(set(queries.query_types()), {queries.LEXICAL, queries.PARAPHRASE})

    def test_summary_counts_match_the_query_list(self):
        info = queries.summary()
        self.assertEqual(info["query_count"], len(queries.LABELLED_QUERIES))
        self.assertEqual(
            info["relevance_judgements"],
            sum(len(q["relevance"]) for q in queries.LABELLED_QUERIES),
        )


def make_destination(name, category, description, tags, **kwargs):
    return Destination.objects.create(
        name=name,
        country=kwargs.get("country", "Testland"),
        country_code=kwargs.get("country_code", "TL"),
        category=category,
        short_description=description[:100],
        description=description,
        tags=tags,
        latitude=0.0,
        longitude=0.0,
        average_cost_per_day_usd=kwargs.get("cost", 100),
        best_season="All year",
    )


@override_settings(DISABLE_SEMANTIC_MODEL=True)
class RunnerTests(TestCase):
    """Runner behaviour, exercised against the TF-IDF backend only.

    Disabling the transformer keeps the suite fast and independent of whether
    the model is cached on the machine running it; the semantic path is
    covered separately in recommendations.tests when it is available.
    """

    def setUp(self):
        engine.reset_caches()
        make_destination(
            "Sandy Cove", "beach", "A quiet sandy beach with excellent seafood.", ["beach", "seafood"]
        )
        make_destination(
            "High Ridge", "mountain", "Steep mountain trails and alpine hiking.", ["hiking", "mountains"]
        )
        make_destination(
            "Old Town", "historical", "Ancient ruins and museums of antiquity.", ["ruins", "museums"]
        )

    def tearDown(self):
        engine.reset_caches()

    def _query_set(self):
        return [
            {
                "id": "t1",
                "query": "quiet sandy beach with seafood",
                "type": queries.LEXICAL,
                "relevance": {"Sandy Cove": 3},
            },
            {
                "id": "t2",
                "query": "mountain hiking trails",
                "type": queries.LEXICAL,
                "relevance": {"High Ridge": 3},
            },
        ]

    def test_runner_produces_metrics_for_each_model(self):
        results = runner.run_evaluation(query_set=self._query_set(), k_values=(1, 3))
        self.assertIn(engine.MODEL_TFIDF, results["models"])
        block = results["models"][engine.MODEL_TFIDF]
        self.assertEqual(block["query_count"], 2)
        self.assertIn("ndcg@3", block["overall"])
        self.assertEqual(len(block["per_query"]), 2)

    def test_runner_finds_the_obvious_answer(self):
        results = runner.run_evaluation(query_set=self._query_set(), k_values=(1,))
        block = results["models"][engine.MODEL_TFIDF]
        self.assertEqual(block["overall"]["precision@1"], 1.0)

    def test_metadata_records_the_conditions_of_the_run(self):
        results = runner.run_evaluation(query_set=self._query_set(), k_values=(1, 3))
        meta = results["meta"]
        self.assertEqual(meta["catalogue_size"], 3)
        self.assertEqual(meta["k_values"], [1, 3])
        self.assertIn(engine.MODEL_TFIDF, meta["models_evaluated"])
        self.assertIn(engine.MODEL_SEMANTIC, meta["models_unavailable"])

    def test_comparison_is_unavailable_with_only_one_model(self):
        results = runner.run_evaluation(query_set=self._query_set())
        self.assertFalse(results["comparison"]["available"])

    def test_empty_catalogue_is_an_error_not_a_silent_zero(self):
        Destination.objects.all().delete()
        with self.assertRaises(runner.EvaluationError):
            runner.run_evaluation(query_set=self._query_set())

    def test_empty_query_set_is_rejected(self):
        with self.assertRaises(runner.EvaluationError):
            runner.run_evaluation(query_set=[])

    def test_csv_flattening_produces_one_row_per_query_per_model(self):
        results = runner.run_evaluation(query_set=self._query_set(), k_values=(1, 3))
        rows = runner.flatten_for_csv(results)
        self.assertEqual(len(rows), 2)
        self.assertIn("ndcg@3", rows[0])
        self.assertIn("query_type", rows[0])


@override_settings(DISABLE_SEMANTIC_MODEL=True)
class EvaluationApiTests(TestCase):
    def setUp(self):
        engine.reset_caches()

    def tearDown(self):
        engine.reset_caches()

    def test_query_set_endpoint_exposes_the_protocol(self):
        response = self.client.get("/api/evaluation/queries/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["query_count"], len(queries.LABELLED_QUERIES))
        self.assertIn("limitation", body)
        self.assertIn("labelling_protocol", body)

    def test_results_endpoint_reports_missing_catalogue_clearly(self):
        cache.clear()
        with override_settings(
            EVALUATION_OUTPUT_DIR=settings.BASE_DIR / "nonexistent-results-dir"
        ):
            response = self.client.get("/api/evaluation/?refresh=1")
        self.assertEqual(response.status_code, 503)
        self.assertIn("hint", response.json())
