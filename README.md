README.md # No Excuses — Dividend Value Model

Subscriber tool for No Excuses (noexcuses.substack.com).
Screens the Dividend Achievers universe using two independent filters:
- 10-year yield percentile (buy zone = 80th percentile+)
- Weinstein Stage Analysis (actionable = Stage 1 or 2 only)

A BUY signal requires both conditions to align simultaneously.

---

## Repository Structure

```
dividend-model/
├── data/
│   └── dividend_screen.json     ← auto-generated weekly, read by dashboard
├── scripts/
│   ├── run_screen.py            ← Python backend (Polygon.io)
│   └── requirements.txt
├── dashboard/
│   └── index.html               ← subscriber-facing dashboard
└── .github/
    └── workflows/
        └── weekly_screen.yml    ← cron: every Sunday 8pm CT
```

---

## Setup (one time, ~20 minutes)

### 1. Create a GitHub repository

- Go to github.com, create a new repo named `dividend-model`
- Make it private (the JSON output via GitHub Pages will be public, but the source code stays private)

### 2. Push this code

```bash
git init
git remote add origin https://github.com/YOUR_USERNAME/dividend-model.git
git add .
git commit -m "Initial setup"
git push -u origin main
```

### 3. Add your Polygon.io API key as a secret

- In your GitHub repo: Settings → Secrets and variables → Actions → New repository secret
- Name: `POLYGON_API_KEY`
- Value: your Polygon.io API key

### 4. Enable GitHub Pages

- Settings → Pages → Source: Deploy from a branch
- Branch: main, Folder: /dashboard
- Save. Your dashboard URL will be: `https://YOUR_USERNAME.github.io/dividend-model/`

### 5. Move the data folder inside dashboard for Pages serving

The dashboard fetches `./data/dividend_screen.json`. For GitHub Pages, the data
folder needs to be inside the dashboard folder, or adjust the DATA_URL in index.html.

Simplest fix: change DATA_URL in index.html to the raw GitHub URL:
```javascript
const DATA_URL = "https://raw.githubusercontent.com/YOUR_USERNAME/dividend-model/main/data/dividend_screen.json";
```

### 6. Run the first screen manually

- In your GitHub repo: Actions → Weekly Dividend Screen → Run workflow
- First run takes 20-40 minutes (one API call per ticker, rate limited)
- After run completes, the JSON is committed to the repo automatically

### 7. Gate it in Substack

- Publish a paid-member post with the GitHub Pages URL
- Or link directly from your welcome email for paid subscribers
- No login required on the tool itself — the Substack paywall is the gate

---

## How the Signal Works

```
BUY   = yield percentile ≥ 80th AND stage 1 or 2
WATCH = yield percentile 60-79th AND stage 1 or 2
AVOID = stage 3 or 4 (regardless of yield)
HOLD  = everything else
```

AVOID is intentionally distinct from HOLD. A stock at the 85th yield percentile
in Stage 4 is not a value opportunity — it is a yield trap. The stage filter
removes it before subscribers ever see a buy signal.

---

## Schedule

The GitHub Actions workflow runs every Monday at 01:00 UTC, which is Sunday 8:00pm CT.
Results are ready before US markets open Monday morning.

To run manually: GitHub repo → Actions → Weekly Dividend Screen → Run workflow.

---

## Updating the Universe

The DIVIDEND_ACHIEVERS list in run_screen.py should be reviewed annually.
Nasdaq publishes the official DAAARP index constituents. Stocks that cut or freeze
dividends are removed from the index and should be removed from the list.

---

## Polygon.io API Notes

- The script uses the free Polygon.io tier with rate limiting (0.25s between calls)
- Full universe run (~350 tickers): approximately 30-45 minutes
- Each ticker makes 3 API calls: price history, dividend history, company details
- Stay well within the 5 calls/minute free tier limit

---

## Disclaimer

This tool is for informational and educational purposes only.
Not investment advice. Past dividend history does not guarantee future payments.
Always conduct your own due diligence before investing.
