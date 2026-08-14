"""Render the evaluation results as figures for the report.

    python manage.py make_figures

Reads evaluation_results/results.json and writes publication-quality PNGs to
evaluation_results/figures/. Regenerating them after a new evaluation run keeps
the report's figures and its numbers in step, which is hard to guarantee when
charts are drawn by hand in a spreadsheet.

Requires matplotlib (not in requirements.txt, since it is only needed for
report figures and nothing in the running application uses it):

    pip install matplotlib
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

SEMANTIC_COLOUR = "#0E7C7B"
TFIDF_COLOUR = "#B4652A"
GRID_COLOUR = "#D8E0E0"


class Command(BaseCommand):
    help = "Render evaluation results as report figures (requires matplotlib)."

    def add_arguments(self, parser):
        parser.add_argument("--dpi", type=int, default=200)
        parser.add_argument(
            "--results",
            default=None,
            help="Path to results.json (default: EVALUATION_OUTPUT_DIR/results.json)",
        )

    def handle(self, *args, **options):
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError as exc:
            raise CommandError(
                "matplotlib is required for this command: pip install matplotlib"
            ) from exc

        path = Path(options["results"] or settings.EVALUATION_OUTPUT_DIR / "results.json")
        try:
            results = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise CommandError(
                f"Could not read {path}. Run `python manage.py run_evaluation` first."
            ) from exc

        models = results.get("models", {})
        if "semantic" not in models or "tfidf" not in models:
            raise CommandError(
                "Both models must be present in the results to draw comparisons."
            )

        out = path.parent / "figures"
        out.mkdir(parents=True, exist_ok=True)
        dpi = options["dpi"]

        plt.rcParams.update(
            {
                "font.size": 10,
                "axes.edgecolor": "#5C6B6B",
                "axes.labelcolor": "#1B2A2A",
                "text.color": "#1B2A2A",
                "xtick.color": "#5C6B6B",
                "ytick.color": "#5C6B6B",
                "axes.spines.top": False,
                "axes.spines.right": False,
            }
        )

        written = []
        written.append(self._fig_ndcg(plt, models, out, dpi))
        written.append(self._fig_precision(plt, models, out, dpi))
        written.append(self._fig_by_type(plt, models, out, dpi))
        written.append(self._fig_scatter(plt, models, out, dpi))
        written.append(self._fig_per_query_diff(plt, models, out, dpi))
        written.append(self._fig_latency(plt, models, out, dpi))

        for name in written:
            self.stdout.write(self.style.SUCCESS(f"  wrote {name}"))
        self.stdout.write(f"\nFigures in {out}")

    # -- individual figures ------------------------------------------------
    def _bar_pair(self, plt, labels, semantic, tfidf, title, ylabel, path, dpi, ylim=None):
        import numpy as np

        x = np.arange(len(labels))
        width = 0.38
        fig, ax = plt.subplots(figsize=(7, 4))
        b1 = ax.bar(x - width / 2, semantic, width, label="Semantic (MiniLM)", color=SEMANTIC_COLOUR)
        b2 = ax.bar(x + width / 2, tfidf, width, label="TF-IDF baseline", color=TFIDF_COLOUR)
        for bars in (b1, b2):
            ax.bar_label(bars, fmt="%.3f", fontsize=7, padding=2)
        ax.set_xticks(x, labels)
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontweight="bold", pad=12)
        ax.set_ylim(0, ylim or max(max(semantic), max(tfidf)) * 1.20)
        ax.yaxis.grid(True, color=GRID_COLOUR, linewidth=0.8)
        ax.set_axisbelow(True)
        # Drop the legend further when tick labels wrap onto a second line,
        # otherwise it collides with them.
        offset = -0.22 if any("\n" in str(label) for label in labels) else -0.13
        ax.legend(
            frameon=False, ncols=2, loc="upper center", bbox_to_anchor=(0.5, offset)
        )
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return path.name

    def _fig_ndcg(self, plt, models, out, dpi):
        ks = [1, 3, 5, 10]
        return self._bar_pair(
            plt,
            [f"nDCG@{k}" for k in ks],
            [models["semantic"]["overall"][f"ndcg@{k}"] for k in ks],
            [models["tfidf"]["overall"][f"ndcg@{k}"] for k in ks],
            "Ranking quality across cut-offs",
            "nDCG",
            out / "fig1-ndcg.png",
            dpi,
            ylim=1.0,
        )

    def _fig_precision(self, plt, models, out, dpi):
        ks = [1, 3, 5, 10]
        return self._bar_pair(
            plt,
            [f"P@{k}" for k in ks],
            [models["semantic"]["overall"][f"precision@{k}"] for k in ks],
            [models["tfidf"]["overall"][f"precision@{k}"] for k in ks],
            "Precision across cut-offs",
            "Precision",
            out / "fig2-precision.png",
            dpi,
            ylim=1.0,
        )

    def _fig_by_type(self, plt, models, out, dpi):
        types = sorted(models["semantic"]["by_query_type"])
        labels = [
            f"{t}\n(n={models['semantic']['by_query_type'][t]['query_count']})" for t in types
        ]
        return self._bar_pair(
            plt,
            labels,
            [models["semantic"]["by_query_type"][t]["ndcg@5"] for t in types],
            [models["tfidf"]["by_query_type"][t]["ndcg@5"] for t in types],
            "nDCG@5 by query type — where the difference actually is",
            "nDCG@5",
            out / "fig3-by-query-type.png",
            dpi,
            ylim=1.0,
        )

    def _fig_scatter(self, plt, models, out, dpi):
        """Per-query scatter with a y=x line: shows spread, not just the mean."""
        tfidf = {q["query_id"]: q for q in models["tfidf"]["per_query"]}
        fig, ax = plt.subplots(figsize=(5.4, 5.4))
        for query_type, marker in (("lexical", "o"), ("paraphrase", "^")):
            xs, ys, ids = [], [], []
            for q in models["semantic"]["per_query"]:
                if q["type"] != query_type or q["query_id"] not in tfidf:
                    continue
                xs.append(tfidf[q["query_id"]]["scores"]["ndcg@5"])
                ys.append(q["scores"]["ndcg@5"])
                ids.append(q["query_id"])
            ax.scatter(
                xs, ys, marker=marker, s=52, label=f"{query_type} (n={len(xs)})",
                color=SEMANTIC_COLOUR if query_type == "paraphrase" else TFIDF_COLOUR,
                alpha=0.75, edgecolors="white", linewidths=0.8, zorder=3,
            )
            for x, y, qid in zip(xs, ys, ids):
                # Only label the outliers, or the chart becomes unreadable.
                if abs(y - x) > 0.2:
                    ax.annotate(qid, (x, y), fontsize=7, xytext=(4, 4),
                                textcoords="offset points", color="#5C6B6B")
        ax.plot([0, 1], [0, 1], "--", color="#5C6B6B", linewidth=1, zorder=1)
        ax.text(0.03, 0.95, "semantic better", fontsize=8, color="#5C6B6B", style="italic")
        ax.text(0.55, 0.04, "TF-IDF better", fontsize=8, color="#5C6B6B", style="italic")
        ax.set_xlabel("TF-IDF nDCG@5")
        ax.set_ylabel("Semantic nDCG@5")
        ax.set_title("Per-query comparison", fontweight="bold", pad=12)
        ax.set_xlim(-0.03, 1.03)
        ax.set_ylim(-0.03, 1.03)
        ax.grid(True, color=GRID_COLOUR, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.legend(frameon=False, loc="lower right", fontsize=8)
        fig.tight_layout()
        path = out / "fig4-per-query-scatter.png"
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return path.name

    def _fig_per_query_diff(self, plt, models, out, dpi):
        """Sorted per-query differences: makes the win/loss distribution visible."""
        tfidf = {q["query_id"]: q for q in models["tfidf"]["per_query"]}
        rows = []
        for q in models["semantic"]["per_query"]:
            if q["query_id"] not in tfidf:
                continue
            rows.append(
                (
                    q["query_id"],
                    q["type"],
                    q["scores"]["ndcg@5"] - tfidf[q["query_id"]]["scores"]["ndcg@5"],
                )
            )
        rows.sort(key=lambda r: r[2])

        fig, ax = plt.subplots(figsize=(7.5, 5))
        colours = [SEMANTIC_COLOUR if r[2] > 0 else TFIDF_COLOUR for r in rows]
        hatches = ["//" if r[1] == "paraphrase" else "" for r in rows]
        bars = ax.barh([r[0] for r in rows], [r[2] for r in rows], color=colours)
        for bar, hatch in zip(bars, hatches):
            bar.set_hatch(hatch)
            bar.set_edgecolor("white")
        ax.axvline(0, color="#5C6B6B", linewidth=1)
        ax.set_xlabel("nDCG@5 difference  (positive = semantic better)")
        ax.set_title("Per-query difference, sorted", fontweight="bold", pad=12)
        ax.xaxis.grid(True, color=GRID_COLOUR, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", labelsize=7)

        from matplotlib.patches import Patch

        ax.legend(
            handles=[
                Patch(facecolor=SEMANTIC_COLOUR, label="Semantic wins"),
                Patch(facecolor=TFIDF_COLOUR, label="TF-IDF wins"),
                Patch(facecolor="#9AA8A8", hatch="//", label="Paraphrase query"),
            ],
            frameon=False, fontsize=8, loc="lower right",
        )
        fig.tight_layout()
        path = out / "fig5-per-query-difference.png"
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return path.name

    def _fig_latency(self, plt, models, out, dpi):
        fig, ax = plt.subplots(figsize=(5, 3.4))
        values = [models["semantic"]["latency_ms"]["mean"], models["tfidf"]["latency_ms"]["mean"]]
        bars = ax.bar(
            ["Semantic\n(MiniLM)", "TF-IDF\nbaseline"], values,
            color=[SEMANTIC_COLOUR, TFIDF_COLOUR], width=0.55,
        )
        ax.bar_label(bars, fmt="%.2f ms", fontsize=9, padding=3)
        ax.set_ylabel("Mean query latency (ms)")
        ax.set_title(
            f"Retrieval cost — {values[0] / max(values[1], 0.001):.2f}× slower",
            fontweight="bold", pad=12,
        )
        ax.set_ylim(0, max(values) * 1.25)
        ax.yaxis.grid(True, color=GRID_COLOUR, linewidth=0.8)
        ax.set_axisbelow(True)
        fig.tight_layout()
        path = out / "fig6-latency.png"
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return path.name
