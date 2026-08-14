# Final Report — planning pack

**This file is scaffolding and data. It is not report text. Do not paste from it.**

It contains: a word budget tied to the mark scheme, what belongs in each chapter,
questions to answer in your own words, and your own experimental results
formatted as tables you can reproduce as figures.

The sentences in your report must be yours. The numbers below are facts from
your own evaluation run — using facts is not plagiarism; using someone else's
sentences is.

---

## 1. Word budget

Target 12,000–15,000. The brief says ~8,000, so confirm the higher figure with
your supervisor before committing. Budget below assumes 13,000.

Weights are from your brief. Allocate words roughly in proportion to marks,
except Implementation, which is easy to overwrite and hard to score in.

| Chapter | Marks | Words | Notes |
|---|---|---|---|
| Title, Acknowledgements, Contents | — | — | Not counted |
| Abstract | Background 5% | 250 | Write this **last** |
| 1. Introduction | Background 5% | 900 | Aim, objectives, chapter summary |
| 2. Literature Review | Discovery 20% | 2,600 | Your weakest area currently — see §3 |
| 3. Requirements | Discovery 20% | 1,600 | Includes ethics, legal, constraints |
| 4. Design | Implementation 20% | 1,800 | Architecture, methodology, decisions |
| 5. Technical Development | Implementation 20% | 2,200 | Implementation, testing, problems solved |
| 6. Evaluation | Outcomes 15% | 1,300 | Method — how you measured |
| 7. Results | Outcomes 15% | 1,000 | Findings, mostly tables and figures |
| 8. Discussion | Outcomes 15% | 1,400 | Critical analysis — highest value per word |
| 9. Conclusion | Outcomes 15% | 700 | Objectives met, future work |
| Bibliography | Quality 10% | — | Harvard, not counted |
| Appendices | — | — | Not counted |

**Discovery is 20% and is your thinnest chapter.** Your interim report has 11
sources with 3 summarised. A 2,600-word review needs roughly 25–30 sources.
Budget real reading time.

---

## 2. What you already have

From your interim report, reusable **after rewriting** (do not paste your own
interim text unmodified either — check your department's self-plagiarism rule):

- Aim and research question — solid, keep the framing
- 11 references + 5 documentation sources
- 3 paper summaries (Adomavicius & Tuzhilin; Lops et al.; Borràs et al.)
- Ethical analysis (a–e) — strong, expand with what actually happened
- BCS professional issues — three standards, keep
- Risk register (8 risks) — **update it**, several materialised
- Kanban methodology justification

---

## 3. Chapter-by-chapter

### 1. Introduction (900)

Cover:
- The problem: users describe trips in natural language; keyword search fails them
- Your aim, stated as a question
- The six core objectives and five advanced objectives, as a list
- One paragraph per chapter, saying what it contains

**Write in your own words:** why this question is worth asking. Your interim
report's reflection (the TF-IDF-as-control realisation) is the honest origin
story — that's genuinely yours and it's good material.

---

### 2. Literature Review (2,600)

Suggested structure:

1. **Recommender systems overview** (400) — collaborative vs content-based vs
   hybrid; why collaborative filtering fails you (no user history, cold start)
2. **Content-based methods** (500) — TF-IDF, vector space model, its known
   weaknesses (vocabulary mismatch, over-specialisation)
3. **Semantic representations** (600) — word2vec → BERT → Sentence-BERT;
   why bi-encoders suit retrieval; MiniLM's distillation
4. **Tourism recommenders specifically** (600) — Borràs et al., Sarkar et al.;
   what's been tried; the evaluation gap
5. **Evaluation of ranking systems** (400) — precision@k, nDCG, graded relevance,
   Cranfield paradigm, why offline evaluation with labelled queries is standard
6. **Gap statement** (100) — what nobody has done that you are doing

**You need more sources on §5** — you currently have none on evaluation
methodology. Look for: Järvelin & Kekäläinen (2002) on nDCG (this is *the*
citation for your main metric — you must have it), Manning, Raghavan & Schütze
*Introduction to Information Retrieval* (free online, chapters 6 and 8),
Voorhees on TREC methodology.

**Do not summarise papers one by one.** Synthesise — group by theme, compare
positions, say where authors disagree. That is what earns Discovery marks.

---

### 3. Requirements (1,600)

- **Functional requirements** — number them (FR1, FR2…), group by area, mark
  MoSCoW priority. Derive from your objectives.
- **Non-functional** — response time, offline degradation, portability across
  databases, the app running without torch
- **Constraints** — solo developer, no budget, no API keys, mobile hardware,
  Python 3.13 dependency friction
- **Legal** — UK GDPR / DPA 2018 (you store accounts and stated preferences);
  licensing of third-party data (Open-Meteo terms, Wikimedia Commons licences,
  the countries provider's terms)
- **Ethics** — expand your interim (a)–(e). Add what actually happened:
  you deliberately widened geographic coverage of the catalogue, which is a
  concrete mitigation of the recommendation-bias concern you raised.
- **Ethics approval** — restate that no human participants were involved, so no
  approval was required, and that this is precisely why the user study stayed an
  advanced objective.

---

### 4. Design (1,800)

- **Architecture** — layered diagram: Expo client → DRF API → recommender
  engine → SQLite/PostgreSQL, plus two external providers
- **Data model** — ER diagram: User, Destination, Review, favourites M2M
- **API design** — REST, resource naming, JWT with access/refresh
- **Recommender design** — this is the chapter's core. The key decision is that
  both models are peers, not primary-and-fallback, and both fit over the full
  catalogue so scores stay comparable under filtering. Explain *why* each
  matters to validity.
- **Evaluation design** — the Cranfield-style setup: fixed corpus, fixed query
  set, graded judgements, same metrics both conditions
- **Methodology** — Kanban, WIP limits, incremental delivery

**Justify decisions, don't just describe them.** For every choice, state the
alternative you rejected and why.

---

### 5. Technical Development (2,200)

Structure by **problem solved**, not by file. Each of these is a genuine
engineering narrative with a beginning and end:

| Problem | What it demonstrates |
|---|---|
| Two models as peers, not fallback | Fixing Risk #1; the change that made the whole study possible |
| Embedding cache invalidation | Caching by model name + timestamp; why staleness matters |
| Fitting TF-IDF over the full corpus | IDF stability; a subtle validity threat |
| REST Countries deprecation mid-project | Risk #4 materialising; provider abstraction |
| Aggregate annotation dropped ORM ordering | Silent pagination bug; found by testing |
| SDK version conflict broke app startup | Transitive dependency pulled a wrong major version |
| Cold-start model load exceeded client timeout | Startup warm-up in a background thread |
| Character encoding on provider response | Missing charset header; parse bytes not text |

**Testing** — 139 automated tests, what they cover, why metrics are tested
against hand-computed values rather than another library, CI on two Python
versions without torch.

---

### 6. Evaluation (1,300)

Method only — results go in chapter 7.

- Corpus: 48 destinations, 7 categories, geographic spread
- Query set: 26 queries, 155 graded judgements, mean 5.96 per query
- **The lexical/paraphrase split and why you designed it**
- Grading scale 0–3 and what each grade means
- Metrics and their formulas — cite Järvelin & Kekäläinen for nDCG
- Why paired comparison (same queries, both systems)
- **Threats to validity** — put them here, honestly:
  - single annotator, no inter-annotator agreement
  - you authored both corpus text and queries
  - n=26, and n=8 for the paraphrase subgroup
  - labels written before running either model (state this — it matters)

---

### 7. Results (1,000)

Mostly tables and figures. See §4 below for your data. Minimal prose —
state what the numbers are, save interpretation for chapter 8.

---

### 8. Discussion (1,400)

**Highest marks per word in the entire report.** This is where you think.

Address:

1. **The headline is a null result** — +0.021 nDCG@5, t=0.41, d=0.08. Say so plainly.
2. **The subgroup analysis inverts it** — and explain the mechanism: TF-IDF cannot
   match what has no shared term.
3. **The honest caveat** (see §5 below) — the paraphrase effect is not uniform.
4. **Cost** — 3.36× latency. At 48 destinations both are imperceptible. Discuss
   what changes at 10,000 destinations and why ANN indexing becomes the question.
5. **Where TF-IDF beat semantic and why** — q15 skiing, q25 wine. Look at those
   queries and reason about it.
6. **Implications** — does a hybrid make sense? Route by query characteristics?
7. **Comparison to literature** — Borràs et al. said evaluation was underdeveloped
   in tourism recommenders; what does your result add?
8. **Limitations** — restate honestly, don't bury.

---

### 9. Conclusion (700)

- Objective-by-objective: met / partially met / not met, with evidence
- Answer your research question in one sentence
- Future work: larger query set, second annotator (with ethics approval),
  pgvector and ANN indexing, hybrid routing, real user study

---

## 4. Your results — data for tables and figures

All from `backend/evaluation_results/results.json`, run over 48 destinations
and 26 queries.

### Table 1 — Overall performance

| Metric | Semantic | TF-IDF | Difference |
|---|---|---|---|
| precision@1 | 0.8846 | 0.8846 | 0.0000 |
| precision@3 | 0.6539 | 0.6539 | 0.0000 |
| precision@5 | 0.5923 | 0.5231 | +0.0692 |
| precision@10 | 0.4077 | 0.3462 | +0.0615 |
| nDCG@1 | 0.7308 | 0.7967 | −0.0659 |
| nDCG@3 | 0.6573 | 0.6530 | +0.0043 |
| nDCG@5 | 0.6704 | 0.6492 | +0.0212 |
| nDCG@10 | 0.7346 | 0.6740 | +0.0606 |
| MRR | 0.8997 | 0.8923 | +0.0074 |
| MAP | 0.5849 | 0.5166 | +0.0683 |
| Mean latency (ms) | 16.59 | 4.94 | 3.36× |

### Table 2 — nDCG@5 by query type

| Query type | n | Semantic | TF-IDF | Difference |
|---|---|---|---|---|
| Lexical | 18 | 0.7450 | 0.7980 | −0.0530 |
| Paraphrase | 8 | 0.5026 | 0.3145 | +0.1881 |
| All | 26 | 0.6704 | 0.6492 | +0.0212 |

### Table 3 — Paired statistics (nDCG@5)

| Statistic | Value |
|---|---|
| n | 26 |
| Mean difference | +0.0212 |
| Paired t | 0.4103 |
| Cohen's d | 0.0805 |
| Semantic wins | 11 |
| TF-IDF wins | 15 |

### Table 4 — Per-query nDCG@5 (appendix table)

| ID | Type | Semantic | TF-IDF | Diff | Winner |
|---|---|---|---|---|---|
| q01 | lexical | 0.612 | 0.704 | −0.092 | TF-IDF |
| q02 | paraphrase | 0.818 | 0.195 | +0.623 | Semantic |
| q03 | lexical | 0.916 | 0.944 | −0.028 | TF-IDF |
| q04 | lexical | 0.687 | 0.553 | +0.134 | Semantic |
| q05 | lexical | 0.863 | 0.965 | −0.102 | TF-IDF |
| q06 | lexical | 0.639 | 0.480 | +0.159 | Semantic |
| q07 | lexical | 0.578 | 0.693 | −0.114 | TF-IDF |
| q08 | lexical | 0.831 | 0.899 | −0.068 | TF-IDF |
| q09 | lexical | 0.701 | 0.900 | −0.198 | TF-IDF |
| q10 | lexical | 0.917 | 1.000 | −0.083 | TF-IDF |
| q11 | lexical | 0.892 | 0.874 | +0.018 | Semantic |
| q12 | lexical | 0.663 | 0.773 | −0.110 | TF-IDF |
| q13 | paraphrase | 0.663 | 0.624 | +0.038 | Semantic |
| q14 | lexical | 0.950 | 0.956 | −0.005 | TF-IDF |
| q15 | lexical | 0.619 | 0.872 | −0.253 | TF-IDF |
| q16 | lexical | 0.474 | 0.582 | −0.109 | TF-IDF |
| q17 | lexical | 0.831 | 0.953 | −0.122 | TF-IDF |
| q18 | paraphrase | 0.871 | 0.000 | +0.871 | Semantic |
| q19 | lexical | 0.795 | 0.508 | +0.287 | Semantic |
| q20 | paraphrase | 0.876 | 0.831 | +0.045 | Semantic |
| q21 | paraphrase | 0.709 | 0.514 | +0.196 | Semantic |
| q22 | paraphrase | 0.084 | 0.000 | +0.084 | Semantic |
| q23 | paraphrase | 0.000 | 0.326 | −0.326 | TF-IDF |
| q24 | lexical | 0.871 | 0.782 | +0.089 | Semantic |
| q25 | lexical | 0.570 | 0.927 | −0.357 | TF-IDF |
| q26 | paraphrase | 0.000 | 0.025 | −0.025 | TF-IDF |

Full data including precision, recall, MRR, MAP and the top-10 returned for
every query: `backend/evaluation_results/results.csv`.

### Suggested figures

1. Grouped bar chart — nDCG@1/3/5/10, two series
2. Grouped bar chart — nDCG@5 by query type (this is your money figure)
3. Scatter — per-query semantic vs TF-IDF nDCG@5, with a y=x diagonal
4. Sorted bar chart — per-query difference, showing the distribution of wins
5. Architecture diagram
6. ER diagram
7. Screenshots: Recommend with model switch, Model Lab head-to-head, Benchmark

Figure 3 is worth building — it shows the spread, not just the average.

---

## 5. The caveat you must state

Do not let a marker find this before you do.

**The paraphrase advantage is not uniform.** Of 8 paraphrase queries:

- 6 favour semantic, 2 favour TF-IDF (q23, q26)
- Two queries carry most of the effect: **q18 (+0.871)** and **q02 (+0.623)**
- Remove those two and the paraphrase mean difference shrinks sharply

So the honest claim is *not* "semantic is better on paraphrase queries." It is
closer to: **on a minority of queries where lexical overlap fails almost
completely, semantic retrieval succeeds where TF-IDF returns nothing usable —
and those cases are severe enough to move the subgroup mean.**

**q18 is your best case study.** Query: *"I want to learn to cook the local
dishes."* TF-IDF scores **0.000** — not one relevant result in the top 10. The
catalogue says "cooking classes" for Hoi An and describes Oaxaca's food culture,
but the query's terms don't align. Semantic scores 0.871. Investigate why and
write it up — a worked example of the mechanism is worth more than another table.

**q23 and q26 are your counter-examples.** Semantic scored 0.000 on both. Work
out why and report it. A discussion that only explains the wins is not a
discussion.

---

## 6. Update your risk register

Several risks materialised. Show the register as living, with an outcome column.

| # | Risk | Outcome |
|---|---|---|
| 1 | Models run as alternatives, not comparable | **Materialised, resolved** — engine rewritten so both are peers |
| 2 | No ground-truth data | **Materialised, resolved** — 26 queries, 155 graded judgements |
| 3 | ML dependency friction | **Partially materialised** — a transitive SDK version conflict broke app startup; resolved by pinning |
| 4 | External API changes terms | **Materialised** — REST Countries deprecated its keyless API mid-project; resolved with a pluggable provider |
| 5 | Competing time demands | Ongoing |
| 6 | Loss of work | Not materialised — **note honestly whether version control was in place** |
| 7 | Frontend integration issues late | **Materialised** — CORS, JWT refresh, cold-start timeout all surfaced during integration |
| 8 | Semantic may not beat baseline | **Materialised** — and reported as the finding, as planned |

Risk 4 is the strongest item in your report. You predicted a specific risk and
it happened exactly as described. Say so.

---

## 7. Appendices

- A: Risk register (updated, with outcomes)
- B: Full labelled query set with grades — `backend/evaluation/queries.py`
- C: Full per-query results — `backend/evaluation_results/results.csv`
- D: API endpoint reference — root of `README.md`
- E: Test output — `python manage.py test --verbosity 2`
- F: Source code listing or repository link
- G: Supervisor meeting notes

---

## 8. Referencing

Harvard. Minimum you should cite:

- **Järvelin & Kekäläinen (2002)** — nDCG. Non-negotiable, it's your main metric.
- Reimers & Gurevych (2019) — Sentence-BERT
- Wang et al. (2020) — MiniLM
- Devlin et al. (2019) — BERT
- Manning, Raghavan & Schütze (2008) — IR textbook, TF-IDF and evaluation
- Adomavicius & Tuzhilin (2005); Lops et al. (2011); Pazzani & Billsus (2007)
- Borràs et al. (2014); Sarkar et al. (2022); Ricci et al. (2011)
- Mikolov et al. (2013)
- Pedregosa et al. (2011) — scikit-learn, if you cite the TF-IDF implementation

Cite software you depend on: Django, DRF, scikit-learn, sentence-transformers,
Open-Meteo, React Native/Expo.

---

## 9. Order of writing

1. Results (chapter 7) — the data exists, it's fastest, it builds momentum
2. Evaluation (6) — method, fresh from writing results
3. Technical Development (5) — the narrative you know best
4. Design (4)
5. Discussion (8) — needs 5–7 done first
6. Literature Review (2) — the reading is the bottleneck, start it **now** in parallel
7. Requirements (3)
8. Conclusion (9)
9. Introduction (1)
10. Abstract — last, always

---

## 10. Declaring AI use

You will need to declare it. Be specific rather than vague — specific
declarations read as honest, vague ones read as hedging. Record which parts of
the codebase were AI-assisted, which you wrote, and that the report text,
analysis and conclusions are your own.

Check your department's exact wording requirement before submitting.
