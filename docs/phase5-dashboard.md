# Phase 5: Streamlit Dashboard Guide

This document provides a comprehensive guide to the AudioWatch dashboard, including features, navigation, and usage instructions.

## Overview

The dashboard provides a web-based interface for browsing listings, managing watch rules, viewing analytics, and monitoring notification history. Built with Streamlit 1.40+, it uses the modern navigation API for a clean multi-page experience.

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
