"""gta6-twitch-ccu-forecast-01 entry (Python 3.13, standard library only).

Forecasts the Twitch concurrent-viewer count of Grand Theft Auto VI for hours
2..24 of its release day (2026-11-19 UTC) from the case's hour-1 print and the
launch-day shapes of past big game launches (the case's `comparables`).

Method, per forecast hour h:
  - Each comparable gives a log-ratio curve: ln(viewers_h / viewers_1) on its
    own release day, where viewers_1 is that launch's hour-1 print. The
    ratio curve is the launch-day shape; hour 1 anchors the scale.
  - Two views of that curve are blended 50/50 in log space:
      (a) a global OLS line of log-ratio on ln(hour-1 print): big launches
          peak barely above hour 1, small ones peak many times above it
          (the peak ratio's correlation with log10(hour-1) is about -0.94);
      (b) the median log-ratio of the 15 comparables nearest in ln(hour-1
          print), which follows the curve's bend where the line overshoots.
  - Spread: the median absolute deviation of those 15 neighbours' log-ratios
    (x1.4826), floored at 0.20 and capped at 1.20 log units; quantiles are
    median * exp(z_tau * sigma) with the standard normal z at each level.
  - Falls back to a widening persistence spread when too few comparables
    have data for an hour, and to the last pre-release hourly mean (else 1)
    when the case carries no hour-1 print.

Deterministic: no randomness, no clock, no network; the same case file always
writes the same bytes. One case runs in well under a second.

How the grader runs it: `python3 -P -s /bot/main.py` (PYTHONHASHSEED=0) in
python:3.13-slim, standard library only: no network, no pip packages. -P
keeps this file's directory OFF sys.path, so a module shipped beside main.py
imports only after the sys.path line below, which puts the directory first;
-s drops user site-packages.

What an entry must do:
  - read every <id>.in in the input directory (the grader runs one case at a
    time, with only that case's file there): JSON {"schema":
    "makefun/twitch-ccu-case/v1", "id", "game", "day_start", "checkpoint",
    "levels", "known", "forecast", "history", "history_hourly", "streams",
    "categories_hourly", "comparables", "notes"}, where `known` holds hour 1's
    print {hour: 1, from, until, viewers, channels, reads} and `forecast`
    lists the hours to forecast, 2..24;
  - write <id>.out to the output directory: {"hours": [{"hour": 2, "q":
    [q05, q25, q50, q75, q95]}, ...]}, exactly 23 rows, hours 2..24 each once,
    no other key, each q five finite numbers above 0 and at most 1e9 (viewers;
    fractions allowed), non-decreasing; at most 65,536 bytes. Anything else is
    an invalid case, scored as if every quantile equalled hour 1's print, and
    an entry with an invalid case takes no prize.

Outside the grader's container, MAKEFUN_INPUT_DIR and MAKEFUN_OUTPUT_DIR
stand in for /input and /output:
    mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so `import model` finds a model.py shipped beside this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level.
Z = [-1.645, -0.674, 0, 0.674, 1.645]

# Blend weight of the global log-linear fit vs the local (nearest-neighbour)
# median, in log space. 0.5 sits in the middle of a flat plateau: practice
# loss 0.198-0.207 for weights 0.4-0.7, against the house baseline's 0.387.
W_OLS = 0.5
# Neighbours used for the local median and the spread.
K_NEIGHBOURS = 15
# Spread (log units) floor and cap.
SIGMA_FLOOR = 0.20
SIGMA_CAP = 1.20
# The persistence fallback's spread growth, in log units per sqrt hour.
FALLBACK_SIGMA = 0.15
# Safety rails on the predicted log-ratio (ratio 0.1x to 100x hour 1).
LOG_RATIO_MIN = math.log(0.1)
LOG_RATIO_MAX = math.log(100.0)
# A comparable needs at least this many usable points to be fitted at all.
MIN_POINTS = 5


def round2(x: float) -> float | int:
    """x rounded to 2 decimals, half up, as JavaScript's Math.round(x * 100) / 100 rounds it.

    A whole number comes back as an int, so json.dumps writes 1240 where JavaScript writes 1240 (not 1240.0).
    """
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def median(values):
    """The median of a non-empty list of numbers (deterministic)."""
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def parse_time(text):
    """An ISO 8601 UTC timestamp from the case files, as a datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def norm_ppf(p):
    """The standard normal's quantile at p (Acklam's rational approximation).

    Only used when a case asks for levels other than the contest's five; for
    those the Z table above applies. Accurate to ~1e-9, deterministic.
    """
    a = [-3.969683028665376e+01, 2.209460984245205e+02,
         -2.759285984469534e+02, 1.383577518672690e+02,
         -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02,
         -1.556989798598866e+02, 6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01,
         2.445134137142996e+00, 3.754408661907416e+00]
    p_low = 0.02425
    p_high = 1 - p_low
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
            (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
        ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)


def ols(xs, ys):
    """Least-squares line y = a + b*x; returns (a, b)."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return my, 0.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - b * mx, b


def comparable_curves(case):
    """Each comparable's release-day hourly viewers, keyed by hour 1..24.

    Only comparables with a positive hour-1 print count: the log-ratio curve
    is undefined without one. A comparable whose release day is not in its
    hourly data (e.g. the GTA VI category's own pre-release history) drops
    out here on its own.
    """
    curves = []
    for comp in case.get("comparables") or []:
        try:
            day_start = parse_time(comp["day_start"])
        except (KeyError, TypeError, ValueError):
            continue
        by_hour = {}
        for row in comp.get("hourly") or []:
            try:
                viewers = row["viewers"]
                hour = int((parse_time(row["from"]) - day_start).total_seconds() // 3600) + 1
            except (KeyError, TypeError, ValueError):
                continue
            if 1 <= hour <= 24 and viewers is not None and viewers > 0:
                by_hour[hour] = viewers
        if 1 in by_hour:
            curves.append(by_hour)
    return curves


def hour_forecast(p1, hour, curves, z_values):
    """The five quantiles of hour `hour`'s count, given hour-1 print p1."""
    points = []
    for by_hour in curves:
        if hour in by_hour:
            points.append((math.log(by_hour[1]), math.log(by_hour[hour] / by_hour[1])))
    if len(points) < MIN_POINTS:
        # Too few launches say anything about this hour: persistence with a
        # spread that widens like a random walk's in log space.
        sigma = FALLBACK_SIGMA * math.sqrt(hour - 1)
        return [round2(p1 * math.exp(z * sigma)) for z in z_values]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    # (a) Global log-linear fit of the log-ratio on ln(hour-1 print).
    a, b = ols(xs, ys)
    m_ols = a + b * math.log(p1)
    # (b) Local median of the nearest launches in ln(hour-1 print), and the
    # spread from their dispersion around it.
    nearest = sorted(points, key=lambda p: (abs(p[0] - math.log(p1)), p[0]))[:K_NEIGHBOURS]
    near_ys = [p[1] for p in nearest]
    m_knn = median(near_ys)
    sigma = 1.4826 * median([abs(y - m_knn) for y in near_ys])
    sigma = min(SIGMA_CAP, max(SIGMA_FLOOR, sigma))
    # Blend the two medians in log space, then clip to the safety rails.
    m = W_OLS * m_ols + (1.0 - W_OLS) * m_knn
    m = min(LOG_RATIO_MAX, max(LOG_RATIO_MIN, m))
    quantiles = [round2(p1 * math.exp(m + z * sigma)) for z in z_values]
    quantiles = [max(1.0, min(1e9, q)) for q in quantiles]
    for i in range(1, len(quantiles)):
        quantiles[i] = max(quantiles[i], quantiles[i - 1])
    return quantiles


def hour1_print(case):
    """Hour 1's print, with fallbacks when the case carries none."""
    for row in case.get("known") or []:
        if row.get("hour") == 1 and row.get("viewers"):
            return max(1.0, float(row["viewers"]))
    hourly = case.get("history_hourly") or []
    if hourly:
        last = hourly[-1].get("viewers")
        if last:
            return max(1.0, float(last))
    return 1.0


def forecast_case(case, name):
    levels = case.get("levels") or LEVELS
    if list(levels) == list(LEVELS):
        z_values = Z
    else:
        z_values = [norm_ppf(float(tau)) for tau in levels]
    p1 = hour1_print(case)
    curves = comparable_curves(case)
    hours = []
    for row in sorted(case["forecast"], key=lambda r: r["hour"]):
        hour = row["hour"]
        hours.append({"hour": hour, "q": hour_forecast(p1, hour, curves, z_values)})
    return {"hours": hours}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
