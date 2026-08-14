import logging
import os
import sys
import threading

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)

# Commands that must never pay for loading a 90MB transformer.
NON_SERVER_COMMANDS = {
    "migrate",
    "makemigrations",
    "test",
    "shell",
    "collectstatic",
    "createsuperuser",
    "check",
    "run_evaluation",
    "seed_destinations",
    "fetch_images",
    "showmigrations",
    "sqlmigrate",
    "flush",
    "dbshell",
}


class RecommendationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "recommendations"

    def ready(self):
        """Warm the semantic model in the background when a server starts.

        Loading the sentence-transformer takes around ten seconds. Paying that
        on the first user request pushes it past the mobile client's HTTP
        timeout, so the first person to open the app sees a failure on an
        otherwise healthy server. Warming it here moves the cost to startup,
        where nobody is waiting on it.

        The thread is a daemon so it never blocks shutdown, and failure is
        logged rather than raised — an unavailable model is a reported state,
        not a reason for the server to refuse to boot.
        """
        if not getattr(settings, "RECOMMENDER_WARMUP", True):
            return
        if getattr(settings, "DISABLE_SEMANTIC_MODEL", False):
            return

        command = sys.argv[1] if len(sys.argv) > 1 else ""
        if command in NON_SERVER_COMMANDS:
            return

        # `python -c ...`, `python script.py` and the REPL are not servers.
        # Warming there loads a 90MB model that the process will not use, and
        # a short-lived script can exit mid-load.
        entrypoint = sys.argv[0] if sys.argv else ""
        if entrypoint in ("", "-c") or entrypoint.endswith((".py",)) and not entrypoint.endswith("manage.py"):
            return

        # runserver's autoreloader calls ready() in both the watcher and the
        # worker. RUN_MAIN is set only in the worker, so this loads the model
        # once rather than twice. With --noreload the variable is absent.
        if command == "runserver" and "--noreload" not in sys.argv:
            if os.environ.get("RUN_MAIN") != "true":
                return

        def warm():
            from . import engine

            try:
                if engine.is_available(engine.MODEL_SEMANTIC):
                    logger.info("Semantic recommender warmed and ready.")
                else:
                    logger.info(
                        "Semantic recommender unavailable: %s",
                        engine.available_models()[engine.MODEL_SEMANTIC]["error"],
                    )
            except Exception as exc:  # never take the server down for this
                logger.warning("Recommender warm-up failed: %s", exc)

        threading.Thread(target=warm, name="recommender-warmup", daemon=True).start()
