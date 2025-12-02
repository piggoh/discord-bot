import json
import asyncio
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Page, Browser
from dotenv import load_dotenv

load_dotenv()

class DiscordMigrator:
    def __init__(self, json_file_path: str):
        self.json_file_path = json_file_path
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.email = os.getenv('DISCORD_EMAIL')
        self.password = os.getenv('DISCORD_PASSWORD')
        self.new_server_name = os.getenv('NEW_SERVER_NAME', '')
        self.target_channel = os.getenv('TARGET_CHANNEL', 'announcement')
        self.messages_data: List[Dict[str, Any]] = []
        
        if not self.email or not self.password:
            raise ValueError("Please set DISCORD_EMAIL and DISCORD_PASSWORD in your .env file")

    async def load_messages_data(self):
        """Load messages from JSON file"""
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                self.messages_data = json.load(f)
            print(f"Loaded {len(self.messages_data)} messages from {self.json_file_path}")
        except Exception as e:
            print(f"Error loading messages data: {e}")
            raise

    async def start_browser(self):
        """Initialize Playwright browser"""
        playwright = await async_playwright().start()
        
        self.browser = await playwright.chromium.launch(
            headless=False,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        
        context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York'
        )
        
        self.page = await context.new_page()

    async def login_to_discord(self):
        """Login to Discord web interface"""
        print("Navigating to Discord...")
        await self.page.goto('https://discord.com/login')
        
        await self.page.wait_for_selector('input[name="email"]', timeout=10000)
        
        print("Filling login credentials...")
        await self.page.fill('input[name="email"]', self.email)
        await self.page.fill('input[name="password"]', self.password)
        
        await self.random_delay(1, 3)
        
        print("Submitting login form...")
        await self.page.click('button[type="submit"]')
        
        try:
            await self.page.wait_for_selector('[data-list-item-id="guildsnav"]', timeout=30000)
            print("Successfully logged in!")
            return True
        except Exception as e:
            print(f"Login may have failed: {e}")
            return False

    async def find_new_server(self):
        """Find and navigate to the new Discord server"""
        print(f"Looking for new server: {self.new_server_name}")
        
        await self.page.wait_for_selector('[data-list-item-id="guildsnav"]', timeout=10000)
        
        server_selector = f'[aria-label*="{self.new_server_name}"]'
        
        try:
            await self.page.wait_for_selector(server_selector, timeout=10000)
            await self.page.click(server_selector)
            print(f"Successfully navigated to new server: {self.new_server_name}")
            await self.random_delay(2, 4)
            return True
        except Exception as e:
            print(f"Could not find new server '{self.new_server_name}': {e}")
            return False

    async def find_target_channel(self):
        """Find and navigate to the target channel in new server"""
        print(f"Looking for channel: {self.target_channel}")
        
        await self.page.wait_for_selector('[data-list-id="channels"]', timeout=10000)
        
        channel_selector = f'[data-list-item-id*="channels"][aria-label*="{self.target_channel}"]'
        
        try:
            await self.page.wait_for_selector(channel_selector, timeout=10000)
            await self.page.click(channel_selector)
            print(f"Successfully navigated to channel: {self.target_channel}")
            await self.random_delay(2, 4)
            return True
        except Exception as e:
            print(f"Could not find channel '{self.target_channel}': {e}")
            return False

    async def post_message(self, message_data: Dict[str, Any]):
        """Post a single message to the new server"""
        try:
            # Find the message input box
            message_input = await self.page.query_selector('[data-slate-editor="true"]')
            if not message_input:
                print("Could not find message input box")
                return False
            
            # Prepare message content
            content = message_data.get('content', '')
            author = message_data.get('author', 'Unknown')
            timestamp = message_data.get('timestamp', '')
            
            # Format the message with metadata
            formatted_message = f"**[{timestamp}] {author}:**\n{content}"
            
            # Add attachments info if present
            attachments = message_data.get('attachments', [])
            if attachments:
                formatted_message += "\n\n**Attachments:**"
                for attachment in attachments:
                    formatted_message += f"\n- {attachment.get('name', 'Unknown')}: {attachment.get('url', 'No URL')}"
            
            # Add embeds info if present
            embeds = message_data.get('embeds', [])
            if embeds:
                formatted_message += "\n\n**Embeds:**"
                for embed in embeds:
                    title = embed.get('title', 'No Title')
                    description = embed.get('description', 'No Description')
                    url = embed.get('url', 'No URL')
                    formatted_message += f"\n- **{title}**: {description}\n  URL: {url}"
            
            # Type the message
            await message_input.click()
            await self.random_delay(0.5, 1)
            
            # Clear any existing content and type new message
            await message_input.evaluate('element => element.innerHTML = ""')
            await message_input.type(formatted_message)
            
            await self.random_delay(1, 2)
            
            # Send the message
            await self.page.keyboard.press('Enter')
            
            print(f"Posted message from {author}")
            await self.random_delay(2, 4)  # Longer delay between posts
            
            return True
            
        except Exception as e:
            print(f"Error posting message: {e}")
            return False

    async def migrate_messages(self, limit: int = None):
        """Migrate messages to the new server"""
        if not self.messages_data:
            print("No messages to migrate")
            return
        
        messages_to_migrate = self.messages_data[:limit] if limit else self.messages_data
        
        print(f"Starting migration of {len(messages_to_migrate)} messages...")
        
        successful_posts = 0
        failed_posts = 0
        
        for i, message_data in enumerate(messages_to_migrate):
            try:
                print(f"Migrating message {i+1}/{len(messages_to_migrate)}")
                
                if await self.post_message(message_data):
                    successful_posts += 1
                else:
                    failed_posts += 1
                
                # Add longer delay every 10 messages to avoid rate limiting
                if (i + 1) % 10 == 0:
                    print(f"Pausing for 30 seconds after {i+1} messages...")
                    await self.random_delay(30, 35)
                
            except Exception as e:
                print(f"Error migrating message {i+1}: {e}")
                failed_posts += 1
                continue
        
        print(f"Migration completed!")
        print(f"Successfully posted: {successful_posts}")
        print(f"Failed posts: {failed_posts}")

    async def random_delay(self, min_seconds: float = 1, max_seconds: float = 3):
        """Add random delay to mimic human behavior"""
        import random
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    async def close_browser(self):
        """Close the browser"""
        if self.browser:
            await self.browser.close()

    async def run(self, limit: int = None):
        """Main execution method"""
        try:
            print("Starting Discord migration...")
            
            await self.load_messages_data()
            await self.start_browser()
            
            if not await self.login_to_discord():
                print("Login failed. Please check your credentials and try again.")
                return
            
            if not await self.find_new_server():
                print("Could not find the new server.")
                return
            
            if not await self.find_target_channel():
                print("Could not find the target channel.")
                return
            
            await self.migrate_messages(limit)
            
            print("Migration completed successfully!")
            
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            await self.close_browser()

async def main():
    """Main function"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python discord_migrator.py <json_file_path> [limit]")
        print("Example: python discord_migrator.py discord_messages_20231201_120000.json 50")
        return
    
    json_file_path = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    if not os.path.exists(json_file_path):
        print(f"File not found: {json_file_path}")
        return
    
    migrator = DiscordMigrator(json_file_path)
    await migrator.run(limit)

if __name__ == "__main__":
    asyncio.run(main())
