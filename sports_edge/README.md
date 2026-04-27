# Sports Edge

Daily NBA + MLB betting-edge dashboard. Pulls live DraftKings lines, models its
own projections from free public stats, ranks the top 15 edges per market, logs
every prediction, auto-grades them when games finish, and shows running
calibration.

## Markets covered

**NBA** — player points, player rebounds, player threes, game total
**MLB** — player hits, pitcher strikeouts, moneyline

## Data sources (all free, no key)

- **Odds:** DraftKings public eventgroup/category JSON endpoints
  (`sportsbook-nash.draftkings.com`)
- **NBA stats:** `stats.nba.com` (player game logs + team advanced stats)
- **MLB stats:** `statsapi.mlb.com` (schedule, game logs, splits)

## How it works

```
┌──────────────────┐   ┌────────────────┐   ┌────────────────┐
│ DK odds scraper  │──▶│ Projection     │──▶│ Top-15 ranker  │
│ NBA stats        │──▶│ model (Normal/ │   │ + EV filter    │
│ MLB stats        │──▶│  Poisson)      │   │                │
└──────────────────┘   └────────────────┘   └───────┬────────┘
                                                    │
                       ┌────────────────────────────▼─────────┐
                       │ data/predictions/YYYY-MM-DD.json     │
                       └───────────────┬─────────┬────────────┘
                                       │         │
                            ┌──────────▼──┐   ┌──▼──────────────┐
                            │ Auto-grader │   │ Static dashboard│
                            │ (next day)  │   │ (GitHub Pages)  │
                            └──────┬──────┘   └─────────────────┘
                                   │
                            data/results/ + calibration.json
```

## Layout

```
sports_edge/
├── odds/             DraftKings client + per-league prop scrapers
├── stats/            NBA/MLB free-API clients
├── models/
│   ├── distributions.py    Normal CDF, Poisson tail, EV, Kelly
│   ├── nba_projections.py  pts/reb/3s + team-total models
│   ├── mlb_projections.py  hits/K/ML models
│   └── ranker.py           Top-N per market, positive-EV only
├── grading/grader.py       Auto-grade predictions + roll up calibration
├── pipeline.py             Daily orchestrator
├── web/index.html          Single-file dashboard
├── data/
│   ├── odds/               Daily snapshots per league
│   ├── stats/              Cached stats fetches (one per day)
│   ├── predictions/        Logged picks (one file per day)
│   ├── results/            Graded outcomes (one file per day)
│   └── public/             What the dashboard reads
└── requirements.txt
```

## Run it

```bash
pip install -r sports_edge/requirements.txt
python -m sports_edge.pipeline
```

Outputs land in `sports_edge/data/`. Open `sports_edge/web/index.html` next to
the public JSON files (or use the GitHub Actions workflow which deploys to
Pages automatically).

## GitHub Actions

`.github/workflows/sports-edge.yml` runs the pipeline twice a day
(7am ET and 1pm ET) plus on-demand via "Run workflow". It:

1. Runs `python -m sports_edge.pipeline`
2. Commits new odds/predictions/results JSON back to the branch
3. Bundles the dashboard + JSON into a `site/` folder and deploys to Pages

To enable Pages once: repo Settings → Pages → Source = "GitHub Actions".

## How "self-improving" works

- Every pick is written to `data/predictions/{date}.json` with the model
  probability that produced it.
- Each run of the pipeline first calls the grader, which looks up actual game
  results for any date in the past, marks each pick win/loss/push, and writes
  `data/results/{date}.json`.
- `calibration.json` aggregates Brier score, hit rate, and ROI per market.
- A future weekly job can ingest those results and refit weights (e.g. the
  `0.55 / 0.45` last-10 vs season mix in `nba_projections._project_market`,
  the sigma floors, the home-field bump in `mlb_projections`). The current
  build logs everything needed to do that, but does not yet auto-retrain.

## Honest limits

- The model is intentionally simple (Normal/Poisson with rolling means,
  pace + def adjustments). It will not "beat" sportsbooks consistently. Its
  job is to surface candidate value bets and track its own calibration so
  weights can be tuned over time.
- DraftKings can change endpoint shapes; the scraper matches by label rather
  than ID so it survives minor changes, but a major redesign would break it.
- `stats.nba.com` rate-limits aggressively; the cache in `data/stats/` keeps
  one run per day light. If you re-run repeatedly, expect 429s.
- Odds are point-in-time. They move all day. The pipeline runs twice a day,
  so the dashboard is a snapshot, not a real-time feed.
