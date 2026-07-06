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
- **AI analysis:** Groq's free-tier API (`llama-3.3-70b-versatile`,
  OpenAI-compatible) — get a free key at https://console.groq.com/keys
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
  ai_analysis.py     Groq call -> executive summary + priorities
  report_generator.py  renders HTML/JSON report, saves to reports/
  email_service.py   sends the report via SMTP
  pipeline.py        orchestrates: crawl -> audits -> AI -> report -> email
  scheduler.py        weekly APScheduler job
  templates/report.html  email report layout
frontend/
  index.html          dashboard shell (empty / running / error / report states)
  styles.css           dark instrument-panel theme, faceted "gem-cut" health score
  app.js               fetch + poll the API, render findings, filter by category
reports/             generated reports land here (latest.html / latest.json)
requirements.txt
.env.example         copy to .env and fill in your values
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Only needed if USE_PLAYWRIGHT_FOR_JS=true:
playwright install chromium

cp .env.example .env
# edit .env: set GROQ_API_KEY, SMTP_*, EMAIL_RECIPIENTS, etc.
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
```

### Run the pipeline directly (no server), useful for local testing
```bash
python3 -m app.pipeline
```

## Notes / current limitations
- **AI analysis has a safe fallback:** if `GROQ_API_KEY` is unset or the
  API call fails, a rule-based summary is generated instead so the weekly
  report — and the dashboard — never break.
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
- Tested end-to-end (crawl → audits → AI fallback → report → dashboard
  render) against a local mock site; not yet run against the live
  amipi.com domain (needs real network access + a filled-in `.env`).

