"""Run the labelled query set through both recommenders and compare them.

This is the experiment the project's aim describes: one catalogue, one set of
queries, two models, the same metrics applied to both. Nothing here knows
which model is "supposed" to win.
"""
from __future__ import annotations

import logging
import platform
import sys
from datetime import datetime, timezone

from django.conf import settings

from recommendations import engine

from . import metrics, queries

logger = logging.getLogger(__name__)

DEFAULT_K_VALUES = (1, 3, 5, 10)
HEADLINE_METRIC = "ndcg@5"


class EvaluationError(RuntimeError):
    """Raised when the evaluation cannot run honestly (bad labels, no model)."""


def _resolve_relevance(labels, name_to_id):
    """Turn ``{destination name: grade}`` into ``{destination id: grade}``."""
    return {name_to_id[name]: grade for name, grade in labels.items() if name in name_to_id}


def run_evaluation(
    models=None,
    k_values=DEFAULT_K_VALUES,
    query_set=None,
    binary_threshold=metrics.DEFAULT_BINARY_THRESHOLD,
    strict=True,
):
    """Evaluate each model over the labelled query set.

    Args:
        models: which backends to evaluate; defaults to every available one.
        k_values: cutoffs for precision/recall/nDCG.
        query_set: override the labelled queries (used by tests).
        binary_threshold: minimum grade counted as relevant by binary metrics.
        strict: fail if a labelled destination is missing from the catalogue,
            rather than quietly scoring against an incomplete ground truth.

    Returns a JSON-serialisable dict: run metadata, per-model aggregate
    metrics, per-query detail, and the paired model-versus-model comparison.
    """
    from destinations.models import Destination

    query_set = query_set or queries.LABELLED_QUERIES
    if not query_set:
        raise EvaluationError("The labelled query set is empty.")

    missing = queries.validate_against_catalogue() if query_set is queries.LABELLED_QUERIES else []
    if missing and strict:
        raise EvaluationError(
            "These labelled destinations are not in the catalogue: "
            + ", ".join(missing)
            + ". Run `python manage.py seed_destinations` first."
        )

    catalogue = list(Destination.objects.all())
    if not catalogue:
        raise EvaluationError(
            "The catalogue is empty. Run `python manage.py seed_destinations` first."
        )
    name_to_id = {d.name: d.id for d in catalogue}

    requested = list(models) if models else list(engine.ALL_MODELS)
    usable = [m for m in requested if engine.is_available(m)]
    unavailable = {
        m: engine.available_models()[m]["error"] for m in requested if m not in usable
    }
    if not usable:
        raise EvaluationError(
            "No recommender is available to evaluate: " + str(unavailable)
        )

    # Embed once up front so per-query timings measure querying, not indexing.
    if engine.MODEL_SEMANTIC in usable:
        engine.ensure_embeddings(catalogue)

    max_k = max(k_values)
    per_model = {}

    for model in usable:
        per_query_rows = []
        for spec in query_set:
            relevance = _resolve_relevance(spec["relevance"], name_to_id)
            if not relevance:
                logger.warning("Query %s has no resolvable labels; skipped.", spec["id"])
                continue

            run = engine.recommend(
                spec["query"],
                catalogue,
                top_k=max_k,
                model=model,
                explain=False,
                allow_fallback=False,
            )
            scores = metrics.evaluate_ranking(
                run.destination_ids, relevance, k_values, binary_threshold
            )
            per_query_rows.append(
                {
                    "query_id": spec["id"],
                    "query": spec["query"],
                    "type": spec.get("type", "unspecified"),
                    "judged_count": len(relevance),
                    "elapsed_ms": run.elapsed_ms,
                    "top_results": [
                        {
                            "id": result.destination.id,
                            "name": result.destination.name,
                            "score": round(result.score, 4),
                            "relevance": relevance.get(result.destination.id, 0),
                        }
                        for result in run.results[:max(k_values)]
                    ],
                    "scores": scores,
                }
            )

        if not per_query_rows:
            continue

        overall = metrics.mean_scores([row["scores"] for row in per_query_rows])
        by_type = {}
        for query_type in sorted({row["type"] for row in per_query_rows}):
            subset = [r["scores"] for r in per_query_rows if r["type"] == query_type]
            by_type[query_type] = {
                "query_count": len(subset),
                **metrics.mean_scores(subset),
            }

        latencies = [row["elapsed_ms"] for row in per_query_rows]
        per_model[model] = {
            "model": model,
            "label": engine.MODEL_LABELS[model],
            "query_count": len(per_query_rows),
            "overall": overall,
            "by_query_type": by_type,
            "latency_ms": {
                "mean": round(sum(latencies) / len(latencies), 2),
                "min": round(min(latencies), 2),
                "max": round(max(latencies), 2),
            },
            "per_query": per_query_rows,
        }

    comparison = _compare_models(per_model, k_values)

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "catalogue_size": len(catalogue),
            "query_set": queries.summary()
            if query_set is queries.LABELLED_QUERIES
            else {"query_count": len(query_set)},
            "k_values": list(k_values),
            "binary_threshold": binary_threshold,
            "headline_metric": HEADLINE_METRIC,
            "models_evaluated": usable,
            "models_unavailable": unavailable,
            "embedding_model": settings.EMBEDDING_MODEL_NAME,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "models": per_model,
        "comparison": comparison,
    }


def _compare_models(per_model, k_values):
    """Paired per-query comparison of semantic against the TF-IDF baseline."""
    semantic = per_model.get(engine.MODEL_SEMANTIC)
    tfidf = per_model.get(engine.MODEL_TFIDF)
    if not semantic or not tfidf:
        return {
            "available": False,
            "reason": "Both models must run for a comparison to be meaningful.",
        }

    # Align on query id — a query skipped for one model must be skipped for both.
    tfidf_rows = {row["query_id"]: row for row in tfidf["per_query"]}
    shared = [
        (row, tfidf_rows[row["query_id"]])
        for row in semantic["per_query"]
        if row["query_id"] in tfidf_rows
    ]

    metric_names = [f"precision@{k}" for k in k_values] + [
        f"ndcg@{k}" for k in k_values
    ] + ["mrr", "map"]

    per_metric = {}
    for name in metric_names:
        per_metric[name] = metrics.paired_differences(
            [s["scores"][name] for s, _ in shared],
            [t["scores"][name] for _, t in shared],
        )

    by_type = {}
    for query_type in sorted({s["type"] for s, _ in shared}):
        subset = [(s, t) for s, t in shared if s["type"] == query_type]
        by_type[query_type] = metrics.paired_differences(
            [s["scores"][HEADLINE_METRIC] for s, _ in subset],
            [t["scores"][HEADLINE_METRIC] for _, t in subset],
        )

    headline = per_metric.get(HEADLINE_METRIC, {})
    difference = headline.get("mean_difference", 0.0)
    if abs(difference) < 0.01:
        verdict = (
            f"No practical difference on {HEADLINE_METRIC} "
            f"({difference:+.4f}); the transformer does not earn its extra cost here."
        )
    elif difference > 0:
        verdict = (
            f"Semantic ahead of TF-IDF on {HEADLINE_METRIC} by {difference:+.4f} "
            f"(wins {headline.get('a_wins')} queries, loses {headline.get('b_wins')})."
        )
    else:
        verdict = (
            f"TF-IDF ahead of semantic on {HEADLINE_METRIC} by {-difference:+.4f} "
            f"(wins {headline.get('b_wins')} queries, loses {headline.get('a_wins')})."
        )

    return {
        "available": True,
        "direction": "positive favours semantic, negative favours tfidf",
        "shared_query_count": len(shared),
        "per_metric": per_metric,
        "headline": {
            "metric": HEADLINE_METRIC,
            "semantic": semantic["overall"][HEADLINE_METRIC],
            "tfidf": tfidf["overall"][HEADLINE_METRIC],
            "difference": round(difference, 4),
            "verdict": verdict,
        },
        "by_query_type": by_type,
        "latency": {
            "semantic_mean_ms": semantic["latency_ms"]["mean"],
            "tfidf_mean_ms": tfidf["latency_ms"]["mean"],
            "semantic_slowdown_x": (
                round(
                    semantic["latency_ms"]["mean"]
                    / max(tfidf["latency_ms"]["mean"], 0.001),
                    2,
                )
            ),
        },
    }


def flatten_for_csv(results):
    """Flatten a results dict into rows for a spreadsheet / the report appendix."""
    rows = []
    for model, data in results.get("models", {}).items():
        for entry in data["per_query"]:
            row = {
                "model": model,
                "query_id": entry["query_id"],
                "query": entry["query"],
                "query_type": entry["type"],
                "judged_count": entry["judged_count"],
                "elapsed_ms": entry["elapsed_ms"],
                "top_1": entry["top_results"][0]["name"] if entry["top_results"] else "",
            }
            row.update(entry["scores"])
            rows.append(row)
    return rows
