# Deployment Guide

This project is designed for local use on your own machine.

This guide is about local setup and repeatable daily use, not public cloud deployment. Earlier versions of this document mixed in speculative production advice; this version is aligned with the current repository state.

## Scope of This Guide

Use this document when you want to:

- set up the project from a fresh clone
- start the backend correctly
- connect the Chrome extension to the backend
- create the minimum local data needed to run
- maintain your local runtime files

For the shortest startup path, read `QUICKSTART.md` first.

## 1. Fresh Local Setup

### Prerequisites

- Python 3.11+
- Chrome or Chromium
- LinkedIn account
- macOS/Linux/Windows with a local browser environment that Playwright can use

### Backend install

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
python -m playwright install chromium
cp .env.example .env
```

### Load the unpacked extension once

1. Open `chrome://extensions/`
2. Enable Developer mode
3. Click `Load unpacked`
4. Select `/Users/away/Desktop/Linkedin投递/linkedin-job-assistant/chrome-extension`
5. Copy the extension ID

### Configure backend CORS for the extension

Edit `/Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/.env`:

```dotenv
LJA_EXTENSION_ID=your_real_extension_id_here
```

Why this matters:

- the backend builds its CORS allowlist from `LJA_EXTENSION_ID`
- without it, the extension may fail to communicate with the backend even if `/health` is reachable

## 2. Start the Backend Correctly

Use the backend directory and explicitly load `.env`:

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8899
```

Health check:

```bash
curl http://127.0.0.1:8899/health
```

Expected output:

```json
{"status":"ok","app":"LinkedIn Job Assistant"}
```

## 3. Connect the Extension

After setting `LJA_EXTENSION_ID`:

1. Return to `chrome://extensions/`
2. Reload the unpacked extension
3. Open the popup
4. Confirm the backend appears connected

If it still shows offline:

- verify backend was started with `--env-file .env`
- verify `LJA_EXTENSION_ID` matches the current extension ID
- verify `curl http://127.0.0.1:8899/health`

## 4. First-Time Local Data Setup

This repository intentionally does not ship your runtime data, so a fresh clone needs initialization.

### Create a filter

In the extension `Settings` page:

1. Add a filter name
2. Add keywords
3. Add a location
4. Save the filter

### Upload a resume

In the same page:

1. Enter a resume name
2. Upload your file
3. Optionally mark it as default

### Update form answers

Edit:

`/Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/config/form_answers.yaml`

Replace the placeholder values before any real run.

## 5. Daily Usage

### Start a session

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8899
```

Then:

1. Open the extension popup
2. Confirm backend status
3. Select a filter
4. Click `Start Auto-Apply`
5. Log into LinkedIn manually if prompted
6. Monitor status in popup, dashboard, logs, and DB

### Stop a session

- Use the popup stop button, or
- call the API:

```bash
curl -X POST http://127.0.0.1:8899/api/v1/automation/stop
```

## 6. Useful Local Maintenance

### Runtime logs

```bash
tail -f /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/logs/automation.log
```

### Database inspection

```bash
sqlite3 /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/db/linkedin_assistant.db ".tables"
sqlite3 /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/db/linkedin_assistant.db "SELECT COUNT(*) FROM applications;"
sqlite3 /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/db/linkedin_assistant.db "SELECT COUNT(*) FROM jobs;"
sqlite3 /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/db/linkedin_assistant.db "SELECT * FROM operation_logs ORDER BY created_at DESC LIMIT 10;"
```

### Backup the database

```bash
cp /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/db/linkedin_assistant.db \
  /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/db/linkedin_assistant.backup.db
```

## 7. Troubleshooting

### Backend will not start

Check:

```bash
python3 --version
which python
lsof -i :8899
```

Then reinstall if needed:

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python -m pip install -e .[dev]
```

### Browser will not launch

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python -m playwright install chromium
```

If Playwright still fails, decide whether the issue is:

- missing local dependencies
- OS/browser permission issue
- local sandbox/environment restriction

### Extension says backend offline

Check in this order:

1. backend is running
2. backend was started with `--env-file .env`
3. `LJA_EXTENSION_ID` is correct
4. extension was reloaded after the config change

### Applications are not being created

Check in this order:

1. a filter exists
2. a resume exists
3. LinkedIn login completed
4. form answers are not placeholders
5. `automation.log` shows progress or a specific error

## 8. What Is Not in Git

These are intentionally local-only and are ignored by git:

- `backend/.env`
- `backend/venv/`
- `backend/data/browser_profile/`
- `backend/data/db/`
- `backend/data/logs/`
- `backend/data/resumes/`
- `backend/data/config/api_key.txt`

If you move to a new machine, you must recreate them.

## 9. What This Project Is Not Yet

This repository is not currently documented as a public cloud deployment target.

Do not assume:

- hosted multi-user backend
- production auth
- managed database
- Chrome Web Store distribution flow
- hardened cloud infra

Treat it as a local operator tool unless you explicitly build those layers.

## Last Updated

April 2026
