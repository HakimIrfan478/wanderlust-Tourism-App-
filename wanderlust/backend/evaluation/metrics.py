"""Ranking metrics for the semantic-versus-TF-IDF comparison.

Implemented directly rather than pulled from a library so the definitions used
in the report are visible and checkable. All functions take:

``ranked_ids``
    Destination ids in the order the model returned them.
``relevance``
    ``{destination_id: graded_relevance}`` for the judged items of one query.
    Anything absent is treated as relevance 0 (not relevant).

Graded relevance runs 0-3; see :mod:`evaluation.queries` for the labelling
protocol. Binary metrics (precision, recall, MRR, MAP) count an item as
relevant when its grade is at or above ``binary_threshold`` (default 1).
"""
from __future__ import annotations

import math
from typing import Mapping, Sequence

DEFAULT_BINARY_THRESHOLD = 1


def _relevant_set(relevance: Mapping, threshold: int) -> set:
    return {key for key, grade in relevance.items() if grade >= threshold}


def precision_at_k(
    ranked_ids: Sequence,
    relevance: Mapping,
    k: int,
    binary_threshold: int = DEFAULT_BINARY_THRESHOLD,
) -> float:
    """Fraction of the top k results that are relevant.

    Divided by k rather than by len(top_k) so a model that returns fewer than
    k results is not rewarded for it.
    """
    if k <= 0:
        return 0.0
    relevant = _relevant_set(relevance, binary_threshold)
    hits = sum(1 for item in ranked_ids[:k] if item in relevant)
    return hits / k


def recall_at_k(
    ranked_ids: Sequence,
    relevance: Mapping,
    k: int,
    binary_threshold: int = DEFAULT_BINARY_THRESHOLD,
) -> float:
    """Fraction of all relevant items that appear in the top k."""
    relevant = _relevant_set(relevance, binary_threshold)
    if not relevant:
        return 0.0
    hits = sum(1 for item in ranked_ids[:k] if item in relevant)
    return hits / len(relevant)


def dcg_at_k(ranked_ids: Sequence, relevance: Mapping, k: int) -> float:
    """Discounted cumulative gain with the exponential gain formulation.

    gain = (2**rel - 1) / log2(rank + 1), which rewards placing a highly
    relevant item above a marginally relevant one.
    """
    total = 0.0
    for index, item in enumerate(ranked_ids[:k], start=1):
        grade = relevance.get(item, 0)
        if grade:
            total += (2**grade - 1) / math.log2(index + 1)
    return total


def ndcg_at_k(ranked_ids: Sequence, relevance: Mapping, k: int) -> float:
    """DCG normalised by the best achievable DCG for this query.

    Returns a value in [0, 1] where 1 means the model produced the ideal
    ordering of the judged items. Queries with no judged relevant item return
    0 and should be excluded from the query set rather than averaged in.
    """
    ideal_grades = sorted(relevance.values(), reverse=True)[:k]
    ideal = sum(
        (2**grade - 1) / math.log2(index + 1)
        for index, grade in enumerate(ideal_grades, start=1)
        if grade
    )
    if ideal == 0:
        return 0.0
    return dcg_at_k(ranked_ids, relevance, k) / ideal


def reciprocal_rank(
    ranked_ids: Sequence,
    relevance: Mapping,
    binary_threshold: int = DEFAULT_BINARY_THRESHOLD,
) -> float:
    """1 / rank of the first relevant result, or 0 if there is none."""
    relevant = _relevant_set(relevance, binary_threshold)
    for index, item in enumerate(ranked_ids, start=1):
        if item in relevant:
            return 1.0 / index
    return 0.0


def average_precision(
    ranked_ids: Sequence,
    relevance: Mapping,
    k: int | None = None,
    binary_threshold: int = DEFAULT_BINARY_THRESHOLD,
) -> float:
    """Mean of the precision values measured at each relevant hit."""
    relevant = _relevant_set(relevance, binary_threshold)
    if not relevant:
        return 0.0
    cutoff = k if k is not None else len(ranked_ids)
    hits = 0
    total = 0.0
    for index, item in enumerate(ranked_ids[:cutoff], start=1):
        if item in relevant:
            hits += 1
            total += hits / index
    denominator = min(len(relevant), cutoff)
    return total / denominator if denominator else 0.0


def evaluate_ranking(
    ranked_ids: Sequence,
    relevance: Mapping,
    k_values: Sequence[int] = (1, 3, 5, 10),
    binary_threshold: int = DEFAULT_BINARY_THRESHOLD,
) -> dict:
    """Every metric for one query's ranking, keyed by metric name."""
    scores = {}
    for k in k_values:
        scores[f"precision@{k}"] = precision_at_k(
            ranked_ids, relevance, k, binary_threshold
        )
        scores[f"recall@{k}"] = recall_at_k(ranked_ids, relevance, k, binary_threshold)
        scores[f"ndcg@{k}"] = ndcg_at_k(ranked_ids, relevance, k)
    scores["mrr"] = reciprocal_rank(ranked_ids, relevance, binary_threshold)
    scores["map"] = average_precision(
        ranked_ids, relevance, max(k_values), binary_threshold
    )
    return {name: round(value, 4) for name, value in scores.items()}


def mean_scores(per_query: Sequence[Mapping]) -> dict:
    """Average each metric across queries (the 'mean' in mean nDCG / MAP)."""
    if not per_query:
        return {}
    names = per_query[0].keys()
    return {
        name: round(sum(row[name] for row in per_query) / len(per_query), 4)
        for name in names
    }


def paired_differences(scores_a: Sequence[float], scores_b: Sequence[float]) -> dict:
    """Summarise a paired per-query comparison of two models.

    The same queries run through both models, so the comparison is paired.
    This reports the mean difference and how often each model wins, which is
    what the report needs in order to say whether any gap is consistent or
    driven by a couple of queries.
    """
    if len(scores_a) != len(scores_b) or not scores_a:
        return {}

    differences = [a - b for a, b in zip(scores_a, scores_b)]
    n = len(differences)
    mean = sum(differences) / n
    wins_a = sum(1 for d in differences if d > 1e-9)
    wins_b = sum(1 for d in differences if d < -1e-9)

    summary = {
        "n_queries": n,
        "mean_difference": round(mean, 4),
        "a_wins": wins_a,
        "b_wins": wins_b,
        "ties": n - wins_a - wins_b,
    }

    if n > 1:
        variance = sum((d - mean) ** 2 for d in differences) / (n - 1)
        std = math.sqrt(variance)
        summary["std_difference"] = round(std, 4)
        if std > 1e-12:
            # Paired t statistic. Reported as a descriptive effect size only:
            # with ~26 queries and a single annotator this is not a
            # publication-grade significance test.
            summary["paired_t"] = round(mean / (std / math.sqrt(n)), 4)
            summary["cohens_d"] = round(mean / std, 4)
        else:
            summary["paired_t"] = None
            summary["cohens_d"] = None

    return summary
