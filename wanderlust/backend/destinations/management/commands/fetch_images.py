"""Fetch a real photo for each destination from Wikipedia.

    python manage.py fetch_images                # fill in destinations with no image
    python manage.py fetch_images --force        # refresh every image
    python manage.py fetch_images --write-back   # also update the JSON data file

Wikipedia's REST summary endpoint returns the article's lead image, which is
hosted on Wikimedia Commons under a free licence. We store the image URL and
the article title as attribution, which keeps the third-party-content licensing
issue raised in the report's ethical analysis on the right side of the line.

No API key is needed. If the endpoint is unreachable the command reports the
failures and leaves the existing values alone.
"""
import json
import time
from pathlib import Path
from urllib.parse import quote

import requests
from django.core.management.base import BaseCommand

from destinations.models import Destination

SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "destinations.json"

# Wikimedia asks that automated clients identify themselves.
HEADERS = {
    "User-Agent": "WanderlustFYP/1.0 (university final-year project; educational use)",
    "Accept": "application/json",
}


class Command(BaseCommand):
    help = "Populate destination image URLs from Wikipedia article lead images."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-fetch images even for destinations that already have one.",
        )
        parser.add_argument(
            "--write-back",
            action="store_true",
            help="Write the resolved URLs back into the JSON catalogue.",
        )
        parser.add_argument(
            "--width",
            type=int,
            default=1000,
            help="Preferred thumbnail width in pixels (default 1000).",
        )

    def handle(self, *args, **options):
        queryset = Destination.objects.exclude(wikipedia_title="")
        if not options["force"]:
            queryset = queryset.filter(image_url="")

        destinations = list(queryset)
        if not destinations:
            self.stdout.write("Nothing to fetch — every destination already has an image.")
            return

        resolved, failed = {}, []
        for destination in destinations:
            url, attribution = self._fetch_with_retry(
                destination.wikipedia_title, options["width"]
            )
            if url:
                destination.image_url = url
                destination.image_attribution = attribution
                resolved[destination.name] = url
                self.stdout.write(f"  OK   {destination.name}")
            else:
                failed.append(destination.name)
                self.stdout.write(self.style.WARNING(f"  MISS {destination.name}"))
            time.sleep(0.1)  # be polite to the API

        updated = [d for d in destinations if d.name in resolved]
        if updated:
            Destination.objects.bulk_update(
                updated, ["image_url", "image_attribution"]
            )

        self.stdout.write(
            self.style.SUCCESS(f"Resolved {len(resolved)} image(s).")
        )
        if failed:
            self.stdout.write(
                self.style.WARNING(f"No image found for: {', '.join(failed)}")
            )

        if options["write_back"] and resolved:
            self._write_back(resolved)

    def _fetch_with_retry(self, title, width, attempts=4):
        """Fetch with exponential backoff, since the API rate-limits bursts."""
        delay = 1.0
        for attempt in range(1, attempts + 1):
            url, attribution, retryable = self._fetch(title, width)
            if url or not retryable:
                return url, attribution
            if attempt < attempts:
                time.sleep(delay)
                delay *= 2
        return None, ""

    def _fetch(self, title, width):
        """Return (image_url, attribution, retryable) for a Wikipedia article."""
        try:
            response = requests.get(
                SUMMARY_URL.format(title=quote(title.replace(" ", "_"))),
                headers=HEADERS,
                timeout=15,
            )
            if response.status_code in (429, 502, 503, 504):
                return None, "", True
            response.raise_for_status()
            data = response.json()
        except requests.Timeout:
            return None, "", True
        except (requests.RequestException, ValueError) as exc:
            self.stderr.write(f"    {title}: {exc}")
            return None, "", False

        thumbnail = data.get("thumbnail") or {}
        original = data.get("originalimage") or {}
        url = thumbnail.get("source") or original.get("source")
        if not url:
            return None, "", False

        # Some articles lead with a locator map or coat of arms rather than a
        # photograph; an SVG is always one of those, so reject it.
        if url.lower().endswith(".svg") or ".svg/" in url.lower():
            return None, "", False

        # Commons thumbnails embed their width in the path; asking for a larger
        # one avoids a blurry image on a high-DPI phone screen.
        if thumbnail.get("source") and thumbnail.get("width"):
            url = url.replace(f"{thumbnail['width']}px-", f"{width}px-")

        page = (data.get("content_urls", {}).get("desktop", {}) or {}).get("page", "")
        attribution = f"Photo via Wikimedia Commons — {data.get('title', title)}"
        if page:
            attribution += f" ({page})"
        return url, attribution[:255], False

    def _write_back(self, resolved):
        """Persist resolved URLs into the JSON catalogue so a fresh clone has them."""
        try:
            records = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.stderr.write(f"Could not update {DATA_FILE}: {exc}")
            return

        changed = 0
        for record in records:
            url = resolved.get(record["name"])
            if url and record.get("image_url") != url:
                record["image_url"] = url
                changed += 1

        DATA_FILE.write_text(
            json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        self.stdout.write(
            self.style.SUCCESS(f"Wrote {changed} image URL(s) back to {DATA_FILE.name}.")
        )
