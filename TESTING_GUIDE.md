# Testing Guide

Complete testing instructions for the LinkedIn Auto-Apply tool.

## Unit Tests (No Browser Required)

### 1. Test Job Search URL Building

```bash
cd backend
source venv/bin/activate
python test_manual.py
```

**What it tests:**
- Job search URL construction with various filter combinations
- Parameter encoding (keywords, location, experience level, job type)
- Human simulator delays

**Expected output:**
```
✓ All manual tests completed successfully!
```

### 2. API Endpoint Tests

**Backend must be running:**
```bash
# In one terminal
python -m uvicorn app.main:app --host 127.0.0.1 --port 8899
```

**In another terminal:**
```bash
# Test health endpoint
curl http://127.0.0.1:8899/health

# Test create filter
curl -X POST http://127.0.0.1:8899/api/v1/filters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Filter",
    "keywords": "Python Engineer",
    "location": "San Francisco",
    "easy_apply_only": true
  }'

# Test list filters
curl http://127.0.0.1:8899/api/v1/filters | jq

# Test get automation status
curl http://127.0.0.1:8899/api/v1/automation/status | jq
```

---

## Integration Tests (Browser Required)

### Prerequisites
```bash
cd backend
source venv/bin/activate

# Install Playwright (if not already done)
python -m pip install playwright
python -m playwright install chromium
```

### Test 1: Browser Launch & Stealth

**File:** `tests/test_automation_integration.py`

```bash
# Run with pytest
pytest tests/test_automation_integration.py::test_browser_manager_launch -v

# Or run directly
python -c "
import asyncio
from app.automation.browser_manager import browser_manager

async def test():
    print('Launching browser...')
    page = await browser_manager.launch(headless=True)
    print(f'✓ Browser launched, URL: {page.url}')
    await browser_manager.close()
    print('✓ Browser closed')

asyncio.run(test())
"
```

### Test 2: LinkedIn Auth Check

```python
import asyncio
from app.automation.browser_manager import browser_manager
from app.automation.linkedin_auth import linkedin_auth

async def test():
    print('Testing LinkedIn authentication check...')
    page = await browser_manager.launch(headless=False)
    print('Opening LinkedIn...')
    await page.goto('https://www.linkedin.com')
    
    is_logged_in = await linkedin_auth.is_logged_in(page)
    print(f'Logged in: {is_logged_in}')
    
    await browser_manager.close()

asyncio.run(test())
```

### Test 3: Manual Login Flow

```python
import asyncio
from app.automation.browser_manager import browser_manager
from app.automation.linkedin_auth import linkedin_auth

async def test():
    print('Testing manual login flow...')
    page = await browser_manager.launch(headless=False)
    
    print('Waiting for manual login (300 seconds timeout)...')
    print('Browser window should open - please log in manually')
    
    success = await linkedin_auth.wait_for_manual_login(timeout_seconds=300)
    
    if success:
        print('✓ Login successful!')
    else:
        print('✗ Login timeout')
    
    await browser_manager.close()

asyncio.run(test())
```

---

## Chrome Extension Testing

### 1. Load Extension in Chrome

```
1. Open chrome://extensions/
2. Enable "Developer mode" (top-right toggle)
3. Click "Load unpacked"
4. Select: linkedin-job-assistant/chrome-extension/
5. Pin extension to toolbar
```

### 2. Test Backend Connection

```
1. Start backend: python -m uvicorn app.main:app --host 127.0.0.1 --port 8899
2. Click extension icon
3. Should show "Backend connected ✓" (green dot)
```

### 3. Test Settings Page

```
1. Click extension → Settings
2. Create a search filter:
   - Name: "Test Python"
   - Keywords: "Python"
   - Location: "San Francisco"
   - ✓ Easy Apply Only
3. Click "Save Filter"
4. Should see filter listed below
5. Upload a resume PDF
```

### 4. Test Dashboard

```
1. Click extension → Dashboard
2. Should open new tab with application tracker
3. Table should be empty initially (no applications yet)
```

---

## End-to-End Testing

### Full Workflow Test

```
1. Start backend: python -m uvicorn app.main:app --host 127.0.0.1 --port 8899
2. Load extension in Chrome
3. Create a test filter in Settings
4. Upload a test resume
5. Click "Start Auto-Apply" in popup
6. Browser launches - LOG IN TO LINKEDIN MANUALLY
7. After login, automation should:
   - Begin searching for jobs
   - Show progress in popup
   - Apply to jobs automatically
8. Watch the dashboard for applications
9. Click "Stop" to stop automation
```

---

## Debugging

### Backend Logs

```bash
# View real-time logs while backend is running
tail -f data/logs/app.log

# Check operation logs in database
sqlite3 data/db/linkedin_assistant.db
> SELECT * FROM operation_logs ORDER BY created_at DESC LIMIT 10;
```

### Browser Inspector

When testing with headless=False:
1. Browser window opens automatically
2. Use F12 to open DevTools
3. Check Console for errors
4. Inspect Elements to verify selectors

### Extension Errors

```
1. Open chrome://extensions/
2. Find "LinkedIn Smart Apply Assistant"
3. Click "Inspect views"
4. Check Console and Network tabs
```

### Database Inspection

```bash
cd backend/data/db

# View database schema
sqlite3 linkedin_assistant.db ".schema"

# Query specific tables
sqlite3 linkedin_assistant.db "SELECT * FROM search_filters LIMIT 5;"
sqlite3 linkedin_assistant.db "SELECT * FROM applications LIMIT 5;"
sqlite3 linkedin_assistant.db "SELECT * FROM operation_logs LIMIT 10;"

# Export to CSV
sqlite3 linkedin_assistant.db ".mode csv" ".output data.csv" "SELECT * FROM applications;"
```

---

## Test Checklist

### Phase 1: Foundation ✓
- [x] Backend starts successfully
- [x] Health check endpoint works
- [x] Database initialized
- [x] API endpoints respond
- [x] Job search URL building works
- [x] Human simulator delays work

### Phase 2: Browser & Auth
- [ ] Browser launches successfully
- [ ] Persistent context profile created
- [ ] Manual login flow works
- [ ] Session persists after restart
- [ ] LinkedIn detection works

### Phase 3: Job Search & Scrape
- [ ] Job search navigates to LinkedIn
- [ ] Job listings are extracted
- [ ] Job data stored in database
- [ ] Pagination works
- [ ] Filters applied correctly

### Phase 4: Easy Apply
- [ ] Easy Apply button detected
- [ ] Form fields identified
- [ ] Form fields filled correctly
- [ ] Resume uploaded successfully
- [ ] Application submitted
- [ ] Success confirmation detected

### Phase 5: Automation Orchestration
- [ ] Rate limiter enforces daily caps
- [ ] Warmup schedule works
- [ ] Status updates broadcast to popup
- [ ] Stop command gracefully halts
- [ ] Error recovery works

### Phase 6: Integration
- [ ] Extension popup shows status
- [ ] Settings page manages filters
- [ ] Dashboard displays applications
- [ ] CSV export works
- [ ] Full workflow end-to-end

---

## Performance Testing

### Metrics to Track

```bash
# Time per application (target: 30-60 seconds)
# Includes: form detection, filling, submission, human delays

# Daily application limit (configurable, default: 25)
# Should enforce hard cap

# Memory usage (target: <200MB for browser)
# Monitor with: top, htop

# Database size growth (target: <10MB for 1000 applications)
# Check with: ls -lh data/db/linkedin_assistant.db
```

---

## Common Issues & Solutions

### "Browser won't launch"
```bash
# Verify Playwright is installed
python -m playwright install chromium

# Check if Chromium executable exists
ls ~/Library/Caches/ms-playwright/chromium-*/
```

### "Login timeout"
- Browser opened in headless mode (can't log in interactively)
- Solution: Set `headless=False` in test code

### "Form fields not found"
- LinkedIn CSS selectors change frequently
- Solution: Update selectors in form_filler.py
- Check browser DevTools to find current selectors

### "Rate limit not enforcing"
- Check operation_logs table for entries
- Verify daily_apply_limit setting
- Restart backend to reset in-memory counters

---

## Continuous Testing

### Automated Test Run

```bash
#!/bin/bash
# save as scripts/test_all.sh

set -e

echo "Starting tests..."

# Unit tests
echo "1. Running unit tests..."
cd backend
source venv/bin/activate
python test_manual.py

# API tests
echo "2. Testing API endpoints..."
python -m uvicorn app.main:app --host 127.0.0.1 --port 8899 &
SERVER_PID=$!
sleep 3

curl -f http://127.0.0.1:8899/health > /dev/null && echo "✓ Health check passed"
curl -f http://127.0.0.1:8899/api/v1/filters > /dev/null && echo "✓ API endpoints work"

kill $SERVER_PID

echo "✓ All tests passed!"
```

---

**Last Updated:** March 2026
**Status:** Testing framework ready for Phase 2
