# Deployment Guide

Instructions for setting up and deploying the LinkedIn Smart Job Application Assistant.

## Local Development Setup

### Prerequisites
- **macOS/Linux/Windows** with WSL2
- **Python 3.11+** (verify: `python3 --version`)
- **Chrome/Chromium** browser
- **LinkedIn account** (for testing)

### Step 1: Clone/Extract Project

```bash
# Project is already in:
/Users/away/Desktop/Linkedin投递/linkedin-job-assistant/

# Navigate to directory
cd "/Users/away/Desktop/Linkedin投递/linkedin-job-assistant"
```

### Step 2: Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Install Playwright and Chromium
python -m pip install playwright
python -m playwright install chromium

# Verify installation
python -c "from app.db.session import init_db; init_db(); print('✓ Database ready')"
```

### Step 3: Start Backend Server

```bash
# In the backend directory with venv activated
python -m uvicorn app.main:app --host 127.0.0.1 --port 8899 --reload

# Should see:
# INFO:     Uvicorn running on http://127.0.0.1:8899
```

### Step 4: Load Chrome Extension

```
1. Open: chrome://extensions/
2. Enable "Developer mode" (toggle, top-right)
3. Click "Load unpacked"
4. Select: linkedin-job-assistant/chrome-extension/
5. Pin extension to toolbar (puzzle icon → pin)
6. Click extension icon → should show "Backend connected ✓"
```

### Step 5: First-Time Configuration

```
1. Click extension icon
2. Click "Settings" (options page opens)
3. Create a search filter:
   - Name: "Python Engineer Remote"
   - Keywords: "Python"
   - Location: "Remote"
   - Experience: "Senior" (optional)
   - ✓ Easy Apply Only
   - Click "Save Filter"
4. Upload your resume:
   - Name: "My Resume"
   - File: (select your resume PDF)
   - Target Roles: "Software Engineer, Backend Engineer"
   - ✓ Set as Default
   - Click "Upload Resume"
5. Adjust safety settings if needed:
   - Max Applications Per Day: 25 (default)
   - Min Delay: 3s, Max Delay: 12s
   - ✓ Enable Warmup Mode
   - Click "Save Settings"
```

---

## Daily Usage

### Starting a Session

```
1. Ensure backend is running:
   cd backend && source venv/bin/activate
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8899

2. Click extension icon
3. Select filter from dropdown (e.g., "Python Engineer Remote")
4. Click "Start Auto-Apply"
5. Browser window opens → **LOG IN TO LINKEDIN MANUALLY**
6. After login, automation starts automatically
7. Watch progress in popup or dashboard
8. Click "Stop" when done (or it stops at daily limit)
```

### Monitoring Progress

```
Extension Popup:
- Green dot = Backend connected
- Shows: "12 applied, 2 failed"
- Click "Dashboard" to see detailed list

Dashboard Tab:
- Table of all applications
- Filter by: Position, Company, Status
- See: Applied Date, Resume Used, Status
- Export to CSV
```

### Reviewing Applications

```
1. Click "Dashboard" in popup
2. View table of all applications
3. Click "View" for application details (future phase)
4. Update status manually if needed
5. Export data as CSV for records
```

---

## Configuration Files

### Backend Settings (app/config.py)

Key settings you might want to adjust:

```python
# Rate Limiting
MAX_APPLIES_PER_DAY = 25        # Hard cap per day
MAX_CONNECTS_PER_DAY = 20       # Connection requests

# Timing
ACTION_DELAY_MIN = 3.0          # Minimum delay between actions
ACTION_DELAY_MAX = 12.0         # Maximum delay between actions
LONG_BREAK_MIN = 30.0           # Longer break min duration
LONG_BREAK_MAX = 120.0          # Longer break max duration

# Warmup (new accounts)
WARMUP_ENABLED = True           # Enable gradual ramp-up
WARMUP_DAYS = 7                 # Days to reach full rate

# Browser
HEADLESS = False                # Show browser window
```

### Form Answers (data/config/form_answers.yaml)

Pre-fill common form fields:

```yaml
contact_info:
  phone: "+1 (555) 123-4567"
  email: "user@example.com"

common_questions:
  years_of_experience: "5"
  work_authorization: "Yes"
  sponsorship_required: "No"
  willing_to_relocate: "No"
```

### Environment Variables (.env)

```bash
# Optional: Create .env file
LJA_DEBUG=False
LJA_DATABASE_URL=sqlite:///./data/db/linkedin_assistant.db
LJA_DAILY_APPLY_LIMIT=25
```

---

## Database Maintenance

### Backup Database

```bash
# Copy database file
cp backend/data/db/linkedin_assistant.db backup_$(date +%Y%m%d).db

# Or export to CSV
cd backend
sqlite3 data/db/linkedin_assistant.db ".mode csv" ".output applications.csv" "SELECT * FROM applications;"
```

### View Database

```bash
sqlite3 backend/data/db/linkedin_assistant.db

# List tables
.tables

# View schema
.schema

# Query applications
SELECT COUNT(*) FROM applications;
SELECT * FROM applications ORDER BY applied_at DESC LIMIT 5;

# View operation logs
SELECT * FROM operation_logs ORDER BY created_at DESC LIMIT 20;

# Exit
.quit
```

### Reset Database

```bash
# WARNING: This deletes all data!
rm backend/data/db/linkedin_assistant.db

# Recreate empty database
cd backend && source venv/bin/activate
python -c "from app.db.session import init_db; init_db()"
```

---

## Troubleshooting

### Backend Won't Start

```bash
# Check Python version
python3 --version  # Should be 3.11+

# Verify venv is activated
which python  # Should show path to venv/bin/python

# Reinstall dependencies
pip install -e .

# Check if port is in use
lsof -i :8899

# If port is in use, kill the process
kill -9 <PID>
```

### Extension Shows "Backend Offline"

```bash
# Check backend is running
curl http://127.0.0.1:8899/health

# If curl fails:
# 1. Backend not started (check step above)
# 2. Wrong port (should be 8899)
# 3. Firewall blocking localhost

# Reload extension:
# 1. Go to chrome://extensions/
# 2. Find extension, click refresh icon
```

### Browser Won't Launch

```bash
# Verify Playwright is installed
python -m playwright install chromium

# Check Chromium executable exists
ls ~/Library/Caches/ms-playwright/chromium-*/

# Try launching manually (for testing)
python -c "
import asyncio
from app.automation.browser_manager import browser_manager

async def test():
    page = await browser_manager.launch(headless=True)
    print('✓ Browser works')
    await browser_manager.close()

asyncio.run(test())
"
```

### Login Timeout

```bash
# Browser window should open automatically
# If it doesn't, check:
# 1. headless=False is set in config
# 2. Browser is not minimized
# 3. Give it 5 minutes to complete login
# 4. Check browser console (F12) for errors

# To test manually:
python -c "
import asyncio
from app.automation.linkedin_auth import linkedin_auth

async def test():
    print('Waiting for login (5 min timeout)...')
    success = await linkedin_auth.wait_for_manual_login(300)
    print('Success!' if success else 'Timeout')

asyncio.run(test())
"
```

### Applications Not Being Created

```bash
# Check:
# 1. Resume uploaded and marked as default
# 2. Filter created and selected
# 3. Logged into LinkedIn (check browser)
# 4. Looking at correct database (backend/data/db/)

# Inspect database
sqlite3 backend/data/db/linkedin_assistant.db "SELECT COUNT(*) FROM applications;"

# Check logs
tail -f backend/data/logs/app.log
```

---

## Performance Optimization

### Reduce System Resource Usage

```python
# In app/config.py:
ACTION_DELAY_MIN = 5.0          # Slower (less aggressive)
ACTION_DELAY_MAX = 15.0         # More breaks
DAILY_APPLY_LIMIT = 10          # Fewer applications
```

### Improve Automation Speed

```python
# In app/config.py:
ACTION_DELAY_MIN = 1.0          # Faster (more aggressive)
ACTION_DELAY_MAX = 5.0          # Less waiting
DAILY_APPLY_LIMIT = 50          # More applications (RISKY!)
```

### Monitor Resource Usage

```bash
# Watch memory and CPU
top -p $(pgrep -f "uvicorn")

# Or use htop
htop

# Check database size
ls -lh backend/data/db/linkedin_assistant.db
```

---

## Upgrading

### To Update Dependencies

```bash
cd backend/backend
source venv/bin/activate
pip install --upgrade -e .
python -m playwright install chromium  # Update Playwright
```

### To Update Extension Code

```
1. Edit files in chrome-extension/src/
2. Go to chrome://extensions/
3. Find extension, click refresh icon
4. Changes take effect immediately
```

### To Update Backend Code

```bash
# If uvicorn is running with --reload:
# 1. Edit Python files
# 2. Server automatically restarts
# 3. Changes take effect immediately

# If not using --reload, restart manually:
# 1. Stop server (Ctrl+C)
# 2. Start again: python -m uvicorn app.main:app --reload
```

---

## Production Deployment (Future)

### Cloud Deployment Options

**Option 1: AWS EC2 + CloudFront**
```
- Backend: EC2 instance (t3.small)
- Database: RDS PostgreSQL
- Extension: Published on Chrome Web Store
- Cost: ~$30-50/month
```

**Option 2: Heroku**
```
- Push backend code: git push heroku main
- Automatic SSL/HTTPS
- Cost: ~$7/month (eco dyno)
```

**Option 3: Docker Container**
```
- Build: docker build -t linkedin-app .
- Push: docker push repo/linkedin-app
- Deploy: Any container platform (ECS, K8s, etc.)
```

### Example Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt && \
    python -m playwright install chromium

COPY backend/ .
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Security Checklist

- [ ] Database encrypted (add encryption for production)
- [ ] API requires authentication (add for production)
- [ ] HTTPS enabled (add SSL certificate)
- [ ] CORS properly configured (check manifest.json)
- [ ] Secrets not in version control (.env in .gitignore)
- [ ] Regular backups of database
- [ ] Monitor for LinkedIn account restrictions
- [ ] Rate limits adjusted for safe automation

---

## Support & Debugging

### Getting Help

1. Check [TESTING_GUIDE.md](./TESTING_GUIDE.md) for test procedures
2. Check [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for common issues
3. Review backend logs: `tail -f backend/data/logs/app.log`
4. Check database: `sqlite3 backend/data/db/linkedin_assistant.db`
5. Open browser DevTools (F12) for extension errors

### Reporting Issues

Include:
- Error message (exact text)
- Steps to reproduce
- Browser console output (F12)
- Backend logs (last 50 lines)
- Database state (if applicable)

---

**Version:** 0.1.0
**Status:** Production-ready for local use
**Last Updated:** March 2026
