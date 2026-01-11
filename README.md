# AudioWatch

Monitor Head-Fi.org classifieds and get notified when items matching your criteria are listed.

## Features

- **Automated Monitoring**: Continuously scrapes Head-Fi classifieds at configurable intervals
- **Smart Matching**: Boolean expression support for complex watch rules
- **Fuzzy Matching**: Handle product name variations (e.g., "ThieAudio Monarch MK4" matches "Monarch MKIV")
- **Regex Support**: Pattern matching for flexible searches (e.g., `64\s*[Aa]udio`)
- **Global Filters**: Set baseline criteria applied to all rules (listing type, shipping region, status)
- **Instant Notifications**: Email (Gmail) and Discord webhook alerts
- **Price Tracking**: Historical price data for trend analysis
- **Sold/Closed Detection**: Automatically filters out sold or closed listings

## Installation

```bash
# Clone the repository
git clone https://github.com/Zi-Deng/AudioWatch.git
cd AudioWatch

# Create and activate environment
conda create -n audiowatch python=3.11 -y
conda activate audiowatch

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browsers
playwright install chromium
```

## Quick Start

1. Copy the example configuration:
   ```bash
   cp config.example.yaml config.yaml
   ```

2. Edit `config.yaml` with your notification settings and watch rules.

3. Initialize the database:
   ```bash
   audiowatch init
   ```

4. Run a single scrape to test:
   ```bash
   audiowatch run --once
   ```

5. Start continuous monitoring:
   ```bash
   audiowatch run
   ```

## Commands

| Command | Description |
|---------|-------------|
| `audiowatch init` | Initialize the database (creates tables) |
| `audiowatch run` | Start continuous monitoring |
| `audiowatch run --once` | Run a single scrape and exit |
| `audiowatch status` | Show status and statistics |
| `audiowatch rules` | List configured watch rules |
| `audiowatch listings` | Browse stored listings |
| `audiowatch test-notify --channel discord` | Send a test notification |
| `audiowatch dashboard` | Start the web dashboard |

## Configuration

### Global Filters

Global filters are applied to ALL watch rules automatically. Set these once to avoid repeating criteria in every rule.

```yaml
global_filters:
  # Only match these listing types (empty = all types allowed)
  listing_types:
    - "For Sale"
    - "For Sale/Trade"

  # Only match listings that ship to these regions (partial match)
  ships_to:
    - "North America"
    - "United States"
    - "US"
    - "USA"
    - "Worldwide"
    - "CONUS"

  # Exclude listings with these statuses
  exclude_status:
    - "sold"
    - "expired"
    - "deleted"

  # Minimum seller reputation (optional)
  # min_seller_reputation: 10
```

### Watch Rules

Watch rules define what listings to notify you about. Each rule has a name, expression, and notification channels.

```yaml
watch_rules:
  - name: "HD800 Under 1k"
    expression: 'title contains "HD800" AND price < 1000'
    notify_via:
      - discord
    enabled: true

  - name: "ThieAudio Monarch"
    expression: 'title fuzzy_contains "ThieAudio Monarch MK4" AND price < 1500'
    notify_via:
      - discord
      - email
    enabled: true
```

### Expression Syntax

Expressions use a simple boolean syntax with various operators:

#### Comparison Operators
| Operator | Example | Description |
|----------|---------|-------------|
| `=` | `category = "headphones"` | Exact match (case-insensitive) |
| `!=` | `seller != "baduser"` | Not equal |
| `<` | `price < 1000` | Less than |
| `>` | `price > 500` | Greater than |
| `<=` | `price <= 2000` | Less than or equal |
| `>=` | `seller_reputation >= 10` | Greater than or equal |

#### String Operators
| Operator | Example | Description |
|----------|---------|-------------|
| `contains` | `title contains "HD800"` | Substring match (case-insensitive) |
| `startswith` | `title startswith "Sennheiser"` | Starts with string |
| `endswith` | `title endswith "mint"` | Ends with string |
| `matches` | `title matches "64\s*[Aa]udio"` | Regex pattern match |
| `fuzzy_contains` | `title fuzzy_contains "ThieAudio Monarch"` | Fuzzy match (~80% similarity) |

#### Boolean Operators
| Operator | Example | Description |
|----------|---------|-------------|
| `AND` | `price < 1000 AND condition = "Excellent"` | Both conditions must match |
| `OR` | `title contains "HD800" OR title contains "HD820"` | Either condition matches |
| `NOT` | `NOT title contains "broken"` | Negates the condition |

#### Available Fields
| Field | Aliases | Description | Example Values |
|-------|---------|-------------|----------------|
| `title` | - | Listing title | "Sennheiser HD800S" |
| `price` | - | Price (numeric) | 999.99 |
| `currency` | - | Currency code | "USD", "EUR" |
| `category` | - | Listing category | "headphones", "amplification" |
| `condition` | - | Item condition | "Excellent", "Good", "Like New" |
| `listing_type` | `type` | Type of listing | "For Sale", "Want To Buy" |
| `ships_to` | `shipping` | Shipping regions | "North America", "Worldwide" |
| `status` | - | Listing status | "active", "sold", "closed" |
| `seller` | `seller_username` | Seller's username | "audiophile99" |
| `seller_reputation` | - | Seller rep score | 42 |

### Notifications

#### Discord
1. In your Discord server, go to **Server Settings > Integrations > Webhooks**
2. Click **New Webhook**, name it, and select the channel
3. Copy the webhook URL and add to config:

```yaml
notifications:
  discord:
    enabled: true
    webhook_url: "https://discord.com/api/webhooks/..."
```

#### Email (Gmail)
1. Enable 2-factor authentication on your Gmail account
2. Go to https://myaccount.google.com/apppasswords
3. Create an App Password for "Mail"
4. Configure in config.yaml:

```yaml
notifications:
  email:
    enabled: true
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    sender_email: "${GMAIL_ADDRESS}"
    sender_password: "${GMAIL_APP_PASSWORD}"
    recipient_email: "your-email@example.com"
    use_tls: true
```

Set environment variables:
```bash
export GMAIL_ADDRESS="your-gmail@gmail.com"
export GMAIL_APP_PASSWORD="your-app-password"
```

## Example Configurations

### Budget Audiophile Setup
```yaml
global_filters:
  listing_types:
    - "For Sale"
  ships_to:
    - "United States"
    - "CONUS"
  exclude_status:
    - "sold"

watch_rules:
  - name: "Budget IEMs"
    expression: 'category = "in-ear-monitors" AND price < 200'
    notify_via: [discord]

  - name: "Entry DAC/Amp"
    expression: 'title contains "DAC" AND price < 300'
    notify_via: [discord]
```

### High-End Hunter
```yaml
watch_rules:
  - name: "Flagship IEMs"
    expression: 'title fuzzy_contains "64 Audio U12t" OR title fuzzy_contains "Empire Ears Odin"'
    notify_via: [discord, email]

  - name: "TOTL Headphones"
    expression: '(title contains "Susvara" OR title contains "Utopia") AND price < 4000'
    notify_via: [discord, email]
```

### Regex Power User
```yaml
watch_rules:
  - name: "Any 64 Audio"
    expression: 'title matches "64\s*[Aa]udio"'
    notify_via: [discord]

  - name: "Sennheiser HD6xx Series"
    expression: 'title matches "HD\s*6[0-9]{2}"'
    notify_via: [discord]
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/audiowatch

# Linting
ruff check src tests
```

## Troubleshooting

### No notifications received
1. Check that notifications are enabled in config: `notifications.discord.enabled: true`
2. Test with: `audiowatch test-notify --channel discord`
3. Verify webhook URL is correct
4. Check that your watch rules match actual listings

### Listings not matching
1. Check global filters aren't too restrictive
2. Use `audiowatch listings` to see what's in the database
3. Test your expression with a broader criteria first

### Database issues
```bash
# Reinitialize database (warning: clears data)
audiowatch init --force
```

## License

MIT License - see LICENSE file for details.

## Author

Zi-Deng (dengzikang@gmail.com)
