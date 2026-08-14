"""
Content-based destination recommenders.

The research question this project asks is whether a transformer-based
*semantic* recommender retrieves more relevant destinations than a classical
*keyword* baseline, for short natural-language travel queries. Answering that
requires both models to be runnable over the same catalogue, on demand, in the
same process — not one as a fallback for the other.

This module therefore exposes two independent, explicitly selectable backends:

``semantic``
    A ``sentence-transformers`` bi-encoder (``all-MiniLM-L6-v2`` by default).
    Query and destination text are mapped into a shared 384-dimensional vector
    space and ranked by cosine similarity, so "somewhere peaceful by the sea"
    can match a description that never uses those words.

``tfidf``
    scikit-learn TF-IDF vectors plus cosine similarity: the classical
    content-based method, and the control condition of the experiment.

Both are fitted over the **full** catalogue even when the caller filters to a
subset, so scores stay comparable across requests. Every ranking returned
records which model produced it, whether a fallback occurred, and how long it
took, which is what makes the comparison reportable.

The two entry points are :func:`recommend` (one model) and :func:`compare`
(both models over one query).
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model identifiers
# ---------------------------------------------------------------------------
MODEL_SEMANTIC = "semantic"
MODEL_TFIDF = "tfidf"
ALL_MODELS = (MODEL_SEMANTIC, MODEL_TFIDF)

MODEL_LABELS = {
    MODEL_SEMANTIC: "Semantic (sentence-transformer)",
    MODEL_TFIDF: "TF-IDF (keyword baseline)",
}

MODEL_DESCRIPTIONS = {
    MODEL_SEMANTIC: (
        "Transformer bi-encoder that compares the meaning of your description "
        "with the meaning of each destination."
    ),
    MODEL_TFIDF: (
        "Classical keyword model that scores destinations on the words they "
        "share with your description, weighted by how rare those words are."
    ),
}

# Accepted spellings, so older clients and report text keep working.
MODEL_ALIASES = {
    "semantic": MODEL_SEMANTIC,
    "sentence-transformer": MODEL_SEMANTIC,
    "sentence_transformer": MODEL_SEMANTIC,
    "sentencetransformer": MODEL_SEMANTIC,
    "transformer": MODEL_SEMANTIC,
    "sbert": MODEL_SEMANTIC,
    "minilm": MODEL_SEMANTIC,
    "embedding": MODEL_SEMANTIC,
    "tfidf": MODEL_TFIDF,
    "tf-idf": MODEL_TFIDF,
    "tf_idf": MODEL_TFIDF,
    "baseline": MODEL_TFIDF,
    "keyword": MODEL_TFIDF,
    "classical": MODEL_TFIDF,
}


class ModelUnavailable(RuntimeError):
    """Raised when a specific backend was demanded but cannot be loaded."""


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass
class RankedDestination:
    """One destination in a ranking, with the reason it scored where it did."""

    destination: object
    score: float
    rank: int
    explanation: str = ""
    matched_terms: list = field(default_factory=list)
    base_score: float | None = None
    personalization_boost: float = 0.0


@dataclass
class RecommendationRun:
    """A complete ranking plus the metadata needed to report on it."""

    query: str
    model: str
    requested_model: str
    fallback: bool
    results: list
    elapsed_ms: float
    catalogue_size: int
    candidate_count: int
    note: str = ""
    personalized: bool = False

    @property
    def destination_ids(self):
        return [r.destination.id for r in self.results]


# ---------------------------------------------------------------------------
# Lazily-built model state
# ---------------------------------------------------------------------------
_lock = threading.RLock()

_semantic_state = {
    "model": None,
    "attempted": False,  # a load has started
    "resolved": False,   # a load has finished, successfully or not
    "error": None,
    "load_seconds": None,
    "dimension": None,
    "tag_vectors": {},
}

_tfidf_state = {
    "vectorizer": None,
    "matrix": None,
    "ids": None,
    "row_by_id": None,
    "signature": None,
    "feature_names": None,
}

# Loaded SentenceTransformer objects, keyed by model name. Kept outside
# _semantic_state because loading one costs ~10 seconds and the object is
# immutable — resetting the caches should not pay that cost again.
_model_registry = {}


def reset_caches():
    """Drop every fitted index. Used by tests and by the seed command."""
    with _lock:
        _semantic_state.update(
            {
                "model": None,
                "attempted": False,
                "resolved": False,
                "error": None,
                "load_seconds": None,
                "dimension": None,
                "tag_vectors": {},
            }
        )
        _tfidf_state.update(
            {
                "vectorizer": None,
                "matrix": None,
                "ids": None,
                "row_by_id": None,
                "signature": None,
                "feature_names": None,
            }
        )


# ---------------------------------------------------------------------------
# Semantic backend
# ---------------------------------------------------------------------------
def _load_semantic_model():
    """Load the sentence-transformer once; return None if it is unavailable.

    Failure is recorded rather than raised so that :func:`available_models`
    can report *why* the semantic condition could not run.

    The fast path checks ``resolved``, not ``attempted``: the startup warm-up
    loads the model on a background thread, and a caller arriving during those
    few seconds must wait for the outcome rather than be told the model is
    unavailable. Checking a flag that is set *before* the slow load would
    report a transient "unavailable" with no reason attached, and a request
    served that way would be attributed to the wrong model.
    """
    if _semantic_state["resolved"]:
        return _semantic_state["model"]

    with _lock:
        if _semantic_state["resolved"]:
            return _semantic_state["model"]
        _semantic_state["attempted"] = True
        try:
            return _load_semantic_model_locked()
        finally:
            # Whatever happened, the outcome is now final — including failure,
            # so a failed load is not retried on every subsequent request.
            _semantic_state["resolved"] = True


def _load_semantic_model_locked():
    """The body of the load. Only called by _load_semantic_model, under the lock."""
    if getattr(settings, "DISABLE_SEMANTIC_MODEL", False):
        _semantic_state["error"] = "Disabled via DISABLE_SEMANTIC_MODEL."
        return None

    if getattr(settings, "HF_OFFLINE_ONLY", False):
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:  # torch missing / incompatible build
        _semantic_state["error"] = f"sentence-transformers could not be imported: {exc}"
        logger.warning("Semantic backend unavailable: %s", exc)
        return None

    name = settings.EMBEDDING_MODEL_NAME
    started = time.perf_counter()
    cached = _model_registry.get(name)
    if cached is not None:
        model = cached
    else:
        try:
            model = SentenceTransformer(name)
        except Exception as exc:  # not cached and no network, corrupt cache...
            _semantic_state["error"] = f"Could not load '{name}': {exc}"
            logger.warning("Semantic model '%s' failed to load: %s", name, exc)
            return None
        _model_registry[name] = model

    _semantic_state["model"] = model
    _semantic_state["load_seconds"] = round(time.perf_counter() - started, 2)
    try:
        _semantic_state["dimension"] = int(model.get_sentence_embedding_dimension())
    except Exception:
        _semantic_state["dimension"] = None
    logger.info(
        "Semantic model '%s' loaded in %ss (dim=%s)",
        name,
        _semantic_state["load_seconds"],
        _semantic_state["dimension"],
    )
    return model


def _normalise(vectors: np.ndarray) -> np.ndarray:
    """L2-normalise row-wise so a dot product equals cosine similarity."""
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1e-9
    return vectors / norms


def embed_texts(texts: Sequence[str]) -> np.ndarray:
    """Embed texts with the transformer, L2-normalised. Requires availability."""
    model = _load_semantic_model()
    if model is None:
        raise ModelUnavailable(_semantic_state["error"] or "Semantic model unavailable.")
    vectors = model.encode(
        list(texts), convert_to_numpy=True, show_progress_bar=False, batch_size=32
    )
    return _normalise(vectors)


def compute_destination_embedding(destination):
    """Return one destination's embedding as a plain list, or None if disabled."""
    if not is_available(MODEL_SEMANTIC):
        return None
    return embed_texts([destination.text_for_embedding()])[0].astype(float).tolist()


def _embedding_is_fresh(destination) -> bool:
    """True when the cached vector matches the current model *and* text."""
    if not destination.embedding:
        return False
    if destination.embedding_model != settings.EMBEDDING_MODEL_NAME:
        return False
    computed = destination.embedding_computed_at
    if computed is None:
        return False
    return computed >= destination.updated_at


def ensure_embeddings(destinations, recompute: bool = False) -> int:
    """Compute and cache any missing/stale embeddings in a single batch.

    Returns the number of destinations that were (re)embedded. Caching means
    an evaluation run embeds the catalogue once rather than once per query.
    """
    if not is_available(MODEL_SEMANTIC):
        return 0

    destinations = list(destinations)
    stale = [
        d for d in destinations if recompute or not _embedding_is_fresh(d)
    ]
    if not stale:
        return 0

    vectors = embed_texts([d.text_for_embedding() for d in stale])
    now = timezone.now()
    for destination, vector in zip(stale, vectors):
        destination.embedding = vector.astype(float).tolist()
        destination.embedding_model = settings.EMBEDDING_MODEL_NAME
        destination.embedding_computed_at = now

    type(stale[0]).objects.bulk_update(
        stale, ["embedding", "embedding_model", "embedding_computed_at"]
    )
    logger.info("Embedded %s destination(s).", len(stale))
    return len(stale)


def _semantic_scores(query: str, destinations: list) -> np.ndarray:
    ensure_embeddings(destinations)
    query_vector = embed_texts([query])[0]
    matrix = _normalise(np.array([d.embedding for d in destinations], dtype=np.float32))
    # Both sides are unit vectors, so the dot product is the cosine similarity.
    return matrix @ query_vector


def _tag_vector(tag: str) -> np.ndarray:
    """Embed (and memoise) a single tag, used to explain semantic matches."""
    cache = _semantic_state["tag_vectors"]
    if tag not in cache:
        cache[tag] = embed_texts([tag])[0]
    return cache[tag]


def _semantic_explanation(query_vector: np.ndarray, destination) -> tuple[str, list]:
    """Name the destination's own facets that best match the query.

    The score itself is a single cosine number and explains nothing, so we
    re-embed the destination's tags, category and season and report the two or
    three that sit closest to the query. This is the "why this destination"
    feature listed as an advanced objective.
    """
    facets = list(destination.tags or [])
    if destination.get_category_display():
        facets.append(destination.get_category_display().lower())
    if destination.best_season:
        facets.append(destination.best_season.lower())
    facets = [f for f in dict.fromkeys(facets) if f]
    if not facets:
        return "", []

    try:
        scored = sorted(
            ((float(_tag_vector(f) @ query_vector), f) for f in facets),
            reverse=True,
        )
    except ModelUnavailable:
        return "", []

    top = [name for score, name in scored[:3] if score > 0.15]
    if not top:
        return "", []
    return "Semantically close to " + ", ".join(top), top


# ---------------------------------------------------------------------------
# TF-IDF backend
# ---------------------------------------------------------------------------
def _catalogue_signature():
    """Cheap fingerprint of the catalogue, so the index refits when data changes."""
    from django.db.models import Count, Max

    from destinations.models import Destination

    agg = Destination.objects.aggregate(n=Count("id"), latest=Max("updated_at"))
    latest = agg["latest"]
    return (agg["n"], latest.isoformat() if latest else None)


def _build_tfidf_index():
    """Fit TF-IDF over the whole catalogue.

    Fitting over everything (not just the filtered candidates) keeps the
    inverse-document-frequency weights stable, so a score means the same thing
    whether or not the caller applied a category filter.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    from destinations.models import Destination

    signature = _catalogue_signature()
    if _tfidf_state["signature"] == signature and _tfidf_state["matrix"] is not None:
        return

    with _lock:
        if _tfidf_state["signature"] == signature and _tfidf_state["matrix"] is not None:
            return

        rows = list(Destination.objects.order_by("id"))
        if not rows:
            _tfidf_state.update(
                {
                    "vectorizer": None,
                    "matrix": None,
                    "ids": [],
                    "row_by_id": {},
                    "signature": signature,
                    "feature_names": None,
                }
            )
            return

        vectorizer = TfidfVectorizer(
            stop_words="english",
            sublinear_tf=True,
            ngram_range=(1, 2),
            min_df=1,
            max_features=20000,
        )
        matrix = vectorizer.fit_transform(d.text_for_embedding() for d in rows)
        ids = [d.id for d in rows]

        _tfidf_state.update(
            {
                "vectorizer": vectorizer,
                "matrix": matrix,
                "ids": ids,
                "row_by_id": {dest_id: i for i, dest_id in enumerate(ids)},
                "signature": signature,
                "feature_names": vectorizer.get_feature_names_out(),
            }
        )
        logger.info(
            "TF-IDF index fitted over %s destinations (%s features).",
            len(ids),
            matrix.shape[1],
        )


def _tfidf_scores(query: str, destinations: list) -> tuple[np.ndarray, object, object]:
    from sklearn.metrics.pairwise import cosine_similarity

    _build_tfidf_index()
    if _tfidf_state["matrix"] is None:
        return np.zeros(len(destinations)), None, None

    query_vector = _tfidf_state["vectorizer"].transform([query])
    row_by_id = _tfidf_state["row_by_id"]

    # Keep track of each candidate's position so scores land back in the
    # caller's order, and skip any candidate the index has not seen yet.
    positions, rows = [], []
    for position, destination in enumerate(destinations):
        row = row_by_id.get(destination.id)
        if row is not None:
            positions.append(position)
            rows.append(row)

    scores = np.zeros(len(destinations), dtype=float)
    if not rows:
        return scores, query_vector, None

    subset = _tfidf_state["matrix"][rows]
    similarities = cosine_similarity(query_vector, subset).ravel()
    scores[positions] = similarities
    return scores, query_vector, subset


def _tfidf_explanation(query_vector, destination) -> tuple[str, list]:
    """Report the shared terms that actually drove the TF-IDF score."""
    if query_vector is None or _tfidf_state["matrix"] is None:
        return "", []
    row = _tfidf_state["row_by_id"].get(destination.id)
    if row is None:
        return "", []

    doc_vector = _tfidf_state["matrix"][row]
    shared = query_vector.multiply(doc_vector).tocoo()
    if shared.nnz == 0:
        return "No shared keywords — matched on nothing", []

    names = _tfidf_state["feature_names"]
    ranked = sorted(zip(shared.data, shared.col), reverse=True)[:3]
    terms = [str(names[col]) for _, col in ranked]
    return "Shares the keywords " + ", ".join(terms), terms


# ---------------------------------------------------------------------------
# Availability / model resolution
# ---------------------------------------------------------------------------
def _tfidf_available() -> tuple[bool, str | None]:
    try:
        import sklearn  # noqa: F401
    except Exception as exc:
        return False, f"scikit-learn could not be imported: {exc}"
    return True, None


def is_available(model: str) -> bool:
    if model == MODEL_SEMANTIC:
        return _load_semantic_model() is not None
    if model == MODEL_TFIDF:
        return _tfidf_available()[0]
    return False


def available_models() -> dict:
    """Describe both backends, including why one may be unavailable."""
    semantic_ok = is_available(MODEL_SEMANTIC)
    tfidf_ok, tfidf_error = _tfidf_available()
    return {
        MODEL_SEMANTIC: {
            "id": MODEL_SEMANTIC,
            "label": MODEL_LABELS[MODEL_SEMANTIC],
            "description": MODEL_DESCRIPTIONS[MODEL_SEMANTIC],
            "available": semantic_ok,
            "error": None if semantic_ok else _semantic_state["error"],
            "model_name": settings.EMBEDDING_MODEL_NAME,
            "dimension": _semantic_state["dimension"],
            "load_seconds": _semantic_state["load_seconds"],
        },
        MODEL_TFIDF: {
            "id": MODEL_TFIDF,
            "label": MODEL_LABELS[MODEL_TFIDF],
            "description": MODEL_DESCRIPTIONS[MODEL_TFIDF],
            "available": tfidf_ok,
            "error": tfidf_error,
            "model_name": "sklearn TfidfVectorizer (1-2 grams, sublinear tf)",
            "dimension": (
                _tfidf_state["matrix"].shape[1]
                if _tfidf_state["matrix"] is not None
                else None
            ),
            "load_seconds": None,
        },
    }


def normalise_model_name(requested) -> str | None:
    """Map any accepted spelling to a canonical id; None means 'no preference'."""
    if requested is None:
        return None
    key = str(requested).strip().lower()
    if key in ("", "auto", "default"):
        return None
    return MODEL_ALIASES.get(key, key)


def resolve_model(requested=None, allow_fallback: bool = True):
    """Decide which backend serves a request.

    Returns ``(model, requested_model, fell_back, note)``. An explicit request
    for an unavailable model falls back to the other one and says so, so a
    response is never silently attributed to the wrong model.
    """
    canonical = normalise_model_name(requested)
    if canonical is not None and canonical not in ALL_MODELS:
        raise ValueError(
            f"Unknown model '{requested}'. Choose one of: {', '.join(ALL_MODELS)}."
        )

    target = canonical or normalise_model_name(
        getattr(settings, "RECOMMENDER_DEFAULT_MODEL", MODEL_SEMANTIC)
    ) or MODEL_SEMANTIC
    requested_label = canonical or "auto"

    if is_available(target):
        return target, requested_label, False, ""

    other = MODEL_TFIDF if target == MODEL_SEMANTIC else MODEL_SEMANTIC
    reason = (
        _semantic_state["error"]
        if target == MODEL_SEMANTIC
        else _tfidf_available()[1]
    ) or "model unavailable"

    if not allow_fallback:
        raise ModelUnavailable(f"The '{target}' model is unavailable: {reason}")

    if not is_available(other):
        raise ModelUnavailable(
            f"No recommender is available. '{target}': {reason}"
        )

    note = f"'{target}' unavailable ({reason}); served by '{other}' instead."
    logger.warning(note)
    return other, requested_label, True, note


# ---------------------------------------------------------------------------
# Public ranking API
# ---------------------------------------------------------------------------
def recommend(
    query: str,
    destinations: Iterable | None = None,
    top_k: int = 5,
    model=None,
    explain: bool = True,
    boosts: dict | None = None,
    allow_fallback: bool = True,
) -> RecommendationRun:
    """Rank destinations against ``query`` using one named model.

    Args:
        query: the user's natural-language description.
        destinations: candidates to rank; defaults to the whole catalogue.
        top_k: how many to return.
        model: ``"semantic"``, ``"tfidf"``, or None for the configured default.
        explain: attach a human-readable reason to each result.
        boosts: optional ``{destination_id: additive_score}`` used for the
            personalised hybrid ranking. Recorded separately from the model's
            own score so the two are never confused.
        allow_fallback: if False, an unavailable model raises rather than
            silently switching — which is what the evaluation runner wants.
    """
    started = time.perf_counter()

    if destinations is None:
        from destinations.models import Destination

        destinations = Destination.objects.all()
    candidates = list(destinations)

    active_model, requested_label, fell_back, note = resolve_model(
        model, allow_fallback=allow_fallback
    )

    from destinations.models import Destination

    catalogue_size = Destination.objects.count()

    if not candidates:
        return RecommendationRun(
            query=query,
            model=active_model,
            requested_model=requested_label,
            fallback=fell_back,
            results=[],
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            catalogue_size=catalogue_size,
            candidate_count=0,
            note=note or "No destinations matched the filters.",
        )

    query_vector = None
    if active_model == MODEL_SEMANTIC:
        scores = _semantic_scores(query, candidates)
        if explain:
            query_vector = embed_texts([query])[0]
    else:
        scores, query_vector, _ = _tfidf_scores(query, candidates)

    base_scores = np.asarray(scores, dtype=float)
    final_scores = base_scores.copy()

    boosts = boosts or {}
    if boosts:
        for index, destination in enumerate(candidates):
            final_scores[index] += boosts.get(destination.id, 0.0)

    order = np.argsort(-final_scores, kind="stable")[:top_k]

    results = []
    for rank, index in enumerate(order, start=1):
        destination = candidates[int(index)]
        explanation, terms = "", []
        if explain:
            if active_model == MODEL_SEMANTIC and query_vector is not None:
                explanation, terms = _semantic_explanation(query_vector, destination)
            elif active_model == MODEL_TFIDF:
                explanation, terms = _tfidf_explanation(query_vector, destination)
        boost = float(boosts.get(destination.id, 0.0))
        results.append(
            RankedDestination(
                destination=destination,
                score=float(final_scores[int(index)]),
                rank=rank,
                explanation=explanation,
                matched_terms=terms,
                base_score=float(base_scores[int(index)]),
                personalization_boost=boost,
            )
        )

    return RecommendationRun(
        query=query,
        model=active_model,
        requested_model=requested_label,
        fallback=fell_back,
        results=results,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        catalogue_size=catalogue_size,
        candidate_count=len(candidates),
        note=note,
        personalized=bool(boosts),
    )


def compare(
    query: str,
    destinations: Iterable | None = None,
    top_k: int = 5,
    explain: bool = True,
) -> dict:
    """Run *both* models over the same query and quantify the disagreement.

    This is the operation the project's aim is built on: identical query,
    identical catalogue, two rankings, reported side by side. Overlap and
    rank-correlation figures make the difference concrete rather than
    impressionistic.
    """
    if destinations is None:
        from destinations.models import Destination

        destinations = Destination.objects.all()
    candidates = list(destinations)

    runs = {}
    for model in ALL_MODELS:
        if not is_available(model):
            continue
        runs[model] = recommend(
            query,
            candidates,
            top_k=top_k,
            model=model,
            explain=explain,
            allow_fallback=False,
        )

    agreement = {}
    if len(runs) == 2:
        semantic_ids = runs[MODEL_SEMANTIC].destination_ids
        tfidf_ids = runs[MODEL_TFIDF].destination_ids
        shared = set(semantic_ids) & set(tfidf_ids)
        union = set(semantic_ids) | set(tfidf_ids)
        agreement = {
            "top_k": top_k,
            "overlap_count": len(shared),
            "overlap_ratio": round(len(shared) / max(1, min(len(semantic_ids), len(tfidf_ids))), 4),
            "jaccard": round(len(shared) / max(1, len(union)), 4),
            "same_top_1": bool(
                semantic_ids and tfidf_ids and semantic_ids[0] == tfidf_ids[0]
            ),
            "kendall_tau": _kendall_tau_on_shared(semantic_ids, tfidf_ids),
            "only_semantic": [i for i in semantic_ids if i not in shared],
            "only_tfidf": [i for i in tfidf_ids if i not in shared],
        }

    return {"query": query, "runs": runs, "agreement": agreement}


def _kendall_tau_on_shared(a: list, b: list):
    """Kendall's tau over the items both rankings returned (None if < 2)."""
    shared = [item for item in a if item in b]
    if len(shared) < 2:
        return None
    rank_a = {item: i for i, item in enumerate(a)}
    rank_b = {item: i for i, item in enumerate(b)}
    concordant = discordant = 0
    for i in range(len(shared)):
        for j in range(i + 1, len(shared)):
            x, y = shared[i], shared[j]
            sign_a = rank_a[x] - rank_a[y]
            sign_b = rank_b[x] - rank_b[y]
            if sign_a * sign_b > 0:
                concordant += 1
            else:
                discordant += 1
    total = concordant + discordant
    if total == 0:
        return None
    return round((concordant - discordant) / total, 4)


# ---------------------------------------------------------------------------
# Personalisation (advanced objective: hybrid ranking)
# ---------------------------------------------------------------------------
_WORD_RE = re.compile(r"[a-z][a-z'-]+")


def build_personalization(user, weight: float = 0.08) -> dict:
    """Small additive boosts derived from what the user already likes.

    Two signals: the categories and tags of destinations they favourited, and
    the words in their stated travel preferences. The boost is deliberately
    modest — it should nudge ties, not overturn the content model, so the
    comparison between the two models stays interpretable.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return {}

    favorites = list(user.favorites.all())
    preference_words = set(_WORD_RE.findall((user.travel_preferences or "").lower()))
    if not favorites and not preference_words:
        return {}

    liked_categories = {d.category for d in favorites}
    liked_tags = {t.lower() for d in favorites for t in (d.tags or [])}
    favorite_ids = {d.id for d in favorites}

    from destinations.models import Destination

    boosts = {}
    for destination in Destination.objects.all():
        if destination.id in favorite_ids:
            continue  # don't re-recommend what they already saved
        tags = {t.lower() for t in (destination.tags or [])}
        signal = 0.0
        if destination.category in liked_categories:
            signal += 1.0
        signal += 1.5 * len(tags & liked_tags)
        signal += 1.0 * len(tags & preference_words)
        if signal:
            # Saturate so a heavily-tagged destination cannot dominate.
            boosts[destination.id] = round(weight * min(signal, 4.0) / 4.0, 6)
    return boosts
