# AudioWatch - Planning Document

## Project Overview

**AudioWatch** is a tool to monitor Head-Fi.org classified listings and send notifications when items matching user-defined criteria become available.

---

## Part 1: Literature Review - Existing Tools

### 1.1 Head-Fi Native Limitations

Head-Fi's built-in search has been problematic since the platform switched to Huddler. Users report:
- Incomplete search results
- Poor sorting capabilities
- No targeted email alerts for specific search terms
- Only options: get alerts for ALL classifieds posts, or manually bookmark searches

**Gap AudioWatch Fills**: There is no existing tool that monitors Head-Fi classifieds and sends targeted notifications for specific items. This is exactly what AudioWatch will provide.

### 1.2 General Marketplace Monitoring Tools

#### Hyacinth (https://github.com/stephanlensky/hyacinth)
**Most relevant reference project**
- Discord bot for marketplace listing notifications
- Python-based with plugin architecture
- Supports Craigslist and Facebook Marketplace out-of-box
- Key features:
  - Complex boolean text filtering rules
  - Configurable polling intervals
  - Search batching to reduce API calls
  - Docker deployment
  - Poetry for dependency management
  - Type-checked with mypy

#### AI Marketplace Monitor (https://pypi.org/project/ai-marketplace-monitor/)
- Uses AI to analyze Facebook Marketplace listings
- Instant notifications when criteria match
- AI-powered listing analysis

#### Product Checker (https://github.com/tnware/product-checker)
- Monitors e-commerce stock availability
- Discord webhook notifications
- Supports Amazon, GameStop, Target

#### Craigslist For Sale Alerts (https://github.com/meub/craigslist-for-sale-alerts)
- Slack/Email notifications for Craigslist items
- Simpler architecture than Hyacinth

### 1.3 Commercial/No-Code Solutions

| Tool | Type | Key Features |
|------|------|--------------|
| Browse AI | No-code | Prebuilt robots, spreadsheet export |
| Octoparse | No-code | CAPTCHA bypass, cloud scraping, templates |
| Apify | Low-code | Pre-built scrapers, Zapier integration |
| n8n | Automation | Open-source workflow automation |

---

## Part 2: Technical Analysis - Head-Fi Classifieds Structure

### 2.1 Page Structure

**Data Available Per Listing:**
- Product image (thumbnail)
- Title/Item name
- Unique Listing ID
- Type: "For Sale", "For Sale/Trade", "Want To Buy"
- Price (USD/EUR)
- Condition (Excellent/Like new, Good, etc.)
- Negotiability (Firm, OBO)
- Shipping regions
- Description snippet
- Seller username + reputation score
- Listed date + last edited timestamp

**Category Hierarchy (All Supported):**
```
Headphones (48K listings)
├── Full-Size (26K)
└── In-Ear Monitors (22K)

Amplification (14K)
├── Desktop (10K)
└── Portable (3K)

Source Components (20K)
├── DACs
├── DAC/Amps
├── DAPs
└── CD Players

Cables, Speakers, Accessories (18K)
Media (85)
```

**Pagination:** 4,971+ pages

### 2.2 Technical Challenges

1. **JavaScript Rendering**: Head-Fi uses dynamic content loading
2. **Anti-Bot Protection**: Need to handle potential rate limiting
3. **Large Dataset**: 100K+ listings across categories
4. **No Official API**: Must rely on HTML scraping

---

## Part 3: Technology Stack Analysis

### 3.1 Web Scraping Options

| Library | Best For | Anti-Bot Handling | Resource Usage |
|---------|----------|-------------------|----------------|
| **Playwright** | Dynamic JS sites | Best (92-95% success with stealth) | High |
| **Selenium** | Legacy browser automation | Moderate (needs plugins) | Very High |
| **BeautifulSoup** | Static HTML parsing | None | Very Low |
| **httpx/requests** | API calls, simple pages | Low | Very Low |

**Stealth Libraries:**
- `playwright-stealth` - Patches Playwright to avoid detection
- `undetected-playwright` - Extended Playwright with fingerprint masking
- `botright` - Advanced anti-detection + CAPTCHA solving

**Decision:** Playwright + playwright-stealth
- Modern async API
- Handles JavaScript rendering
- Strong anti-detection with stealth plugins
- Good documentation

### 3.2 Database: DuckDB

**DuckDB v1.4.3** (Released December 9, 2025)
- In-process analytical database
- Zero external dependencies
- Columnar storage optimized for analytics
- Excellent for price trend analysis
- Native Python API + SQLAlchemy support via `duckdb-engine` v0.17.0

**Key Features:**
- Blazing fast analytical queries
- Handles larger-than-memory workloads
- Direct Pandas/Polars DataFrame integration
- Parquet/CSV/JSON file support
- MIT License

**SQLAlchemy Integration:**
```python
from sqlalchemy import create_engine
engine = create_engine("duckdb:///audiowatch.db")
```

**Note:** DuckDB's SQLAlchemy driver inherits from PostgreSQL dialect. For auto-incrementing primary keys, use `Sequence()` instead of `SERIAL`.

### 3.3 Boolean Expression Parsing

**boolean_parser** library (https://pypi.org/project/boolean-parser/)
- Parses conditional expressions with boolean operators (AND, OR, NOT)
- Built-in SQLAlchemy integration via `SQLAParser` class
- Converts parsed expressions directly to SQLAlchemy filter conditions
- Supports comparison operators: `=`, `!=`, `<`, `>`, `<=`, `>=`, `BETWEEN`

**Example Usage:**
```python
from boolean_parser import parse

# Parse: "Moses AND price < 3500"
result = parse('title contains "Moses" and price < 3500')
filter_expr = result.filter(ListingModel)
session.query(ListingModel).filter(filter_expr).all()
```

**Alternative:** Lark parser for custom DSL if more flexibility needed.

### 3.4 Notification Systems

#### Discord
| Library | Description |
|---------|-------------|
| `discord-webhook` | Simple webhook sending (recommended) |
| `discord.py` | Full bot framework (overkill for notifications) |
| `dhooks` | Lightweight webhook wrapper |

**Decision:** `discord-webhook`
- Simple, focused on webhooks
- Supports embeds, attachments
- No bot token needed
- Latest version: March 2025

#### Email
| Approach | Pros | Cons |
|----------|------|------|
| `smtplib` + Gmail App Password | Built-in, simple | 500 emails/day limit |
| `aiosmtplib` | Async support | Same Gmail limits |
| Gmail API + OAuth2 | Higher limits, more secure | More complex setup |

**Decision:** `smtplib` with Gmail App Password for prototype

### 3.5 Web Framework

| Framework | Best For | Complexity |
|-----------|----------|------------|
| **Streamlit** | Data dashboards | Very Low |
| **FastAPI** | APIs + async | Medium |
| **Flask** | Simple web apps | Low |

**Decision:** Streamlit for prototype dashboard
- Rapid prototyping
- Python-only (no JS/HTML needed)
- Built-in data visualization
- Easy deployment

### 3.6 Task Scheduling

| Library | Complexity | Distributed | External Dependencies |
|---------|------------|-------------|----------------------|
| **APScheduler** | Low | No | None |
| **Celery** | High | Yes | Redis/RabbitMQ |
| **Huey** | Low-Medium | Yes | Redis |

**Decision:** APScheduler
- No external dependencies
- Supports interval triggers (1 min to 1 hour)
- Can persist jobs to database
- Simple configuration

---

## Part 4: Feature Specification

### 4.1 Core Features (Prototype)

1. **HTML Scraper**
   - Scrape Head-Fi classifieds via direct HTML parsing
   - Configurable polling intervals (1 min - 1 hour, default: 5 min)
   - Support all Head-Fi categories
   - Handle pagination efficiently
   - Respect rate limits
   - **Initial scrape**: Recent listings only (configurable, default: 1 month)

2. **Watch Rules with Boolean Expressions**
   - Keyword matching: `"Hercules Audio Moses"`
   - Boolean operators: `"Moses AND price < 3500"`
   - Supported operators: AND, OR, NOT
   - Comparison operators: `<`, `>`, `<=`, `>=`, `=`, `!=`
   - Field filters: title, price, condition, category, seller

3. **Notifications (Immediate)**
   - Email (Gmail SMTP)
   - Discord webhooks
   - Sent immediately when match found (not batched)
   - Configurable per-rule notification channels

4. **Data Storage (DuckDB)**
   - Store all scraped listings
   - Track listing status (active, sold, expired)
   - Historical price data for trend analysis

5. **Streamlit Dashboard**
   - View all listings (with search/filter)
   - Manage watch rules
   - View price trends/analytics
   - Notification history

### 4.2 Enhanced Features (Post-Prototype)

1. **Advanced Matching**
   - Fuzzy matching for typos/variations
   - Seller reputation filtering
   - Location-based filtering
   - Shipping availability filtering

2. **Price Intelligence**
   - Price trend graphs
   - "Good deal" detection (below average price)
   - Price drop alerts

3. **User Management** (for shared deployment)
   - Multi-user support
   - Per-user watch rules
   - User authentication

### 4.3 Polish Features

1. **Reliability**
   - Automatic retry on failures
   - Health monitoring
   - Error alerting

2. **Logging**
   - Structured logging (JSON) via structlog
   - Log rotation
   - Debug mode

3. **Configuration**
   - YAML config files
   - Environment variable support
   - Pydantic validation on startup

---

## Part 5: Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AudioWatch                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐ │
│  │   Scraper    │────▶│   Database   │◀────│    Dashboard     │ │
│  │ (Playwright) │     │   (DuckDB)   │     │   (Streamlit)    │ │
│  └──────┬───────┘     └──────────────┘     └──────────────────┘ │
│         │                    ▲                                   │
│         │                    │                                   │
│         ▼                    │                                   │
│  ┌──────────────┐     ┌──────────────┐                          │
│  │   Matcher    │────▶│  Notifier    │                          │
│  │ (boolean_    │     │  (Email +    │                          │
│  │  parser)     │     │   Discord)   │                          │
│  └──────────────┘     └──────────────┘                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Scheduler (APScheduler)                      │   │
│  │   Polls every 1-5 min, immediate notification on match   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Data Flow:**
1. Scheduler triggers scraper at configured interval (1-5 min typical)
2. Scraper fetches new/updated listings via HTML parsing
3. New listings stored in DuckDB
4. Matcher evaluates all watch rules against new listings
5. Matches trigger immediate notifications (email + Discord)
6. Dashboard reads from DuckDB for display and analytics

---

## Part 6: Technology Stack Summary

### Prototype Stack (Local Development)

| Component | Technology | Version | Justification |
|-----------|------------|---------|---------------|
| **Language** | Python | 3.11+ | Your preference, excellent ecosystem |
| **Scraping** | Playwright + playwright-stealth | Latest | Best for JS-heavy sites, anti-detection |
| **Database** | DuckDB + duckdb-engine | 1.4.3 / 0.17.0 | Fast analytics, zero config, SQLAlchemy support |
| **ORM** | SQLAlchemy | 2.0+ | Industry standard, async support |
| **Rule Engine** | boolean_parser | 0.1.5 | SQLAlchemy integration, boolean expressions |
| **Scheduler** | APScheduler | 3.10+ | Lightweight, no external deps |
| **Email** | smtplib | Built-in | Simple, no dependencies |
| **Discord** | discord-webhook | Latest | Lightweight, focused |
| **Dashboard** | Streamlit | 1.40+ | Rapid prototyping, Python-only |
| **Config** | Pydantic + PyYAML | v2 / 6.0 | Type-safe configuration |
| **Logging** | structlog | Latest | Structured, modern logging |
| **CLI** | Typer | Latest | Modern CLI framework |

### Production Stack (AWS Deployment - Future)

| Component | Technology | Justification |
|-----------|------------|---------------|
| **Database** | PostgreSQL (RDS) or DuckDB on S3 | Multi-user, production-ready |
| **Task Queue** | Huey + Redis | Lightweight distributed tasks |
| **API** | FastAPI | Async, auto-docs, production-ready |
| **Frontend** | React + Tailwind | Polished UI |
| **Container** | Docker + docker-compose | Easy deployment |
| **Hosting** | AWS EC2/ECS | Scalable |

---

## Part 7: Project Structure

```
audiowatch/
├── pyproject.toml              # Project metadata, dependencies (Poetry/uv)
├── README.md
├── .env.example                # Environment variables template
├── config.yaml                 # User configuration
│
├── src/
│   └── audiowatch/
│       ├── __init__.py
│       ├── __main__.py         # Entry point
│       ├── cli.py              # Typer CLI commands
│       ├── config.py           # Pydantic configuration
│       │
│       ├── scraper/
│       │   ├── __init__.py
│       │   ├── headfi.py       # Head-Fi HTML scraper
│       │   └── models.py       # Listing Pydantic models
│       │
│       ├── database/
│       │   ├── __init__.py
│       │   ├── models.py       # SQLAlchemy/DuckDB models
│       │   ├── repository.py   # Data access layer
│       │   └── migrations/     # Alembic migrations
│       │
│       ├── matcher/
│       │   ├── __init__.py
│       │   ├── parser.py       # boolean_parser integration
│       │   └── rules.py        # Watch rule engine
│       │
│       ├── notifier/
│       │   ├── __init__.py
│       │   ├── base.py         # Notifier interface
│       │   ├── email.py        # Gmail SMTP
│       │   └── discord.py      # Discord webhook
│       │
│       ├── scheduler/
│       │   ├── __init__.py
│       │   └── jobs.py         # APScheduler jobs
│       │
│       └── dashboard/
│           ├── __init__.py
│           ├── app.py          # Streamlit main app
│           ├── pages/          # Streamlit pages
│           │   ├── listings.py
│           │   ├── rules.py
│           │   └── analytics.py
│           └── components/     # Reusable UI components
│
├── tests/
│   ├── conftest.py
│   ├── test_scraper.py
│   ├── test_matcher.py
│   └── test_notifier.py
│
└── docker/
    ├── Dockerfile
    └── docker-compose.yml
```

---

## Part 8: Implementation Phases

### Phase 1: Foundation
- Project setup (Poetry/uv, structure, dependencies)
- Pydantic configuration with YAML loading
- DuckDB + SQLAlchemy models
- Basic logging with structlog

### Phase 2: HTML Scraping
- Playwright setup with stealth
- Head-Fi classifieds HTML parser
- Pagination handling
- Rate limiting
- Data persistence to DuckDB
- Initial scrape (recent 1 month default)

### Phase 3: Matching & Notifications
- boolean_parser integration
- Watch rule CRUD
- Email notifications (Gmail SMTP)
- Discord webhook notifications
- Immediate notification on match

### Phase 4: Scheduler
- APScheduler integration
- Configurable intervals (1 min - 1 hour)
- Job persistence
- Graceful shutdown handling

### Phase 5: Streamlit Dashboard
- Listing viewer with search/filter
- Watch rule management UI
- Price trend analytics
- Notification history

### Phase 6: Polish
- Comprehensive error handling
- Retry logic with exponential backoff
- Configuration validation
- Documentation
- Tests

---

## Part 9: Configuration Example

```yaml
# config.yaml
scraper:
  poll_interval_minutes: 5        # How often to check (1-60)
  initial_scrape_days: 30         # How far back on first run
  rate_limit_delay_seconds: 2     # Delay between page requests
  categories:                      # Which categories to monitor (all by default)
    - headphones
    - amplification
    - source-components
    - cables-accessories
    - media

database:
  path: "./data/audiowatch.db"    # DuckDB file path

notifications:
  email:
    enabled: true
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    sender_email: "${GMAIL_ADDRESS}"    # From environment
    sender_password: "${GMAIL_APP_PASSWORD}"
    recipient_email: "your-email@gmail.com"

  discord:
    enabled: true
    webhook_url: "${DISCORD_WEBHOOK_URL}"

watch_rules:
  - name: "Moses Deal"
    expression: 'title contains "Moses" AND price < 3500'
    notify_via:
      - email
      - discord

  - name: "HD800 Under 1k"
    expression: 'title contains "HD800" AND price < 1000'
    notify_via:
      - discord

dashboard:
  port: 8501
```

---

## Part 10: Key Dependencies

```toml
# pyproject.toml (partial)
[project]
name = "audiowatch"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    # Core
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "structlog>=24.0",
    "typer>=0.12",

    # Scraping
    "playwright>=1.40",
    "playwright-stealth>=1.0",
    "beautifulsoup4>=4.12",
    "lxml>=5.0",

    # Database
    "duckdb>=1.0",
    "duckdb-engine>=0.17",
    "sqlalchemy>=2.0",

    # Matching
    "boolean-parser>=0.1",

    # Scheduling
    "apscheduler>=3.10",

    # Notifications
    "discord-webhook>=1.3",

    # Dashboard
    "streamlit>=1.40",
    "plotly>=5.20",
    "pandas>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.5",
    "mypy>=1.10",
]
```

---

## Sources

### Similar Tools
- [Hyacinth - Discord marketplace bot](https://github.com/stephanlensky/hyacinth)
- [AI Marketplace Monitor](https://pypi.org/project/ai-marketplace-monitor/)
- [Product Checker](https://github.com/tnware/product-checker)
- [Craigslist For Sale Alerts](https://github.com/meub/craigslist-for-sale-alerts)

### Head-Fi Resources
- [Head-Fi Classifieds](https://www.head-fi.org/classifieds/)
- [Head-Fi Classifieds FAQ](https://www.head-fi.org/articles/head-fi-classifieds-faq-and-walkthrough.19757/)
- [Classifieds Alerts Discussion](https://www.head-fi.org/threads/classifieds-alerts.958413/)

### Technical Resources
- [DuckDB Python API](https://duckdb.org/docs/stable/clients/python/overview.html)
- [DuckDB SQLAlchemy Engine](https://github.com/Mause/duckdb_engine)
- [boolean_parser Documentation](https://boolean-parser.readthedocs.io/en/latest/intro.html)
- [Playwright Python](https://playwright.dev/python/)
- [Playwright vs Selenium 2025](https://roundproxies.com/blog/playwright-vs-selenium/)
- [Anti-Bot Bypass Techniques](https://scrapeops.io/python-web-scraping-playbook/python-how-to-bypass-anti-bots/)
- [Discord Webhook Python](https://pypi.org/project/discord-webhook/)
- [Python Email with Gmail](https://mailtrap.io/blog/python-send-email-gmail/)
- [APScheduler vs Celery](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-vs-celery)
- [Streamlit Documentation](https://docs.streamlit.io/)
