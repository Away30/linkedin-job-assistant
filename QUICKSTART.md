# Quick Start

Use this if you want the shortest path from fresh clone to a working local setup.

## 1. Backend install

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
python -m playwright install chromium
cp .env.example .env
```

## 2. Load the extension once

1. Open `chrome://extensions/`
2. Enable Developer mode
3. Click `Load unpacked`
4. Select `/Users/away/Desktop/Linkedin投递/linkedin-job-assistant/chrome-extension`
5. Copy the extension ID

## 3. Put the extension ID into `.env`

Edit `/Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/.env`:

```dotenv
LJA_EXTENSION_ID=your_real_extension_id_here
```

Without this, the backend CORS configuration may reject the extension.

## 4. Start the backend

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8899
```

Verify:

```bash
curl http://127.0.0.1:8899/health
```

Expected:

```json
{"status":"ok","app":"LinkedIn Job Assistant"}
```

## 5. Reload the extension

After updating `.env`, go back to `chrome://extensions/` and click reload on the unpacked extension.

## 6. Create real local data

In the extension:

1. Open `Settings`
2. Create a filter
3. Upload a resume

In local config:

1. Open `/Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend/data/config/form_answers.yaml`
2. Replace the placeholder values with your real information

## 7. Start a run

1. Open the extension popup
2. Confirm backend status is connected
3. Select a filter
4. Click `Start Auto-Apply`
5. Log into LinkedIn manually if prompted

## Useful checks

```bash
curl http://127.0.0.1:8899/api/v1/filters
curl http://127.0.0.1:8899/api/v1/resumes
curl http://127.0.0.1:8899/api/v1/applications
curl http://127.0.0.1:8899/api/v1/automation/status
```

## Common first-run failures

### Popup says backend offline

- Backend is not running
- Backend was started without `--env-file .env`
- `LJA_EXTENSION_ID` is missing or wrong
- Extension was not reloaded after updating `.env`

### Resume upload works locally, but nothing applies

- No filter selected
- No default resume uploaded
- LinkedIn login not completed in the launched browser
- Selectors or flow changed on LinkedIn

### You expected existing DB data

That data is not committed. This repo intentionally excludes:

- local SQLite database
- browser session/profile
- resumes
- logs
- API key files

For longer setup details, read `README.md`.
