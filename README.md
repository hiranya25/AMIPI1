# AI Website Health Monitor

Full-stack automated crawling, SEO/technical/performance auditing, and
AI-summarized weekly reporting for **amipi.com** — replaces the current
manual process of running PageSpeed Insights, GTmetrix, SEOptimer,
Ubersuggest, and Screaming Frog by hand.

## Stack
- **Backend:** Python + FastAPI
- **Frontend:** Static HTML/CSS/JS dashboard, served by FastAPI on the same
  origin (no build step, no framework — open `uvicorn app.main:app` and go)
- **Crawler:** `requests` + `BeautifulSoup` (static HTML), optional
  Playwright fallback for JS-rendered pages (`USE_PLAYWRIGHT_FOR_JS=true`)
- **PDF Generation:** `playwright` (Chromium) used for generating PDF reports on the fly
- **AI analysis:** NVIDIA Nemotron API (`nvidia/nemotron-3-ultra-550b-a55b`)
  via OpenAI-compatible streaming API. Handles reasoning tokens and parses JSON output.
- **Scheduler:** APScheduler (weekly cron, default Monday 6:00 AM)
- **Email:** stdlib `smtplib` (works with Gmail/Outlook/any SMTP+STARTTLS)

## Project layout
```
app/
  main.py            FastAPI app + API routes + mounts /frontend as the SPA
  config.py          All settings, loaded from .env
  models.py          PageRecord / Issue / AuditResult data classes
  crawler.py         Full-site BFS crawler
  audits/
    broken_links.py    4xx/5xx pages + broken resources
    metadata.py        title/meta description/canonical/lang/H1
    alt_tags.py        missing image ALT attributes
    seo_checks.py      robots.txt / sitemap / HTTPS / structured data
    performance.py     response time, payload size, render-blocking scripts
  ai_analysis.py     NVIDIA Nemotron call -> executive summary + priorities
  report_generator.py  renders HTML/JSON report, saves to reports/
  pdf_generator.py   converts the HTML report to a PDF via Playwright
  issue_diff.py      diffs current run vs previous run (fixed/new issues)
  email_service.py   sends the HTML report + PDF attachment via SMTP
  pipeline.py        orchestrates: crawl -> audits -> AI -> report -> email
  scheduler.py        weekly APScheduler job
  templates/report.html  email report layout
frontend/
  index.html          dashboard shell (empty / running / error / report states)
  styles.css           dark instrument-panel theme, faceted "gem-cut" health score
  app.js               fetch + poll the API, render findings, filter by category
reports/             generated reports land here (latest.html / latest.json / latest.pdf)
requirements.txt
.env.example         copy to .env and fill in your values
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Playwright is required for PDF generation (and optionally JS crawling)
playwright install --with-deps chromium

cp .env.example .env
# edit .env: set AI_API_KEY, SMTP_*, EMAIL_RECIPIENTS, etc.
```

## Run

```bash
uvicorn app.main:app --reload
```

Then open **http://localhost:8000** — that's the dashboard. It starts in an
empty state ("No scan on record yet"); click **Run audit now** to crawl the
site, run all five audit modules, get the AI summary, and see the report
render live (health score, severity counts, top priorities, and a
filterable findings table). The weekly scheduler also starts automatically
with the app (cron controlled by `WEEKLY_CRON` in `.env`), so reports keep
flowing without opening the dashboard.

API docs (Swagger UI) are at **http://localhost:8000/docs**.

### API endpoints (used by the dashboard, also callable directly)
```bash
curl -X POST "http://localhost:8000/audit/run?send_email=false"
# -> {"job_id": "...", "status": "queued"}

curl "http://localhost:8000/audit/status/<job_id>"
curl "http://localhost:8000/audit/latest"          # JSON
curl "http://localhost:8000/audit/latest/html"      # emailed-style HTML report
curl "http://localhost:8000/audit/latest/pdf"       # downloads the PDF version
curl -X POST "http://localhost:8000/audit/email"    # explicitly triggers the email w/ PDF
```

### Run the pipeline directly (no server), useful for local testing
```bash
python3 -m app.pipeline
```

## Notes / current limitations
- **AI analysis has a safe fallback:** if `AI_API_KEY` is unset or the
  API call times out (the 550B model reasoning can be slow), a rule-based
  summary is generated instead so the weekly report — and the dashboard — never break.
- **Performance checks are lightweight** (response time, payload size,
  render-blocking script count) rather than a full Lighthouse run — this
  avoids requiring headless Chrome for every page. Swapping in
  Playwright's Web Vitals timing is a natural next step.
- **Broken-link checking of outbound resources** does a live HEAD/GET
  request per unique URL — for very large sites, consider capping this or
  running it as a separate, less-frequent job.
- The dashboard polls `/audit/status/{job_id}` every 2s while a run is in
  progress; a full amipi.com crawl (~40+ pages) will typically finish in
  under a minute.