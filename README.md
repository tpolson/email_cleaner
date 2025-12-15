# Email Cleaner Agent

An intelligent agent that scans your email inbox, identifies junk emails (spam, phishing, promotional), and helps you clean them up.

## Features

- **Smart Junk Detection**: Analyzes emails using multiple indicators:
  - Spam keywords and patterns
  - Phishing detection (suspicious links, urgency language)
  - Money scam patterns
  - Sender reputation analysis
  - Email authentication checks (SPF, DKIM, DMARC)
  - Promotional/newsletter identification

- **Confidence Scoring**: Each email gets a confidence score (0-100%) indicating how likely it is to be junk

- **Safe by Default**: Runs in dry-run mode by default, so you can preview what would happen before making changes

- **Actionable Results**: Recommends actions based on confidence:
  - High confidence (≥90%): Delete
  - Medium confidence (≥70%): Move to spam
  - Lower confidence: Review manually

## Installation

```bash
# Clone the repository
git clone https://github.com/example/email-cleaner.git
cd email-cleaner

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package
pip install -e .
```

## Configuration

1. Create a `.env` file with your email credentials:

```bash
email-cleaner init
```

2. Edit the `.env` file:

```env
# Email Server Configuration
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_PASSWORD=your-app-password

# Agent Configuration
DRY_RUN=true
MAX_EMAILS_TO_PROCESS=100
JUNK_CONFIDENCE_THRESHOLD=0.7
```

### Gmail Setup

For Gmail, you need to use an App Password:

1. Go to your Google Account settings
2. Navigate to Security → 2-Step Verification
3. Scroll down to "App passwords"
4. Generate a new app password for "Mail"
5. Use this password in your `.env` file

More info: https://support.google.com/accounts/answer/185833

### Other Email Providers

| Provider | IMAP Server | Port |
|----------|-------------|------|
| Gmail | imap.gmail.com | 993 |
| Outlook/Hotmail | outlook.office365.com | 993 |
| Yahoo | imap.mail.yahoo.com | 993 |
| iCloud | imap.mail.me.com | 993 |

## Usage

### Web UI

The easiest way to use Email Cleaner is through the web interface:

```bash
# Start the web UI
email-cleaner-ui

# Or with options
email-cleaner-ui --host 0.0.0.0 --port 8080
```

Then open http://localhost:5000 in your browser. The web UI allows you to:

- Enter your email credentials directly (no `.env` file needed)
- Test the connection before scanning
- Select which folder to scan
- View all emails with junk classification
- Select specific emails to delete
- Preview deletions before confirming

![Web UI Screenshot](docs/screenshot.png)

### Command Line Interface

For automation and scripting, use the CLI:

#### Scan Emails (Preview Only)

```bash
# Scan your inbox
email-cleaner scan

# Scan with options
email-cleaner scan --folder "INBOX" --limit 50

# Scan only unread emails
email-cleaner scan --search "UNSEEN"

# Scan emails from the last month
email-cleaner scan --search "SINCE 01-Dec-2024"
```

### Clean Junk Emails

```bash
# Preview what would be cleaned (dry run - default)
email-cleaner clean

# Actually clean junk emails
email-cleaner clean --no-dry-run

# Skip confirmation prompt
email-cleaner clean --no-dry-run --force
```

### List Folders

```bash
email-cleaner folders
```

## How It Works

The agent uses multiple detection methods to identify junk:

### 1. Content Analysis
- Scans for common spam keywords (casino, lottery, pharmacy, etc.)
- Detects phishing patterns ("verify your account", "suspended", etc.)
- Identifies urgency language ("act now", "limited time", etc.)
- Finds money scam patterns

### 2. Sender Analysis
- Checks sender domain reputation
- Detects suspicious TLDs (.xyz, .click, .win, etc.)
- Identifies randomly-generated domain names
- Compares display name with actual email address

### 3. Link Analysis
- Finds suspicious URLs
- Detects IP-based URLs
- Identifies URL shorteners
- Checks for suspicious TLDs in links

### 4. Header Analysis
- Checks email authentication (SPF, DKIM, DMARC)
- Identifies bulk mail headers
- Detects marketing platform senders

### 5. Pattern Recognition
- Newsletter detection
- Promotional content identification
- Unsubscribe link detection

## Confidence Levels

| Confidence | Classification | Action |
|------------|----------------|--------|
| ≥90% | High | Delete (move to trash) |
| 70-89% | Medium | Move to spam folder |
| <70% | Low | Mark for review |

## Project Structure

```
email_cleaner/
├── src/email_cleaner/
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   ├── config.py            # Configuration management
│   ├── agents/
│   │   └── junk_detector.py # Main detection agent
│   ├── models/
│   │   ├── email.py         # Email data model
│   │   └── classification.py # Classification results
│   ├── services/
│   │   ├── imap_client.py   # IMAP email client
│   │   └── junk_classifier.py # Classification logic
│   └── web/
│       ├── app.py           # Flask web application
│       └── templates/       # HTML templates
├── .env.example
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/

# Lint
ruff check src/
```

## Safety Notes

- The agent runs in **dry-run mode by default** - no emails are deleted unless you explicitly use `--no-dry-run`
- Always review the scan results before cleaning
- Start with a small `--limit` to test the detection accuracy on your emails
- Adjust `JUNK_CONFIDENCE_THRESHOLD` in `.env` to be more or less aggressive

## License

MIT License
