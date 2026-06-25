"""
Model Room: Acceleration Screen, Phase 1 (Polygon, reported-only)

LIVE-READY: reads the S&P 1500 universe from sp1500.csv and paces itself
to the Polygon rate limit. To revert to a quick 5-ticker test, flip the
TEST/LIVE switch in main().

Signals (reported-only, your Polygon plan covers these):
  A. Sequential revenue acceleration (YoY-of-YoY) with base-effect fix
  B. Earnings momentum proxy (reported YoY EPS growth + gross-margin trend)

Files in repo:
  acceleration_screen.py   (this file)
  sp1500.csv               (universe: one column 'ticker')
  acceleration_output/     (written by the run)

Dependencies: requests, pandas
Key: POLYGON_API_KEY (GitHub secret).
"""

import os
import csv
import time
import logging
from datetime import datetime, timezone

import requests
import pandas as pd

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------

API_KEY = os.environ.get("POLYGON_API_KEY", "")
BASE = "https://api.polygon.io"
UNIVERSE_FILE = "sp1500.csv"

MIN_MARKET_CAP = 1_000_000_000
EXCLUDED_SECTORS_SIC = {"49", "2836", "8731"}   # utilities, biologics, research

MIN_CURRENT_GROWTH = 0.03     # must be growing > 3% YoY now to qualify
NEG_BASE_DAMPING = 0.25       # damp acceleration off a negative prior-year base

WEIGHTS = {"A": 0.60, "B": 0.40}
MIN_QUARTERS = 6
TOP_N = 25
OUT_DIR = "acceleration_output"

# Rate limiting. Polygon lower tiers allow ~5 calls/min; paid tiers far more.
# CALLS_PER_MIN sets the pace. If your plan is unlimited, raise it high.
# This screen makes 2 calls per ticker (financials + overview).
CALLS_PER_MIN = 100           # conservative default; safe to raise on paid tiers
_MIN_INTERVAL = 60.0 / max(CALLS_PER_MIN, 1)
_last_call = [0.0]

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("accel")


# ----------------------------------------------------------------------
# Polygon request helper (rate-paced)
# ----------------------------------------------------------------------

def poly_get(url, params=None, retries=4):
    params = dict(params or {})
    params["apiKey"] = API_KEY
    # pace to the configured rate
    wait = _MIN_INTERVAL - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=30)
            _last_call[0] = time.time()
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 503):     # throttled, back off and retry
                time.sleep(min(2 ** attempt * 5, 60))
                continue
            return None
        except requests.RequestException:
            time.sleep(2)
    return None


# ----------------------------------------------------------------------
# Getters (all Polygon field paths live here)
# ----------------------------------------------------------------------

def get_quarterly_financials(ticker, limit=8):
    url = f"{BASE}/vX/reference/financials"
    data = poly_get(url, {"ticker": ticker, "timeframe": "quarterly",
                          "order": "desc", "sort": "period_of_report_date",
                          "limit": limit})
    if not data or "results" not in data:
        return []
    return data["results"]

def _nested(record, *path):
    node = record.get("financials", {})
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    if isinstance(node, dict):
        return node.get("value")
    return None

def rev_of(record):
    return _nested(record, "income_statement", "revenues")

def eps_of(record):
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


# ----------------------------------------------------------------------
# Universe
# ----------------------------------------------------------------------

def load_universe():
    if not os.path.exists(UNIVERSE_FILE):
        raise SystemExit(f"{UNIVERSE_FILE} not found in repo")
    tickers = []
    with open(UNIVERSE_FILE) as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = (row.get("ticker") or "").strip().upper()
            if t:
                tickers.append(t)
    log.info("loaded %d tickers from %s", len(tickers), UNIVERSE_FILE)
    return tickers


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
    if rev[4] <= 0 or rev[5] <= 0:
        return None
    yoy_curr = rev[0] / rev[4] - 1
    yoy_prior = rev[1] / rev[5] - 1
    if yoy_curr < MIN_CURRENT_GROWTH:
        return None
    raw_accel = yoy_curr - yoy_prior
    accel = raw_accel * NEG_BASE_DAMPING if yoy_prior < 0 else raw_accel
    return {"accel": accel, "raw_accel": raw_accel,
            "yoy_curr": yoy_curr, "yoy_prior": yoy_prior}

def signal_B_eps_and_margin(quarters):
    if len(quarters) < 5:
        return None
    try:
        eps0 = eps_of(quarters[0]); eps4 = eps_of(quarters[4])
        rev0 = rev_of(quarters[0]); rev1 = rev_of(quarters[1])
        gp0 = gross_profit_of(quarters[0]); gp1 = gross_profit_of(quarters[1])
    except (TypeError, ValueError):
        return None
    if None in (eps0, eps4, rev0, rev1, gp0, gp1):
        return None
    if eps4 == 0 or rev0 == 0 or rev1 == 0:
        return None
    eps_growth = (eps0 - eps4) / abs(eps4)
    margin0 = gp0 / rev0
    margin1 = gp1 / rev1
    margin_trend = margin0 - margin1
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
    return any(sic.startswith(bad) for bad in EXCLUDED_SECTORS_SIC)

def passes_gates(quarters, overview):
    mc = (overview or {}).get("market_cap") or 0
    if mc < MIN_MARKET_CAP:
        return False, "market_cap"
    if excluded_by_sic(overview):
        return False, "excluded_sic"
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

    # ---- TEST / LIVE switch -------------------------------------------
    # LIVE mode (active): full S&P 1500 from file.
    universe = load_universe()
    # TEST mode: comment the line above and uncomment the line below.
    # universe = ["PAYX", "STZ", "KMB", "CWT", "BCRX"]
    # -------------------------------------------------------------------

    total = len(universe)
    records = []
    for i, sym in enumerate(universe):
        if i % 50 == 0:
            log.info("processing %d / %d  (survivors so far: %d)", i, total, len(records))

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
            "raw_accel": A["raw_accel"],
            "yoy_curr": A["yoy_curr"],
            "yoy_prior": A["yoy_prior"],
            "eps_score": B["score"],
            "eps_growth": B["eps_growth"],
            "margin": B["margin"],
            "margin_trend": B["margin_trend"],
        })

    log.info("scan complete: %d survivors of %d", len(records), total)
    if not records:
        log.error("no survivors; check field paths, gates, or universe file")
        return

    df = pd.DataFrame(records)
    df["A_pct"] = df["accel"].rank(pct=True)
    df["B_pct"] = df["eps_score"].rank(pct=True)
    df["compositeScore"] = WEIGHTS["A"] * df["A_pct"] + WEIGHTS["B"] * df["B_pct"]
    df = df.sort_values("compositeScore", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    df["runDate"] = datetime.now(timezone.utc).date().isoformat()

    os.makedirs(OUT_DIR, exist_ok=True)
    cols = ["rank", "ticker", "compositeScore", "accel", "raw_accel",
            "yoy_curr", "yoy_prior", "eps_growth", "margin", "margin_trend",
            "marketCap", "sic", "runDate"]
    df[cols].head(TOP_N).to_csv(f"{OUT_DIR}/acceleration_queue.csv", index=False)
    df[cols].to_json(f"{OUT_DIR}/acceleration_full.json", orient="records", indent=2)
    log.info("done. wrote top %d and full list of %d survivors", TOP_N, len(df))


if __name__ == "__main__":
    main()
