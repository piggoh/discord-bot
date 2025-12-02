# Discord Server Data Migration Tool

This tool helps you migrate data from an old Discord server to a new one using Playwright automation. Perfect for recovering important business information from a Discord server you've lost admin access to.

## Features
- 🔐 Automated Discord login with stealth settings
- 📝 Scrape messages from specific channels (e.g., announcements)
- 📊 Export data in multiple formats (JSON, CSV)
- 🛡️ Handle rate limiting and anti-bot measures
- 📎 Preserve message metadata (timestamps, authors, attachments, embeds)
- 🔄 Automated migration to new Discord server
- ⚡ Human-like behavior simulation

## Quick Start

### Option 1: Automated Setup
```bash
python setup.py
```

### Option 2: Manual Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
playwright install
```

3. Configure your credentials:
```bash
cp config.env .env
# Edit .env with your actual Discord credentials
```

## Usage

### Step 1: Scrape Data from Old Server
```bash
python discord_scraper.py
```

This will:
- Login to Discord with your credentials
- Navigate to the "cooks" server
- Find the "announcement" channel
- Scroll to load all messages
- Export data to JSON and CSV files

### Step 2: Migrate Data to New Server
```bash
python discord_migrator.py discord_messages_20231201_120000.json
```

Optional: Limit number of messages to migrate:
```bash
python discord_migrator.py discord_messages_20231201_120000.json 50
```

## Configuration

Edit your `.env` file with the following settings:

```env
# Discord Credentials
DISCORD_EMAIL=your_email@example.com
DISCORD_PASSWORD=your_password

# Server Configuration
OLD_SERVER_NAME=cooks
TARGET_CHANNEL=announcement

# For migration to new server
NEW_SERVER_NAME=your_new_server_name

# Rate limiting (optional)
MIN_DELAY=1
MAX_DELAY=3
SCROLL_COUNT=20
```

## Output Files

The scraper creates several files:

- `discord_messages_YYYYMMDD_HHMMSS.json` - Complete message data
- `discord_messages_YYYYMMDD_HHMMSS.csv` - Message data in spreadsheet format
- `scraping_summary_YYYYMMDD_HHMMSS.json` - Summary statistics

## Troubleshooting

### Common Issues

1. **Login Failed**
   - Check your email/password in `.env`
   - Disable 2FA temporarily or use app password
   - Ensure you're not already logged in elsewhere

2. **Server Not Found**
   - Verify the server name matches exactly
   - Check if you have access to the server
   - The script will list available servers if it can't find yours

3. **Channel Not Found**
   - Verify the channel name matches exactly
   - Check channel permissions
   - The script will list available channels

4. **Rate Limiting**
   - Increase delays in the script
   - Reduce scroll count
   - Run during off-peak hours

### Advanced Configuration

You can modify the scraper behavior by editing these variables in `discord_scraper.py`:

```python
# Number of scrolls to load messages
scroll_count = 20

# Delay between actions (seconds)
min_delay = 1
max_delay = 3

# Headless mode (set to True to run without browser window)
headless = False
```

## Important Notes

⚠️ **Legal and Ethical Considerations:**
- This tool uses browser automation which may be detected by Discord
- Use responsibly and respect Discord's Terms of Service
- Only use on servers you have legitimate access to
- Consider rate limiting to avoid being flagged as a bot
- Always backup your data before migration
- Test with a small amount of data first

🔒 **Security:**
- Never share your `.env` file
- Use strong passwords
- Consider using Discord app passwords instead of main password

📊 **Data Preservation:**
- Messages are exported with full metadata
- Attachments and embeds are preserved
- Timestamps maintain original format
- Author information is captured

## Legal Disclaimer

This tool is for personal use only. Make sure you have permission to access the Discord server and comply with Discord's Terms of Service. The authors are not responsible for any misuse of this tool.

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify your Discord credentials and server access
3. Ensure all dependencies are properly installed
4. Check Discord's current web interface for changes

## File Structure

```
discord-scraper/
├── discord_scraper.py      # Main scraping script
├── discord_migrator.py     # Migration script
├── setup.py               # Automated setup
├── requirements.txt       # Python dependencies
├── config.env            # Configuration template
├── README.md             # This file
└── .env                  # Your credentials (create this)
```
