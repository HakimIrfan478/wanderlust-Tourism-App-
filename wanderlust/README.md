# Wanderlust

A full-stack tourism management app built around one question:

> **When a user describes a trip in their own words, does a transformer-based
> semantic recommender retrieve more relevant destinations than a classical
> TF-IDF keyword baseline — and is the extra cost worth it?**

The app is a Django REST Framework API and a React Native (Expo) client. Both
recommenders are first-class and explicitly selectable, every response records
which model produced it, and an offline evaluation over a labelled query set
measures them against each other with standard ranking metrics.

---

## The result

Over 48 destinations and 26 labelled natural-language queries:

| Metric | Semantic (MiniLM) | TF-IDF | Difference |
|---|---|---|---|
| precision@1 | 0.885 | 0.885 | 0.000 |
| precision@5 | 0.592 | 0.523 | **+0.069** |
| nDCG@1 | 0.731 | 0.797 | −0.066 |
| nDCG@5 | 0.670 | 0.649 | +0.021 |
| nDCG@10 | 0.735 | 0.674 | **+0.061** |
| MRR | 0.900 | 0.892 | +0.007 |
| MAP | 0.585 | 0.517 | **+0.068** |
| mean latency | 16.6 ms | 4.9 ms | **3.4× slower** |

**Overall the two models are close** — nDCG@5 differs by +0.021 in the
transformer's favour, with a paired *t* of 0.41 and Cohen's *d* of 0.08. On its
own that says the transformer does not earn its complexity.

**The breakdown is where the answer actually lives.** Splitting the query set by
type:

| nDCG@5 | Semantic | TF-IDF | Difference |
|---|---|---|---|
| **lexical** queries (18) — reuse catalogue vocabulary | 0.745 | **0.798** | −0.053 |
| **paraphrase** queries (8) — same intent, different words | **0.503** | 0.315 | **+0.188** |

The keyword baseline is *better* when the user happens to use the catalogue's
own words, and it is three times faster. The transformer's advantage is
confined to paraphrase queries — where it is worth roughly 60% relative
improvement, because TF-IDF has nothing to match on.

So the honest answer is conditional rather than a clean win, and the aggregate
average hides it: semantic wins 11 queries and loses 15, but wins by larger
margins than it loses by. Reproduce it with `python manage.py run_evaluation`.

---

## Quick start

Two terminals. **Terminal 1 — backend:**

```bash
cd backend && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt && python manage.py migrate && python manage.py seed_destinations --embed && python manage.py runserver 0.0.0.0:8000
```

On macOS/Linux the activate line is `source .venv/bin/activate`.

**Terminal 2 — the app:**

```bash
cd frontend && npm install && npm start
```

Scan the QR code with Expo Go, or press `a` for an Android emulator. The app
finds the API automatically from the Metro host, so no IP editing is needed on
a real device — see [Connecting the app](#connecting-the-app) if it cannot.

Nothing here needs a database server or an API key. `USE_SQLITE=1` is the
default, and the two external APIs are keyless.

> Android and iOS are the supported targets, and both bundle and run.
> `npm run web` is included for convenience but is not part of the deliverable
> and has not been verified.

---

## What is in the box

**Backend** (`backend/`, Django 5 + DRF + SimpleJWT)

| App | Responsibility |
|---|---|
| `accounts` | Custom user with travel preferences, JWT auth, favourites |
| `destinations` | Catalogue of 48 destinations, reviews, filters, facets |
| `recommendations` | Both recommenders, model selection, comparison, explanations |
| `evaluation` | Labelled query set, ranking metrics, the experiment runner |
| `integrations` | Server-side weather and country facts with caching |

**Frontend** (`frontend/`, Expo SDK 51 + React Navigation)

| Screen | What it does |
|---|---|
| Login / Register | JWT auth with token refresh |
| Discover | Browse, search, filter by category, sort, save favourites |
| Recommend | Free-text query with a **model switch** — flip between the two recommenders and watch the results change |
| **Model Lab** | *Head to head*: one query, both models, side by side with overlap stats. *Benchmark*: the offline evaluation charted in-app |
| Destination detail | Live weather, country facts, reviews, favourite toggle |
| Profile | Travel preferences that feed the recommender, saved places |

---

## The two recommenders

Both live in [`backend/recommendations/engine.py`](backend/recommendations/engine.py)
and are independently loadable in the same process.

**`semantic`** — a `sentence-transformers` bi-encoder (`all-MiniLM-L6-v2`).
Query and destination text are mapped into a shared 384-dimension space and
ranked by cosine similarity, so "somewhere peaceful by the sea" matches a
description that never uses those words. Destination vectors are cached in the
database and invalidated when either the model or the destination's text
changes.

**`tfidf`** — scikit-learn TF-IDF (1–2 grams, sublinear tf) with cosine
similarity. The classical content-based method, and the control condition.

Three design points that make the comparison trustworthy:

1. **Both are always fitted over the full catalogue**, even when the caller
   filters to one category, so a score means the same thing in every request.
2. **Every response names the model that produced it**, plus whether a fallback
   occurred. A ranking whose provenance is ambiguous is worthless to the
   experiment.
3. **Fallback is visible, never silent.** Ask for `semantic` on a machine
   without torch and you get TF-IDF results *labelled as TF-IDF*, with a note
   explaining why — not TF-IDF results wearing the transformer's name.

Each result also carries an **explanation**: for the semantic model, the
destination's own tags that sit closest to the query; for TF-IDF, the shared
keywords that actually drove the score.

### Running without torch

`sentence-transformers` pulls in a large torch install. If it will not install:

```bash
pip install -r requirements-ci.txt
```

then set `DISABLE_SEMANTIC_MODEL=1`. The app runs unchanged, the TF-IDF
baseline serves every request, and `/api/recommendations/models/` reports the
semantic model as unavailable with the reason. This is the path CI uses.

---

## The evaluation

The experiment lives in [`backend/evaluation/`](backend/evaluation/).

- **[`queries.py`](backend/evaluation/queries.py)** — 26 natural-language
  queries with 155 graded relevance judgements (3 = ideal, 2 = relevant,
  1 = marginal, 0 = not relevant). Each query is tagged `lexical` or
  `paraphrase`, which is what makes the breakdown above possible.
- **[`metrics.py`](backend/evaluation/metrics.py)** — precision@k, recall@k,
  nDCG@k (exponential gain), MRR, MAP, and a paired per-query comparison.
  Implemented directly rather than imported, so the definitions used in the
  report are visible and checkable.
- **[`runner.py`](backend/evaluation/runner.py)** — runs the query set through
  each model and aligns the results for a paired comparison.

```bash
python manage.py run_evaluation             # run both, print and save
python manage.py run_evaluation --validate  # check labels against the catalogue
python manage.py run_evaluation --models tfidf --k 1 3 5
```

Results are written to `backend/evaluation_results/` as `results.json` (full
per-query detail) and `results.csv` (one row per query per model, for the
report appendix), plus timestamped copies so earlier runs are not overwritten.

### Limitations, stated plainly

- The relevance grades are **single-annotator judgements written by the project
  author**. No inter-annotator agreement can be computed, so differences are
  indicative, not conclusive.
- 26 queries is a small sample. The paired *t* and Cohen's *d* are reported as
  descriptive effect sizes, not as significance tests.
- The destination descriptions were also written by the author, so the
  lexical/paraphrase split is a designed contrast rather than a natural one.
- `all-MiniLM-L6-v2` is a compact 2020 model. It is a reasonable
  mobile-scale choice; it is not "state of the art".

The labelling protocol and these limitations are also served by the API at
`/api/evaluation/queries/`, so they travel with the data.

---

## API reference

Visit `http://localhost:8000/` for a self-describing index. DRF's browsable API
works in a browser when logged into `/admin/`.

### Auth
| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/register/` | Enforces Django's password validators |
| POST | `/api/auth/token/` | Returns `access` + `refresh` |
| POST | `/api/auth/token/refresh/` | |
| GET PATCH | `/api/auth/me/` | Profile and travel preferences |
| GET | `/api/auth/favorites/` | Saved destinations, in full |
| POST | `/api/auth/favorites/<id>/` | Toggle |

### Destinations
| Method | Path | Notes |
|---|---|---|
| GET | `/api/destinations/` | `?category= &country= &search= &tag= &max_cost= &sort= &ids=` |
| GET | `/api/destinations/<id>/` | Includes reviews |
| GET | `/api/destinations/facets/` | Counts per category and country |
| GET POST | `/api/destinations/<id>/reviews/` | One review per user per destination |
| GET PATCH DELETE | `/api/destinations/reviews/<id>/` | Your own reviews only |

### Recommendations
| Method | Path | Notes |
|---|---|---|
| GET POST | `/api/recommendations/` | `query`, `model`, `category`, `country`, `max_cost`, `top_k`, `personalize`, `explain` |
| GET POST | `/api/recommendations/compare/` | Both models, one query, plus overlap / Kendall's τ |
| GET | `/api/recommendations/models/` | Availability and why, per backend |

```bash
curl -X POST http://localhost:8000/api/recommendations/ -H "Content-Type: application/json" -d "{\"query\":\"somewhere peaceful by the sea\",\"model\":\"semantic\",\"top_k\":5}"
```

### Evaluation
| Method | Path | Notes |
|---|---|---|
| GET | `/api/evaluation/` | Saved results; `?full=1` for per-query detail, `?refresh=1` to recompute |
| GET | `/api/evaluation/queries/` | The labelled query set and its protocol |

### Integrations
| Method | Path | Notes |
|---|---|---|
| GET | `/api/integrations/weather/` | `?destination=<id>` or `?lat=&lon=` |
| GET | `/api/integrations/country/` | `?destination=<id>` or `?code=PT` |
| GET | `/api/integrations/context/` | Both in one round trip |

---

## External data

Both providers are called **server-side**, cached, and degrade gracefully: a
provider problem returns HTTP 200 with `"available": false` and a reason, so the
destination screen renders without that block instead of failing.

**Weather — [Open-Meteo](https://open-meteo.com/).** Free, keyless, cached 30
minutes.

**Country facts — [countries.dev](https://countries.dev).** Free, keyless,
cached 24 hours.

> **A note on REST Countries.** This project originally used REST Countries
> v3.1, as cited in the interim report. During development that API was
> deprecated: `/v3.1` now 301-redirects to a stub returning
> `{"success": false, ...}` with a deprecation message, and the replacement v5
> API requires a signed-up `Authorization: Bearer` key. This is exactly risk #4
> in the report's register — *"an external API has downtime, rate limits, or
> changes its terms"* — arriving in practice.
>
> The provider is therefore pluggable rather than hard-coded. `countries.dev`
> is the keyless default; set `RESTCOUNTRIES_API_KEY` and REST Countries v5 is
> used instead, with no code change. Both are normalised to one response shape,
> and `test_deprecated_provider_envelope_is_not_treated_as_success` pins the
> specific failure mode that a naive client would report as success.

**Destination photos** come from Wikipedia article lead images via
`python manage.py fetch_images`, which stores the URL and an attribution string
alongside each destination.

---

## Tests and CI

```bash
cd backend
python manage.py test                              # 139 tests
DISABLE_SEMANTIC_MODEL=1 python manage.py test     # same suite, no torch
cd ../frontend && npm run check                    # parse every source file
```

Coverage: JWT auth and registration validation, catalogue filters and ordering,
reviews and their permissions, favourites, both recommender backends, model
resolution and fallback, personalisation, ranking metrics against hand-computed
values, the evaluation runner, and both integrations with mocked providers
including outage and deprecation paths.

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the backend suite on
Python 3.11 and 3.12 without torch, checks for missing migrations, validates the
labelled query set against the catalogue, runs the TF-IDF evaluation, and
parses every frontend source file.

---

## Configuration

Everything is read from `backend/.env` (see `.env.example`); real environment
variables always win. The loader is dependency-free — there is no
`django-environ` to install.

| Variable | Default | Purpose |
|---|---|---|
| `USE_SQLITE` | `1` | `0` switches to PostgreSQL using the `DB_*` settings |
| `EMBEDDING_MODEL_NAME` | `all-MiniLM-L6-v2` | Sentence-transformer to load |
| `RECOMMENDER_DEFAULT_MODEL` | `semantic` | What an unqualified request gets |
| `DISABLE_SEMANTIC_MODEL` | `0` | `1` skips loading the transformer entirely |
| `HF_OFFLINE_ONLY` | `0` | `1` loads only from the local HuggingFace cache |
| `COUNTRY_API_PROVIDER` | `auto` | `countries.dev` or `restcountries` |
| `RESTCOUNTRIES_API_KEY` | — | Setting this selects REST Countries v5 |
| `WEATHER_CACHE_SECONDS` | `1800` | |
| `COUNTRY_CACHE_SECONDS` | `86400` | |

### Using PostgreSQL

Set `USE_SQLITE=0` and fill in `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`,
`DB_PORT`, then `python manage.py migrate`. `psycopg2-binary` is already in
`requirements.txt`.

---

## Connecting the app

`frontend/src/config.js` resolves the API base URL in this order:

1. `EXPO_PUBLIC_API_URL`, if set.
2. The host Metro is served from — usually the same machine running Django, so
   a physical device on the same Wi-Fi works with no edit.
3. `10.0.2.2:8000` on Android emulators, `127.0.0.1:8000` otherwise.

Start Django with `runserver 0.0.0.0:8000` so it accepts connections from the
phone rather than only from localhost. The Profile screen shows which URL the
app is actually using, which is the fastest way to diagnose a connection
problem. To override:

```bash
EXPO_PUBLIC_API_URL=http://192.168.1.42:8000 npm start
```

---

## Management commands

```bash
python manage.py seed_destinations            # load the catalogue
python manage.py seed_destinations --embed    # and cache embeddings
python manage.py seed_destinations --prune    # drop rows no longer in the data file
python manage.py fetch_images                 # pull photos from Wikipedia
python manage.py fetch_images --write-back    # and save the URLs into the data file
python manage.py run_evaluation               # the experiment
python manage.py createsuperuser              # then visit /admin/
```

The catalogue is data, not code:
[`backend/destinations/data/destinations.json`](backend/destinations/data/destinations.json).
Adding a destination means adding an entry and re-running `seed_destinations`.

---

## Project structure

```
backend/
  wanderlust/settings.py          .env loader, DRF/JWT, cache, model config
  accounts/                       custom user, JWT, favourites
  destinations/
    data/destinations.json        the 48-destination catalogue
    management/commands/          seed_destinations, fetch_images
  recommendations/
    engine.py                     both recommenders + comparison
    views.py                      recommend / compare / models endpoints
  evaluation/
    queries.py                    labelled query set + protocol
    metrics.py                    precision, recall, nDCG, MRR, MAP
    runner.py                     the experiment
    management/commands/          run_evaluation
  integrations/                   Open-Meteo, country facts
  evaluation_results/             results.json / results.csv
frontend/
  src/screens/ResearchScreen.js   Model Lab: head-to-head + benchmark
  src/screens/RecommendScreen.js  free-text query with model switch
  src/api/                        axios client with JWT refresh
.github/workflows/ci.yml
```
