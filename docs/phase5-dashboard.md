# Phase 5: Streamlit Dashboard Guide

This document provides a comprehensive guide to the AudioWatch dashboard, including features, navigation, and usage instructions.

## Overview

The dashboard provides a web-based interface for browsing listings, managing watch rules, viewing analytics, and monitoring notification history. Built with Streamlit 1.40+, it uses the modern navigation API for a clean multi-page experience.

---

## Phase 4 vs Phase 5: What Changed?

### Phase 4 Recap: Scheduler

Phase 4 implemented **automated background monitoring** using APScheduler:

| Component | What It Does |
|-----------|--------------|
| **ScrapeScheduler** | Runs scrapes at configurable intervals (1-60 min) |
| **Job Persistence** | Saves scheduler state to SQLite for restart survival |
| **Signal Handlers** | Graceful shutdown on Ctrl+C / SIGTERM |
| **Page Limits** | Separate limits for initial vs scheduled scrapes |

**Phase 4 Limitation:** All interaction was command-line only. Users had to:
- Edit `config.yaml` manually to change watch rules
- Run CLI commands to view listings (`audiowatch listings`)
- Check logs to see notification history
- No visual way to analyze price trends

### Phase 5 Addition: Web Dashboard

Phase 5 adds a **visual interface** for everything you could do via CLI (and more):

| Component | What It Does |
|-----------|--------------|
| **Streamlit App** | Web-based UI at localhost:8501 |
| **Listings Browser** | Search, filter, view details with price history |
| **Rule Manager** | Create/edit/delete watch rules from UI |
| **Analytics** | Plotly charts for price trends and distributions |
| **Notification History** | View all sent notifications with filters |

### Comparison Table

| Aspect | Phase 4 (Scheduler) | Phase 5 (Dashboard) |
|--------|---------------------|---------------------|
| **Purpose** | Automate scraping | Visualize and manage |
| **Interface** | CLI only | Web browser |
| **Rule Management** | Edit config.yaml | UI forms |
| **Viewing Listings** | `audiowatch listings` | Interactive table |
| **Analytics** | None | Plotly charts |
| **Notification History** | Check logs | Searchable table |

### How They Work Together

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INTERACTION                                 │
│                                                                          │
│   ┌─────────────────────┐              ┌─────────────────────────────┐  │
│   │    CLI Commands     │              │    Streamlit Dashboard      │  │
│   │  - audiowatch run   │              │  - Browse listings          │  │
│   │  - audiowatch init  │              │  - Manage rules             │  │
│   │  - audiowatch rules │              │  - View analytics           │  │
│   └──────────┬──────────┘              └──────────────┬──────────────┘  │
│              │                                        │                  │
└──────────────┼────────────────────────────────────────┼──────────────────┘
               │                                        │
               ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           PHASE 4: Scheduler                             │
│                                                                          │
│   ┌─────────────────┐                                                   │
│   │   APScheduler   │──── every N minutes ────┐                         │
│   │   (Background)  │                         │                         │
│   └─────────────────┘                         ▼                         │
│                                    ┌─────────────────────┐              │
│                                    │    Scrape Job       │              │
│                                    │  (HeadFi Scraper)   │              │
│                                    └──────────┬──────────┘              │
│                                               │                          │
└───────────────────────────────────────────────┼──────────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           PHASE 3: Matching                              │
│                                                                          │
│   ┌──────────────┐   ┌──────────────┐   ┌────────────────────────────┐  │
│   │   Database   │◄──│   Listings   │──►│   Rule Evaluator           │  │
│   │   (DuckDB)   │   │   (Parsed)   │   │   (Boolean Expressions)    │  │
│   └──────┬───────┘   └──────────────┘   └─────────────┬──────────────┘  │
│          │                                            │                  │
│          │           ┌────────────────────────────────┘                  │
│          │           ▼                                                   │
│          │   ┌──────────────────┐                                       │
│          │   │   Notifier       │                                       │
│          │   │ (Discord/Email)  │                                       │
│          │   └──────────────────┘                                       │
│          │                                                               │
└──────────┼───────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          PHASE 5: Dashboard                              │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    Streamlit Web App                             │   │
│   │                                                                  │   │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│   │
│   │  │ Overview │ │ Listings │ │  Rules   │ │ Notifs   │ │Analytics││   │
│   │  │          │ │ Browser  │ │ Manager  │ │ History  │ │ Charts ││   │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘│   │
│   │                                                                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              │ reads from                                │
│                              ▼                                           │
│                    ┌─────────────────┐                                  │
│                    │    Database     │                                  │
│                    │    (DuckDB)     │                                  │
│                    └─────────────────┘                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Before and After

**Before Phase 5 (CLI Only):**
```bash
# View listings
audiowatch listings --query "HD800" --limit 20

# Check rules
audiowatch rules

# View notification count
audiowatch status

# No way to:
# - See price trends
# - Edit rules without touching config.yaml
# - View notification details
# - Filter/search interactively
```

**After Phase 5 (Web Dashboard):**
```bash
# Start the dashboard
audiowatch dashboard

# Then in browser:
# - Interactive listing search with filters
# - Create/edit rules via forms
# - View price trend charts
# - Browse notification history
# - Analyze market by category
```

### Code Changes Summary

**Phase 4 created:**
- `src/audiowatch/scheduler/__init__.py` - APScheduler integration
- Modified `cli.py` for continuous monitoring

**Phase 5 created:**
- `src/audiowatch/dashboard/app.py` - Main Streamlit app
- `src/audiowatch/dashboard/db.py` - Database query helpers
- `src/audiowatch/dashboard/pages/overview.py` - Home page
- `src/audiowatch/dashboard/pages/listings.py` - Listing browser
- `src/audiowatch/dashboard/pages/rules.py` - Rule management
- `src/audiowatch/dashboard/pages/analytics.py` - Price charts
- `src/audiowatch/dashboard/pages/notifications.py` - History view

**Phase 4's code is unchanged** - Phase 5 reads the same database that Phase 4 populates.

### Interaction Model

| User Goal | Phase 4 (CLI) | Phase 5 (Dashboard) |
|-----------|---------------|---------------------|
| Start monitoring | `audiowatch run` | Same (CLI) |
| View listings | `audiowatch listings` | Listings page |
| Search listings | `--query "term"` | Search box + filters |
| Create rule | Edit config.yaml | Rules page form |
| Edit rule | Edit config.yaml | Click ✏️ button |
| View notifications | Check logs | Notifications page |
| Price analysis | Not available | Analytics page |
| Check status | `audiowatch status` | Overview page |

---

## Starting the Dashboard

```bash
# Start with default settings (localhost:8501)
audiowatch dashboard

# Or specify a custom config
audiowatch dashboard --config /path/to/config.yaml
```

The dashboard will be available at `http://localhost:8501`.

## Pages

### 1. Overview (Home)

The overview page provides a quick snapshot of your AudioWatch instance:

**Key Metrics:**
- Total listings in database
- Active listings count
- Notifications sent (with 24h delta)
- Average listing price

**Last Scrape Status:**
- Start time and duration
- Success/failure status
- Pages scraped
- New vs updated listings

**Category Breakdown:**
- Listing counts per category
- Percentage distribution

**Scrape History:**
- Table of recent scrapes with status and statistics

### 2. Listings Browser

A powerful interface for searching and browsing Head-Fi listings.

**Filters:**
| Filter | Description |
|--------|-------------|
| Search | Title keyword search |
| Category | Filter by listing category |
| Price Range | Slider for min/max price |
| Status | Active, Sold, Expired, or All |

**Features:**
- Sortable data table with all listing details
- Click to view detailed listing information
- Price history chart for individual listings
- Direct link to Head-Fi listing page
- Listing image preview (when available)

**Listing Detail View:**
- Full title and status badge
- Price, condition, category
- Seller info and reputation
- Shipping regions
- Timestamps (listed, last edited)
- Price history chart

### 3. Watch Rules Management

Create and manage your watch rules directly from the dashboard.

**Rule List:**
- All rules displayed as cards
- Status indicator (enabled/disabled)
- Expression preview
- Quick action buttons:
  - ✏️ Edit
  - ⏸️/▶️ Toggle enabled
  - 🗑️ Delete

**Create Rule Form:**
- Rule name
- Boolean expression
- Notification channels (discord, email)
- Enable/disable toggle

**Expression Syntax Help:**
- Built-in documentation panel
- Boolean operators (AND, OR, NOT)
- Comparison operators (=, !=, <, >, <=, >=)
- String operators (contains, startswith, endswith, matches, fuzzy_contains)
- Available fields reference
- Example expressions

### 4. Notifications History

View all notifications sent by AudioWatch.

**Statistics:**
- Total sent
- Successful vs failed
- Last 24 hours count
- Breakdown by channel (Discord, Email)

**Notification Table:**
- Listing title
- Rule that triggered it
- Channel used
- Timestamp
- Success/failure status
- Error message (if failed)

**Filters:**
- Filter by channel
- Filter by status (successful/failed)

**Detail View:**
- Full notification details
- Link to original listing
- Listing metadata (price, category, seller)

### 5. Analytics

Price trends and statistical analysis of the classifieds market.

**Overview Charts:**
- Listings over time (30-day area chart)
- Average price by category (multi-line chart)
- Category distribution (pie chart)
- Price distribution (histogram)

**Category Deep Dive:**
- Select any category for detailed analysis
- Category-specific stats (avg, min, max price)
- Price distribution histogram
- Top sellers in category
- Recent listings table

## Architecture

### File Structure

```
src/audiowatch/dashboard/
├── __init__.py          # Package init, exports main()
├── app.py               # Main Streamlit app with navigation
├── db.py                # Database helper functions
└── pages/
    ├── __init__.py
    ├── overview.py      # Overview/home page
    ├── listings.py      # Listings browser
    ├── rules.py         # Watch rules management
    ├── analytics.py     # Price trends & analytics
    └── notifications.py # Notification history
```

### Database Access

The dashboard uses a separate database helper module (`db.py`) that provides:
- Cached SQLAlchemy engine (via `@st.cache_resource`)
- Query functions that return Pandas DataFrames
- Automatic session management

All queries are read-only except for watch rule management (create, update, delete).

### Navigation

Uses Streamlit's `st.navigation()` and `st.Page()` API (introduced in v1.36):

```python
pages = {
    "Dashboard": [
        st.Page(overview.render, title="Overview", icon="🏠", default=True),
        st.Page(listings.render, title="Listings", icon="📋"),
    ],
    "Management": [
        st.Page(rules.render, title="Watch Rules", icon="👁️"),
        st.Page(notifications.render, title="Notifications", icon="🔔"),
    ],
    "Analytics": [
        st.Page(analytics.render, title="Price Trends", icon="📈"),
    ],
}
pg = st.navigation(pages)
pg.run()
```

## Configuration

Dashboard settings in `config.yaml`:

```yaml
dashboard:
  port: 8501        # Web server port
  host: "localhost" # Bind address (use "0.0.0.0" for network access)
```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| streamlit | ≥1.40 | Web framework |
| plotly | ≥5.20 | Interactive charts |
| pandas | ≥2.0 | Data manipulation |

## Troubleshooting

### Dashboard won't start

1. **Database not found:**
   ```
   Database not found at ./data/audiowatch.db
   ```
   Run `audiowatch init` first to create the database.

2. **Port in use:**
   ```
   Port 8501 is already in use
   ```
   Either stop the other process or change the port in config.yaml.

### Charts not showing

- Ensure you have data in the database (run `audiowatch run --once` first)
- Check browser console for JavaScript errors
- Try refreshing the page

### Slow performance

- Large datasets may cause slow initial load
- Use filters to reduce data volume
- Consider limiting historical data retention

## Screenshots

### Overview Page
```
┌─────────────────────────────────────────────────────────────┐
│  AudioWatch Dashboard                                        │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 1,234    │ │   892    │ │    45    │ │  $1,234  │       │
│  │ Total    │ │ Active   │ │ Notified │ │ Avg Price│       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                              │
│  Last Scrape              │  Categories                      │
│  ─────────────            │  ────────────                    │
│  Status: SUCCESS          │  Full-Size: 200 (22%)           │
│  Started: 10:30:00        │  IEMs: 180 (20%)                │
│  Duration: 45s            │  DACs: 150 (17%)                │
│  Pages: 20                │  ...                             │
└─────────────────────────────────────────────────────────────┘
```

### Listings Browser
```
┌─────────────────────────────────────────────────────────────┐
│  Listings Browser                                            │
│                                                              │
│  Filters                                                     │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │ Search...  │ │ Category ▼ │ │ $0 - $10k  │ │ Status ▼ │ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────┘ │
│                                                              │
│  200 listings found                                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Title           │ Price  │ Category │ Condition │ ... │ │
│  │─────────────────│────────│──────────│───────────│─────│ │
│  │ HD800S Mint     │ $1,200 │ Full-Siz │ Excellent │ ... │ │
│  │ LCD-5 w/ Case   │ $3,500 │ Full-Siz │ Like New  │ ... │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Summary

Phase 5 adds a complete web interface to AudioWatch:

| Feature | Implementation |
|---------|----------------|
| Listing browser | Search, filter, detail view, price history |
| Rule management | Full CRUD operations from UI |
| Analytics | Plotly charts for trends and distributions |
| Notifications | History table with filters |
| Navigation | Modern Streamlit multi-page app |

The dashboard complements the CLI by providing a visual interface for monitoring and management tasks that are easier to do in a GUI than on the command line.
