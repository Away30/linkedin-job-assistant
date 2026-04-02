# LinkedIn Smart Job Application Assistant

A Chrome extension + Python backend tool for automating LinkedIn job applications with human-like behavior, safety features, and real-time tracking.

## 🎯 Features

### Core Features (MVP)
- **Auto-Apply to Jobs** — Automatically search and apply to LinkedIn Easy Apply positions
- **Smart Filtering** — Pre-configured search filters for position, location, experience level, salary range
- **Resume Management** — Upload and manage multiple resume versions with target role assignments
- **Rate Limiting** — Daily caps on applications (default: 25/day) with 7-day warmup schedule
- **Human-Like Behavior** — Random delays (3-12s), mouse curves, scrolling, occasional breaks

### UI Features
- **Popup Dashboard** — Quick status, today's apply count, start/stop controls
- **Options Page** — Configure filters, upload resumes, adjust safety settings
- **Application Tracker** — View all applications in a searchable table (like future-express.net)
- **Real-Time Status** — Stream updates while automation is running

### Safety Features
- **Persistent Login** — Manual login once, session persists across restarts
- **Fingerprint Consistency** — Same User-Agent, viewport, timezone across sessions
- **CAPTCHA Detection** — Automatic pause if CAPTCHA detected
- **Operation Logging** — Full audit trail of all actions

---

## 📦 Architecture

```
├── Chrome Extension (MV3)
│   ├── Popup (quick controls)
│   ├── Options Page (filter/resume management)
│   ├── Dashboard (application tracker)
│   ├── Service Worker (API proxy & message bus)
│   └── Content Scripts (LinkedIn page detection)
│
└── Python Backend (FastAPI + Playwright)
    ├── REST API (localhost:8899/api/v1)
    ├── SQLite Database (local storage)
    ├── Playwright Browser Automation
    └── Safety & Rate Limiting Modules
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (optional, for building extension)
- Chrome/Chromium browser
- LinkedIn account

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd linkedin-job-assistant/backend
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -e .
   ```

4. **Initialize database:**
   ```bash
   python -c "from app.db.session import init_db; init_db()"
   ```

5. **Start backend server:**
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8899 --reload
   ```
   You should see: `Uvicorn running on http://127.0.0.1:8899`

### Chrome Extension Setup

1. **Open Chrome Extensions page:**
   - Go to `chrome://extensions/`
   - Enable **Developer mode** (toggle in top-right)

2. **Load extension:**
   - Click **Load unpacked**
   - Select the `linkedin-job-assistant/chrome-extension/` folder

3. **Pin the extension:**
   - Click the puzzle icon in Chrome toolbar
   - Find "LinkedIn Smart Apply Assistant" and pin it

### First Time Use

1. **Open extension popup** (click pinned icon)
   - You should see "Backend connected ✓"

2. **Go to Settings** (options page)
   - Create a search filter (e.g., "Python Engineer, San Francisco")
   - Upload your resume (PDF)
   - Adjust rate limits if desired

3. **Start automation:**
   - In popup, select the filter from dropdown
   - Click "Start Auto-Apply"
   - Browser will launch (headed mode) — manually log into LinkedIn
   - Once logged in, the automation will start searching and applying

---

## 🔌 API Endpoints

Base URL: `http://localhost:8899/api/v1`

### Automation
| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/automation/start` | Start auto-apply session |
| `POST` | `/automation/stop` | Stop gracefully |
| `GET` | `/automation/status` | Get current status |
| `GET` | `/automation/status/stream` | Stream status updates (SSE) |

### Jobs
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/jobs` | List scraped jobs (paginated) |
| `POST` | `/jobs` | Create/save job |
| `GET` | `/jobs/{id}` | Get job details |

### Applications
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/applications` | List applications with filters |
| `PATCH` | `/applications/{id}` | Update application status/notes |
| `GET` | `/applications/stats` | Analytics: daily counts, success rates |

### Resumes
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/resumes` | List all resumes |
| `POST` | `/resumes` | Upload new resume (multipart/form-data) |
| `DELETE` | `/resumes/{id}` | Delete resume |

### Search Filters
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/filters` | List saved filters |
| `POST` | `/filters` | Create filter |
| `PUT` | `/filters/{id}` | Update filter |
| `DELETE` | `/filters/{id}` | Delete filter |

---

## ⚙️ Configuration

### Backend Config (app/config.py)
- `DAILY_APPLY_LIMIT`: 25 (max applications per day)
- `DAILY_CONNECT_LIMIT`: 20 (max connection requests per day)
- `ACTION_DELAY_MIN`: 3s (minimum delay between actions)
- `ACTION_DELAY_MAX`: 12s (maximum delay between actions)
- `WARMUP_DAYS`: 7 (days to reach full rate from new account)
- `HEADLESS`: False (show browser during automation)
- `DATABASE_URL`: SQLite file path

### Form Answers (data/config/form_answers.yaml)
Pre-configured answers for common form fields:
```yaml
contact_info:
  phone: "555-123-4567"
  email: "user@example.com"

common_questions:
  work_authorization: "Yes"
  sponsorship_required: "No"
  willing_to_relocate: "No"
  years_of_experience: "5"
```

---

## 📊 Data Storage

### SQLite Database (data/db/linkedin_assistant.db)

**Tables:**
- `jobs` — Scraped job listings
- `applications` — Application history with status
- `resumes` — Resume metadata and file paths
- `search_filters` — Saved search filter presets
- `operation_logs` — Audit trail of all operations
- `connections` — Sent connection requests (Phase 2)

---

## 🛡️ Safety & Anti-Detection

### Built-In Protections
1. **Playwright persistent context** — Preserves login cookies across sessions
2. **Random action delays** — Gaussian distribution, not uniform random
3. **Human-like mouse movement** — Bezier curves, variable speed
4. **Occasional breaks** — 30-120s pauses to simulate reading
5. **Consistent fingerprint** — Same User-Agent and viewport every session
6. **CAPTCHA detection** — Automatic pause with user notification
7. **Rate limiting** — Hard daily caps, gradual warmup for new accounts

### Best Practices
- **Never automate login** — User logs in manually once per session
- **Run during business hours** — 9am-5pm is less suspicious
- **Take breaks** — Run for max 2 hours, pause 5-15 minutes
- **Start small** — Apply to 3-5 jobs on day 1, increase gradually
- **Monitor account** — Check LinkedIn daily for any restriction notices

---

## 🐛 Troubleshooting

### Backend won't start
```bash
# Make sure venv is activated
source venv/bin/activate

# Check dependencies
pip install -e .

# Try running directly
python -m uvicorn app.main:app --host 127.0.0.1 --port 8899
```

### Extension not connecting to backend
- Verify backend is running: `curl http://127.0.0.1:8899/health`
- Check extension permissions in `chrome://extensions/`
- Reload extension (Ctrl+R on extension page)
- Check browser console for errors (F12)

### Applications not applying
- Check that resume is uploaded and marked as default
- Verify search filter is created
- Check backend logs: `tail -f data/logs/app.log`
- Look for CAPTCHA or unusual LinkedIn behavior

### Browser not launching
- Ensure Playwright is installed: `pip install playwright`
- Install Chromium: `playwright install chromium`

---

## 📝 Project Structure

```
linkedin-job-assistant/
├── chrome-extension/
│   ├── manifest.json
│   ├── src/
│   │   ├── popup/              # Quick status & controls
│   │   ├── options/            # Settings page
│   │   ├── dashboard/          # Application tracker
│   │   ├── background/         # Service worker
│   │   ├── content/            # Content scripts
│   │   └── assets/             # Icons, styles
│   └── dist/                   # Built extension
│
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app
│   │   ├── config.py           # Settings
│   │   ├── api/                # API routes
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── db/                 # Database session
│   │   ├── services/           # Business logic
│   │   ├── automation/         # Browser automation
│   │   ├── safety/             # Rate limiting, stealth
│   │   └── utils/              # Helpers
│   ├── data/
│   │   ├── db/                 # SQLite database
│   │   ├── resumes/            # PDF storage
│   │   ├── logs/               # Operation logs
│   │   ├── browser_profile/    # Playwright profile
│   │   └── config/             # form_answers.yaml
│   ├── tests/                  # Unit tests
│   ├── pyproject.toml          # Dependencies
│   └── venv/                   # Virtual environment
│
└── docs/
    ├── setup.md                # This file
    ├── architecture.md         # Design details
    └── api-reference.md        # API documentation
```

---

## 🔄 Workflow

### Session Flow
1. **User clicks "Start Auto-Apply"** in extension popup
2. **Service worker sends request** to backend `/automation/start`
3. **Backend launches Playwright browser** (headed mode)
4. **User manually logs into LinkedIn** (one-time per session)
5. **Backend verifies login**, then starts automation loop
6. **For each job:**
   - Navigate to job listing
   - Extract job details
   - Click "Easy Apply"
   - Fill form fields using pre-configured answers
   - Upload resume
   - Submit application
   - Record result in database
   - Random delay before next job
7. **Popup updates in real-time** with progress
8. **When done or stopped**, session closes gracefully

---

## 📈 Future Phases

### Phase 2: Smart Connections
- Auto-send personalized connection requests to HR/recruiters
- Track connection acceptance rates
- Follow-up messaging

### Phase 3: Job Matching
- ML-based job relevance scoring
- Auto-select best matching resume per job
- Prioritize applications by match score

### Phase 4: Advanced Features
- Multi-account support
- Interview scheduling integration
- Follow-up reminders
- Salary negotiation insights

---

## ⚖️ Legal Disclaimer

This tool automates job applications on LinkedIn. Users are responsible for ensuring compliance with:
- LinkedIn's Terms of Service
- Local employment laws
- Your jurisdiction's regulations

LinkedIn has automated detection systems and may restrict accounts for suspicious activity. Use responsibly and always review what you're applying for.

---

## 📧 Support & Contributing

For issues, feature requests, or contributions:
1. Check existing GitHub issues
2. Review troubleshooting section above
3. Check backend logs: `data/logs/`
4. Check browser console: F12 in Chrome

---

**Version:** 0.1.0
**Status:** MVP (Auto-Apply Feature)
**Last Updated:** March 2026
