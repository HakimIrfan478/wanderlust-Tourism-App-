"""The labelled query set used to compare the two recommenders.

Labelling protocol
------------------
Each query is a short natural-language description of a trip, of the kind a
user would actually type into the app. Destinations are graded on a four-point
scale against the *whole* query, not against individual words:

    3  Ideal. Satisfies every part of the query; a user would be pleased to
       see this first.
    2  Relevant. Satisfies the main intent but misses a secondary condition
       (right activity, wrong budget; right feel, wrong region).
    1  Marginal. Defensible but weak — a user would not complain, but would
       not have chosen it.
    0  Not relevant. Anything not listed below.

Labels were assigned from the destination descriptions in
``destinations/data/destinations.json``, before either model was run, so the
grades are not fitted to the output of one of the systems.

Query design
------------
The set deliberately mixes two kinds of query, because the project's question
is about *where* the two model families differ rather than which wins overall:

* **Lexical** queries reuse vocabulary that appears in the catalogue text
  ("skiing and snowboarding", "wine tasting and vineyards"). TF-IDF should
  handle these well.
* **Paraphrase** queries describe the same intent in words the catalogue never
  uses ("somewhere peaceful by the sea to switch off completely",
  "photograph rare animals in their natural habitat"). These are where a
  semantic model is expected to pull ahead — and testing that expectation is
  the point of the experiment.

Each query records which kind it is in ``type``, so results can be broken down
by query type rather than only reported as one average.

Known limitation
----------------
These are single-annotator judgements written by the project author, so they
carry that author's assumptions and no inter-annotator agreement can be
computed. That limits how strongly any result should be stated, and is why a
small independent relevance-judgement study is listed as an advanced objective
in the report rather than claimed here.
"""

LEXICAL = "lexical"
PARAPHRASE = "paraphrase"

# Destination names must match `name` in destinations/data/destinations.json.
# `manage.py run_evaluation --validate` checks that and fails loudly otherwise.
LABELLED_QUERIES = [
    {
        "id": "q01",
        "query": "quiet beaches with great seafood and no big crowds",
        "type": LEXICAL,
        "relevance": {
            "Algarve": 3,
            "Zanzibar": 3,
            "El Nido, Palawan": 3,
            "Maldives": 2,
            "Santorini": 2,
            "Phuket": 1,
            "Tulum": 1,
        },
    },
    {
        "id": "q02",
        "query": "somewhere peaceful by the sea to switch off completely",
        "type": PARAPHRASE,
        "relevance": {
            "Maldives": 3,
            "El Nido, Palawan": 3,
            "Zanzibar": 2,
            "Algarve": 2,
            "Santorini": 2,
            "Bali": 1,
            "Tulum": 1,
        },
    },
    {
        "id": "q03",
        "query": "ancient ruins and museums with amazing local food",
        "type": LEXICAL,
        "relevance": {
            "Rome": 3,
            "Athens": 3,
            "Istanbul": 2,
            "Pyramids of Giza": 2,
            "Oaxaca": 2,
            "Petra": 1,
            "Angkor Wat": 1,
            "Machu Picchu": 1,
        },
    },
    {
        "id": "q04",
        "query": "extreme adventure sports in the mountains",
        "type": LEXICAL,
        "relevance": {
            "Queenstown": 3,
            "Chamonix": 3,
            "Interlaken": 2,
            "Moab": 2,
            "Everest Base Camp Trek": 2,
            "Banff National Park": 1,
            "Dolomites": 1,
            "Torres del Paine": 1,
        },
    },
    {
        "id": "q05",
        "query": "wildlife safari and unspoiled nature",
        "type": LEXICAL,
        "relevance": {
            "Serengeti National Park": 3,
            "Kruger National Park": 3,
            "Galápagos Islands": 2,
            "Amazon Rainforest": 2,
            "Yellowstone National Park": 1,
        },
    },
    {
        "id": "q06",
        "query": "romantic getaway with beautiful sunsets",
        "type": LEXICAL,
        "relevance": {
            "Santorini": 3,
            "Maldives": 3,
            "Bali": 2,
            "Zanzibar": 2,
            "Tulum": 1,
            "El Nido, Palawan": 1,
            "Kyoto": 1,
        },
    },
    {
        "id": "q07",
        "query": "cheap trip in Asia with amazing street food",
        "type": LEXICAL,
        "relevance": {
            "Hoi An": 3,
            "Phuket": 3,
            "Angkor Wat": 2,
            "Varanasi": 2,
            "Jaipur": 2,
            "Bali": 2,
            "Istanbul": 1,
        },
    },
    {
        "id": "q08",
        "query": "trekking at high altitude in the Himalayas",
        "type": LEXICAL,
        "relevance": {
            "Everest Base Camp Trek": 3,
            "Hunza Valley": 3,
            "Paro Valley": 2,
            "Machu Picchu": 1,
            "Torres del Paine": 1,
        },
    },
    {
        "id": "q09",
        "query": "a city break with great architecture and walkable streets",
        "type": LEXICAL,
        "relevance": {
            "Barcelona": 3,
            "Lisbon": 3,
            "Amsterdam": 3,
            "Rome": 2,
            "Istanbul": 2,
            "Athens": 1,
            "Buenos Aires": 1,
            "Singapore": 1,
        },
    },
    {
        "id": "q10",
        "query": "see the northern lights and dramatic volcanic landscapes",
        "type": LEXICAL,
        "relevance": {
            "Reykjavik": 3,
            "Santorini": 1,
        },
    },
    {
        "id": "q11",
        "query": "learn about Buddhist temples and monasteries",
        "type": LEXICAL,
        "relevance": {
            "Paro Valley": 3,
            "Kyoto": 3,
            "Angkor Wat": 2,
            "Varanasi": 1,
        },
    },
    {
        "id": "q12",
        "query": "desert landscapes and camping under the stars",
        "type": LEXICAL,
        "relevance": {
            "Wadi Rum": 3,
            "Moab": 2,
            "Marrakesh": 2,
            "Dubai": 1,
            "Pyramids of Giza": 1,
        },
    },
    {
        "id": "q13",
        "query": "a safe destination that is easy to travel with children",
        "type": PARAPHRASE,
        "relevance": {
            "Singapore": 3,
            "Amsterdam": 2,
            "Lisbon": 2,
            "Barcelona": 1,
            "Tokyo": 1,
        },
    },
    {
        "id": "q14",
        "query": "snorkelling and diving on coral reefs",
        "type": LEXICAL,
        "relevance": {
            "Maldives": 3,
            "El Nido, Palawan": 3,
            "Galápagos Islands": 3,
            "Phuket": 2,
            "Zanzibar": 2,
            "Tulum": 1,
        },
    },
    {
        "id": "q15",
        "query": "skiing and snowboarding holiday",
        "type": LEXICAL,
        "relevance": {
            "Chamonix": 3,
            "Banff National Park": 3,
            "Queenstown": 2,
            "Interlaken": 2,
            "Dolomites": 2,
        },
    },
    {
        "id": "q16",
        "query": "traditional crafts, markets and haggling",
        "type": LEXICAL,
        "relevance": {
            "Marrakesh": 3,
            "Jaipur": 3,
            "Oaxaca": 2,
            "Istanbul": 2,
            "Hoi An": 1,
            "Varanasi": 1,
        },
    },
    {
        "id": "q17",
        "query": "waterfalls, lakes and forest walks",
        "type": LEXICAL,
        "relevance": {
            "Plitvice Lakes": 3,
            "Banff National Park": 2,
            "Interlaken": 2,
            "Yellowstone National Park": 1,
            "Reykjavik": 1,
        },
    },
    {
        "id": "q18",
        "query": "I want to learn to cook the local dishes",
        "type": PARAPHRASE,
        "relevance": {
            "Hoi An": 3,
            "Oaxaca": 3,
            "Kyoto": 2,
            "Marrakesh": 2,
            "Rome": 1,
            "Istanbul": 1,
        },
    },
    {
        "id": "q19",
        "query": "world class nightlife and bars",
        "type": LEXICAL,
        "relevance": {
            "Barcelona": 3,
            "Buenos Aires": 3,
            "Tokyo": 2,
            "Amsterdam": 2,
            "Phuket": 1,
            "Lisbon": 1,
        },
    },
    {
        "id": "q20",
        "query": "somewhere sacred where faith is part of daily life",
        "type": PARAPHRASE,
        "relevance": {
            "Varanasi": 3,
            "Paro Valley": 3,
            "Kyoto": 2,
            "Angkor Wat": 1,
            "Istanbul": 1,
        },
    },
    {
        "id": "q21",
        "query": "photograph rare animals in their natural habitat",
        "type": PARAPHRASE,
        "relevance": {
            "Serengeti National Park": 3,
            "Galápagos Islands": 3,
            "Kruger National Park": 3,
            "Amazon Rainforest": 2,
            "Yellowstone National Park": 2,
            "Banff National Park": 1,
        },
    },
    {
        "id": "q22",
        "query": "a once in a lifetime trip where money is no object",
        "type": PARAPHRASE,
        "relevance": {
            "Maldives": 3,
            "Galápagos Islands": 3,
            "Paro Valley": 2,
            "Dubai": 2,
            "Serengeti National Park": 2,
            "Interlaken": 1,
        },
    },
    {
        "id": "q23",
        "query": "somewhere very cheap for a long backpacking trip",
        "type": PARAPHRASE,
        "relevance": {
            "Hunza Valley": 3,
            "Varanasi": 3,
            "Hoi An": 3,
            "Angkor Wat": 2,
            "El Nido, Palawan": 2,
            "Jaipur": 2,
            "Phuket": 2,
            "Bali": 1,
            "Oaxaca": 1,
        },
    },
    {
        "id": "q24",
        "query": "big modern city with excellent public transport",
        "type": LEXICAL,
        "relevance": {
            "Tokyo": 3,
            "Singapore": 3,
            "Amsterdam": 2,
            "Dubai": 2,
            "Barcelona": 1,
        },
    },
    {
        "id": "q25",
        "query": "wine tasting and vineyards",
        "type": LEXICAL,
        "relevance": {
            "Cape Town": 3,
            "Santorini": 2,
            "Buenos Aires": 2,
            "Rome": 1,
            "Barcelona": 1,
        },
    },
    {
        "id": "q26",
        "query": "get away from the tourist trail to somewhere few people go",
        "type": PARAPHRASE,
        "relevance": {
            "Hunza Valley": 3,
            "Paro Valley": 3,
            "Torres del Paine": 2,
            "Amazon Rainforest": 2,
            "El Nido, Palawan": 2,
            "Zanzibar": 1,
            "Algarve": 1,
        },
    },
]


def query_types():
    """The distinct query types present in the set."""
    return sorted({q["type"] for q in LABELLED_QUERIES})


def summary():
    """Counts used in the report's methodology section."""
    by_type = {}
    for query in LABELLED_QUERIES:
        by_type[query["type"]] = by_type.get(query["type"], 0) + 1
    judgements = sum(len(q["relevance"]) for q in LABELLED_QUERIES)
    return {
        "query_count": len(LABELLED_QUERIES),
        "queries_by_type": by_type,
        "relevance_judgements": judgements,
        "mean_judged_per_query": round(judgements / len(LABELLED_QUERIES), 2),
        "grade_scale": {3: "ideal", 2: "relevant", 1: "marginal", 0: "not relevant"},
    }


def validate_against_catalogue():
    """Return the labelled destination names that are not in the database.

    A typo in a label would silently deflate a model's score, so the runner
    refuses to produce results until this comes back empty.
    """
    from destinations.models import Destination

    known = set(Destination.objects.values_list("name", flat=True))
    labelled = {name for q in LABELLED_QUERIES for name in q["relevance"]}
    return sorted(labelled - known)
