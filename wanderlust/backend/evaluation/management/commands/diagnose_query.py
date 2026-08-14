"""Explain why each model ranked a query the way it did.

    python manage.py diagnose_query q18
    python manage.py diagnose_query q18 q23 q26
    python manage.py diagnose_query --all --losses-only
    python manage.py diagnose_query --text "somewhere quiet by the sea"

An aggregate metric says one model scored higher; it does not say why. This
reports, for a single query: what each model returned, where every labelled
destination actually ranked, and — for TF-IDF — which query terms survived the
vectoriser's vocabulary at all.

That last part is the useful one. A TF-IDF query vector can be entirely empty
when the query and the corpus share no vocabulary, in which case every document
scores zero and the "ranking" is just the underlying queryset order. That looks
identical to a bad ranking in a metrics table but is a completely different
failure, and it is only visible from here.
"""
from django.core.management.base import BaseCommand, CommandError

from destinations.models import Destination
from evaluation import queries as Q
from recommendations import engine


class Command(BaseCommand):
    help = "Diagnose how each recommender handled a labelled query."

    def add_arguments(self, parser):
        parser.add_argument("query_ids", nargs="*", help="Query ids, e.g. q18 q23")
        parser.add_argument("--all", action="store_true", help="Every labelled query.")
        parser.add_argument(
            "--losses-only",
            action="store_true",
            help="Only queries where the semantic model scored lower than TF-IDF.",
        )
        parser.add_argument("--text", help="Diagnose ad-hoc text with no labels.")
        parser.add_argument("--top-k", type=int, default=6)

    def handle(self, *args, **options):
        if options["text"]:
            self._report({"id": "adhoc", "query": options["text"], "type": "ad-hoc",
                          "relevance": {}}, options["top_k"])
            return

        by_id = {q["id"]: q for q in Q.LABELLED_QUERIES}
        if options["all"] or options["losses_only"]:
            wanted = list(by_id)
        else:
            wanted = options["query_ids"]
        if not wanted:
            raise CommandError(
                "Give one or more query ids, or --all, or --text. "
                f"Known ids: {', '.join(sorted(by_id))}"
            )

        unknown = [q for q in wanted if q not in by_id]
        if unknown:
            raise CommandError(f"Unknown query id(s): {', '.join(unknown)}")

        for qid in sorted(wanted):
            spec = by_id[qid]
            if options["losses_only"] and not self._semantic_lost(spec):
                continue
            self._report(spec, options["top_k"])

    def _semantic_lost(self, spec):
        from evaluation import metrics

        scores = {}
        for model in engine.ALL_MODELS:
            if not engine.is_available(model):
                return False
            run = engine.recommend(spec["query"], Destination.objects.all(), top_k=10,
                                   model=model, explain=False, allow_fallback=False)
            relevance = self._relevance_by_id(spec)
            scores[model] = metrics.ndcg_at_k(run.destination_ids, relevance, 5)
        return scores[engine.MODEL_SEMANTIC] < scores[engine.MODEL_TFIDF]

    def _relevance_by_id(self, spec):
        name_to_id = {d.name: d.id for d in Destination.objects.all()}
        return {name_to_id[n]: g for n, g in spec["relevance"].items() if n in name_to_id}

    def _report(self, spec, top_k):
        rule = "=" * 78
        self.stdout.write("")
        self.stdout.write(rule)
        self.stdout.write(f"  {spec['id']}  [{spec['type']}]")
        self.stdout.write(f"  \"{spec['query']}\"")
        if spec["relevance"]:
            graded = sorted(spec["relevance"].items(), key=lambda kv: -kv[1])
            self.stdout.write(
                "  labelled: " + ", ".join(f"{n} ({g})" for n, g in graded)
            )
        self.stdout.write(rule)

        catalogue = list(Destination.objects.all())

        for model in engine.ALL_MODELS:
            if not engine.is_available(model):
                self.stdout.write(f"\n  --- {model}: unavailable ---")
                continue

            run = engine.recommend(spec["query"], catalogue, top_k=top_k,
                                   model=model, explain=True, allow_fallback=False)
            self.stdout.write(f"\n  --- {model} ({run.elapsed_ms}ms) ---")
            for r in run.results:
                grade = spec["relevance"].get(r.destination.name, 0)
                mark = f"  <== relevant ({grade})" if grade else ""
                self.stdout.write(
                    f"    {r.rank}. {r.destination.name:<28} {r.score:.4f}{mark}"
                )
                if r.explanation:
                    self.stdout.write(f"       {r.explanation}")

            if spec["relevance"]:
                full = engine.recommend(spec["query"], catalogue, top_k=len(catalogue),
                                        model=model, explain=False, allow_fallback=False)
                where = [
                    (r.rank, r.destination.name, r.score)
                    for r in full.results
                    if r.destination.name in spec["relevance"]
                ]
                self.stdout.write(
                    "    rank of each labelled item: "
                    + ", ".join(f"{n} #{rk} ({s:.3f})" for rk, n, s in sorted(where))
                )

        self._tfidf_vocabulary_report(spec["query"])

    def _tfidf_vocabulary_report(self, query):
        """Which of the query's terms the TF-IDF vocabulary actually contains."""
        if not engine.is_available(engine.MODEL_TFIDF):
            return
        engine._build_tfidf_index()
        vectorizer = engine._tfidf_state["vectorizer"]
        if vectorizer is None:
            return

        names = engine._tfidf_state["feature_names"]
        vector = vectorizer.transform([query])
        used = sorted(
            ((vector[0, c], str(names[c])) for c in vector.nonzero()[1]), reverse=True
        )
        produced = vectorizer.build_analyzer()(query)
        missing = sorted({t for t in produced if t not in set(names)})

        self.stdout.write("")
        self.stdout.write(f"    TF-IDF usable terms : {[t for _, t in used] or 'NONE'}")
        self.stdout.write(f"    not in vocabulary   : {missing}")
        if not used:
            self.stdout.write(
                self.style.WARNING(
                    "    The query vector is empty: every destination scores 0.0, so the "
                    "ordering is the queryset's, not a ranking. This is a retrieval "
                    "failure, not a poor ranking."
                )
            )
        self.stdout.write("")
