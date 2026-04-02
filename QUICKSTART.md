# Quick Start Guide

Get the LinkedIn Auto-Apply tool running in 5 minutes.

## Step 1: Start the Backend

```bash
cd linkedin-job-assistant/backend
source venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8899
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8899
```

**Verify it's working:**
```bash
curl http://127.0.0.1:8899/health
# Should return: {"status":"ok","app":"LinkedIn Job Assistant"}
```

## Step 2: Load Chrome Extension

1. Open `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked**
4. Select: `linkedin-job-assistant/chrome-extension/`
5. Pin the extension to your toolbar

## Step 3: Create Your First Filter

1. Click the extension icon (pinned in toolbar)
2. Click **Settings**
3. Fill in search criteria:
   - Filter Name: "Software Engineer"
   - Keywords: "Python, Backend"
   - Location: "San Francisco, CA"
   - Experience Level: "Senior"
   - ✓ Easy Apply Only
4. Click **Save Filter**

## Step 4: Upload Resume

Still in Settings:
1. Name: "Software Engineer Resume"
2. Select file: (your resume PDF)
3. Target Roles: "Software Engineer, Backend Engineer"
4. ✓ Set as Default
5. Click **Upload Resume**

## Step 5: Start Automation

1. Click extension popup again
2. Select your filter from dropdown
3. Click **Start Auto-Apply**
4. A Chrome browser window opens — **manually log into LinkedIn**
5. After login, automation starts automatically
6. Watch progress in the popup

## Step 6: View Applications

1. Click **Dashboard** in popup
2. See all your applications in a table
3. Filter by position, company, or status
4. Export to CSV

---

## Testing the API

Test endpoints directly (backend must be running):

```bash
# List filters
curl http://127.0.0.1:8899/api/v1/filters

# List applications
curl http://127.0.0.1:8899/api/v1/applications

# Get automation status
curl http://127.0.0.1:8899/api/v1/automation/status

# Check health
curl http://127.0.0.1:8899/health
```

---

## Common Issues

**"Backend offline" in extension popup**
- Backend server not running (check step 1)
- Wrong port (should be 8899)
- `curl http://127.0.0.1:8899/health` to verify

**"Please log in to LinkedIn" message
- Browser is waiting for you to log in manually
- Open the browser window and enter your credentials
- After login, automation will start

**Applications not being created
- Resume not uploaded yet (required)
- Filter not selected (dropdown in popup)
- Browser window closed during automation

---

## Next Steps

1. Review safety settings in Settings page
2. Adjust rate limits if needed (default: 25 apps/day)
3. Read full [README.md](./README.md) for detailed documentation
4. Check [API reference](./docs/api-reference.md) for all endpoints

---

Good luck with your job search! 🚀
