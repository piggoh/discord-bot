# Discord Continuous Monitor & Auto-Migration Tool

This tool provides **continuous monitoring** of a Discord server you don't have admin access to, automatically detecting new messages and migrating them to your own server with custom formatting.

## 🚀 Quick Start

### Option 1: Automated Setup (Recommended)
```bash
python3 setup_venv.py
```

### Option 2: Manual Setup
```bash
# Create virtual environment
python3 -m venv discord_monitor_env

# Activate virtual environment
source discord_monitor_env/bin/activate  # On macOS/Linux
# OR
discord_monitor_env\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
playwright install
```

### Option 3: Use Activation Script
```bash
./activate_env.sh
```

## 📋 Configuration

Edit your `.env` file with the following settings:

```env
# Discord Credentials
DISCORD_EMAIL=your_email@example.com
DISCORD_PASSWORD=your_password

# Source Server Configuration (server you're monitoring)
SOURCE_SERVER_NAME=cooks
SOURCE_CHANNEL=announcement

# Destination Server Configuration (your new server)
DEST_SERVER_NAME=your_new_server_name
DEST_CHANNEL=announcement

# Monitoring Settings
CHECK_INTERVAL=30                    # Check every 30 seconds
MAX_MESSAGES_PER_BATCH=10           # Max messages to process per batch
ENABLE_AUTO_MIGRATION=true          # Auto-migrate to destination server

# Rate limiting
MIN_DELAY=2
MAX_DELAY=5
SCROLL_COUNT=5
```

## 🔄 Usage Modes

### 1. Continuous Monitoring (Recommended)
```bash
python discord_monitor.py
```

**What it does:**
- Continuously monitors the "cooks" server's "announcement" channel
- Detects new messages automatically
- Converts message structure to your desired format
- Automatically migrates to your new server (if enabled)
- Saves all messages to `monitored_messages.json`
- Maintains state to avoid duplicate processing

### 2. One-Time Scrape
```bash
python discord_scraper.py
```

**What it does:**
- Scrapes all existing messages from the source server
- Exports to JSON and CSV formats
- Good for initial data recovery

### 3. Manual Migration
```bash
python discord_migrator.py monitored_messages.json
```

**What it does:**
- Migrates previously scraped messages
- Useful for batch processing

## 🎯 Key Features

### Continuous Monitoring
- **Real-time Detection**: Automatically detects new messages as they're posted
- **State Persistence**: Remembers processed messages to avoid duplicates
- **Configurable Intervals**: Check every 30 seconds (configurable)
- **Error Recovery**: Continues monitoring even if individual messages fail

### Message Structure Conversion
The tool automatically converts messages to your desired format:

```python
# Original message structure
{
    "content": "Hello world",
    "author": "John Doe",
    "timestamp": "Today at 2:30 PM"
}

# Converted structure (customizable)
{
    "formatted_content": "📋 **Migrated from cooks**\n\n**Original Author:** John Doe\n**Original Time:** Today at 2:30 PM\n\nHello world",
    "migration_status": "pending",
    "source_info": {
        "server": "cooks",
        "channel": "announcement"
    }
}
```

### Auto-Migration
- **Seamless Transfer**: Automatically posts converted messages to your new server
- **Rate Limiting**: Built-in delays to avoid detection
- **Error Handling**: Continues processing even if some messages fail
- **Status Tracking**: Monitors migration success/failure

## 📊 Output Files

### `monitored_messages.json`
Complete log of all monitored messages with metadata:
```json
[
  {
    "message_id": "chat-messages-1234567890",
    "content": "Message content",
    "author": "Original Author",
    "timestamp": "Today at 2:30 PM",
    "attachments": [...],
    "embeds": [...],
    "scraped_at": "2023-12-01T14:30:00",
    "source_server": "cooks",
    "source_channel": "announcement"
  }
]
```

### `monitor_state.json`
Tracks monitoring state to prevent duplicate processing:
```json
{
  "last_message_id": "chat-messages-1234567890",
  "processed_messages": ["msg1", "msg2", "msg3"],
  "last_check": "2023-12-01T14:30:00"
}
```

## ⚙️ Customization

### Modify Message Format
Edit the `convert_message_structure()` function in `discord_monitor.py`:

```python
def convert_message_structure(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
    # Your custom formatting logic here
    converted_message = {
        'formatted_content': f"🔄 **FROM {self.source_server.upper()}**\n\n{message_data.get('content', '')}",
        'original_author': message_data.get('author', 'Unknown'),
        'migrated_at': datetime.now().isoformat()
    }
    return converted_message
```

### Adjust Monitoring Settings
```env
CHECK_INTERVAL=60          # Check every minute
MAX_MESSAGES_PER_BATCH=5   # Process fewer messages per batch
ENABLE_AUTO_MIGRATION=false  # Disable auto-migration
```

## 🛡️ Safety Features

### Rate Limiting
- Random delays between actions (2-5 seconds)
- Longer delays every 10 messages
- Configurable delay ranges

### Error Handling
- Continues monitoring even if individual messages fail
- Saves state regularly to prevent data loss
- Graceful handling of network issues

### Stealth Mode
- Realistic browser settings
- Human-like behavior patterns
- Anti-detection measures

## 🔧 Troubleshooting

### Common Issues

1. **"ModuleNotFoundError: No module named 'playwright'"**
   ```bash
   # Make sure you're in the virtual environment
   source discord_monitor_env/bin/activate
   playwright install
   ```

2. **Login Failed**
   - Check credentials in `.env`
   - Disable 2FA temporarily
   - Ensure you're not logged in elsewhere

3. **Server/Channel Not Found**
   - Verify exact names in `.env`
   - Check server/channel permissions
   - Script will list available options

4. **Rate Limiting**
   - Increase delays in `.env`
   - Reduce `CHECK_INTERVAL`
   - Run during off-peak hours

### Monitoring Status
The tool provides detailed debug logging with visual indicators:
```
Starting Discord Monitor...
Navigating to Discord...
✓ Successfully logged in!

📍 Navigating to source server and channel...

🔍 Finding source server: 'cooks'
⏳ Waiting for server selector...
✓ Server found! Clicking on 'cooks'...
✓ Successfully navigated to source server: cooks

🔍 Finding source channel: 'announcement'
⏳ Waiting for channel selector...
✓ Channel found! Clicking on 'announcement'...
✓ Successfully navigated to source channel: announcement

✓ Successfully navigated to target server and channel!
📋 Monitoring: cooks > announcement

============================================================
🚀 Starting continuous monitoring...
⏱️  Checking every 30 seconds
📥 Source: cooks > announcement
============================================================

[2023-12-01 14:30:00] 🔄 Checking for new messages...

📥 Fetching messages from cooks > announcement...
⏳ Waiting for messages to load...
⏳ Extracting message elements...
✓ Found 25 message elements
  ✓ Processing message 1/25
  ✓ Processing message 2/25
✓ Fetch successful! Found 3 new messages
✓ Found 3 new messages

💾 Saving messages...
✓ Messages saved
⏳ Waiting 30 seconds before next check...
```

The debug logs include:
- ✓ Success indicators
- ✗ Error indicators
- ⏳ Wait/loading indicators
- 📋 Status information
- 📍 Navigation steps
- 💡 Helpful tips when errors occur

## 📁 File Structure

```
discord-monitor/
├── discord_monitor.py      # Continuous monitoring script
├── discord_scraper.py      # One-time scraping script
├── discord_migrator.py     # Manual migration script
├── setup_venv.py          # Virtual environment setup
├── activate_env.sh        # Environment activation script
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── .env                  # Your credentials (create this)
├── monitored_messages.json # Message log (auto-generated)
└── monitor_state.json     # State tracking (auto-generated)
```

## ⚠️ Important Notes

### Legal Considerations
- Only monitor servers you have legitimate access to
- Respect Discord's Terms of Service
- Use responsibly and ethically
- Consider the privacy of other users

### Technical Considerations
- Browser automation may be detected
- Use appropriate rate limiting
- Test with small amounts of data first
- Monitor system resources

### Data Privacy
- Messages are stored locally in JSON files
- Never share your `.env` file
- Consider encrypting sensitive data
- Regular cleanup of old logs

## 🚀 Getting Started

1. **Setup Environment:**
   ```bash
   python3 setup_venv.py
   ```

2. **Configure Settings:**
   ```bash
   # Edit .env with your credentials
   nano .env
   ```

3. **Start Monitoring:**
   ```bash
   python discord_monitor.py
   ```

4. **Monitor Output:**
   - Watch console for real-time updates
   - Check `monitored_messages.json` for saved data
   - Verify messages appear in your destination server

The tool will now continuously monitor your source Discord server and automatically migrate new messages to your destination server with your custom formatting!
