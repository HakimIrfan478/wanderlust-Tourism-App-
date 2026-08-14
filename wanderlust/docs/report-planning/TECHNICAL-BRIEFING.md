# Technical briefing

**Reference material, not report text.** These are the facts, decisions and
mechanisms behind your artefact, so you can write chapters 4, 5 and 8 from
understanding rather than guesswork. Everything here is checkable against the
code — verify anything you intend to claim.

---

## 1. What the system is

A mobile tourism application whose purpose is to make one comparison possible:
the same natural-language query, the same catalogue, two different retrieval
models, measured with the same metrics.

| Layer | Technology | Lines |
|---|---|---|
| Client | React Native (Expo SDK 51), React Navigation | ~3,300 JS |
| API | Django 5 + Django REST Framework + SimpleJWT | ~5,900 Python |
| Retrieval | sentence-transformers (MiniLM) and scikit-learn TF-IDF | — |
| Storage | SQLite by default, PostgreSQL supported | 13 tables |
| External | Open-Meteo (weather), countries.dev (country facts) | keyless |

Five Django apps: `accounts`, `destinations`, `recommendations`, `evaluation`,
`integrations`.

---

## 2. Design decisions, and what was rejected

For each of these, the alternative matters as much as the choice — the mark
scheme rewards justification over description.

### 2.1 Two peer models, not primary-and-fallback

**Chosen:** both backends independently loadable and explicitly selectable in
the same process, with `model=semantic|tfidf` on every request.

**Rejected:** the original design, where MiniLM was primary and TF-IDF ran only
if MiniLM failed to load.

**Why it matters:** under the original design the two models could never run
against the same catalogue in the same session, so the comparison the project
exists to make was impossible to perform in code. This is Risk 1 from your
register, and it is the single most important change in the artefact.

### 2.2 Both models fit over the full catalogue, always

**Chosen:** when a request filters to one category, the filter restricts which
destinations are *scored*, not which are *indexed*.

**Rejected:** fitting TF-IDF over only the filtered subset.

**Why it matters:** TF-IDF weights a term by how rare it is across the corpus.
Refitting over a subset changes those weights, so "beach" would be common (and
therefore near-worthless) inside the beach category but rare across the whole
catalogue. The same destination would score differently depending on an
unrelated filter, and scores would not be comparable between requests. There
is a test that pins this: `test_filtered_candidates_are_scored_against_the_full_corpus`.

### 2.3 Fallback is always visible

**Chosen:** if a requested model is unavailable, the response is served by the
other model, **labelled as that other model**, with a `fallback: true` flag and
a note explaining why.

**Rejected:** silently substituting.

**Why it matters:** a ranking whose provenance is ambiguous is useless to a
comparison study. Silent substitution would let TF-IDF results be reported as
transformer results.

### 2.4 Embeddings cached with invalidation keys

**Chosen:** each destination stores its vector, the model name that produced
it, and a computation timestamp. A vector is stale if either the model name
differs or the destination's `updated_at` is newer.

**Rejected:** computing on every request (slow), or caching without keys
(silently wrong after a text edit or model change).

**Why it matters:** an evaluation run makes 26 queries against 48 destinations.
Without caching that is 1,248 encodes instead of 48.

### 2.5 Metrics implemented, not imported

**Chosen:** precision@k, recall@k, nDCG@k, MRR and MAP written directly and
unit-tested against hand-computed values.

**Rejected:** importing from a library.

**Why it matters:** these numbers go in your report. A subtly wrong metric
would invalidate every result, and you cannot defend a formula you did not
write. The tests assert against arithmetic done by hand, not against another
implementation.

### 2.6 Server-side external API calls

**Chosen:** the app calls your API; your API calls the providers.

**Rejected:** calling providers directly from the phone.

**Why it matters:** one place to handle failure, one cache shared by all users,
no provider contact details in the client, and the app never has to handle a
third-party outage itself.

---

## 3. The two retrieval models

### 3.1 Semantic (`all-MiniLM-L6-v2`)

Each destination's text — name, city, country, category, descriptions, tags,
season — is encoded into a 384-dimension vector. The query is encoded the same
way. Both are L2-normalised, so a dot product *is* the cosine similarity.
Ranking is by that similarity.

Explanation for each result: the destination's own tags, category and season
are re-encoded and the two or three closest to the query are reported. That is
why the app can say "semantically close to quiet beaches, beach, honeymoon".

### 3.2 TF-IDF baseline

scikit-learn `TfidfVectorizer` with English stop words, sublinear term
frequency, unigrams and bigrams, max 20,000 features. Cosine similarity against
the query vector.

Explanation: the query vector and document vector are multiplied elementwise
and the highest-weighted shared terms reported. That is why the app can say
"shares the keywords sea".

**Critical property, and the source of your best finding: there is no
stemming.** "cook" and "cooking" are different tokens. A query term that does
not appear verbatim in the corpus contributes nothing.

---

## 4. Worked examples — the mechanism behind your result

Reproduce any of these with:

```bash
python manage.py diagnose_query q18
python manage.py diagnose_query --all --losses-only
```

### 4.1 q18 — TF-IDF does not rank badly, it fails to rank at all

Query: *"I want to learn to cook the local dishes"*
Labelled relevant: Hoi An (3), Oaxaca (3), Kyoto (2), Marrakesh (2), Rome (1), Istanbul (1)

**TF-IDF usable query terms: none.** Every token the analyser produced —
`cook`, `dishes`, `learn`, `local`, `want`, and all bigrams — is absent from the
vocabulary built from the corpus. The catalogue says "cooking classes", not
"cook"; "cuisine" and "food", not "dishes".

Consequence: the query vector is entirely zero, so **every destination scores
exactly 0.0000**. The returned order is therefore not a ranking at all — it is
the underlying queryset order, which is alphabetical:

> Algarve, Amazon Rainforest, Amsterdam, Angkor Wat, Athens, Bali

The six relevant destinations sit at ranks 17, 20, 23, 28, 30 and 38 — exactly
their alphabetical positions. nDCG@5 = 0.000.

Semantic returns Oaxaca (grade 3) first, Hoi An (grade 3) second, Kyoto (2)
fourth. nDCG@5 = 0.871.

**Why this matters for your report:** in a metrics table, "0.000" looks like a
bad ranking. It is not. It is a total retrieval failure with a specific,
explainable cause — zero lexical overlap plus no stemming. This distinction is
the single most valuable observation available to you, and it is invisible
without inspecting the query vector.

### 4.2 q23 — the semantic model loses, and why

Query: *"somewhere very cheap for a long backpacking trip"*

Semantic returns Wadi Rum, La Fortuna, Kruger, Everest Base Camp, Dubai — it
locked onto the *trekking / camping / outdoors* direction of the sentence and
diluted "cheap". Its best labelled item, Phuket, is at rank 12. nDCG@5 = 0.000.

TF-IDF matched `cheap` and `long` literally: Phuket #1 (grade 2), Angkor Wat #3
(grade 2), El Nido #5 (grade 2). nDCG@5 = 0.326.

**Mechanism:** the operative constraint was a *literal attribute* that appears
verbatim in the corpus. A sentence embedding averages the whole sentence into
one vector, so a single decisive adjective can be swamped by the surrounding
travel vocabulary. A bag-of-words model cannot average anything away, so it
retains the constraint exactly.

Note TF-IDF won this on only two words — `backpacking` and `trip` were also out
of vocabulary.

### 4.3 q26 — both models fail, for different reasons

Query: *"get away from the tourist trail to somewhere few people go"*

Semantic returns Serengeti, Kruger, Queenstown — it read "get away" as
wilderness and outdoors.

TF-IDF matched `trail` and `away`, returning Machu Picchu and Chamonix — places
with literal hiking trails. This is a **polysemy failure**: "tourist trail" is
figurative, "trail" in the corpus is a footpath.

Both scored near zero. The catalogue literally contains the tag "off the beaten
path" on the two grade-3 destinations, and neither model reached it.

**Worth reporting honestly:** neither approach handles figurative language, and
your query set contains figurative queries because real users write them.

### 4.4 q02 — the semantic model wins clearly

Query: *"somewhere peaceful by the sea to switch off completely"*

Semantic: Maldives (3), El Nido (3), Santorini (2) in the top five.
TF-IDF: Algarve (2) on `sea`, then **Marrakesh** and **Kyoto** on `peaceful` —
a desert city and an inland temple town, for a query about the sea.

This is the demonstration to show a supervisor. It takes ten seconds in the app.

---

## 5. Problems encountered and resolved

Chapter 5 material. Each has a diagnosis, not just a symptom.

| # | Problem | Diagnosis | Resolution |
|---|---|---|---|
| 1 | Backend would not start | `settings.py` never read `.env`, so `USE_SQLITE` was ignored and Django attempted PostgreSQL | Dependency-free `.env` loader; SQLite default |
| 2 | Models not comparable | Primary-and-fallback architecture | Rewritten as peers (§2.1) |
| 3 | Provider returned an error envelope with HTTP 200 | REST Countries deprecated v3.1 mid-project; v5 requires a paid key | Pluggable provider; keyless default; explicit test for the deprecation envelope |
| 4 | Non-ASCII country names corrupted | Provider omits `charset` in Content-Type, so `requests` guessed the encoding wrongly | Parse `response.content` as UTF-8 bytes rather than `response.text` |
| 5 | Paginated pages overlapped/skipped | An aggregate annotation drops Django's `Meta.ordering`, leaving the queryset unordered | Explicit `order_by` on every list queryset |
| 6 | "Top rated" sort inconsistent across databases | SQLite and PostgreSQL disagree on NULL ordering | Explicit `nulls_last=True` |
| 7 | App would not start at all | `@expo/vector-icons` declares `expo-font` as a loose peer dep; npm installed an SDK 56 package into an SDK 51 project, which called an API that did not exist | Pinned `expo-font` to the SDK 51 version |
| 8 | First request after startup timed out | Cold transformer load (~9s) exceeded the client's 15s timeout when combined | Background warm-up at startup; client timeout raised to 30s |
| 9 | Model reported "unavailable" with no reason during warm-up | Race: the "attempted" flag was set *before* the slow load and checked *outside* the lock, so concurrent callers saw a null model | Separate `resolved` flag set in a `finally`; fast path waits on the lock |

Problem 7 is worth dwelling on: the app bundled successfully for Android and
iOS while being completely broken, because bundling does not execute module
bodies. It is a good illustration of why a green build is not evidence of a
working system.

Problem 9 was found while investigating §4 — the diagnostic script could not
load the model. Worth mentioning as an example of tooling surfacing a defect.

---

## 6. Testing

139 automated tests, passing on Python 3.13 locally and 3.11/3.12 in CI.

| Area | What is covered |
|---|---|
| `accounts` | Registration validation, password policy, duplicate email, JWT issue/refresh/reject, profile permissions, favourites |
| `destinations` | Filters, search, sort, ordering regressions, facets, review CRUD, one-review-per-user, ownership |
| `recommendations` | Both backends, alias resolution, fallback behaviour and its refusal, full-corpus fitting, index refit, personalisation, concurrency |
| `evaluation` | Every metric against hand-computed values, boundary cases, query-set integrity, runner behaviour |
| `integrations` | Mocked providers, caching, outage, timeout, deprecation envelope, encoding |

CI runs the suite **without torch installed** (`DISABLE_SEMANTIC_MODEL=1`),
which also proves the degradation path works rather than just asserting it does.

---

## 7. Numbers you may need

| | |
|---|---|
| Destinations | 48 across 7 categories |
| Countries represented | 38 |
| Labelled queries | 26 (18 lexical, 8 paraphrase) |
| Relevance judgements | 155, mean 5.96 per query |
| Embedding dimensions | 384 |
| Automated tests | 139 |
| Semantic mean latency | 16.59 ms |
| TF-IDF mean latency | 4.94 ms |
| Cold model load | ~9 s (once, at startup) |
| Backend | ~5,900 lines Python, 57 files |
| Frontend | ~3,300 lines JavaScript, 19 files |

Full metrics are in `evaluation_results/results.json`; per-query detail in
`results.csv`; figures in `evaluation_results/figures/`.

---

## 8. Things to verify before you claim them

- **Version control.** State honestly what was actually in place. The guide
  asks for your approach, and an accurate account of a weakness costs less than
  an inaccurate claim.
- **Which parts you wrote.** Your AI-use statement is assessed. Be specific.
- **The 38-country figure** and any other count — re-derive it rather than
  trusting this document.
- **Anything in §4** — run `diagnose_query` yourself and confirm the output
  matches before writing about it.

---

## 9. Commands

```bash
python manage.py runserver 0.0.0.0:8000     # start the API
python manage.py seed_destinations --embed  # load catalogue, cache embeddings
python manage.py fetch_images               # photos from Wikipedia
python manage.py run_evaluation             # the experiment
python manage.py run_evaluation --validate  # check labels against catalogue
python manage.py make_figures               # regenerate report figures
python manage.py diagnose_query q18         # explain one query's ranking
python manage.py test                       # 139 tests
```
