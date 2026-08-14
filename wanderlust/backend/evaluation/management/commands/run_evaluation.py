"""Run the semantic-versus-TF-IDF comparison and write the results.

    python manage.py run_evaluation                    # run both, print + save
    python manage.py run_evaluation --models tfidf     # one model only
    python manage.py run_evaluation --k 1 3 5          # different cutoffs
    python manage.py run_evaluation --validate         # check labels, run nothing
    python manage.py run_evaluation --no-save          # print only

Writes ``results.json`` (full detail) and ``results.csv`` (one row per
query per model) to EVALUATION_OUTPUT_DIR, plus a timestamped copy so earlier
runs are not overwritten. This is the evidence the report's evaluation
chapter is written from.
"""
import csv
import json
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from evaluation import queries, runner
from recommendations import engine


class Command(BaseCommand):
    help = "Compare the semantic and TF-IDF recommenders on the labelled query set."

    def add_arguments(self, parser):
        parser.add_argument(
            "--models",
            nargs="+",
            choices=list(engine.ALL_MODELS),
            help="Which models to evaluate (default: every available model).",
        )
        parser.add_argument(
            "--k",
            nargs="+",
            type=int,
            default=list(runner.DEFAULT_K_VALUES),
            help="Cutoffs for precision/recall/nDCG (default: 1 3 5 10).",
        )
        parser.add_argument(
            "--threshold",
            type=int,
            default=1,
            help="Minimum grade counted as relevant by the binary metrics.",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Directory for results files (default: EVALUATION_OUTPUT_DIR).",
        )
        parser.add_argument(
            "--no-save", action="store_true", help="Print results without saving."
        )
        parser.add_argument(
            "--validate",
            action="store_true",
            help="Only check the query labels against the catalogue, then exit.",
        )

    def handle(self, *args, **options):
        if options["validate"]:
            return self._validate()

        try:
            results = runner.run_evaluation(
                models=options["models"],
                k_values=tuple(options["k"]),
                binary_threshold=options["threshold"],
            )
        except runner.EvaluationError as exc:
            raise CommandError(str(exc)) from exc

        self._print_report(results, options["k"])

        if not options["no_save"]:
            directory = (
                options["output"]
                if options["output"]
                else settings.EVALUATION_OUTPUT_DIR
            )
            self._save(results, directory)

    # -- output ------------------------------------------------------------
    def _validate(self):
        missing = queries.validate_against_catalogue()
        info = queries.summary()
        self.stdout.write(
            f"Query set: {info['query_count']} queries, "
            f"{info['relevance_judgements']} relevance judgements "
            f"({info['mean_judged_per_query']} per query)."
        )
        for query_type, count in sorted(info["queries_by_type"].items()):
            self.stdout.write(f"  {query_type}: {count}")
        if missing:
            raise CommandError(
                "Labelled destinations missing from the catalogue: "
                + ", ".join(missing)
            )
        self.stdout.write(self.style.SUCCESS("All labelled destinations exist."))

    def _print_report(self, results, k_values):
        meta = results["meta"]
        rule = "=" * 78

        self.stdout.write("")
        self.stdout.write(rule)
        self.stdout.write("  WANDERLUST RECOMMENDER EVALUATION")
        self.stdout.write(rule)
        self.stdout.write(
            f"  catalogue      : {meta['catalogue_size']} destinations"
        )
        self.stdout.write(
            f"  query set      : {meta['query_set']['query_count']} labelled queries"
        )
        self.stdout.write(f"  models         : {', '.join(meta['models_evaluated'])}")
        if meta["models_unavailable"]:
            for model, error in meta["models_unavailable"].items():
                self.stdout.write(self.style.WARNING(f"  unavailable    : {model} — {error}"))
        self.stdout.write("")

        metric_names = (
            [f"precision@{k}" for k in k_values]
            + [f"ndcg@{k}" for k in k_values]
            + ["mrr", "map"]
        )
        models = list(results["models"])

        header = f"  {'metric':<16}" + "".join(f"{m:>14}" for m in models)
        if len(models) == 2:
            header += f"{'difference':>14}"
        self.stdout.write(header)
        self.stdout.write("  " + "-" * (len(header) - 2))

        for name in metric_names:
            line = f"  {name:<16}"
            values = []
            for model in models:
                value = results["models"][model]["overall"][name]
                values.append(value)
                line += f"{value:>14.4f}"
            if len(values) == 2:
                delta = values[0] - values[1]
                line += f"{delta:>+14.4f}"
            self.stdout.write(line)

        self.stdout.write("")
        line = f"  {'mean latency ms':<16}"
        for model in models:
            line += f"{results['models'][model]['latency_ms']['mean']:>14.2f}"
        self.stdout.write(line)

        # Breakdown by query type: the interesting part of the result.
        self.stdout.write("")
        self.stdout.write("  nDCG@5 by query type")
        self.stdout.write("  " + "-" * 60)
        types = sorted(
            {t for m in models for t in results["models"][m]["by_query_type"]}
        )
        for query_type in types:
            line = f"  {query_type:<16}"
            for model in models:
                bucket = results["models"][model]["by_query_type"].get(query_type)
                line += f"{bucket['ndcg@5']:>14.4f}" if bucket else f"{'-':>14}"
            self.stdout.write(line)

        comparison = results["comparison"]
        if comparison.get("available"):
            headline = comparison["headline"]
            self.stdout.write("")
            self.stdout.write(rule)
            self.stdout.write("  RESULT")
            self.stdout.write(rule)
            self.stdout.write(f"  {headline['verdict']}")
            paired = comparison["per_metric"].get(runner.HEADLINE_METRIC, {})
            if paired.get("paired_t") is not None:
                self.stdout.write(
                    f"  paired t = {paired['paired_t']}, "
                    f"Cohen's d = {paired['cohens_d']}, n = {paired['n_queries']} "
                    "(descriptive only — single annotator)"
                )
            self.stdout.write(
                f"  semantic is {comparison['latency']['semantic_slowdown_x']}x "
                f"the latency of the TF-IDF baseline "
                f"({comparison['latency']['semantic_mean_ms']}ms vs "
                f"{comparison['latency']['tfidf_mean_ms']}ms per query)."
            )
            self.stdout.write(rule)
        self.stdout.write("")

    def _save(self, results, directory):
        from pathlib import Path

        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        for target in (directory / "results.json", directory / f"results-{stamp}.json"):
            target.write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )

        rows = runner.flatten_for_csv(results)
        if rows:
            for target in (directory / "results.csv", directory / f"results-{stamp}.csv"):
                with target.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)

        self.stdout.write(
            self.style.SUCCESS(
                f"  Saved results.json and results.csv to {directory} "
                f"(timestamped copies: *-{stamp}.*)"
            )
        )
        self.stdout.write("")
