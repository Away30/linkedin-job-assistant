# LinkedIn Job Assistant

[中文说明 / Chinese README](./README.zh-CN.md)

A local-only Chrome extension plus FastAPI backend for tracking LinkedIn jobs and automating parts of the Easy Apply flow.

## What This Repo Contains

- `chrome-extension/` - Manifest V3 extension with popup, settings page, dashboard, and background API proxy.
- `backend/` - FastAPI app, SQLite models, Playwright automation modules, and test suite.
- Root docs - `QUICKSTART.md`, `ARCHITECTURE.md`, `TESTING_GUIDE.md`, and `DEPLOYMENT.md`.

## Current Status

- The repository is upload-safe: local browser profile, SQLite DB, logs, resumes, `.env`, and API keys are ignored.
- The backend API, database models, and extension UI are present in source control.
- Runtime data is intentionally not included, so a fresh clone needs a small setup step before the extension can talk to the backend.
- Some deeper docs were written earlier and may be more optimistic than reality; use this README as the source of truth for first-time setup.

## Before You Start

This project stores real runtime state locally and does not commit it. The
following paths are gitignored — **do not track them, they leak PII or
session state**:

- `backend/.env`
- `backend/data/db/`
- `backend/data/browser_profile/`
- `backend/data/chrome_profile/` (Chrome user-data dir created in CDP mode; contains LinkedIn cookies)
- `backend/data/logs/`
- `backend/data/resumes/`
- `backend/data/config/api_key.txt`
- `backend/data/config/form_answers.yaml` (your real PII — name/phone/email/work auth)
- `backend/data/config/connection_messages.yaml` (custom recruiter outreach copy)
- `backend/data/config/runtime_settings.json` (per-machine setting overrides)

That is intentional. A fresh clone gives you code, not your local session state.

> **If you are setting up for the first time:** copy `backend/data/config/form_answers.yaml.example` to `backend/data/config/form_answers.yaml` and fill in your real values locally. The example file is the only one that lives in version control.

## Fresh Clone Setup

### 1. Clone the repo

```bash
git clone git@github.com:Away30/linkedin-job-assistant.git
cd linkedin-job-assistant
```

### 2. Create and activate the backend virtual environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
python -m playwright install chromium
```

### 3. Create your local backend config

```bash
cp .env.example .env
```

Important:

- `backend/.env` is not loaded automatically by the app.
- Start the backend with `uvicorn --env-file .env ...` so the values are actually used.
- You will need to fill in `LJA_EXTENSION_ID` after loading the extension once.

### 4. Load the unpacked extension once to get its ID

1. Open `chrome://extensions/`
2. Enable Developer mode
3. Click `Load unpacked`
4. Select `/Users/away/Desktop/Linkedin投递/linkedin-job-assistant/chrome-extension`
5. Copy the extension ID shown on the card

Then update `backend/.env`:

```dotenv
LJA_EXTENSION_ID=your_real_extension_id_here
```

Why this matters:

- The backend CORS allowlist is built from `LJA_EXTENSION_ID`.
- If this is missing or wrong, the extension may show the backend as offline even when `http://127.0.0.1:8899/health` works.

### 5. Start the backend

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8899
```

Quick health check:

```bash
curl http://127.0.0.1:8899/health
```

Expected response:

```json
{"status":"ok","app":"LinkedIn Job Assistant"}
```

### 6. Reload the extension

After setting `LJA_EXTENSION_ID` and starting the backend:

1. Go back to `chrome://extensions/`
2. Click the reload icon for the unpacked extension
3. Open the popup
4. Confirm it shows the backend as connected

### 7. Initialize actual user data

In the extension:

1. Open `Settings`
2. Create at least one search filter
3. Upload one resume

In local files:

- Copy `backend/data/config/form_answers.yaml.example` → `backend/data/config/form_answers.yaml`
- Replace the placeholder answers with your real contact info / work-auth / education
- (Optional) seed `backend/data/config/connection_messages.yaml` to override the post-apply recruiter outreach copy

## Daily Run Workflow

Once setup is done, the normal workflow is:

1. Start the backend
2. Open the extension popup
3. Verify backend connectivity
4. Select a saved filter
5. Click `Start Auto-Apply`
6. Log into LinkedIn manually if prompted
7. Watch status in the popup or dashboard

## API Surface You Can Rely On

Base URL: `http://127.0.0.1:8899/api/v1`

### Core endpoints

- `GET /ping`
- `GET /health` at the app root
- `POST /automation/start`
- `POST /automation/stop`
- `GET /automation/status`
- `GET /automation/status/stream`
- `GET /filters`
- `POST /filters`
- `GET /resumes`
- `POST /resumes`
- `GET /applications`
- `PATCH /applications/{app_id}`
- `POST /applications/{app_id}/retry`
- `GET /stats/summary`
- `GET /settings`
- `POST /settings` (only `max_applies_per_day`, `max_connects_per_day`, `action_delay_min/max`, `networking_*` are user-editable; persisted to `data/config/runtime_settings.json`)
- `GET /blacklist`
- `POST /blacklist`

### Networking endpoints (post-apply recruiter / hiring-manager outreach)

- `GET /connections` - list sent / pending / accepted invites
- `GET /connections/stats` - 7-day aggregate
- `PATCH /connections/{id}` - mark accepted, etc. (body: `{"status": "accepted"}`)
- `GET /connections/messages` / `POST /connections/messages` - per-persona message templates (recruiter / hiring_manager / engineer / default)
- `POST /connections/trigger?job_id=…` - manually fire networking for a saved job's company

`enable_networking: true` on `POST /automation/start` runs the same flow automatically after each successful apply.

## Database Migrations

The schema is created by SQLAlchemy on first run via `init_db()`. When the
ORM gains a new index on an already-populated DB, run the one-shot migrator:

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python -m scripts.migrate_indexes
```

Idempotent — safe to re-run.

## Security Posture

- **Loopback only** — backend binds to `127.0.0.1` and never exposes a remote port.
- **API key auth** — every `/api/*` route requires `X-API-Key`; the key is generated on first launch into `backend/data/config/api_key.txt` and compared with `secrets.compare_digest` (constant-time).
- **CORS** — when `LJA_EXTENSION_ID` is set the allowlist pins one origin and `allow_credentials=True`. Without it the dev fallback uses an origin regex with `allow_credentials=False`, avoiding the spec-banned wildcard-with-credentials combination.
- **PII / session data is gitignored** — the listed runtime files never enter version control. Re-check `git status` after every pull before committing.
- **Rate limits + warmup** — the human simulator and `RateLimiter` enforce daily caps; tune via `/settings` (persisted to `runtime_settings.json`).

## Troubleshooting

### Backend looks healthy, but the extension says offline

Check these in order:

1. `curl http://127.0.0.1:8899/health`
2. Confirm backend was started with `--env-file .env`
3. Confirm `LJA_EXTENSION_ID` matches the unpacked extension ID
4. Reload the extension after changing `.env`

### Playwright browser does not launch

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python -m playwright install chromium
```

### You want logs

Current runtime log file:

```bash
tail -f /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/logs/automation.log
```

### You cloned the repo and expected existing data

That data is local-only by design. Recreate it locally:

- filters through the extension settings page
- resumes through the resume upload flow
- browser login state by logging in again

## Repository Layout

```text
linkedin-job-assistant/
├── chrome-extension/
├── backend/
│   ├── app/
│   ├── data/
│   │   └── config/
│   ├── tests/
│   ├── .env.example
│   └── pyproject.toml
├── QUICKSTART.md
├── ARCHITECTURE.md
├── TESTING_GUIDE.md
└── DEPLOYMENT.md
```

## Recommended Next Reads

- `QUICKSTART.md` - shorter operational checklist
- `ARCHITECTURE.md` - system layout and responsibilities
- `TESTING_GUIDE.md` - manual and automated verification notes
- `DEPLOYMENT.md` - longer-form environment setup

## Safety Note

This project automates activity on LinkedIn. Use it conservatively, review the forms it submits, and assume LinkedIn can change selectors or anti-automation behavior at any time.
