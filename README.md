# AudioWatch

Monitor Head-Fi.org classifieds and get notified when items matching your criteria are listed.

## Features

- **Automated Monitoring**: Continuously scrapes Head-Fi classifieds at configurable intervals
- **Smart Matching**: Boolean expression support for complex watch rules (e.g., `"Moses AND price < 3500"`)
- **Instant Notifications**: Email and Discord alerts when matches are found
- **Price Tracking**: Historical price data for trend analysis
- **Dashboard**: Streamlit-based UI for viewing listings and managing rules

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

4. Start monitoring:
   ```bash
   audiowatch run
   ```

## Configuration

See `config.example.yaml` for all available options.

### Watch Rules

Watch rules use boolean expressions to match listings:

```yaml
watch_rules:
  - name: "Moses Deal"
    expression: 'title contains "Moses" AND price < 3500'
    notify_via:
      - email
      - discord
```

### Notifications

#### Email (Gmail)
1. Enable 2-factor authentication on your Gmail account
2. Create an App Password at https://myaccount.google.com/apppasswords
3. Set `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` environment variables

#### Discord
1. Create a webhook in your Discord server settings
2. Set `DISCORD_WEBHOOK_URL` environment variable

## Commands

```bash
audiowatch --help          # Show help
audiowatch init            # Initialize database
audiowatch run             # Start monitoring
audiowatch run --once      # Run once and exit
audiowatch status          # Show status and statistics
audiowatch rules           # List configured watch rules
audiowatch dashboard       # Start the web dashboard
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

## License

MIT License - see LICENSE file for details.

## Author

Zi-Deng (dengzikang@gmail.com)
