"""
Model Room: Acceleration Screen, Phase 1 (Polygon, reported-only)

Runs entirely on Polygon's prices + financials, which your plan includes.
No analyst data (your plan returned 403/404 on the Benzinga ratings/estimates
endpoints), so the engine uses the two reported signals that are its core:

  A. Sequential revenue acceleration  (YoY-of-YoY, from quarterly financials)
  B. Earnings surprise proxy          (EPS growth + margin trend, reported)

Quality gates and ranking run on the same financials endpoint. The estimates
snapshot is omitted because there are no estimates to snapshot; if you later
add Polygon's analyst add-on, the revision overlay slots back in.

Dependencies: requests, pandas  ->  pip install requests pandas
Key: POLYGON_API_KEY (already in your GitHub secrets).

NOTE: field paths reflect the live JSON your check.py returned. If Polygon
shifts the schema, every path lives in the GETTERS section below.
"""

import os
import json
import time
import logging
from datetime import datetime

import requests
import pandas as pd

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------

API_KEY = os.environ.get("POLYGON_API_KEY", "")
BASE = "https://api.polygon.io"

# Universe filters
MIN_MARKET_CAP = 1_000_000_000          # $1B
EXCLUDED_SECTORS_SIC = {                # coarse SIC-prefix exclusions
    "49",   # utilities (electric, gas, water, sanitary)
    "2836", # biological products
    "8731", # commercial physical & biological research
}
# Polygon gives SIC codes, not GICS sectors. We exclude utilities and the
# biotech-ish SIC buckets. Refine once you see what the universe returns.

WEIGHTS = {"A": 0.60, "B": 0.40}        # reported core only
MIN_QUARTERS = 6                        # need q0..q-5 for YoY-of-YoY
TOP_N = 25

OUT_DIR = "acceleration_output"         # separate from ./dashboard

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("accel")


# ----------------------------------------------------------------------
# Polygon request helper
# ----------------------------------------------------------------------

def poly_get(url, params=None, retries=3, pause=0.2):
    params = dict(params or {})
    params["apiKey"] = API_KEY
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 200:
                time.sleep(pause)
                return r.json()
            if r.status_code in (429, 503):
                time.sleep(2 ** attempt)
                continue
            return None
        except requests.RequestException:
            time.sleep(1)
    return None


# ----------------------------------------------------------------------
# GETTERS  (every Polygon field path lives here)
# ----------------------------------------------------------------------

def get_quarterly_financials(ticker, limit=8):
    """Return quarterly financial records, newest first."""
    url = f"{BASE}/vX/reference/financials"
    data = poly_get(url, {"ticker": ticker, "timeframe": "quarterly",
                          "order": "desc", "sort": "period_of_report_date",
                          "limit": limit})
    if not data or "results" not in data:
        return []
    return data["results"]

def _nested(record, *path):
    """Safely walk record['financials'][a][b]['value']."""
    node = record.get("financials", {})
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    if isinstance(node, dict):
        return node.get("value")
    return None

def rev_of(record):
    # income_statement.revenues.value
    return _nested(record, "income_statement", "revenues")

def eps_of(record):
    # diluted EPS; fall back to basic
    v = _nested(record, "income_statement", "diluted_earnings_per_share")
    if v is None:
        v = _nested(record, "income_statement", "basic_earnings_per_share")
    return v

def gross_profit_of(record):
    return _nested(record, "income_statement", "gross_profit")


def get_overview(ticker):
    url = f"{BASE}/v3/reference/tickers/{ticker}"
    data = poly_get(url)
    return (data or {}).get("results")

def get_last_price(ticker):
    url = f"{BASE}/v2/aggs/ticker/{ticker}/prev"
    data = poly_get(url)
    res = (data or {}).get("results")
    if res and isinstance(res, list):
        return res[0].get("c")   # previous close
    return None


# ----------------------------------------------------------------------
# universe = ["PAYX", "STZ", "KMB", "CWT", "BCRX"]
# ----------------------------------------------------------------------

def build_universe(max_pages=20):
    """Page through active US common stocks."""
    url = f"{BASE}/v3/reference/tickers"
    params = {"market": "stocks", "type": "CS", "active": "true",
              "limit": 1000}
    tickers, pages = [], 0
    while url and pages < max_pages:
        data = poly_get(url, params if pages == 0 else None)
        if not data or "results" not in data:
            break
        for row in data["results"]:
            tickers.append(row.get("ticker"))
        url = data.get("next_url")
        pages += 1
    log.info("raw universe: %d tickers", len(tickers))
    return [t for t in tickers if t]


# ----------------------------------------------------------------------
# Signals
# ----------------------------------------------------------------------

def signal_A_acceleration(quarters):
    if len(quarters) < MIN_QUARTERS:
        return None
    try:
        rev = [float(rev_of(q)) for q in quarters[:6]]
    except (TypeError, ValueError):
        return None
    if any(r is None for r in rev) or rev[4] <= 0 or rev[5] <= 0:
        return None
    yoy_curr = rev[0] / rev[4] - 1
    yoy_prior = rev[1] / rev[5] - 1
    return {"accel": yoy_curr - yoy_prior,
            "yoy_curr": yoy_curr, "yoy_prior": yoy_prior}

def signal_B_eps_and_margin(quarters):
    """Reported surprise proxy: YoY EPS growth + gross-margin trend.

    Without analyst estimates there is no true surprise, so we proxy
    'positive earnings momentum' with YoY diluted-EPS growth and an
    improving gross margin, both reported.
    """
    if len(quarters) < 5:
        return None
    try:
        eps0 = eps_of(quarters[0]); eps4 = eps_of(quarters[4])
        rev0 = rev_of(quarters[0]); rev1 = rev_of(quarters[1])
        gp0 = gross_profit_of(quarters[0]); gp1 = gross_profit_of(quarters[1])
    except (TypeError, ValueError):
        return None
    if None in (eps0, eps4, rev0, rev1, gp0, gp1) or eps4 == 0 or rev0 == 0 or rev1 == 0:
        return None
    eps_growth = (eps0 - eps4) / abs(eps4)
    margin0 = gp0 / rev0
    margin1 = gp1 / rev1
    margin_trend = margin0 - margin1
    # blended score: EPS growth carries it, margin trend confirms
    score = eps_growth + (margin_trend * 2.0)
    return {"score": score, "eps_growth": eps_growth,
            "margin": margin0, "margin_trend": margin_trend}


# ----------------------------------------------------------------------
# Gates
# ----------------------------------------------------------------------

def excluded_by_sic(overview):
    sic = str((overview or {}).get("sic_code") or "")
    if not sic:
        return False
    for bad in EXCLUDED_SECTORS_SIC:
        if sic.startswith(bad):
            return True
    return False

def passes_gates(quarters, overview):
    # market cap
    mc = (overview or {}).get("market_cap") or 0
    if mc < MIN_MARKET_CAP:
        return False, "market_cap"
    # sector exclusion
    if excluded_by_sic(overview):
        return False, "excluded_sic"
    # margin floor and trend (latest vs prior quarter)
    try:
        rev0 = rev_of(quarters[0]); rev1 = rev_of(quarters[1])
        gp0 = gross_profit_of(quarters[0]); gp1 = gross_profit_of(quarters[1])
        if None in (rev0, rev1, gp0, gp1) or rev0 <= 0 or rev1 <= 0:
            return False, "no_margin"
        m0, m1 = gp0 / rev0, gp1 / rev1
        if m0 <= 0 or m0 < m1:
            return False, "margin_floor_or_trend"
    except (TypeError, ValueError, IndexError):
        return False, "no_margin"
    return True, "ok"


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    if not API_KEY:
        raise SystemExit("POLYGON_API_KEY not set")

    universe = build_universe()
    records = []

    for i, sym in enumerate(universe):
        if i % 100 == 0:
            log.info("processing %d / %d  (survivors: %d)",
                     i, len(universe), len(records))

        quarters = get_quarterly_financials(sym)
        if len(quarters) < MIN_QUARTERS:
            continue
        overview = get_overview(sym)

        ok, reason = passes_gates(quarters, overview)
        if not ok:
            continue

        A = signal_A_acceleration(quarters)
        B = signal_B_eps_and_margin(quarters)
        if A is None or B is None:
            continue

        records.append({
            "ticker": sym,
            "marketCap": (overview or {}).get("market_cap"),
            "sic": (overview or {}).get("sic_code"),
            "accel": A["accel"],
            "yoy_curr": A["yoy_curr"],
            "yoy_prior": A["yoy_prior"],
            "eps_score": B["score"],
            "eps_growth": B["eps_growth"],
            "margin": B["margin"],
            "margin_trend": B["margin_trend"],
        })

    if not records:
        log.error("no survivors; check field paths in GETTERS")
        return

    df = pd.DataFrame(records)
    df["A_pct"] = df["accel"].rank(pct=True)
    df["B_pct"] = df["eps_score"].rank(pct=True)
    df["compositeScore"] = WEIGHTS["A"] * df["A_pct"] + WEIGHTS["B"] * df["B_pct"]
    df = df.sort_values("compositeScore", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    df["runDate"] = datetime.utcnow().date().isoformat()

    os.makedirs(OUT_DIR, exist_ok=True)
    cols = ["rank", "ticker", "compositeScore", "accel", "yoy_curr",
            "yoy_prior", "eps_growth", "margin", "margin_trend",
            "marketCap", "sic", "runDate"]
    df[cols].head(TOP_N).to_csv(f"{OUT_DIR}/acceleration_queue.csv", index=False)
    df[cols].to_json(f"{OUT_DIR}/acceleration_full.json", orient="records", indent=2)
    log.info("done. wrote top %d of %d survivors", TOP_N, len(df))


if __name__ == "__main__":
    main()
