"""Recommendation endpoints.

Three views:

``/api/recommendations/``          rank with one model (explicitly selectable)
``/api/recommendations/compare/``  rank with *both* models over the same query
``/api/recommendations/models/``   which backends this deployment can run

Every response names the model that produced it. That is not decoration: the
project's claim is a comparison between two models, so a ranking whose
provenance is ambiguous is worthless.
"""
import logging

from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from destinations.serializers import DestinationListSerializer

from . import engine
from .serializers import RecommendationRequestSerializer

logger = logging.getLogger(__name__)


def _serialize_result(result):
    """One ranked destination, with its score and the reason for it."""
    payload = DestinationListSerializer(result.destination).data
    payload["match_score"] = round(result.score, 4)
    payload["match_percent"] = round(max(0.0, min(result.score, 1.0)) * 100)
    payload["rank"] = result.rank
    payload["explanation"] = result.explanation
    payload["matched_terms"] = result.matched_terms
    if result.personalization_boost:
        payload["base_score"] = round(result.base_score, 4)
        payload["personalization_boost"] = round(result.personalization_boost, 4)
    return payload


def _serialize_run(run):
    return {
        "model": run.model,
        "model_label": engine.MODEL_LABELS[run.model],
        "requested_model": run.requested_model,
        "fallback": run.fallback,
        "note": run.note,
        "elapsed_ms": run.elapsed_ms,
        "catalogue_size": run.catalogue_size,
        "candidate_count": run.candidate_count,
        "personalized": run.personalized,
        "count": len(run.results),
        "results": [_serialize_result(r) for r in run.results],
    }


def _read_request(request):
    """Validate params from either the JSON body or the query string."""
    source = request.data if request.method == "POST" and request.data else request.query_params
    serializer = RecommendationRequestSerializer(data=source)
    serializer.is_valid(raise_exception=True)
    return serializer


def _resolve_query(serializer, request):
    """The text to rank against, falling back to the user's saved preferences."""
    query = (serializer.validated_data.get("query") or "").strip()
    used_profile = False
    if not query and request.user.is_authenticated:
        query = (request.user.travel_preferences or "").strip()
        used_profile = bool(query)
    return query, used_profile


class RecommendationView(APIView):
    """Rank destinations against a free-text description using one model.

    POST or GET, with any of:

        query        the user's description (falls back to their saved
                     travel_preferences when signed in)
        model        "semantic" | "tfidf" | omitted for the configured default
        category     restrict to one category
        country      restrict by country name (substring match)
        max_cost     maximum average cost per day in USD
        top_k        how many results (1-50, default 6)
        personalize  blend in the signed-in user's favourites and preferences
        explain      attach a reason to each result (default true)
    """

    permission_classes = [AllowAny]

    def post(self, request):
        return self._handle(request)

    def get(self, request):
        return self._handle(request)

    def _handle(self, request):
        serializer = _read_request(request)
        data = serializer.validated_data
        query, used_profile = _resolve_query(serializer, request)

        if not query:
            return Response(
                {
                    "detail": "Provide a 'query' describing the trip you want, "
                    "or save travel_preferences on your profile.",
                },
                status=400,
            )

        boosts = {}
        if data.get("personalize"):
            boosts = engine.build_personalization(request.user)

        try:
            run = engine.recommend(
                query,
                serializer.candidates(),
                top_k=data["top_k"],
                model=data.get("model"),
                explain=data["explain"],
                boosts=boosts,
            )
        except engine.ModelUnavailable as exc:
            return Response({"detail": str(exc)}, status=503)

        payload = _serialize_run(run)
        payload["query"] = query
        payload["query_from_profile"] = used_profile
        return Response(payload)


class ModelComparisonView(APIView):
    """Rank the same query with both models and report where they disagree.

    This is the endpoint the project's research question is built on. It takes
    the same parameters as the main endpoint (minus `model`, since it runs
    every available one) and adds an `agreement` block: how much the two top-k
    lists overlap, whether they agree on the best result, and Kendall's tau
    over the destinations both returned.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        return self._handle(request)

    def get(self, request):
        return self._handle(request)

    def _handle(self, request):
        serializer = _read_request(request)
        data = serializer.validated_data
        query, used_profile = _resolve_query(serializer, request)

        if not query:
            return Response(
                {"detail": "Provide a 'query' to compare the two models on."},
                status=400,
            )

        outcome = engine.compare(
            query,
            serializer.candidates(),
            top_k=data["top_k"],
            explain=data["explain"],
        )

        if not outcome["runs"]:
            return Response(
                {"detail": "No recommender backend is available."}, status=503
            )

        return Response(
            {
                "query": query,
                "query_from_profile": used_profile,
                "models_compared": list(outcome["runs"]),
                "runs": {
                    name: _serialize_run(run) for name, run in outcome["runs"].items()
                },
                "agreement": outcome["agreement"],
                "interpretation": _describe_agreement(outcome["agreement"]),
            }
        )


def _describe_agreement(agreement):
    """Plain-English reading of the overlap numbers, for the app to display."""
    if not agreement:
        return "Only one model is available, so there is nothing to compare."

    overlap = agreement["overlap_count"]
    k = agreement["top_k"]
    same_top = agreement["same_top_1"]
    tau = agreement["kendall_tau"]

    parts = [f"The two models agree on {overlap} of the top {k} destinations."]
    parts.append(
        "They pick the same top result."
        if same_top
        else "They disagree on the best result."
    )
    if tau is not None:
        if tau > 0.6:
            parts.append("Where they overlap, they order results very similarly.")
        elif tau > 0.2:
            parts.append("Where they overlap, the ordering is broadly similar.")
        elif tau > -0.2:
            parts.append("Where they overlap, the ordering is essentially unrelated.")
        else:
            parts.append("Where they overlap, they order results almost in reverse.")
    return " ".join(parts)


class AvailableModelsView(APIView):
    """GET /api/recommendations/models/ — what this deployment can actually run.

    Reports the reason a backend is unavailable rather than hiding it, so a
    machine that cannot install torch degrades visibly instead of silently
    reporting TF-IDF results as if they came from the transformer.
    """

    permission_classes = [AllowAny]

    def get(self, _request):
        models = engine.available_models()
        return Response(
            {
                "models": list(models.values()),
                "default": engine.normalise_model_name(
                    settings.RECOMMENDER_DEFAULT_MODEL
                ),
                "any_available": any(m["available"] for m in models.values()),
            }
        )
