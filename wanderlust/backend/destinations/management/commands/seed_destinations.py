"""Load the destination catalogue from destinations/data/destinations.json.

    python manage.py seed_destinations                # load / refresh the catalogue
    python manage.py seed_destinations --embed        # also cache semantic embeddings
    python manage.py seed_destinations --recompute    # re-embed everything from scratch
    python manage.py seed_destinations --prune        # delete rows no longer in the file

The catalogue lives in a JSON data file rather than in Python so it can be
extended, reviewed and cited without touching application code.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from destinations.models import Destination
from recommendations import engine

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "destinations.json"

# Keys in the JSON that are not model fields.
NON_FIELD_KEYS = {"wikipedia"}


class Command(BaseCommand):
    help = "Seed the destination catalogue from the bundled JSON data file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(DATA_FILE),
            help="Alternative JSON catalogue to load.",
        )
        parser.add_argument(
            "--embed",
            action="store_true",
            help="Cache semantic embeddings for every destination after loading.",
        )
        parser.add_argument(
            "--recompute",
            action="store_true",
            help="Recompute every embedding, even ones already cached.",
        )
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Delete destinations that are not present in the data file.",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise CommandError(f"Could not read {path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise CommandError(f"{path} is not valid JSON: {exc}") from exc

        valid_categories = {value for value, _ in Destination.CATEGORY_CHOICES}
        created = updated = 0
        seen = []

        for record in records:
            fields = {k: v for k, v in record.items() if k not in NON_FIELD_KEYS}
            fields["wikipedia_title"] = record.get("wikipedia", "")

            if fields["category"] not in valid_categories:
                raise CommandError(
                    f"{fields['name']}: unknown category '{fields['category']}'. "
                    f"Valid categories: {', '.join(sorted(valid_categories))}"
                )

            # Never wipe an image URL that fetch_images already resolved.
            if not fields.get("image_url"):
                fields.pop("image_url", None)

            obj, was_created = Destination.objects.update_or_create(
                name=fields["name"], country=fields["country"], defaults=fields
            )
            seen.append(obj.pk)
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Catalogue loaded from {path.name}: "
                f"{created} created, {updated} updated, {len(records)} total."
            )
        )

        if options["prune"]:
            removed, _ = Destination.objects.exclude(pk__in=seen).delete()
            if removed:
                self.stdout.write(self.style.WARNING(f"Pruned {removed} old row(s)."))

        missing_images = Destination.objects.filter(image_url="").count()
        if missing_images:
            self.stdout.write(
                f"{missing_images} destination(s) have no image. "
                "Run `python manage.py fetch_images` to pull real photos from Wikipedia."
            )

        # Embeddings are only meaningful for the semantic backend; the TF-IDF
        # baseline fits its own index over the live catalogue at query time.
        engine.reset_caches()
        if options["embed"] or options["recompute"]:
            if not engine.is_available(engine.MODEL_SEMANTIC):
                models = engine.available_models()
                self.stdout.write(
                    self.style.WARNING(
                        "Semantic model unavailable, skipping embeddings: "
                        f"{models[engine.MODEL_SEMANTIC]['error']}"
                    )
                )
                return
            self.stdout.write("Computing embeddings...")
            count = engine.ensure_embeddings(
                Destination.objects.all(), recompute=options["recompute"]
            )
            self.stdout.write(
                self.style.SUCCESS(f"Embeddings ready ({count} computed).")
            )
        else:
            self.stdout.write(
                "Embeddings not computed. Pass --embed to cache them now "
                "(otherwise the first recommendation request will do it)."
            )
