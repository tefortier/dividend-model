"""
No Excuses — Dividend Value Model
Weekly screener: Dividend Achievers universe
Signal: 10-year yield percentile (buy zone = 80th percentile+)
Stage Analysis applied manually via TradingView before Smart Money Portfolio inclusion
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

TICKERS = sorted(set(DIVIDEND_ACHIEVERS))

YIELD_LOOKBACK = 520     # weeks (~10 years)
RATE_LIMIT_DELAY = 0.12  # seconds between calls
MAX_RATE_LIMIT_RETRIES = 3


def polygon_get(path: str, params: dict) -> Optional[dict]:
    """Single Polygon API call with retry and rate limit cap."""
    params["apiKey"] = POLYGON_API_KEY
    url = f"{BASE_URL}{path}"
    rate_limit_hits = 0
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 429:
                rate_limit_hits += 1
                if rate_limit_hits >= MAX_RATE_LIMIT_RETRIES:
                    log.warning(f"Rate limit max retries hit for {path}, skipping")
                    return None
                wait = 15 * rate_limit_hits
                log.warning(f"Rate limited, sleeping {wait}s (hit {rate_limit_hits})")
                time.sleep(wait)
                continue
            if r.status_code == 200:
                return r.json()
            log.warning(f"HTTP {r.status_code} for {path}")
            return None
        except requests.exceptions.Timeout:
            log.error(f"Timeout on attempt {attempt+1} for {path}")
            time.sleep(2)
        except Exception as e:
            log.error(f"Request error (attempt {attempt+1}): {e}")
            time.sleep(2)
    return None


def get_weekly_closes(ticker: str, years: int = 11) -> list[dict]:
    """Pull weekly closing prices from Polygon."""
    end = date.today()
    start = end - timedelta(weeks=years * 52)
    url = f"/v2/aggs/ticker/{ticker}/range/1/week/{start}/{end}"
    params = {"adjusted": "true", "sort": "asc", "limit": 50000}
    data = polygon_get(url, params)
    results = data.get("results", []) if data else []
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
    """Pull company name and sector from Polygon."""
    data = polygon_get(f"/v3/reference/tickers/{ticker}", {})
    if data and data.get("results"):
        r = data["results"]
        return {
            "company": r.get("name", ticker),
            "sector": r.get("sic_description", "Unknown"),
        }
    time.sleep(RATE_LIMIT_DELAY)
    return {"company": ticker, "sector": "Unknown"}


def calc_yield_series(closes: list[dict], dividends: list[dict]) -> list[float]:
    """Calculate trailing 12-month yield at each weekly close."""
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


def calc_signal(yield_pct: int) -> str:
    """
    Signal based purely on yield percentile.
    Stage Analysis applied manually via TradingView before Smart Money Portfolio inclusion.
    BUY   = yield 80th percentile+
    WATCH = yield 60-79th percentile
    HOLD  = below 60th percentile
    """
    if yield_pct >= 80:
        return "BUY"
    if yield_pct >= 60:
        return "WATCH"
    return "HOLD"


def estimate_streak(dividends: list[dict]) -> int:
    """Estimate consecutive years of dividend growth from annual totals."""
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


def process_ticker(ticker: str) -> Optional[dict]:
    log.info(f"Processing {ticker}")
    try:
        details = get_ticker_details(ticker)
        closes = get_weekly_closes(ticker, years=11)
        dividends = get_dividends(ticker, years=11)

        if len(closes) < 52:
            log.warning(f"{ticker}: insufficient price history ({len(closes)} bars)")
            return None

        if not dividends:
            log.warning(f"{ticker}: no dividend history, skipping")
            return None

        yield_series = calc_yield_series(closes, dividends)
        if len(yield_series) < 52:
            log.warning(f"{ticker}: insufficient yield data ({len(yield_series)} points)")
            return None

        yield_window = yield_series[-YIELD_LOOKBACK:]
        current_yield = yield_window[-1]
        yield_high = max(yield_window)
        yield_low = min(yield_window)
        yield_mean = np.mean(yield_window)

        yield_percentile = int(
            np.searchsorted(sorted(yield_window), current_yield) / len(yield_window) * 100
        )
        yield_percentile = max(0, min(100, yield_percentile))

        signal = calc_signal(yield_percentile)
        streak = estimate_streak(dividends)

        # Downsample yield history for chart (~40 points)
        step = max(1, len(yield_series) // 40)
        chart_yields = [round(y, 2) for y in yield_series[::step][-40:]]
        total = len(chart_yields)
        start_year = date.today().year - 10
        chart_labels = [str(start_year + int(i / total * 10)) for i in range(total)]

        return {
            "ticker": ticker,
            "company": details["company"],
            "sector": simplify_sector(details["sector"]),
            "currentYield": round(current_yield, 2),
            "yieldHigh": round(yield_high, 2),
            "yieldLow": round(yield_low, 2),
            "yieldMean": round(yield_mean, 2),
            "percentile": yield_percentile,
            "signal": signal,
            "streak": streak,
            "chartYields": chart_yields,
            "chartLabels": chart_labels,
            "lastUpdated": date.today().isoformat(),
        }

    except Exception as e:
        log.error(f"{ticker} failed: {e}")
        return None


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

    buy_count = sum(1 for r in results if r["signal"] == "BUY")
    watch_count = sum(1 for r in results if r["signal"] == "WATCH")
    avg_pct = round(np.mean([r["percentile"] for r in results]), 1) if results else 0

    output = {
        "meta": {
            "generatedAt": datetime.utcnow().isoformat() + "Z",
            "universe": len(results),
            "buyCount": buy_count,
            "watchCount": watch_count,
            "avgPercentile": avg_pct,
            "lookbackYears": 10,
            "buyThreshold": 80,
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
