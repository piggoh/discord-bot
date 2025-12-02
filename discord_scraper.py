import asyncio
import json
import csv
import os
import time
import random
from datetime import datetime
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Page, Browser

from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

class DiscordScraper:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.email = os.getenv('DISCORD_EMAIL')
        self.password = os.getenv('DISCORD_PASSWORD')
        self.server_name = os.getenv('OLD_SERVER_NAME', 'cooks')
        self.target_channel = os.getenv('TARGET_CHANNEL', 'announcement')
        self.messages_data: List[Dict[str, Any]] = []
        
        if not self.email or not self.password:
            raise ValueError("Please set DISCORD_EMAIL and DISCORD_PASSWORD in your .env file")

    async def start_browser(self):
        """Initialize Playwright browser with stealth settings"""
        playwright = await async_playwright().start()
        
        # Use Chromium with stealth settings
        self.browser = await playwright.chromium.launch(
            headless=False,  # Set to True for headless mode
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        
        # Create context with realistic user agent
        context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York'
        )
        
        self.page = await context.new_page()
        
        # Add stealth scripts
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)

    async def login_to_discord(self):
        """Login to Discord web interface"""
        print("Navigating to Discord...")
        await self.page.goto('https://discord.com/login')
        
        # Wait for login form
        await self.page.wait_for_selector('input[name="email"]', timeout=10000)
        
        print("Filling login credentials...")
        await self.page.fill('input[name="email"]', self.email)
        await self.page.fill('input[name="password"]', self.password)
        
        # Add random delay to mimic human behavior
        await self.random_delay(1, 3)
        
        print("Submitting login form...")
        await self.page.click('button[type="submit"]')
        
        # Wait for login to complete (check for server list or main interface)
        try:
            await self.page.wait_for_selector('[data-list-item-id="guildsnav"]', timeout=30000)
            print("Successfully logged in!")
        except Exception as e:
            print(f"Login may have failed or requires additional verification: {e}")
            print("Please check if 2FA is required or if there are other verification steps.")
            return False
        
        return True

    async def find_server(self):
        """Find and click on the target Discord server"""
        print(f"Looking for server: {self.server_name}")
        
        # Wait for servers to load
        await self.page.wait_for_selector('[data-list-item-id="guildsnav"]', timeout=10000)
        
        # Look for server with matching name
        server_selector = f'[aria-label*="{self.server_name}"]'
        
        try:
            await self.page.wait_for_selector(server_selector, timeout=10000)
            await self.page.click(server_selector)
            print(f"Successfully navigated to server: {self.server_name}")
            await self.random_delay(2, 4)
            return True
        except Exception as e:
            print(f"Could not find server '{self.server_name}': {e}")
            print("Available servers:")
            servers = await self.page.query_selector_all('[data-list-item-id="guildsnav"] [aria-label]')
            for server in servers:
                name = await server.get_attribute('aria-label')
                print(f"  - {name}")
            return False

    async def find_channel(self):
        """Find and navigate to the target channel"""
        print(f"Looking for channel: {self.target_channel}")
        
        # Wait for channels to load
        await self.page.wait_for_selector('[data-list-id="channels"]', timeout=10000)
        
        # Look for channel with matching name
        channel_selector = f'[data-list-item-id*="channels"][aria-label*="{self.target_channel}"]'
        
        try:
            await self.page.wait_for_selector(channel_selector, timeout=10000)
            await self.page.click(channel_selector)
            print(f"Successfully navigated to channel: {self.target_channel}")
            await self.random_delay(2, 4)
            return True
        except Exception as e:
            print(f"Could not find channel '{self.target_channel}': {e}")
            print("Available channels:")
            channels = await self.page.query_selector_all('[data-list-item-id*="channels"] [aria-label]')
            for channel in channels:
                name = await channel.get_attribute('aria-label')
                print(f"  - {name}")
            return False

    async def scroll_to_load_messages(self, scroll_count: int = 10):
        """Scroll up to load more messages"""
        print(f"Scrolling to load messages (scrolls: {scroll_count})")
        
        # Find the message container
        message_container = await self.page.query_selector('[data-list-id="chat-messages"]')
        if not message_container:
            print("Could not find message container")
            return
        
        for i in range(scroll_count):
            # Scroll up to load older messages
            await message_container.evaluate('element => element.scrollTop = 0')
            await self.random_delay(2, 4)
            
            # Check if we've reached the top
            scroll_position = await message_container.evaluate('element => element.scrollTop')
            if scroll_position == 0:
                print(f"Reached the top after {i+1} scrolls")
                break
            
            print(f"Scroll {i+1}/{scroll_count} completed")

    async def scrape_messages(self):
        """Scrape all visible messages from the channel"""
        print("Starting message scraping...")
        
        # Wait for messages to load
        await self.page.wait_for_selector('[data-list-id="chat-messages"]', timeout=10000)
        
        # Get all message elements
        message_elements = await self.page.query_selector_all('[data-list-id="chat-messages"] [id^="chat-messages-"]')
        
        print(f"Found {len(message_elements)} messages")
        
        for i, message_element in enumerate(message_elements):
            try:
                message_data = await self.extract_message_data(message_element)
                if message_data:
                    self.messages_data.append(message_data)
                    print(f"Scraped message {i+1}/{len(message_elements)}: {message_data.get('content', '')[:50]}...")
                
                # Add delay between messages to avoid rate limiting
                await self.random_delay(0.5, 1.5)
                
            except Exception as e:
                print(f"Error scraping message {i+1}: {e}")
                continue
        
        print(f"Successfully scraped {len(self.messages_data)} messages")

    async def extract_message_data(self, message_element) -> Optional[Dict[str, Any]]:
        """Extract data from a single message element"""
        try:
            # Extract message content
            content_element = await message_element.query_selector('[data-slate-editor="true"]')
            content = ""
            if content_element:
                content = await content_element.inner_text()
            
            # Extract author name
            author_element = await message_element.query_selector('[class*="username"]')
            author = ""
            if author_element:
                author = await author_element.inner_text()
            
            # Extract timestamp
            timestamp_element = await message_element.query_selector('[class*="timestamp"]')
            timestamp = ""
            if timestamp_element:
                timestamp = await timestamp_element.inner_text()
            
            # Extract attachments
            attachments = []
            attachment_elements = await message_element.query_selector_all('[class*="attachment"]')
            for attachment in attachment_elements:
                attachment_data = await self.extract_attachment_data(attachment)
                if attachment_data:
                    attachments.append(attachment_data)
            
            # Extract embeds
            embeds = []
            embed_elements = await message_element.query_selector_all('[class*="embed"]')
            for embed in embed_elements:
                embed_data = await self.extract_embed_data(embed)
                if embed_data:
                    embeds.append(embed_data)
            
            return {
                'content': content,
                'author': author,
                'timestamp': timestamp,
                'attachments': attachments,
                'embeds': embeds,
                'scraped_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error extracting message data: {e}")
            return None

    async def extract_attachment_data(self, attachment_element) -> Optional[Dict[str, Any]]:
        """Extract attachment data"""
        try:
            # Get attachment URL
            link_element = await attachment_element.query_selector('a')
            url = ""
            if link_element:
                url = await link_element.get_attribute('href')
            
            # Get attachment name
            name_element = await attachment_element.query_selector('[class*="filename"]')
            name = ""
            if name_element:
                name = await name_element.inner_text()
            
            return {
                'url': url,
                'name': name
            }
        except Exception as e:
            print(f"Error extracting attachment data: {e}")
            return None

    async def extract_embed_data(self, embed_element) -> Optional[Dict[str, Any]]:
        """Extract embed data"""
        try:
            # Get embed title
            title_element = await embed_element.query_selector('[class*="embedTitle"]')
            title = ""
            if title_element:
                title = await title_element.inner_text()
            
            # Get embed description
            description_element = await embed_element.query_selector('[class*="embedDescription"]')
            description = ""
            if description_element:
                description = await description_element.inner_text()
            
            # Get embed URL
            url_element = await embed_element.query_selector('[class*="embedTitle"] a')
            url = ""
            if url_element:
                url = await url_element.get_attribute('href')
            
            return {
                'title': title,
                'description': description,
                'url': url
            }
        except Exception as e:
            print(f"Error extracting embed data: {e}")
            return None

    async def export_data(self):
        """Export scraped data to JSON and CSV files"""
        if not self.messages_data:
            print("No data to export")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Export to JSON
        json_filename = f"discord_messages_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(self.messages_data, f, indent=2, ensure_ascii=False)
        print(f"Data exported to {json_filename}")
        
        # Export to CSV
        csv_filename = f"discord_messages_{timestamp}.csv"
        df = pd.DataFrame(self.messages_data)
        df.to_csv(csv_filename, index=False, encoding='utf-8')
        print(f"Data exported to {csv_filename}")
        
        # Create summary
        summary = {
            'total_messages': len(self.messages_data),
            'unique_authors': len(set(msg.get('author', '') for msg in self.messages_data)),
            'messages_with_attachments': len([msg for msg in self.messages_data if msg.get('attachments')]),
            'messages_with_embeds': len([msg for msg in self.messages_data if msg.get('embeds')]),
            'scraped_at': datetime.now().isoformat(),
            'server_name': self.server_name,
            'channel_name': self.target_channel
        }
        
        summary_filename = f"scraping_summary_{timestamp}.json"
        with open(summary_filename, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"Summary exported to {summary_filename}")

    async def random_delay(self, min_seconds: float = 1, max_seconds: float = 3):
        """Add random delay to mimic human behavior"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    async def close_browser(self):
        """Close the browser"""
        if self.browser:
            await self.browser.close()

    async def run(self):
        """Main execution method"""
        try:
            print("Starting Discord scraper...")
            
            await self.start_browser()
            
            if not await self.login_to_discord():
                print("Login failed. Please check your credentials and try again.")
                return
            
            if not await self.find_server():
                print("Could not find the target server.")
                return
            
            if not await self.find_channel():
                print("Could not find the target channel.")
                return
            
            # Scroll to load more messages
            await self.scroll_to_load_messages(scroll_count=20)
            
            # Scrape messages
            await self.scrape_messages()
            
            # Export data
            await self.export_data()
            
            print("Scraping completed successfully!")
            
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            await self.close_browser()

async def main():
    """Main function"""
    scraper = DiscordScraper()
    await scraper.run()

if __name__ == "__main__":
    asyncio.run(main())
