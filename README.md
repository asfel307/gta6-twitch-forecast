# GTA VI Twitch CCU forecast — make.fun entry

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/asfel307/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/asfel307/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts the Twitch concurrent-viewer count of Grand Theft Auto VI for hours
2–24 of its release day (2026-11-19 UTC), as five quantiles an hour, from the
case's hour-1 print and the launch-day shapes of past big game launches
(the case's `comparables`).

## Method (`main.py`, Python 3.13 stdlib only)

Per forecast hour, each comparable gives a log-ratio curve
`ln(viewers_h / viewers_1)` on its own release day. The forecast blends two
views of that curve 50/50 in log space:

1. a global OLS line of log-ratio on `ln(hour-1 print)` — big launches peak
   barely above hour 1, small ones peak many times above it;
2. the median log-ratio of the 15 comparables nearest in `ln(hour-1 print)`,
   which follows the curve's bend where the line overshoots.

Spread: the median absolute deviation of those 15 neighbours' log-ratios
(×1.4826), floored at 0.20 and capped at 1.20 log units; quantiles are
`median * exp(z_tau * sigma)`. Falls back to a widening persistence spread
when too few comparables have data for an hour. Deterministic, no network,
~0.1 s per case.

## Local practice score

Scored against the practice answers (SullyGnome hourly averages, re-fetched
via the kit's `input/NOTICE.txt` URLs; the kit ships no local grader —
`grade-local` reports the scorer is server-only, and the baseline check below
reproduces the kit's published 0.387 exactly, which validates the answers):

| case | loss | typical miss | 90% coverage |
|------|------|--------------|--------------|
| p00 Marvel's Wolverine | 0.222 | 40.0% | 0.87 |
| p01 Red Dead Redemption 2 | 0.194 | 38.9% | 0.96 |
| p02 God of War Ragnarök | 0.183 | 38.9% | 1.00 |
| p03 Marvel's Spider-Man 2 | 0.202 | 31.6% | 0.87 |
| **mean** | **0.201** | | |

House persistence baseline: **0.387** (typical miss 82.8%, coverage 0.783).
The house-model forecast's practice loss is not published in the kit.

## Run locally

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=out python3 main.py
```
