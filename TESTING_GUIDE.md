# Testing Guide

Practical verification steps for the current repository state.

This document is aligned with `README.md` and `QUICKSTART.md`. If you find conflicting instructions elsewhere, treat those two files plus this guide as the source of truth.

## Test Goals

Use testing in this order:

1. Verify the backend can start locally
2. Verify API endpoints and database initialization
3. Verify the extension can talk to the backend
4. Verify Playwright/browser automation in your local environment
5. Verify one controlled end-to-end flow

## Recommended Test Environment

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
python -m playwright install chromium
cp .env.example .env
```

Before testing the extension, set `LJA_EXTENSION_ID` in `backend/.env` and start the backend with:

```bash
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8899
```

## 1. Smoke Test: Backend Startup

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8899
```

In another terminal:

```bash
curl http://127.0.0.1:8899/health
curl http://127.0.0.1:8899/api/v1/ping
```

Expected responses:

```json
{"status":"ok","app":"LinkedIn Job Assistant"}
```

```json
{"message":"pong"}
```

## 2. Python Test Suite

### Manual sanity script

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python test_manual.py
```

This is a quick sanity check for utility code such as search URL generation and delay helpers.

### API tests

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python -m pytest tests/test_api.py -q
```

### Additional backend tests

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python -m pytest tests -q
```

Notes:

- Some tests are pure API/database tests and should run without a browser.
- Browser automation tests may depend on local OS/browser permissions and Playwright availability.
- If browser tests fail, separate environment failures from code failures.

## 3. API Verification by Hand

With the backend running:

```bash
curl http://127.0.0.1:8899/api/v1/filters
curl http://127.0.0.1:8899/api/v1/resumes
curl http://127.0.0.1:8899/api/v1/applications
curl http://127.0.0.1:8899/api/v1/automation/status
curl http://127.0.0.1:8899/api/v1/stats/summary
```

Useful write checks:

```bash
curl -X POST http://127.0.0.1:8899/api/v1/filters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Filter",
    "keywords": "Python Engineer",
    "location": "Remote",
    "easy_apply_only": true
  }'
```

## 4. Extension Testing

### Load the extension

1. Open `chrome://extensions/`
2. Enable Developer mode
3. Click `Load unpacked`
4. Select `/Users/away/Desktop/Linkedin投递/linkedin-job-assistant/chrome-extension`
5. Copy the extension ID into `backend/.env` as `LJA_EXTENSION_ID`
6. Reload the backend if needed
7. Reload the extension

### Backend connectivity test

1. Start backend with `--env-file .env`
2. Open the extension popup
3. Confirm it shows backend connected

If it still shows offline:

- confirm `curl http://127.0.0.1:8899/health`
- confirm `LJA_EXTENSION_ID` is correct
- reload the extension after editing `.env`

### Settings page test

1. Open extension `Settings`
2. Create a test filter
3. Upload a test resume
4. Confirm both appear in their respective lists

### Dashboard test

1. Open extension `Dashboard`
2. Confirm the page loads without console errors
3. Confirm empty state or current application rows render
4. Confirm filters and CSV export do not crash

## 5. Browser Automation Tests

### Playwright launch test

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python -m pytest tests/test_automation_integration.py::test_browser_manager_launch -q
```

### Manual browser launch check

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python - <<'PY'
import asyncio
from app.automation.browser_manager import browser_manager

async def main():
    page = await browser_manager.launch(headless=False)
    print("Browser launched:", bool(page))
    await browser_manager.close()

asyncio.run(main())
PY
```

### Login flow check

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python - <<'PY'
import asyncio
from app.automation.linkedin_auth import linkedin_auth

async def main():
    ok = await linkedin_auth.wait_for_manual_login(timeout_seconds=300)
    print("Login success:", ok)

asyncio.run(main())
PY
```

## 6. End-to-End Verification

Use a controlled test, not an unlimited live run:

1. Start backend with `--env-file .env`
2. Load and reload the extension after setting `LJA_EXTENSION_ID`
3. Create one filter
4. Upload one resume
5. Replace placeholder values in `backend/data/config/form_answers.yaml`
6. Start automation from the popup
7. Log into LinkedIn manually if prompted
8. Watch:
   - popup status
   - backend log file
   - database rows

What to verify:

- automation status changes from idle to running
- browser opens
- login detection works
- search starts
- jobs are found or a clear failure reason is recorded
- results appear in logs or database

## Logs and Database Inspection

### Runtime logs

```bash
tail -f /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/logs/automation.log
```

### SQLite inspection

```bash
sqlite3 /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/db/linkedin_assistant.db ".tables"
sqlite3 /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/db/linkedin_assistant.db "SELECT COUNT(*) FROM search_filters;"
sqlite3 /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/db/linkedin_assistant.db "SELECT COUNT(*) FROM resumes;"
sqlite3 /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/db/linkedin_assistant.db "SELECT COUNT(*) FROM applications;"
sqlite3 /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/db/linkedin_assistant.db "SELECT * FROM operation_logs ORDER BY created_at DESC LIMIT 10;"
```

## Common Failures

### Backend is healthy, extension is offline

Likely causes:

- backend started without `--env-file .env`
- wrong or missing `LJA_EXTENSION_ID`
- extension was not reloaded after config change

### Playwright browser does not launch

Likely causes:

- Chromium not installed with `python -m playwright install chromium`
- local OS restrictions
- environment/sandbox restrictions

### No applications appear

Check these in order:

1. A filter exists
2. A resume exists
3. Form answers are not still placeholders
4. LinkedIn login completed
5. `automation.log` contains search/apply progress or clear errors

## Suggested Verification Checklist

- [ ] Backend starts locally
- [ ] `/health` returns 200
- [ ] `tests/test_api.py` passes
- [ ] Extension connects to backend
- [ ] Filter creation works
- [ ] Resume upload works
- [ ] Browser launches locally
- [ ] Login check works
- [ ] One end-to-end run produces logs and/or DB records

## Last Updated

April 2026
