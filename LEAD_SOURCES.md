# Lead Sources & Consensus

How the CRM finds businesses, which keys unlock which sources, and why a
consensus run produces better leads than any single source.

---

## The problem consensus solves

Any one source lies to you in a predictable way:

- **Google Places** is accurate but only lists businesses that claimed a
  profile — it structurally cannot show you the ones with no web presence,
  which are your best prospects.
- **Yelp** has the best review data but never returns the business's own
  website, only its Yelp page.
- **Web search** finds businesses the places APIs never indexed, but half the
  results are directory listicles, not businesses.
- **OpenStreetMap** is free and unlimited but sparse on phone numbers.

Query one and you get a biased slice. Query six, cluster the results, and count
how many independently found the same business — **that count is the signal**. A
business four sources agree on exists and is trading. One a single web search
saw might be a defunct listing or a blog post.

---

## Sources

| Source | Env var | Trust | Cost (Sept 2026) | Best for |
|---|---|---|---|---|
| **Google Places (New)** | `GOOGLE_PLACES_API_KEY` | 1.00 | ~$32/1k, 5k/mo free | Accuracy, phone, website, reviews |
| **Yelp Fusion** | `YELP_API_KEY` | 0.90 | from ~$7.99/1k, no free tier | Review counts and ratings |
| **Serper** | `SERPER_API_KEY` | 0.85 | credit-based, cheap | Google Maps data without GCP |
| **Foursquare** | `FOURSQUARE_API_KEY` | 0.80 | credit-based | Independent corroboration |
| **OpenStreetMap** | *(none)* | 0.70 | free, unlimited | Baseline coverage, always on |
| **Firecrawl** | `FIRECRAWL_API_KEY` | 0.60 | credit-based | Businesses no places API indexed |

**Trust is used for tie-breaking**, not filtering. When two sources report
different phone numbers, the weighted vote favours the higher-trust one — and
the disagreement is surfaced as a conflict rather than hidden.

**OpenStreetMap needs no key and is always available**, so the system works
before you configure anything. Every other source is additive.

### Notes on the paid ones

- **Yelp ended its free tier.** Accounts are paid now. Worth it only if review
  data matters to you — the audit uses review count and rating as two of its
  seventeen signals.
- **Google Places** replaced the pooled $200 credit with per-SKU monthly free
  caps. Text Search bills at the Pro SKU, 5,000 free calls a month. A consensus
  run at 3 terms uses 3 calls, so the free tier covers roughly 1,600 runs.
- **Foursquare retired v3 on 15 May 2026.** This targets the new Places API at
  `places-api.foursquare.com` with the `X-Places-Api-Version` header.

### Recommended starting set

Start with **Serper + OpenStreetMap**. Serper gives you Google Maps data
cheaply and without a Google Cloud project, OSM is free, and two independent
sources is enough for the consensus engine to be meaningful. Add Google Places
when you want the accuracy, and Yelp only if you specifically want review data.

---

## How a run works

```
plan  →  step × N  →  finalize
```

1. **Plan** builds the list of (source × search term) pairs. Junk removal with
   3 terms across 4 sources is 12 steps.
2. **Each step** queries one source with one term and pools the raw candidates
   in the database. Steps are separate HTTP requests, so no single one
   approaches the serverless timeout, and progress stays visible.
3. **Finalize** clusters, scores, deduplicates and saves.

The pacing is deliberate. A run takes a minute or two rather than seconds
because the point is corroborated data, not speed.

### Clustering

Candidates are grouped by union-find over three linking keys — **phone**,
**registrable domain**, and **normalized name + city** — so matches chain
correctly: if A and B share a phone and B and C share a domain, all three are
one business.

A fuzzy pass then catches what exact keys miss. "Joe's Junk Removal" and
"Joe Junk Removal Co" are one character apart after normalization but would
otherwise survive as two leads — the exact repeat-contact problem the system
exists to prevent. Similarity is bucketed by locality, so "Bay State Hauling" in
Brockton never merges with the one in Providence.

### Confidence score

```
confidence = corroboration × 0.50
           + completeness  × 0.25
           + agreement     × 0.25
```

- **Corroboration** — trust-weighted count of independent sources. Dominates,
  because it is the only signal that cannot be faked by one source being verbose.
- **Completeness** — how many of name, phone, website, address, city are filled.
- **Agreement** — the winning value's share of the vote on each contested field.
  Two sources contradicting each other scores lower than two confirming.

### Modes

| Mode | Floor | Use when |
|---|---|---|
| **Wide** | 25 | You want volume and will filter by hand |
| **Balanced** | 45 | Default — good signal, good volume |
| **Strict** | 65 | Only well-corroborated businesses |

**Minimum sources per lead** is a separate, harder gate. Set it to 2 and a lead
found by only one source is rejected regardless of how complete its record is.
That is the setting to use when you care most about not wasting outreach.

---

## What a run reports

Every run tells you what it discarded, not just what it kept:

```
Added 3 new leads — 14 raw results from 4 sources, clustered to 3 businesses,
0 below confidence, 2 already in CRM

Per source: google places 4 · yelp 4 · serper 4 · osm 2

  89  Joe's Junk Removal          4 sources: google_places, osm, serper, yelp
      ! 2 different phone numbers reported
  78  Bay State Hauling           2 sources: google_places, yelp
  57  Quick Haul                  1 source:  serper
```

"Found 60, kept 12" is only trustworthy if the other 48 are inspectable. The
rejected list and the duplicate list are both returned.

---

## Deduplication

Nothing is written until it clears the CRM-wide dedupe check. Three independent
keys, and a hit on any one rejects the lead:

| Key | Catches |
|---|---|
| Phone (last 10 digits) | Reformatting — `(508) 555-1234` vs `+15085551234` |
| Registrable domain | `www` / `http` / path variants of the same site |
| Normalized name + city | `Joe's Barbershop` vs `Joes Barber Shop LLC` |

Corporate suffixes (`LLC`, `Inc`, `Co`), punctuation and word boundaries are all
stripped before comparison. Locality stays in the key so the same trading name
in two towns is not merged.

---

## Other sources worth adding later

Researched but not built, roughly in order of value:

**Newly licensed real estate agents.** Massachusetts DOL publishes license
issue dates in its public *Check a License* database, updated within 24–48 hours
of issuance. There is no bulk API, but the search is public and Firecrawl can
read it. This is the single highest-value untapped source in the taxonomy — a
newly licensed agent has a commission budget, no brand, and no marketing support
from their brokerage. RI and CT publish equivalents.

**New business registrations.** The MA Secretary of the Commonwealth
Corporations Division search is free and public — around 30,000 new entities a
year. No bulk download or API, so it needs scraping. A business registered last
month needs everything.

**Building permits.** Many MA municipalities publish permit data on open-data
portals. A contractor pulling permits is actively working and has cash flow —
a much better signal than merely existing.

**Openmart / Outscraper.** Commercial aggregators with 200M+ records sourced
from registrations, tax filings and Maps. Paid, but no restrictive storage terms
— relevant because Google's terms limit what you may cache.

---

## Adding a source

Sources are self-contained. Subclass `Source`, implement `_search`, register it:

```python
class MySource(Source):
    name = "mysource"
    trust = 0.75
    env_key = "MYSOURCE_API_KEY"

    def _search(self, term, city, state, limit):
        ...
        return [Candidate(business_name=..., phone=..., website=...)]

register(MySource())
```

The base class handles normalization, directory filtering, and error isolation —
a source that throws is logged and skipped, never taking down the run. Nothing
else in the pipeline changes.

Files: `leadgen/research/sources/` · `leadgen/research/consensus.py` ·
`leadgen/research/discovery.py`
