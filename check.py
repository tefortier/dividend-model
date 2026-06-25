import os, requests, json

key = os.environ["POLYGON_API_KEY"]
base = "https://api.polygon.io"

tests = {
    "ticker_overview": f"{base}/v3/reference/tickers/PAYX",
    "financials":      f"{base}/vX/reference/financials?ticker=PAYX&limit=2",
    "ratings_benzinga":f"{base}/benzinga/v1/ratings?ticker=PAYX&limit=2",
    "estimates_bz":    f"{base}/benzinga/v1/consensus_ratings?ticker=PAYX",
}

for name, url in tests.items():
    try:
        r = requests.get(url, params={"apiKey": key}, timeout=30)
        print(f"\n===== {name}  HTTP {r.status_code} =====")
        body = r.json()
        print(json.dumps(body, indent=2)[:1500])
    except Exception as e:
        print(f"\n===== {name}  ERROR {e} =====")
