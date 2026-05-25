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

# Full Dividend Achievers universe (current official constituents, 10+ consecutive years of increases)
# Source: Nasdaq DAAARP index, May 2026. Update annually.
# Non-US listed shares (ASX, MIL, XETR, NSE) excluded — Polygon.io covers US exchanges only.
DIVIDEND_ACHIEVERS = [
    "A", "AAPL", "ABBV", "ABM", "ABT", "ACN", "ADC", "ADI", "ADM", "ADP",
    "AEE", "AEP", "AES", "AFG", "AFL", "AGM", "AGO", "AIT", "AIZ", "AJG",
    "ALB", "ALG", "ALL", "ALLE", "ALRS", "AMGN", "AMP", "AMSF", "AMT", "ANDE",
    "AOS", "APD", "APH", "APOG", "AROW", "ASB", "ASH", "ATO", "ATR", "AUB",
    "AVA", "AVGO", "AVNT", "AVT", "AVY", "AWK", "AWR", "BAC", "BAH", "BANF",
    "BBY", "BC", "BCPC", "BDX", "BEN", "BEP", "BFC", "BHB", "BIP", "BKH",
    "BLK", "BMI", "BMY", "BNY", "BOKF", "BR", "BRC", "BRO", "BWXT", "CAH",
    "CASS", "CASY", "CAT", "CB", "CBOE", "CBSH", "CBT", "CBU", "CCBG", "CDW",
    "CFR", "CGNX", "CHCO", "CHCT", "CHD", "CHDN", "CHE", "CHRW", "CINF", "CIVB",
    "CL", "CLX", "CMCSA", "CME", "CMI", "CMS", "CNO", "CNS", "COR", "COST",
    "CPK", "CSCO", "CSX", "CTAS", "CTBI", "CTRE", "CUBE", "CVX", "CWT", "DCI",
    "DDS", "DGICA", "DGX", "DHI", "DHR", "DKL", "DKS", "DLB", "DOV", "DPZ",
    "DUK", "ECL", "ED", "EFSC", "EGP", "EIX", "ELV", "EMN", "EMR", "ENSG",
    "EPD", "EQIX", "ERIE", "ES", "ESS", "ETN", "ETR", "EVR", "EVRG", "EXPD",
    "EXPO", "FAF", "FAST", "FBIZ", "FCBC", "FDS", "FELE", "FFIN", "FITB", "FIX",
    "FLO", "FNF", "FR", "FRME", "FRT", "FUL", "GABC", "GATX", "GD", "GFF",
    "GGG", "GILD", "GL", "GPC", "GRC", "GS", "GTY", "GWW", "HBCP", "HD",
    "HEI", "HFWA", "HIG", "HII", "HLI", "HMN", "HNI", "HOMB", "HON", "HPQ",
    "HRB", "HRL", "HTO", "HUBB", "HVT", "HWKN", "HY", "IBCP", "IBM", "IBOC",
    "ICE", "IDA", "INDB", "INGR", "INTU", "IOSP", "ITT", "ITW", "JBHT", "JJSF",
    "JKHY", "JNJ", "JPM", "KAI", "KLAC", "KMB", "KO", "KR", "KWR", "LAD",
    "LAND", "LECO", "LFUS", "LHX", "LII", "LIN", "LKFN", "LLY", "LMAT", "LMT",
    "LNN", "LNT", "LOW", "LRCX", "LSTR", "LYB", "MA", "MAA", "MAIN", "MAS",
    "MATW", "MATX", "MBWM", "MCD", "MCHP", "MCK", "MCO", "MDLZ", "MDT", "MET",
    "MGEE", "MGRC", "MKC", "MKTX", "MLM", "MO", "MORN", "MPLX", "MRK", "MRSH",
    "MS", "MSA", "MSCI", "MSEX", "MSFT", "MSI", "MTRN", "MWA", "MZTI", "NBHC",
    "NBTB", "NDAQ", "NDSN", "NEE", "NFG", "NI", "NJR", "NKE", "NNI", "NNN",
    "NOC", "NPO", "NRIM", "NSA", "NSP", "NUE", "NWN", "NXRT", "NXST", "O",
    "OC", "ODC", "OGE", "OGS", "ORCL", "ORI", "ORRF", "OSK", "OTTR", "OZK",
    "PAYX", "PB", "PEBO", "PEG", "PEP", "PFE", "PFG", "PG", "PII", "PLD",
    "PM", "PNC", "PNW", "POOL", "POR", "POWI", "PPG", "PRGO", "PRI", "PRU",
    "PSX", "QCOM", "R", "RBCAA", "REG", "REXR", "RF", "RGA", "RGLD", "RHI",
    "RJF", "RLI", "RMD", "RNR", "ROK", "ROP", "RPM", "RS", "RSG", "RTX",
    "SBUX", "SCL", "SCVL", "SEIC", "SFBS", "SFNC", "SHW", "SIGI", "SJM", "SLGN",
    "SMBC", "SNA", "SO", "SON", "SPGI", "SR", "SRCE", "SRE", "SSB", "SSD",
    "STAG", "STBA", "STE", "STLD", "STT", "STZ", "SWK", "SWKS", "SXI", "SYBT",
    "SYK", "SYY", "TCBK", "TEL", "TGT", "THFF", "THG", "THO", "TKR", "TMP",
    "TNC", "TOWN", "TPL", "TR", "TRN", "TRNO", "TROW", "TRV", "TSCO", "TSN",
    "TT", "TTC", "TTEK", "TXN", "UBSI", "UCB", "UDR", "UFPI", "UHT", "UMBF",
    "UNH", "UNM", "UNP", "UNTY", "UPS", "USB", "UTL", "UVV", "V", "VMC",
    "VZ", "WABC", "WAFD", "WDFC", "WEC", "WLK", "WLY", "WM", "WMS", "WMT",
    "WRB", "WSBC", "WSM", "WSO", "WST", "WTFC", "WTS", "XEL", "XOM", "XYL",
    "YORW", "ZION", "ZTS",
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

    # Stage classification - strict Weinstein rules
    # Stage 2: price ABOVE rising 30w MA. Non-negotiable.
    if price_vs_ma > 0 and ma_slope > 0.1:
        stage = 2
        stage_label = "Stage 2 — Advance"
    # Stage 4: price BELOW declining 30w MA. Non-negotiable.
    elif price_vs_ma < 0 and ma_slope < -0.1:
        stage = 4
        stage_label = "Stage 4 — Decline"
    # Stage 1: price near or above MA, MA flattening after decline (basing)
    elif price_vs_ma > -3 and ma_slope >= -0.1:
        stage = 1
        stage_label = "Stage 1 — Base"
    # Stage 3: price near or below MA, MA flattening or rolling over after advance (topping)
    elif price_vs_ma <= 0 and ma_slope <= 0.1:
        stage = 3
        stage_label = "Stage 3 — Top"
    # Edge case: price above MA but slope not yet rising - late Stage 1
    elif price_vs_ma > 0 and ma_slope <= 0.1:
        stage = 1
        stage_label = "Stage 1 — Base"
    # Fallback
    else:
        stage = 4
        stage_label = "Stage 4 — Decline"

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
