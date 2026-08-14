"""Read-only API over the evaluation results.

The mobile app shows the comparison inside the product, so the research
question is visible to anyone using it rather than buried in a report
appendix. Running a full evaluation takes seconds, so the endpoint serves the
saved results file by default and only recomputes when explicitly asked.
"""
import json
import logging

from django.conf import settings
from django.core.cache import cache
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import queries, runner

logger = logging.getLogger(__name__)

CACHE_KEY = "evaluation:last-results"
CACHE_SECONDS = 60 * 60


def _stored_results():
    """Load the most recent saved run, if `manage.py run_evaluation` has run."""
    path = settings.EVALUATION_OUTPUT_DIR / "results.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _summarise(results):
    """Trim a full result set down to what a phone screen needs."""
    comparison = results.get("comparison", {})
    models = {
        name: {
            "model": data["model"],
            "label": data["label"],
            "overall": data["overall"],
            "by_query_type": data["by_query_type"],
            "latency_ms": data["latency_ms"],
            "query_count": data["query_count"],
        }
        for name, data in results.get("models", {}).items()
    }
    return {
        "meta": results.get("meta", {}),
        "models": models,
        "comparison": {
            key: value for key, value in comparison.items() if key != "per_metric"
        },
        "headline": comparison.get("headline"),
    }


class EvaluationResultsView(APIView):
    """GET /api/evaluation/

    Query parameters:
        refresh=1   recompute instead of serving the saved/cached results
        full=1      include per-query detail and every paired metric
    """

    permission_classes = [AllowAny]

    def get(self, request):
        want_full = request.query_params.get("full") in ("1", "true", "yes")
        refresh = request.query_params.get("refresh") in ("1", "true", "yes")

        results = None
        source = "cache"

        if not refresh:
            results = cache.get(CACHE_KEY)
            if results is None:
                results = _stored_results()
                source = "file"

        if results is None:
            source = "computed"
            try:
                results = runner.run_evaluation()
            except runner.EvaluationError as exc:
                return Response(
                    {
                        "detail": str(exc),
                        "hint": "Run `python manage.py seed_destinations` then "
                        "`python manage.py run_evaluation`.",
                    },
                    status=503,
                )
            cache.set(CACHE_KEY, results, CACHE_SECONDS)

        payload = results if want_full else _summarise(results)
        payload = {**payload, "source": source}
        return Response(payload)


class QuerySetView(APIView):
    """GET /api/evaluation/queries/ — the labelled query set and its protocol."""

    permission_classes = [AllowAny]

    def get(self, _request):
        return Response(
            {
                "summary": queries.summary(),
                "missing_from_catalogue": queries.validate_against_catalogue(),
                "labelling_protocol": {
                    "3": "Ideal — satisfies every part of the query.",
                    "2": "Relevant — satisfies the main intent, misses a secondary condition.",
                    "1": "Marginal — defensible but weak.",
                    "0": "Not relevant (anything unlisted).",
                },
                "limitation": (
                    "Single-annotator judgements written by the project author. "
                    "No inter-annotator agreement is available, so differences "
                    "should be read as indicative rather than conclusive."
                ),
                "queries": [
                    {
                        "id": q["id"],
                        "query": q["query"],
                        "type": q["type"],
                        "judged_count": len(q["relevance"]),
                        "relevance": q["relevance"],
                    }
                    for q in queries.LABELLED_QUERIES
                ],
            }
        )
