# Phase 4: Scheduler Implementation Guide

This document provides a comprehensive explanation of the scheduler system implemented in Phase 4 of AudioWatch, including architecture details, configuration options, and usage instructions.

## Overview

Phase 4 introduces automated, continuous monitoring of Head-Fi classifieds using APScheduler. The scheduler runs scrape jobs at configurable intervals, persists job state across restarts, and handles graceful shutdown when interrupted.

---

## Phase 3 vs Phase 4: What Changed?

### Phase 3 Recap: Matching & Notifications

Phase 3 implemented the **core logic** for matching listings and sending notifications:

| Component | What It Does |
|-----------|--------------|
| **Matcher/Evaluator** | Parses boolean expressions (`title contains "HD800" AND price < 1000`) |
| **Watch Rules** | User-defined criteria stored in config.yaml |
| **Global Filters** | Baseline filters applied to all rules (listing_type, ships_to, status) |
| **Per-Rule Filters** | Rule-specific overrides for categories and filters |
| **Notifiers** | Discord webhook and Gmail SMTP notification senders |
| **NotificationOrchestrator** | Coordinates matching and notification delivery |

**Phase 3 Limitation:** You had to manually trigger scrapes with `audiowatch run --once`. There was no way to run continuous monitoring.

### Phase 4 Addition: Scheduler

Phase 4 adds the **automation layer** that runs Phase 3's logic repeatedly:

| Component | What It Does |
|-----------|--------------|
| **ScrapeScheduler** | Manages recurring scrape jobs with APScheduler |
| **Job Persistence** | Saves scheduler state to survive restarts |
| **Signal Handlers** | Enables graceful Ctrl+C shutdown |
| **Interval Trigger** | Configurable 1-60 minute scrape intervals |

### Comparison Table

| Aspect | Phase 3 (Matching) | Phase 4 (Scheduler) |
|--------|-------------------|---------------------|
| **Purpose** | Match listings, send notifications | Automate when matching happens |
| **Trigger** | Manual (`--once` flag) | Automatic (timer-based) |
| **Persistence** | Listings in DuckDB | Jobs in SQLite |
| **User Action** | Run command each time | Start once, runs forever |
| **Shutdown** | Immediate exit | Graceful (waits for scrape) |

### How They Work Together

```
┌─────────────────────────────────────────────────────────────┐
│                      PHASE 4: Scheduler                     │
│                                                             │
│   ┌─────────────┐    every N minutes    ┌─────────────┐    │
│   │  APScheduler │ ──────────────────► │ Scrape Job  │    │
│   │  (Timer)     │                      │ (Trigger)   │    │
│   └─────────────┘                       └──────┬──────┘    │
│                                                │            │
└────────────────────────────────────────────────┼────────────┘
                                                 │
                                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                      PHASE 3: Matching                      │
│                                                             │
│   ┌──────────┐   ┌──────────────┐   ┌──────────────────┐   │
│   │ Scraper  │ → │ New Listings │ → │ Rule Evaluator   │   │
│   │ (HTML)   │   │ (Database)   │   │ (Boolean Parser) │   │
│   └──────────┘   └──────────────┘   └────────┬─────────┘   │
│                                              │              │
│                                              ▼              │
│   ┌──────────────────┐   ┌─────────────────────────────┐   │
│   │ Global Filters   │ → │ NotificationOrchestrator    │   │
│   │ Per-Rule Filters │   │ (Discord, Email)            │   │
│   └──────────────────┘   └─────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Before and After

**Before Phase 4 (Manual Monitoring):**
```bash
# User must run manually each time
audiowatch run --once   # 10:00 AM
# ... wait ...
audiowatch run --once   # 10:05 AM
# ... wait ...
audiowatch run --once   # 10:10 AM
# Tedious and easy to forget!
```

**After Phase 4 (Automated Monitoring):**
```bash
# Start once, runs forever
audiowatch run
# Scrapes at 10:00, 10:05, 10:10, 10:15... automatically
# Press Ctrl+C when done
```

### Code Changes

**Phase 3 created:**
- `src/audiowatch/matcher/` - Expression parsing and evaluation
- `src/audiowatch/notifier/` - Discord and email notification senders
- Watch rule and filter models in `config.py`

**Phase 4 created:**
- `src/audiowatch/scheduler/__init__.py` - New scheduler module
- Modified `cli.py` to use scheduler when `--once` is not specified

**Phase 3's code is unchanged** - Phase 4 simply calls it on a schedule.

### Key Features

| Feature | Description |
|---------|-------------|
| **Interval Scheduling** | Run scrapes every 1-60 minutes (configurable) |
| **Job Persistence** | Scheduler state survives application restarts |
| **Graceful Shutdown** | Clean shutdown on Ctrl+C or SIGTERM |
| **Single Instance** | Only one scrape runs at a time (prevents overlap) |
| **Missed Run Handling** | Coalesces missed runs into a single execution |
| **Initial Scrape** | Optionally run a scrape immediately on startup |

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     AudioWatch CLI                          │
│                    (audiowatch run)                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    ScrapeScheduler                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              APScheduler (Background)                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │  JobStore   │  │  Executor   │  │   Trigger   │  │   │
│  │  │  (SQLite)   │  │ (ThreadPool)│  │ (Interval)  │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Signal Handlers                         │   │
│  │         (SIGINT, SIGTERM, SIGBREAK)                 │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Scrape Job Function                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Scraper  │→ │ Database │→ │ Matcher  │→ │ Notifier │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. ScrapeScheduler Class

The main scheduler class that wraps APScheduler and provides:

- **Initialization**: Sets up job stores, executors, and job defaults
- **Job Management**: Adds/removes the scrape job with configurable intervals
- **Signal Handling**: Catches shutdown signals for graceful termination
- **Lifecycle Management**: Start, stop, and blocking run methods

```python
# Location: src/audiowatch/scheduler/__init__.py

class ScrapeScheduler:
    def __init__(self, settings, scrape_func, job_store_path=None):
        # Initialize APScheduler with persistence

    def start(self, run_immediately=True):
        # Start the scheduler

    def stop(self):
        # Gracefully stop the scheduler

    def run_blocking(self, run_immediately=True):
        # Start and block until shutdown signal
```

#### 2. Job Store (Persistence)

The scheduler uses SQLAlchemy-based job persistence:

```
data/
├── audiowatch.db      # Main application database (DuckDB)
└── scheduler.db       # Scheduler job store (SQLite)
```

**Why separate databases?**
- APScheduler's SQLAlchemy job store requires SQLite/PostgreSQL
- DuckDB (main database) is optimized for analytics, not job scheduling
- Separation keeps concerns isolated

**What's persisted:**
- Job ID and name
- Next scheduled run time
- Trigger configuration
- Job state (paused/active)

#### 3. Executor Configuration

```python
executors = {
    "default": ThreadPoolExecutor(max_workers=1),  # Single worker
}

job_defaults = {
    "coalesce": True,           # Combine missed runs
    "max_instances": 1,         # Only one instance at a time
    "misfire_grace_time": 300,  # 5-minute grace period
}
```

| Setting | Value | Purpose |
|---------|-------|---------|
| `max_workers` | 1 | Prevents concurrent scrapes |
| `coalesce` | True | If multiple runs were missed, only run once |
| `max_instances` | 1 | Never run the same job concurrently |
| `misfire_grace_time` | 300s | How late a job can start and still run |

#### 4. Signal Handlers

The scheduler registers handlers for clean shutdown:

| Signal | Platform | Trigger |
|--------|----------|---------|
| `SIGINT` | All | Ctrl+C |
| `SIGTERM` | Unix | `kill` command, Docker stop |
| `SIGBREAK` | Windows | Ctrl+Break |

When a signal is received:
1. Log the shutdown request
2. Stop accepting new jobs
3. Wait for current scrape to complete
4. Clean up resources
5. Exit gracefully

---

## Configuration

### Scraper Settings

Configure the scheduler in `config.yaml`:

```yaml
scraper:
  # How often to run scrapes (1-60 minutes)
  poll_interval_minutes: 5

  # How far back to look for listings (days)
  initial_scrape_days: 30

  # Pages per category for initial scrape (thorough)
  initial_max_pages: 10

  # Pages per category for scheduled scrapes (only need recent listings)
  scheduled_max_pages: 2

  # Delay between page requests (rate limiting)
  rate_limit_delay_seconds: 2.0

  # Browser settings
  headless: true
  timeout_seconds: 30
```

### Page Limits Explained

The scheduler uses **different page limits** for initial vs scheduled scrapes:

| Scrape Type | Default Pages | Purpose |
|-------------|---------------|---------|
| **Initial** | 10 per category | Thorough scan on first run (100 pages total) |
| **Scheduled** | 2 per category | Quick check every N minutes (20 pages total) |

**Why the difference?**
- Initial scrape needs to backfill listings from the past 30 days
- Scheduled scrapes run every 5 minutes, so only the most recent listings matter
- Head-Fi classifieds doesn't update fast enough to warrant deep scrapes every 5 minutes
- Lower page limits = faster scrapes, less server load, quicker notifications

### Interval Guidelines

| Use Case | Recommended Interval | Notes |
|----------|---------------------|-------|
| Active hunting | 1-2 minutes | High API load, use sparingly |
| Regular monitoring | 5 minutes | Good balance (default) |
| Casual browsing | 15-30 minutes | Low resource usage |
| Background check | 60 minutes | Minimal load |

**Note:** Lower intervals mean more requests to Head-Fi. Be respectful of their servers.

---

## Usage

### Starting Continuous Monitoring

```bash
# Start with default settings (scrape immediately, then every 5 minutes)
audiowatch run

# Start without initial scrape (useful for resuming)
audiowatch run --skip-initial

# Limit pages per category (faster scrapes)
audiowatch run --max-pages 5

# Show browser window for debugging
audiowatch run --no-headless
```

### Command Options

| Option | Default | Description |
|--------|---------|-------------|
| `--once` | False | Run single scrape and exit |
| `--skip-initial` | False | Don't run scrape on startup |
| `--max-pages` | 10 | Max pages per category |
| `--headless/--no-headless` | True | Browser visibility |
| `--config` | config.yaml | Configuration file path |

### Expected Output

When you run `audiowatch run`, you'll see:

```
Starting scheduled scraper (every 5 minutes)...
Press Ctrl+C to stop

Running initial scrape...
2024-01-11 10:00:00 [info] Starting scheduled scrape
2024-01-11 10:00:05 [info] Scraping category: Full-Size Headphones
2024-01-11 10:00:30 [info] Scraping category: In-Ear Monitors
...
2024-01-11 10:02:00 [info] Scrape results pages_scraped=150 new_listings=5 notifications_sent=2
2024-01-11 10:02:00 [info] Scrape job completed job_id=scrape_headfi

# Next scrape runs automatically at 10:05:00, 10:10:00, etc.
```

### Stopping the Scheduler

Press `Ctrl+C` to stop:

```
^C
2024-01-11 10:03:45 [info] Received shutdown signal signal=SIGINT
2024-01-11 10:03:45 [info] Stopping scheduler...
2024-01-11 10:03:46 [info] Scheduler stopped
```

The scheduler waits for any in-progress scrape to complete before exiting.

---

## How It Works

### Startup Sequence

1. **Load Configuration**: Read `config.yaml` and validate settings
2. **Initialize Database**: Ensure DuckDB tables exist
3. **Create Job Store**: Open/create `scheduler.db` for persistence
4. **Register Signal Handlers**: Set up Ctrl+C handling
5. **Add Scrape Job**: Schedule the recurring job
6. **Run Initial Scrape** (optional): Execute immediately
7. **Enter Main Loop**: Keep process alive, waiting for signals

### Scrape Job Execution

Each scheduled scrape:

1. **Start Scraper**: Launch headless Chromium via Playwright
2. **Scrape Categories**: Iterate through all 10 leaf categories
3. **Parse Listings**: Extract data from HTML pages
4. **Save to Database**: Upsert listings (insert new, update existing)
5. **Match Rules**: Check new listings against watch rules
6. **Send Notifications**: Discord/email for matches
7. **Log Results**: Record scrape statistics

### Persistence Behavior

**On Normal Restart:**
- Scheduler reads job state from `scheduler.db`
- Resumes with the previously configured interval
- If a run was missed, it executes immediately (coalescing)

**On Configuration Change:**
- If `poll_interval_minutes` changes, the job is updated
- Next run uses the new interval

**On Crash:**
- Job state is preserved in `scheduler.db`
- On restart, scheduler picks up where it left off
- Missed runs are coalesced into one

---

## Files Created/Modified

### New Files

| File | Purpose |
|------|---------|
| `src/audiowatch/scheduler/__init__.py` | Scheduler module (380 lines) |
| `data/scheduler.db` | Job persistence database (created at runtime) |
| `docs/phase4-scheduler.md` | This documentation |

### Modified Files

| File | Changes |
|------|---------|
| `src/audiowatch/cli.py` | Added scheduler integration to `run` command |
| `README.md` | Added scheduler section and new command options |

---

## Troubleshooting

### Scheduler Not Starting

**Symptom:** `audiowatch run` exits immediately

**Solutions:**
1. Check for Python errors in output
2. Ensure database is initialized: `audiowatch init`
3. Verify config.yaml exists and is valid

### Scrapes Not Running

**Symptom:** Scheduler starts but no scrapes execute

**Solutions:**
1. Check `poll_interval_minutes` is set (1-60)
2. Look for errors in logs
3. Try `audiowatch run --once` to test scraping independently

### Job Store Errors

**Symptom:** SQLAlchemy errors about scheduler.db

**Solutions:**
```bash
# Remove corrupt job store and restart
rm data/scheduler.db
audiowatch run
```

### Graceful Shutdown Not Working

**Symptom:** Process doesn't stop on Ctrl+C

**Solutions:**
1. Wait a moment - it may be finishing a scrape
2. Press Ctrl+C again (force stop)
3. Check if browser process is stuck: `ps aux | grep chromium`

---

## Advanced Usage

### Running as a Service (systemd)

Create `/etc/systemd/system/audiowatch.service`:

```ini
[Unit]
Description=AudioWatch Head-Fi Monitor
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/AudioWatch
ExecStart=/path/to/venv/bin/audiowatch run
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable audiowatch
sudo systemctl start audiowatch
sudo systemctl status audiowatch
```

### Running with Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -e . && playwright install chromium --with-deps

CMD ["audiowatch", "run"]
```

```bash
docker build -t audiowatch .
docker run -d --name audiowatch \
  -v ./config.yaml:/app/config.yaml \
  -v ./data:/app/data \
  audiowatch
```

### Monitoring Scheduler Health

Check scheduler status:
```bash
audiowatch status
```

View recent scrape logs:
```bash
# Using DuckDB CLI
duckdb data/audiowatch.db "SELECT * FROM scrape_logs ORDER BY started_at DESC LIMIT 10"
```

---

## API Reference

### ScrapeScheduler

```python
from audiowatch.scheduler import ScrapeScheduler, create_scrape_job

# Create a scrape function
scrape_func = create_scrape_job(settings, max_pages=10, headless=True)

# Create scheduler
scheduler = ScrapeScheduler(
    settings=settings,
    scrape_func=scrape_func,
    job_store_path=Path("data/scheduler.db"),  # Optional persistence
)

# Start (non-blocking)
scheduler.start(run_immediately=True)

# Check status
if scheduler.is_running():
    next_run = scheduler.get_next_run_time()
    print(f"Next scrape at: {next_run}")

# Stop
scheduler.stop()

# Or run blocking (recommended for CLI)
scheduler.run_blocking(run_immediately=True)
```

### create_scrape_job

Factory function that creates a synchronous wrapper for the async scrape operation:

```python
def create_scrape_job(
    settings: Settings,      # Application settings
    max_pages: int = 10,     # Max pages per category
    headless: bool = True,   # Browser visibility
) -> Callable[[], None]:
    """Returns a sync function suitable for APScheduler."""
```

---

## Summary

Phase 4 transforms AudioWatch from a manual tool into an automated monitoring service:

| Before Phase 4 | After Phase 4 |
|----------------|---------------|
| Manual `--once` runs | Automatic scheduled runs |
| No persistence | Job state survives restarts |
| Ctrl+C kills immediately | Graceful shutdown |
| Single execution | Continuous monitoring |

The scheduler is designed to be:
- **Reliable**: Persists state, handles crashes
- **Respectful**: Rate-limited, single-instance
- **Flexible**: Configurable intervals, optional initial scrape
- **Observable**: Detailed logging, status commands
