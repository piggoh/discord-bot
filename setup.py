#!/usr/bin/env python3
"""
Setup script for Discord Scraper
This script helps set up the environment and install dependencies
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\n{description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def main():
    print("Discord Scraper Setup")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("✗ Python 3.8 or higher is required")
        sys.exit(1)
    else:
        print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Install Python dependencies
    if not run_command("pip install -r requirements.txt", "Installing Python dependencies"):
        print("Failed to install Python dependencies")
        sys.exit(1)
    
    # Install Playwright browsers
    if not run_command("playwright install", "Installing Playwright browsers"):
        print("Failed to install Playwright browsers")
        sys.exit(1)
    
    # Create .env file if it doesn't exist
    if not os.path.exists('.env'):
        print("\nCreating .env file from template...")
        try:
            # Create a basic .env template
            env_content = """# Discord Credentials
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
SCROLL_COUNT=20"""
            
            with open('.env', 'w') as env_file:
                env_file.write(env_content)
            
            print("✓ .env file created")
            print("⚠️  Please edit .env file with your actual Discord credentials")
        except Exception as e:
            print(f"✗ Failed to create .env file: {e}")
    else:
        print("✓ .env file already exists")
    
    print("\n" + "=" * 50)
    print("Setup completed!")
    print("\nNext steps:")
    print("1. Edit the .env file with your Discord credentials")
    print("2. Run: python discord_scraper.py")
    print("3. After scraping, run: python discord_migrator.py <json_file>")
    print("\nFor more information, see README.md")

if __name__ == "__main__":
    main()
