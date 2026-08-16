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
CHART_MAX_POINTS = 120   # ~10 years of monthly points (was 40, which trimmed the chart to ~3 years)


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


def calc_yield_series(closes: list[dict], dividends: list[dict]) -> list[dict]:
    """
    Calculate trailing 12-month yield at each weekly close.
    Returns a list of {"date": ISO string, "yield": float} pairs, oldest first.
    Dates travel with the values now so the chart can never be mislabeled.
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
            yield_series.append({"date": bar_date.isoformat(), "yield": ttm_div / close * 100})

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


def build_chart_series(yield_series: list[dict], max_points: int = CHART_MAX_POINTS) -> tuple[list[float], list[str]]:
    """
    Build the chart's (values, labels) from real dated data.
    One point per calendar month (last observation in that month wins),
    with the most recent actual data point always guaranteed to be last.
    Labels are the real YYYY-MM of each plotted point, never fabricated.
    """
    if not yield_series:
        return [], []

    monthly: dict[str, dict] = {}
    for pt in yield_series:
        key = pt["date"][:7]  # YYYY-MM
        monthly[key] = pt      # last observation in that month wins

    chart_points = list(monthly.values())[-max_points:]

    latest = yield_series[-1]
    if not chart_points or chart_points[-1]["date"] != latest["date"]:
        chart_points.append(latest)
        chart_points = chart_points[-max_points:]

    chart_yields = [round(p["yield"], 2) for p in chart_points]
    chart_labels = [p["date"][:7] for p in chart_points]
    return chart_yields, chart_labels


def process_ticker(ticker: str) -> tuple[Optional[dict], Optional[str]]:
    """Returns (result, failure_reason). Exactly one of the two is None."""
    log.info(f"Processing {ticker}")
    try:
        details = get_ticker_details(ticker)
        closes = get_weekly_closes(ticker, years=11)
        dividends = get_dividends(ticker, years=11)

        if len(closes) < 52:
            reason = f"insufficient price history ({len(closes)} bars)"
            log.warning(f"{ticker}: {reason}")
            return None, reason

        if not dividends:
            reason = "no dividend history returned"
            log.warning(f"{ticker}: {reason}")
            return None, reason

        yield_series = calc_yield_series(closes, dividends)
        if len(yield_series) < 52:
            reason = f"insufficient yield data ({len(yield_series)} points)"
            log.warning(f"{ticker}: {reason}")
            return None, reason

        yield_window_full = yield_series[-YIELD_LOOKBACK:]
        yield_window = [pt["yield"] for pt in yield_window_full]
        current_yield = yield_window[-1]
        yield_high = max(yield_window)
        yield_low = min(yield_window)
        yield_mean = np.mean(yield_window)

        years_of_history = round(len(yield_window_full) / 52, 1)

        yield_percentile = int(
            np.searchsorted(sorted(yield_window), current_yield) / len(yield_window) * 100
        )
        yield_percentile = max(0, min(100, yield_percentile))

        signal = calc_signal(yield_percentile)
        streak = estimate_streak(dividends)

        chart_yields, chart_labels = build_chart_series(yield_window_full)

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
            "yearsOfHistory": years_of_history,
            "chartYields": chart_yields,
            "chartLabels": chart_labels,
            "lastUpdated": date.today().isoformat(),
        }, None

    except Exception as e:
        reason = f"exception: {e}"
        log.error(f"{ticker} failed: {e}")
        return None, reason


FAILURE_RATE_ALERT_THRESHOLD = 0.05  # exit non-zero (triggers GitHub's failure email) if >5% of universe fails


def run_pass(tickers: list[str]) -> tuple[list[dict], dict[str, str]]:
    """Run process_ticker across a list of tickers. Returns (results, {ticker: reason} for failures)."""
    results = []
    reasons = {}
    for ticker in tickers:
        result, reason = process_ticker(ticker)
        if result:
            results.append(result)
        else:
            reasons[ticker] = reason
        time.sleep(RATE_LIMIT_DELAY)
    return results, reasons


def main():
    log.info(f"Starting No Excuses Dividend Screen — {date.today()}")

    results, failure_reasons = run_pass(TICKERS)

    # Retry pass: transient rate-limit/timeout failures often clear on a second attempt.
    if failure_reasons:
        retry_tickers = list(failure_reasons.keys())
        log.info(f"Retrying {len(retry_tickers)} failed tickers: {retry_tickers}")
        time.sleep(5)
        retry_results, retry_reasons = run_pass(retry_tickers)
        results.extend(retry_results)
        for t in retry_results:
            failure_reasons.pop(t["ticker"], None)
        failure_reasons.update(retry_reasons)  # keep latest reason for tickers that failed twice

    buy_count = sum(1 for r in results if r["signal"] == "BUY")
    watch_count = sum(1 for r in results if r["signal"] == "WATCH")
    avg_pct = round(np.mean([r["percentile"] for r in results]), 1) if results else 0
    actual_lookback_years = round(np.median([r["yearsOfHistory"] for r in results]), 1) if results else 0

    failed_detail = [{"ticker": t, "reason": r} for t, r in sorted(failure_reasons.items())]
    failure_rate = len(failed_detail) / len(TICKERS) if TICKERS else 0

    output = {
        "meta": {
            "generatedAt": datetime.utcnow().isoformat() + "Z",
            "universe": len(results),
            "buyCount": buy_count,
            "watchCount": watch_count,
            "avgPercentile": avg_pct,
            "lookbackYears": actual_lookback_years,   # actual median history available, not a fixed target
            "dataSource": "Polygon.io free tier (~2yr history cap)",
            "buyThreshold": 80,
            "failedCount": len(failed_detail),
            "failureRate": round(failure_rate, 4),
            "failed": failed_detail,
        },
        "stocks": sorted(results, key=lambda x: x["percentile"], reverse=True)
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "dividend_screen.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    log.info(f"Done. {len(results)} stocks processed. {buy_count} BUY signals. "
             f"{len(failed_detail)} failed ({failure_rate:.1%}).")
    log.info(f"Output: {out_path}")

    if failure_rate > FAILURE_RATE_ALERT_THRESHOLD:
        log.error(
            f"Failure rate {failure_rate:.1%} exceeds {FAILURE_RATE_ALERT_THRESHOLD:.0%} threshold "
            f"after retry. Failing the job so GitHub sends a failure notification. "
            f"Failed tickers: {[f['ticker'] for f in failed_detail]}"
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
