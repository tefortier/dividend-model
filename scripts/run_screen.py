"""
No Excuses — Dividend Value Model
Weekly screener: Dividend Achievers universe
Signals: 10-year yield percentile + Weinstein Stage Analysis
Runs every Sunday evening via GitHub Actions
Output: data/dividend_screen.json
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta, date
from typing import Optional
import requests
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

POLYGON_API_KEY = os.environ["POLYGON_API_KEY"]
BASE_URL = "https://api.polygon.io"

# Full Dividend Achievers universe (Nasdaq DAAARP constituents, 10+ consecutive years of increases)
# Update this list annually as constituents change
DIVIDEND_ACHIEVERS = [
    "ABM","ABT","ADM","AFL","ADP","AEP","AIZ","ALB","AMAT","AME",
    "AMP","AMT","AMCR","AON","APD","ATO","AVY","AXP","BAC","BCE",
    "BDX","BEN","BF.B","BKH","BLK","BMI","BRO","BSX","CAH","CAT",
    "CB","CBSH","CHRW","CI","CINF","CL","CLX","CMS","CNI","CNP",
    "CPB","CPKF","CSL","CTAS","CTL","CVX","D","DE","DGX","DHR",
    "DLR","DOV","DRI","DTE","DTN","ECL","ED","EFX","EIX","EMN",
    "EMR","ENB","ESS","ETN","EV","EXC","EXPD","F","FDS","FHN",
    "FLIC","FNB","FRT","GD","GGG","GHC","GPC","GWW","HAS","HIG",
    "HRL","HSY","IBM","IEX","ITW","JNJ","JPM","K","KEY","KIM",
    "KMB","KO","L","LEG","LIN","LMT","LOW","LYB","MCD","MCO",
    "MDT","MKC","MMC","MMM","MO","MPC","MSA","MSI","MTB","NDSN",
    "NEE","NFG","NI","NNN","NOC","NUE","NWN","O","OGE","OLD",
    "ORI","ORCL","OZK","PAYX","PEG","PEP","PFE","PG","PH","PKG",
    "PNR","PNW","PPG","PPL","PRU","PSA","RLI","ROP","RPM","RTX",
    "SBUX","SCL","SEIC","SHW","SJM","SNA","SNV","SO","SON","SWK",
    "SYK","SYY","T","TGT","TJX","TRMK","TRV","TSN","UGI","UNH",
    "USB","VFC","VZ","WAT","WBA","WEC","WM","WMT","WST","XOM",
    "YORW","ABM","ABT","ACN","AFL","AJG","AMP","AOS","APH","ATO",
    "AVGO","AVY","AXS","BCO","BFAM","BRC","BRO","CASS","CBSH",
    "CFR","CHD","CHCO","CINF","CL","CLDT","CMP","CNO","CPK","CSX",
    "CTXS","DCI","DGII","DOV","EV","EXPD","FDS","FFIN","FLO","GD",
    "GHC","GSBC","HRL","HSBCP","HTLF","IEX","IIPR","JACK","JKHY",
    "KMB","LANC","LECO","LEG","MGRC","MGEE","MSA","MSEX","NCR",
    "NDSN","NNN","NUE","OGE","ORI","PBCT","PH","PKOH","PNR","POR",
    "PRGO","RJF","RLI","ROST","SAFE","SCL","SEIC","SJW","SNA",
    "SRCE","STE","SWK","TRMK","TTC","UGI","UNF","UMBF","UVSP",
    "WAFD","WBS","WDFC","WRB","WSO","YORW"
]

# Deduplicate
TICKERS = sorted(set(DIVIDEND_ACHIEVERS))

STAGE_WINDOW = 30       # weeks for Weinstein MA
YIELD_LOOKBACK = 520    # weeks (~10 years)
RATE_LIMIT_DELAY = 0.25 # seconds between Polygon calls (stay within free tier limits)


def polygon_get(path: str, params: dict) -> Optional[dict]:
    """Single Polygon API call with basic retry."""
    params["apiKey"] = POLYGON_API_KEY
    url = f"{BASE_URL}{path}"
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 429:
                log.warning("Rate limited, sleeping 60s")
                time.sleep(60)
                continue
            if r.status_code == 200:
                return r.json()
            log.warning(f"HTTP {r.status_code} for {path}")
            return None
        except Exception as e:
            log.error(f"Request error (attempt {attempt+1}): {e}")
            time.sleep(2)
    return None


def get_weekly_closes(ticker: str, years: int = 11) -> list[dict]:
    """Pull weekly OHLCV bars from Polygon for the last N years."""
    end = date.today()
    start = end - timedelta(weeks=years * 52)
    results = []
    url = f"/v2/aggs/ticker/{ticker}/range/1/week/{start}/{end}"
    params = {"adjusted": "true", "sort": "asc", "limit": 50000}
    data = polygon_get(url, params)
    if data and data.get("results"):
        results = data["results"]
    time.sleep(RATE_LIMIT_DELAY)
    return results


def get_dividends(ticker: str, years: int = 11) -> list[dict]:
    """Pull cash dividend history from Polygon."""
    start = date.today() - timedelta(weeks=years * 52)
    params = {
        "ticker": ticker,
        "ex_dividend_date.gte": str(start),
        "dividend_type": "CD",
        "limit": 1000,
        "sort": "ex_dividend_date",
        "order": "asc"
    }
    data = polygon_get("/v3/reference/dividends", params)
    results = data.get("results", []) if data else []
    time.sleep(RATE_LIMIT_DELAY)
    return results


def get_ticker_details(ticker: str) -> dict:
    """Pull company name, sector, market cap from Polygon."""
    data = polygon_get(f"/v3/reference/tickers/{ticker}", {})
    if data and data.get("results"):
        r = data["results"]
        return {
            "company": r.get("name", ticker),
            "sector": r.get("sic_description", "Unknown"),
            "market_cap": r.get("market_cap", 0),
        }
    time.sleep(RATE_LIMIT_DELAY)
    return {"company": ticker, "sector": "Unknown", "market_cap": 0}


def calc_yield_series(closes: list[dict], dividends: list[dict]) -> list[float]:
    """
    For each weekly close, calculate trailing 12-month dividend yield.
    TTM dividend = sum of all dividends paid in the 52 weeks prior to that date.
    Yield = TTM dividend / close price
    """
    if not closes or not dividends:
        return []

    div_by_date = {}
    for d in dividends:
        ex_date = d.get("ex_dividend_date", "")
        cash = d.get("cash_amount", 0) or 0
        if ex_date:
            div_by_date[ex_date] = div_by_date.get(ex_date, 0) + cash

    yield_series = []
    for bar in closes:
        ts_ms = bar["t"]
        bar_date = datetime.utcfromtimestamp(ts_ms / 1000).date()
        cutoff = bar_date - timedelta(weeks=52)
        ttm_div = sum(
            v for k, v in div_by_date.items()
            if cutoff <= date.fromisoformat(k) <= bar_date
        )
        close = bar["c"]
        if close and close > 0 and ttm_div > 0:
            yield_series.append(ttm_div / close * 100)

    return yield_series


def classify_stage(closes: list[dict]) -> dict:
    """
    Weinstein Stage Analysis using 30-week SMA.
    Returns stage (1-4), 30w MA value, slope direction, and price vs MA.
    """
    if len(closes) < STAGE_WINDOW + 4:
        return {"stage": 0, "stage_label": "Insufficient data", "ma30": None, "price_vs_ma": None}

    prices = [bar["c"] for bar in closes]
    volumes = [bar.get("v", 0) for bar in closes]

    ma30_series = []
    for i in range(STAGE_WINDOW - 1, len(prices)):
        window = prices[i - STAGE_WINDOW + 1: i + 1]
        ma30_series.append(np.mean(window))

    current_price = prices[-1]
    current_ma = ma30_series[-1]
    prev_ma = ma30_series[-5] if len(ma30_series) >= 5 else ma30_series[0]

    ma_slope = (current_ma - prev_ma) / prev_ma * 100 if prev_ma else 0
    price_vs_ma = (current_price - current_ma) / current_ma * 100 if current_ma else 0

    # Volume trend: compare recent 8w avg vs prior 8w avg
    recent_vol = np.mean(volumes[-8:]) if len(volumes) >= 8 else 0
    prior_vol = np.mean(volumes[-16:-8]) if len(volumes) >= 16 else recent_vol
    vol_expanding = recent_vol > prior_vol

    # Stage classification
    if price_vs_ma > -5 and ma_slope > 0.1:
        stage = 2
        stage_label = "Stage 2 — Advance"
    elif price_vs_ma > -8 and -0.1 <= ma_slope <= 0.1:
        if vol_expanding:
            stage = 1
            stage_label = "Stage 1 — Base"
        else:
            stage = 3
            stage_label = "Stage 3 — Top"
    elif price_vs_ma <= -8 or ma_slope < -0.1:
        stage = 4
        stage_label = "Stage 4 — Decline"
    elif ma_slope > 0:
        stage = 2
        stage_label = "Stage 2 — Advance"
    else:
        stage = 1
        stage_label = "Stage 1 — Base"

    return {
        "stage": stage,
        "stage_label": stage_label,
        "ma30": round(current_ma, 2),
        "price_vs_ma": round(price_vs_ma, 2),
        "ma_slope": round(ma_slope, 3),
        "vol_expanding": vol_expanding,
    }


def calc_signal(yield_pct: int, stage: int) -> str:
    """
    Combined signal logic:
    BUY   = yield 80th pct+ AND stage 1 or 2
    AVOID = stage 3 or 4 regardless of yield
    WATCH = yield 60-79th pct AND stage 1 or 2
    HOLD  = everything else
    """
    if stage in (3, 4):
        return "AVOID"
    if yield_pct >= 80 and stage in (1, 2):
        return "BUY"
    if yield_pct >= 60 and stage in (1, 2):
        return "WATCH"
    return "HOLD"


def process_ticker(ticker: str) -> Optional[dict]:
    log.info(f"Processing {ticker}")
    try:
        details = get_ticker_details(ticker)
        closes = get_weekly_closes(ticker, years=11)
        dividends = get_dividends(ticker, years=11)

        if len(closes) < STAGE_WINDOW + 10:
            log.warning(f"{ticker}: insufficient price history ({len(closes)} bars)")
            return None

        if not dividends:
            log.warning(f"{ticker}: no dividend history, skipping")
            return None

        yield_series = calc_yield_series(closes, dividends)
        if len(yield_series) < 52:
            log.warning(f"{ticker}: insufficient yield data ({len(yield_series)} points)")
            return None

        # Use last 10 years (520 weeks) of yield data
        yield_window = yield_series[-YIELD_LOOKBACK:]
        current_yield = yield_window[-1]
        yield_high = max(yield_window)
        yield_low = min(yield_window)
        yield_mean = np.mean(yield_window)
        yield_percentile = int(np.percentile(
            sorted(yield_window),
            [100 * (current_yield - yield_low) / (yield_high - yield_low)]
        )[0]) if yield_high > yield_low else 50

        # Simpler percentile: rank of current yield in the distribution
        yield_percentile = int(
            np.searchsorted(sorted(yield_window), current_yield) / len(yield_window) * 100
        )
        yield_percentile = max(0, min(100, yield_percentile))

        stage_data = classify_stage(closes)
        signal = calc_signal(yield_percentile, stage_data["stage"])

        # 10-year yield history: downsample to ~40 annual/quarterly points for the chart
        step = max(1, len(yield_series) // 40)
        chart_yields = [round(y, 2) for y in yield_series[::step][-40:]]
        chart_labels = []
        total = len(chart_yields)
        start_year = date.today().year - 10
        for i in range(total):
            yr = start_year + int(i / total * 10)
            chart_labels.append(str(yr))

        # Consecutive years of dividend increases (approximated from dividend history)
        streak = estimate_streak(dividends)

        return {
            "ticker": ticker,
            "company": details["company"],
            "sector": simplify_sector(details["sector"]),
            "currentYield": round(current_yield, 2),
            "yieldHigh": round(yield_high, 2),
            "yieldLow": round(yield_low, 2),
            "yieldMean": round(yield_mean, 2),
            "percentile": yield_percentile,
            "stage": stage_data["stage"],
            "stageLabel": stage_data["stage_label"],
            "ma30": stage_data["ma30"],
            "priceVsMa": stage_data["price_vs_ma"],
            "maSlope": stage_data["ma_slope"],
            "signal": signal,
            "streak": streak,
            "chartYields": chart_yields,
            "chartLabels": chart_labels,
            "lastUpdated": date.today().isoformat(),
        }

    except Exception as e:
        log.error(f"{ticker} failed: {e}")
        return None


def estimate_streak(dividends: list[dict]) -> int:
    """
    Estimate consecutive years of dividend growth.
    Groups dividends by year, compares annual totals.
    """
    if not dividends:
        return 0
    annual = {}
    for d in dividends:
        yr = d.get("ex_dividend_date", "")[:4]
        if yr:
            annual[yr] = annual.get(yr, 0) + (d.get("cash_amount", 0) or 0)
    years = sorted(annual.keys())
    streak = 0
    for i in range(len(years) - 1, 0, -1):
        if annual[years[i]] > annual[years[i - 1]]:
            streak += 1
        else:
            break
    return streak


def simplify_sector(raw: str) -> str:
    """Map Polygon SIC descriptions to clean sector labels."""
    raw = raw.lower()
    mapping = {
        "bank": "Financials", "insurance": "Financials", "invest": "Financials", "finance": "Financials",
        "drug": "Healthcare", "pharma": "Healthcare", "medical": "Healthcare", "health": "Healthcare",
        "oil": "Energy", "gas": "Energy", "petroleum": "Energy", "energy": "Energy",
        "food": "Staples", "beverage": "Staples", "grocery": "Staples", "household": "Staples",
        "retail": "Retail", "store": "Retail",
        "utility": "Utilities", "electric": "Utilities", "water": "Utilities", "power": "Utilities",
        "tech": "Technology", "software": "Technology", "semiconductor": "Technology",
        "industrial": "Industrials", "manufactur": "Industrials", "equipment": "Industrials",
        "real estate": "REITs", "reit": "REITs",
        "telecom": "Telecom", "communicat": "Telecom",
        "material": "Materials", "chemical": "Materials",
    }
    for key, label in mapping.items():
        if key in raw:
            return label
    return "Other"


def main():
    log.info(f"Starting No Excuses Dividend Screen — {date.today()}")
    results = []
    failed = []

    for ticker in TICKERS:
        result = process_ticker(ticker)
        if result:
            results.append(result)
        else:
            failed.append(ticker)
        time.sleep(RATE_LIMIT_DELAY)

    # Summary stats
    buy_count = sum(1 for r in results if r["signal"] == "BUY")
    watch_count = sum(1 for r in results if r["signal"] == "WATCH")
    avoid_count = sum(1 for r in results if r["signal"] == "AVOID")
    avg_pct = round(np.mean([r["percentile"] for r in results]), 1) if results else 0

    output = {
        "meta": {
            "generatedAt": datetime.utcnow().isoformat() + "Z",
            "universe": len(results),
            "buyCount": buy_count,
            "watchCount": watch_count,
            "avoidCount": avoid_count,
            "avgPercentile": avg_pct,
            "lookbackYears": 10,
            "buyThreshold": 80,
            "stageWindow": STAGE_WINDOW,
            "failed": failed,
        },
        "stocks": sorted(results, key=lambda x: x["percentile"], reverse=True)
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "dividend_screen.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    log.info(f"Done. {len(results)} stocks processed. {buy_count} BUY signals. {len(failed)} failed.")
    log.info(f"Output: {out_path}")


if __name__ == "__main__":
    main()
