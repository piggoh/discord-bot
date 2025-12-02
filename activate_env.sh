#!/bin/bash
# Discord Monitor Activation Script

echo "Discord Monitor Virtual Environment Setup"
echo "=========================================="

# Check if virtual environment exists
if [ ! -d "discord_monitor_env" ]; then
    echo "Virtual environment not found. Running setup..."
    python3 setup_venv.py
fi

# Activate virtual environment
echo "Activating virtual environment..."
source discord_monitor_env/bin/activate

echo "Virtual environment activated!"
echo ""
echo "Available commands:"
echo "  python discord_monitor.py    - Start continuous monitoring"
echo "  python discord_scraper.py    - One-time scrape"
echo "  python discord_migrator.py  - Migrate existing data"
echo ""
echo "To deactivate: deactivate"
echo "To exit: Ctrl+C"
echo ""

# Keep the shell active
exec bash
