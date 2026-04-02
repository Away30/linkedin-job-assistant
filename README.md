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

This project stores real runtime state locally and does not commit it:

- `backend/.env`
- `backend/data/db/`
- `backend/data/browser_profile/`
- `backend/data/logs/`
- `backend/data/resumes/`
- `backend/data/config/api_key.txt`

That is intentional. A fresh clone gives you code, not your local session state.

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

- Replace the placeholder answers in `backend/data/config/form_answers.yaml`
- Do not leave the default fake contact info in place

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
- `POST /settings`
- `GET /blacklist`
- `POST /blacklist`

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
