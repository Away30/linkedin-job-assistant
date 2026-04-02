# Architecture Overview

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     Chrome Extension (MV3)                       │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Popup      │  │  Options     │  │   Dashboard          │  │
│  │  (Quick UI)  │  │  (Settings)  │  │   (Applications)     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                 │                      │              │
│         └─────────────────┴──────────────────────┘              │
│                          │                                       │
│                    ┌─────▼──────┐                               │
│                    │  Service    │ (API Proxy)                 │
│                    │  Worker     │ (Message Bus)               │
│                    │  (MV3)      │ (Status Polling)            │
│                    └─────┬───────┘                              │
│                          │                                       │
│         ┌────────────────┴────────────────┐                     │
│         │                                 │                     │
│    ┌────▼────┐                    ┌──────▼───────┐             │
│    │ Content  │                    │ Content      │             │
│    │ Script 1 │                    │ Script 2     │             │
│    │ (Job     │                    │ (Page        │             │
│    │ Detect)  │                    │ Observer)    │             │
│    └──────────┘                    └──────────────┘             │
└─────────────────────────────────────────────────────────────────┘
         │
         │ HTTP/localhost:8899
         │
┌────────▼──────────────────────────────────────────────────────┐
│           Python Backend (FastAPI + Playwright)               │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    FastAPI App                         │  │
│  │                                                         │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │  │
│  │  │  Jobs    │ │Applications │ Resumes │ │ Filters │ │  │
│  │  │   API    │ │    API     │   API    │ │   API   │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ │  │
│  │                                                         │  │
│  │  ┌──────────────────────────────────────────────────┐ │  │
│  │  │         Automation Control API                   │ │  │
│  │  │  /automation/start  /automation/stop /status     │ │  │
│  │  └──────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────┘  │
│                           │                                    │
│          ┌────────────────┼────────────────┐                 │
│          │                │                │                 │
│  ┌───────▼────────┐ ┌─────▼──────┐ ┌─────▼────────┐        │
│  │    Services    │ │ Automation │ │    Safety    │        │
│  │    Layer       │ │   Layer    │ │    Layer     │        │
│  │                │ │            │ │              │        │
│  │ - Automation   │ │ - Browser  │ │ - Rate       │        │
│  │   Service      │ │   Manager  │ │   Limiter    │        │
│  │                │ │ - Job      │ │ - Stealth    │        │
│  │                │ │   Searcher │ │ - Warmup     │        │
│  │                │ │ - Job      │ │ - Alert      │        │
│  │                │ │   Scraper  │ │   Manager    │        │
│  │                │ │ - Easy     │ │              │        │
│  │                │ │   Apply    │ │              │        │
│  │                │ │ - Form     │ │              │        │
│  │                │ │   Filler   │ │              │        │
│  │                │ │ - Human    │ │              │        │
│  │                │ │   Simulator│ │              │        │
│  └────────────────┘ └────────────┘ └──────────────┘        │
│         │                    │                  │            │
└─────────┼────────────────────┼──────────────────┼────────────┘
          │                    │                  │
    ┌─────▼────────────────────▼──────────────────▼────┐
    │            SQLite Database                       │
    │  /data/db/linkedin_assistant.db                  │
    │                                                   │
    │  ┌─────────┬──────────┬───────────┬────────────┐│
    │  │  jobs   │   apps   │  resumes  │  filters   ││
    │  ├─────────┼──────────┼───────────┼────────────┤│
    │  │ logs    │connections│ settings  │   (6 tables)││
    │  └─────────┴──────────┴───────────┴────────────┘│
    └───────────────────────────────────────────────────┘
          │
    ┌─────▼──────────────────────┐
    │  Playwright Browser         │
    │  (Persistent Context)       │
    │                             │
    │  - LinkedIn.com login       │
    │  - Job search              │
    │  - Apply automation        │
    │  - Form filling            │
    │  - Resume upload           │
    └─────┬──────────────────────┘
          │
    ┌─────▼──────────────────────┐
    │   LinkedIn.com             │
    │   (Target System)          │
    └────────────────────────────┘
```

## Message Flow

### 1. User Starts Auto-Apply

```
User clicks "Start" in Popup
    │
    └─> Popup.js sends message to Service Worker
           │
           └─> chrome.runtime.sendMessage({ action: "startAutomation", ... })
                  │
                  └─> Service Worker receives message
                        │
                        └─> Calls backend: POST /api/v1/automation/start
                             │
                             └─> FastAPI processes request
                                  │
                                  └─> AutomationService.start() begins
                                       │
                                       └─> Launches Playwright browser
```

### 2. Browser Automation Loop

```
AutomationService starts
    │
    ├─> LinkedIn Auth (manual login)
    │
    ├─> FOR EACH search filter:
    │    │
    │    ├─> JobSearcher navigates LinkedIn search
    │    │
    │    ├─> JobScraper extracts job listings
    │    │
    │    └─> FOR EACH job:
    │         │
    │         ├─> Check rate limiter (25/day limit)
    │         │
    │         ├─> EasyApplyHandler:
    │         │    ├─> Click "Easy Apply"
    │         │    ├─> FormFiller fills fields
    │         │    ├─> Upload resume
    │         │    └─> Submit form
    │         │
    │         ├─> Record in database
    │         │
    │         ├─> HumanSimulator.random_delay(3-12s)
    │         │
    │         └─> Update status (broadcast to popup)
    │
    └─> Session ends (user clicks stop or daily limit reached)
```

### 3. Real-Time Status Updates

```
Backend running /automation/status
    │
    └─> Service Worker polls every 2 seconds
           │
           └─> Updates chrome.storage.local
                  │
                  └─> Popup reads from storage
                       │
                       └─> Displays "12 applied, 2 failed"
```

## Data Models

### Job
```
Job(id, linkedin_job_id, title, company, location, description, 
    job_url, is_easy_apply, salary_range, match_score, posted_date, 
    scraped_at, created_at)
```

### Application
```
Application(id, job_id, resume_id, status, applied_at, apply_method,
           form_answers, error_message, notes, created_at, updated_at)
```

### SearchFilter
```
SearchFilter(id, name, keywords, location, experience_level, 
             job_type, easy_apply_only, salary_min, date_posted,
             is_active, created_at, updated_at)
```

### Resume
```
Resume(id, name, file_path, file_hash, target_roles, is_default,
       created_at)
```

### OperationLog
```
OperationLog(id, operation_type, details, status, duration_ms,
            created_at)
```

## Key Design Patterns

### 1. Service Worker as API Proxy
- Content scripts cannot access localhost due to CORS
- Service worker proxies all HTTP calls
- Solves cross-origin restriction problem

### 2. Persistent Browser Context
- Single Playwright browser instance (singleton)
- Reuses login session across application restarts
- Stores profile in `data/browser_profile/`

### 3. Manual Login Strategy
- Avoid automating LinkedIn login (high detection risk)
- User logs in once manually
- Persistent context preserves session cookies

### 4. Rate Limiting + Warmup
- Hard daily caps (25 applies, 20 connects)
- Gradual ramp-up over 7 days for new accounts
- Prevents suspicious activity patterns

### 5. Async/Await Automation
- FastAPI + Playwright native async support
- Non-blocking I/O for browser interactions
- Efficient concurrency handling

## Extension Architecture (MV3)

### Manifest V3 Changes
- Service Worker (not background page)
- Async message passing (no blocking)
- Content Security Policy enforcement

### Message Types

**From Popup/Options to Service Worker:**
```javascript
{
  action: "apiCall",
  method: "GET|POST|PUT|PATCH|DELETE",
  path: "/api/v1/...",
  body: {...} // optional
}
```

**From Service Worker to Backend:**
```
HTTP Request to localhost:8899/api/v1/...
Headers: Content-Type: application/json
```

**From Backend to Service Worker:**
```
HTTP Response (JSON)
{ok: boolean, data: any, status: number}
```

## Security Model

### Local Storage
- All data stored on user's machine
- SQLite database file unencrypted (add encryption if needed)
- Resumes stored as files in `data/resumes/`

### Browser Isolation
- Playwright runs in isolated user profile
- No shared state with main Chrome profile
- Can be easily cleaned/reset

### Credential Handling
- LinkedIn credentials never stored
- User logs in manually once per session
- Cookies stored by Playwright automatically

### API Security
- No authentication required (localhost only)
- CORS allows only chrome-extension://* origin
- Input validation on all endpoints

## Scalability Considerations

### Current Limits
- Single browser instance (per-device limit)
- Concurrent jobs: 1 (sequential processing)
- Rate limits: 25 applies/day (configurable)

### Future Scaling
- Multi-account support: Multiple browser instances
- Parallel jobs: Job queue with worker pool
- Cloud deployment: Database migration to PostgreSQL

## Error Handling Strategy

```
Try Operation
    │
    ├─ Success → Record in OperationLog (status: success)
    │            Update database
    │            Update status message
    │
    └─ Failure → Log error details
                 Record in OperationLog (status: failed)
                 Send notification to user
                 Continue to next job
                 Skip retry (fail-forward approach)
```

## Deployment Architecture

### Development
```
chrome-extension/ (Load unpacked)
   │
   └─> localhost:8899 (python -m uvicorn)
        │
        └─> SQLite (local file)
        └─> Playwright (local Chromium)
        └─> LinkedIn.com (live)
```

### Production (Future)
```
Chrome Web Store (Published extension)
   │
   └─> cloudapi.example.com (Cloud backend)
        │
        └─> PostgreSQL (RDS)
        └─> Kubernetes (Browser instances)
        └─> LinkedIn.com (live)
```

---

**Last Updated:** March 2026
**Version:** 0.1.0 (MVP)
