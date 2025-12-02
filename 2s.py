import asyncio
import json
import os
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from playwright.async_api import async_playwright, Page, Browser
from dotenv import load_dotenv
import pandas as pd
import aiofiles
from dateutil import parser
import pytz
import re
import requests
import aiohttp
import ssl
import certifi

# Load environment variables
load_dotenv()

class DiscordMonitor:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.email = os.getenv('DISCORD_EMAIL')
        self.password = os.getenv('DISCORD_PASSWORD')
        self.source_server = os.getenv('SOURCE_SERVER_NAME', 'Oculus Trading')
        self.source_channel = os.getenv('SOURCE_CHANNEL', '🚨・oculus-vip-alert')
        self.dest_server = os.getenv('DEST_SERVER_NAME', 'SULTAN TRADING SIGNAL')
        self.dest_channel = os.getenv('DEST_CHANNEL', '📊│options-vip-signal')
        self.source_channel_url = os.getenv('SOURCE_CHANNEL_URL', '')
        self.dest_channel_url = os.getenv('DEST_CHANNEL_URL', '')
        self.check_interval = float(os.getenv('CHECK_INTERVAL', '0.5'))
        self.max_messages_per_batch = int(os.getenv('MAX_MESSAGES_PER_BATCH', '10'))
        self.enable_auto_migration = os.getenv('ENABLE_AUTO_MIGRATION', 'true').lower() == 'true'
        self.max_message_age_seconds = int(os.getenv('MAX_MESSAGE_AGE_SECONDS', '10'))
        
        # State tracking
        self.last_message_id: Optional[str] = None
        self.processed_messages: Set[str] = set()
        self.state_file = 'monitor_state.json'
        self.messages_log_file = 'monitored_messages.json'
        
        if not self.email or not self.password:
            raise ValueError("Please set DISCORD_EMAIL and DISCORD_PASSWORD in your .env file")

    async def start_browser(self):
        """Initialize Playwright browser with stealth settings"""
        playwright = await async_playwright().start()
        
        self.browser = await playwright.chromium.launch(
            headless=False,  # Set to True for headless mode
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
                '--window-size=1024,768',  # Initial window size
                '--window-position=50,50',  # Initial window position
                '--start-maximized'  # Allow window to be maximized
                
            ]
        )
        
        context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            no_viewport=True,
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
        print("🌐 Navigating to Discord...")
        # Prefer SOURCE_CHANNEL_URL if provided, else keep current direct URL
        start_url = self.source_channel_url.strip() or 'https://discord.com/channels/1432250238319726664/1432380508846821496'
        await self.page.goto(start_url)
        
        
        try:
            await self.page.wait_for_selector('input[name="email"]', timeout=5000)
        except Exception:
            # No email field visible — likely already logged in
            current_url = self.page.url
            print(f"🔗 Current URL: {current_url}")
            if '/channels/' in current_url:
                print("✓ Already authenticated and on a channel page")
                return True
        
        print("📝 Filling login credentials...")
        await self.page.fill('input[name="email"]', self.email)
        await self.page.fill('input[name="password"]', self.password)
        
        await self.random_delay(1, 3)
        await self.page.click('button[type="submit"]')
        
        # Wait a bit for the form to process
        await self.random_delay(2, 4)
        

        
        # Check URL change (primary for direct channel access)
        current_url = self.page.url
        print(f"🔗 Current URL: {current_url}")
        if 'channels' in current_url or 'app' in current_url:
            print("✓ URL indicates successful login!")
            return True
        
        # Method 4: Check for error messages
        try:
            error_element = await self.page.query_selector('[class*="error"], [class*="invalid"]')
            if error_element:
                error_text = await error_element.inner_text()
                print(f"✗ Login error detected: {error_text}")
                return False
        except:
            pass
        
        # Check for 2FA or verification
        try:
            print("⏳ Checking for 2FA or verification...")
            await self.page.wait_for_selector('input[name="code"], [class*="verification"], [class*="captcha"]', timeout=3000)
            print("⚠️  2FA or verification required - please complete manually")
            print("💡 Complete the verification in the browser, then press Enter to continue...")
            input("Press Enter after completing verification...")
            
            # Check again after manual verification
            try:
                await self.page.wait_for_selector('[data-list-item-id="guildsnav"]', timeout=10000)
                print("✓ Login successful after verification!")
                return True
            except:
                pass
        except:
            pass
        
        print("❌ Login status unclear - checking page content...")
        
        # Debug: Take screenshot and show page title
        try:
            title = await self.page.title()
            print(f"📄 Page title: {title}")
        except:
            pass
        
        # Check if we're still on login page
        if 'login' in current_url.lower():
            print("❌ Still on login page - login likely failed")
            return False
        else:
            print("⚠️  Not on login page but success unclear - proceeding with caution")
            return True

    async def _get_current_location(self) -> Dict[str, str]:
        """Best-effort read of current server and channel names for debug logs."""
        server_name = ''
        channel_name = ''
        try:
            # Channel header often contains the name
            header_el = await self.page.query_selector('[data-list-id="chat-messages"]')
            if header_el:
                # Try common title selectors
                title_el = await self.page.query_selector('[class*="title-"], [class*="channelName-"], [class*="name-"], h1[role="heading"]')
                if title_el:
                    channel_name = (await title_el.inner_text()).strip()
        except Exception:
            pass
        try:
            # Tooltip/aria-label on active guild icon sometimes has the server name
            active_guild = await self.page.query_selector('[aria-label][class*="selected-"], [aria-label][class*="active-"], nav[aria-label*="Servers"] [aria-current="page"]')
            if active_guild:
                server_name = (await active_guild.get_attribute('aria-label')) or ''
        except Exception:
            pass
        return {
            'server': server_name or self.source_server,
            'channel': channel_name or self.source_channel
        }

    async def get_new_messages(self) -> List[Dict[str, Any]]:
        """Get new messages since last check with per-second retry and detailed logs"""
        loc = await self._get_current_location()
        print(f"\n📥 Fetching from: {loc['server']} > {loc['channel']}")
        
        try:
            # Retry up to 10 seconds for messages container
            found = False
            for i in range(1, 11):
                try:
                    await self.page.wait_for_selector('[data-list-id="chat-messages"]', timeout=1000)
                    found = True
                    print(f"  ⏳ trying {i}s: messages container visible")
                    break
                except Exception:
                    print(f"  ⏳ trying {i}s: waiting for messages container...")
            if not found:
                print("✗ Messages container not found after 10s")
                return []
            
            # Light auto-scroll to ensure messages render (Discord virtualizes)
            try:
                await self.page.mouse.wheel(0, -800)
                await asyncio.sleep(0.1)
                await self.page.mouse.wheel(0, 800)
                await asyncio.sleep(0.1)
            except Exception:
                pass

            # Try multiple selectors for message elements
            print("⏳ Extracting message elements...")
            selectors = [
                '[data-list-id="chat-messages"] [id^="chat-messages-"]',
                '[id^="chat-messages-"]',
                '[data-list-id="chat-messages"] article',
                'li[id^="chat-messages-"]'
            ]
            message_elements: List[Any] = []
            for sel in selectors:
                message_elements = await self.page.query_selector_all(sel)
                print(f"  • selector '{sel}' -> {len(message_elements)} elements")
                if message_elements:
                    break
            if not message_elements:
                print("✗ No message elements found with known selectors")
                return []
            print(f"✓ Found {len(message_elements)} message elements")

            # Debug: print id, timestamp and a text preview for the last 10 message elements
            try:
                print("🔎 Debug: dumping last 10 message elements (id | timestamp | preview)")
                last_items = message_elements[-10:]
                start_idx = max(0, len(message_elements) - len(last_items))
                for i, el in enumerate(last_items, start=start_idx + 1):
                    try:
                        mid = await el.get_attribute('id')
                    except Exception:
                        mid = None
                    try:
                        ts_el = await el.query_selector('[class*="timestamp_"], time')
                        ts = (await ts_el.inner_text()).strip() if ts_el else ''
                    except Exception:
                        ts = ''
                    try:
                        raw_text = await el.evaluate('node => node.innerText || node.textContent || ""')
                        preview = raw_text.strip().replace('\n', ' ')[:300]
                    except Exception as e:
                        preview = f"<error reading text: {e}>"
                    print(f"  • [{i}] id={mid} | ts='{ts}' | preview='{preview}'")
            except Exception as e:
                print(f"🔎 Debug dump failed: {e}")
            
            new_messages = []
            current_time = datetime.now()
            max_age_seconds = self.max_message_age_seconds
            
            for idx, message_element in enumerate(message_elements):
                try:
                    message_data = await self.extract_message_data(message_element)
                    if not message_data:
                        print(f"  ℹ️  Skipping element #{idx+1}: no message_data extracted")
                        continue

                    mid = message_data.get('message_id')
                    if mid in self.processed_messages:
                        print(f"  ℹ️  Skipping {mid}: already processed")
                        continue

                    # Check if message has substantial content
                    content = (message_data.get('content') or '').strip()
                    if not content or len(content) < 20:
                        preview = (content or '').replace('\n', ' ')[:120]
                        print(f"  ℹ️  Skipping {mid}: content too short ({len(content)}) preview='{preview}'")
                        continue

                    # Only process messages that look like trading signals
                    # Accept several common variants/casing of the markers
                    signal_found = False
                    try:
                        if 'oculus trading signal' in content.lower():
                            signal_found = True
                        if 'ticker' in content.lower() and (':' in content):
                            signal_found = True
                    except Exception:
                        signal_found = False

                    if not signal_found:
                        preview = content.replace('\n', ' ')[:120]
                        print(f"  ℹ️  Skipping {mid}: no signal keywords found preview='{preview}'")
                        continue

                    # Check if message is recent (within the specified time window)
                    is_recent = False
                    try:
                        timestamp_str = (message_data.get('timestamp') or '').strip()
                        if timestamp_str:
                            # Fast checks
                            if 'Just now' in timestamp_str or 'Today at' in timestamp_str:
                                is_recent = True
                            else:
                                # Try to parse a full datetime first (handles formats like "Wednesday, 26 November 2025 at 13:34")
                                try:
                                    parsed_dt = parser.parse(timestamp_str, fuzzy=True)
                                    delta_secs = abs((datetime.now() - parsed_dt).total_seconds())
                                    if delta_secs <= self.max_message_age_seconds:
                                        is_recent = True
                                except Exception:
                                    # Fallback: look for HH:MM (24h or 12h) and compare to today
                                    m = re.search(r"(\d{1,2}:\d{2})", timestamp_str)
                                    if m:
                                        time_part = m.group(1)
                                        try:
                                            msg_time = datetime.strptime(time_part, '%H:%M').time()
                                        except Exception:
                                            try:
                                                msg_time = datetime.strptime(time_part, '%I:%M').time()
                                            except Exception:
                                                msg_time = None
                                        if msg_time:
                                            now = datetime.now()
                                            msg_dt = datetime.combine(now.date(), msg_time)
                                            # If message time looks like it's in the future (cross-midnight), adjust backwards one day
                                            if msg_dt > now:
                                                msg_dt = msg_dt - timedelta(days=1)
                                            delta = abs((now - msg_dt).total_seconds())
                                            if delta <= self.max_message_age_seconds:
                                                is_recent = True
                    except Exception:
                        # If we can't parse timestamp, skip this message
                        continue

                    if not is_recent:
                        continue

                    new_messages.append(message_data)
                    self.processed_messages.add(message_data['message_id'])

                    # Update last message ID
                    if not self.last_message_id:
                        self.last_message_id = message_data['message_id']

                    preview = content.replace('\n', ' ')
                    if len(preview) > 120:
                        preview = preview[:117] + '...'
                    print(f"  ✓ fetched #{idx+1}: '{preview}'")

                except Exception as e:
                    print(f"  ✗ Error extracting message {idx+1}: {e}")
                    continue
            
            # Sort by timestamp (oldest first)
            new_messages.sort(key=lambda x: x.get('timestamp', ''))
            
            print(f"✓ Fetch successful! {len(new_messages)} new trading signal messages")
            return new_messages
            
        except Exception as e:
            print(f"✗ Error getting messages: {e}")
            return []

    async def extract_message_data(self, message_element) -> Optional[Dict[str, Any]]:
        """Extract data from a single message element"""
        try:
            # Get message ID
            message_id = await message_element.get_attribute('id')
            if not message_id:
                return None
            
            # Extract message content from current Discord DOM
            content = ""
            # 1) Direct message content div
            content_el = await message_element.query_selector('[id^="message-content-"]')
            if content_el:
                try:
                    content = (await content_el.inner_text()).strip()
                except Exception:
                    pass
            # 2) Fallback: common class prefixes (obfuscated suffixes)
            if not content:
                for sel in [
                    '[class^="messageContent_"]',
                    '[class^="markup__"]',
                    'div[role="document"]',
                    'div[role="textbox"]',
                ]:
                    el = await message_element.query_selector(sel)
                    if el:
                        try:
                            content = (await el.inner_text()).strip()
                            if content:
                                break
                        except Exception:
                            pass
            # 3) Last resort: grab textContent of the whole message node
            if not content:
                try:
                    content = (await message_element.evaluate('el => el.textContent || ""')).strip()
                except Exception:
                    pass
            if not content:
                print("    ⚠️  Empty content extracted for", message_id)
            
            # Extract author name
            author_element = await message_element.query_selector('[class*="username_"], [class*="headerText_"] [class*="username_"], [class*="headerText-"] [class*="username-"], h3[role="heading"]')
            author = ""
            if author_element:
                author = await author_element.inner_text()
            
            # Extract timestamp
            timestamp_element = await message_element.query_selector('[class*="timestamp_"], [class*="timestamp"], time')
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
                'message_id': message_id,
                'content': content,
                'author': author,
                'timestamp': timestamp,
                'attachments': attachments,
                'embeds': embeds,
                'scraped_at': datetime.now().isoformat(),
                'source_server': self.source_server,
                'source_channel': self.source_channel
            }
            
        except Exception as e:
            print(f"Error extracting message data: {e}")
            return None

    async def extract_attachment_data(self, attachment_element) -> Optional[Dict[str, Any]]:
        """Extract attachment data"""
        try:
            link_element = await attachment_element.query_selector('a')
            url = ""
            if link_element:
                url = await link_element.get_attribute('href')
            
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
            title_element = await embed_element.query_selector('[class*="embedTitle"]')
            title = ""
            if title_element:
                title = await title_element.inner_text()
            
            description_element = await embed_element.query_selector('[class*="embedDescription"]')
            description = ""
            if description_element:
                description = await description_element.inner_text()
            
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

    def convert_message_structure(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert message structure to desired format"""
        # Customize this function based on your specific requirements
        converted_message = {
            'id': message_data.get('message_id', ''),
            'original_author': message_data.get('author', 'Unknown'),
            'original_timestamp': message_data.get('timestamp', ''),
            'content': message_data.get('content', ''),
            'attachments': message_data.get('attachments', []),
            'embeds': message_data.get('embeds', []),
            'migrated_at': datetime.now().isoformat(),
            'migration_status': 'pending',
            'source_info': {
                'server': message_data.get('source_server', ''),
                'channel': message_data.get('source_channel', ''),
                'scraped_at': message_data.get('scraped_at', '')
            }
        }
        
        # Transform source format to requested destination format
        content_text = (message_data.get('content') or '').strip()
        if content_text:
            # Remove decorative dividers and unwanted lines
            cleaned_lines: List[str] = []
            for raw in content_text.splitlines():
                line = raw.strip()
                if not line:
                    cleaned_lines.append("")
                    continue
                if set(line) == {'='}:  # divider line
                    continue
                if re.match(r"^discord\.gg/", line, flags=re.I):
                    continue
                if re.search(r"oculus\s+trading\s+signal", line, flags=re.I):
                    continue
                cleaned_lines.append(line)
            cleaned_text = "\n".join(cleaned_lines).strip()

            # Extract fields
            fields = {'ticker': '', 'strike': '', 'expiry': '', 'entry': ''}
            pattern = re.compile(r">?\s*(Ticker|Strike|Expiry|Entry)\s*[:：]\s*(.+)", re.I)
            for raw in cleaned_text.splitlines():
                m = pattern.match(raw.strip())
                if m:
                    key = m.group(1).lower()
                    val = m.group(2).strip()
                    fields[key] = val

            # Build destination format
            formatted_lines = [
                "@everyone",
                "***SULTAN TRADING SIGNAL:***",
                "",
                f"> Ticker : {fields['ticker']}",
                f"> Entry : {fields['entry']}",
                f"> Expiry : {fields['expiry']}",
                f"> Strike : {fields['strike']}",
            ]
            converted_message['formatted_content'] = "\n".join(formatted_lines).strip()
        
        return converted_message

    async def save_messages(self, messages: List[Dict[str, Any]]):
        """Save messages to log file"""
        if not messages:
            return
        
        try:
            # Load existing messages
            existing_messages = []
            existing_ids: Set[str] = set()
            if os.path.exists(self.messages_log_file):
                async with aiofiles.open(self.messages_log_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    if content.strip():
                        existing_messages = json.loads(content)
                        for m in existing_messages:
                            mid = m.get('message_id')
                            if mid:
                                existing_ids.add(mid)
            
            # Add new messages
            new_unique_messages = [m for m in messages if m.get('message_id') not in existing_ids]
            if not new_unique_messages:
                print("ℹ️  No new unique messages to save")
                return
            existing_messages.extend(new_unique_messages)
            
            # Save updated messages
            async with aiofiles.open(self.messages_log_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(existing_messages, indent=2, ensure_ascii=False))
            
            print(f"Saved {len(new_unique_messages)} new messages to {self.messages_log_file}")
            
        except Exception as e:
            print(f"Error saving messages: {e}")

    async def save_state(self):
        """Save monitoring state"""
        state = {
            'last_message_id': self.last_message_id,
            'processed_messages': list(self.processed_messages),
            'last_check': datetime.now().isoformat()
        }
        
        try:
            async with aiofiles.open(self.state_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(state, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"Error saving state: {e}")

    async def load_state(self):
        """Load monitoring state"""
        if not os.path.exists(self.state_file):
            return
        
        try:
            async with aiofiles.open(self.state_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content.strip():
                    state = json.loads(content)
                    self.last_message_id = state.get('last_message_id')
                    self.processed_messages = set(state.get('processed_messages', []))
                    print(f"Loaded state: {len(self.processed_messages)} processed messages")
            # Also load processed IDs from existing log for dedupe across runs
            await self.load_processed_from_log()
        except Exception as e:
            print(f"Error loading state: {e}")

    async def migrate_messages(self, messages: List[Dict[str, Any]]):
        """Migrate messages to destination server"""
        if not self.enable_auto_migration:
            print("⚠️  Auto-migration disabled")
            return
        
        # Check if we have destination URL (preferred) or server name
        if not self.dest_channel_url.strip() and not self.dest_server:
            print("⚠️  No destination configured. Set DEST_CHANNEL_URL or DEST_SERVER_NAME in .env")
            return
        
        dest_name = self.dest_channel_url.strip() or f"{self.dest_server} > {self.dest_channel}"
        print(f"\n📤 Starting migration of {len(messages)} messages to {dest_name}")
        
        # If we have a direct channel URL, skip server/channel finding
        if self.dest_channel_url.strip():
            print(f"↪️  Using direct channel URL: {self.dest_channel_url.strip()}")
        else:
            # Navigate to destination server using traditional method
            if not await self.find_dest_server():
                print("✗ Failed to find destination server. Migration aborted.")
                return
            
            if not await self.find_dest_channel():
                print("✗ Failed to find destination channel. Migration aborted.")
                return
        
        successful_migrations = 0
        
        for i, message_data in enumerate(messages):
            try:
                print(f"\n📝 Migrating message {i+1}/{len(messages)}...")
                converted_message = self.convert_message_structure(message_data)
                preview = (converted_message.get('formatted_content') or converted_message.get('content') or '').strip().replace('\n', ' ')
                if len(preview) > 120:
                    preview = preview[:117] + '...'
                print(f"   ✍️  rewrite preview: '{preview}'")
                
                if await self.post_message(converted_message):
                    successful_migrations += 1
                    dest_display = self.dest_channel_url.strip() or f"{self.dest_server} > {self.dest_channel}"
                    print(f"✓ Posted to '{dest_display}' (#{i+1})")
                else:
                    print(f"✗ Failed to migrate message {i+1}/{len(messages)}")
                
                # Rate limiting
                
            except Exception as e:
                print(f"✗ Error migrating message {i+1}: {e}")
                continue
        
        print(f"\n{'='*60}")
        print(f"✓ Migration completed: {successful_migrations}/{len(messages)} messages migrated successfully")
        print(f"{'='*60}\n")

    async def find_dest_server(self):
        """Find and navigate to destination server"""
        print(f"\n🔍 Finding destination server: '{self.dest_server}'")
        
        server_selector = f'[aria-label*="{self.dest_server}"]'
        
        try:
            print(f"⏳ Waiting for destination server selector...")
            await self.page.wait_for_selector(server_selector, timeout=10000)
            print(f"✓ Destination server found! Clicking on '{self.dest_server}'...")
            await self.page.click(server_selector)
            print(f"✓ Successfully navigated to destination server: {self.dest_server}")
            return True
        except Exception as e:
            print(f"✗ Could not find destination server '{self.dest_server}': {e}")
            return False

    async def find_dest_channel(self):
        """Find and navigate to destination channel"""
        print(f"\n🔍 Finding destination channel: '{self.dest_channel}'")
        
        channel_selector = f'[data-list-item-id*="channels"][aria-label*="{self.dest_channel}"]'
        
        try:
            print(f"⏳ Waiting for destination channel selector...")
            await self.page.wait_for_selector(channel_selector, timeout=10000)
            print(f"✓ Destination channel found! Clicking on '{self.dest_channel}'...")
            await self.page.click(channel_selector)
            print(f"✓ Successfully navigated to destination channel: {self.dest_channel}")
            return True
        except Exception as e:
            print(f"✗ Could not find destination channel '{self.dest_channel}': {e}")
            return False

    async def post_message(self, message_data: Dict[str, Any]):
        """Post a message to destination Discord channel using webhook"""
        try:
            # Get webhook URL from environment variable
            webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
            if not webhook_url:
                print("❌ No webhook URL configured. Set DISCORD_WEBHOOK_URL in your .env file")
                return False

            # Extract the message content
            content = message_data.get('formatted_content', message_data.get('content', ''))
            if not content.strip():
                print("⚠️ No message content to send.")
                return False

            print(f"� Sending message via webhook: {content[:100]}...")
            
            # Prepare the webhook payload
            payload = {
                'content': content,
                'username': 'Signal Monitor',  # Optional: customize the webhook bot name
                'avatar_url': None  # Optional: customize the webhook bot avatar
            }

            message_input = None
            # Configure SSL context with system certificates
            import ssl
            import certifi
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            
            # Send the webhook request with configured SSL context
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 204:  # Discord returns 204 on successful webhook
                        print("✅ Message sent successfully via webhook!")
                        return True
                    else:
                        error_text = await response.text()
                        print(f"❌ Failed to send webhook. Status: {response.status}, Error: {error_text}")
                        return False

            return True

        except Exception as e:
            print(f"❌ Error posting message: {e}")
            return False


    async def random_delay(self, min_seconds: float = 1, max_seconds: float = 3):
        """Add random delay to mimic human behavior"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    async def close_browser(self):
        """Close the browser"""
        if self.browser:
            await self.browser.close()

    async def monitor_loop(self):
        """Main monitoring loop"""
        print(f"\n{'='*60}")
        print(f"🚀 Starting continuous monitoring...")
        print(f"⏱️  Checking every {self.check_interval} seconds")
        loc = await self._get_current_location()
        print(f"📥 Source: {loc['server']} > {loc['channel']}")
        if self.enable_auto_migration:
            print(f"📤 Destination: {self.dest_server} > {self.dest_channel}")
        print(f"{'='*60}\n")
        
        await self.load_state()
        
        try:
            while True:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔄 Checking for new messages...")
                
                # Get new messages (we're already on the correct server/channel)
                new_messages = await self.get_new_messages()
                
                if new_messages:
                    print(f"✓ Found {len(new_messages)} new messages")
                    
                    # Save messages
                    print("💾 Saving messages...")
                    await self.save_messages(new_messages)
                    print("✓ Messages saved")
                    
                    # Migrate messages if enabled
                    if self.enable_auto_migration:
                        await self.migrate_messages(new_messages)
                    
                    # Save state
                    await self.save_state()
                else:
                    print("ℹ️  No new messages found")
                
                # Wait before next check
                print(f"⏳ Waiting {self.check_interval} seconds before next check...")
                await asyncio.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoring stopped by user")
        except Exception as e:
            print(f"✗ Error in monitoring loop: {e}")
        finally:
            await self.save_state()
            await self.close_browser()

    async def run(self):
        """Main execution method"""
        try:
            print("Starting Discord Monitor...")
            
            await self.start_browser()
            
            if not await self.login_to_discord():
                print("Login failed. Please check your credentials and try again.")
                return
            
            # We are already on the target channel by direct URL
            loc = await self._get_current_location()
            print("\n✓ Ready on target channel")
            print(f"📋 Monitoring: {loc['server']} > {loc['channel']}")
            
            await self.monitor_loop()
            
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            await self.close_browser()

async def main():
    """Main function"""
    monitor = DiscordMonitor()
    await monitor.run()

if __name__ == "__main__":
    asyncio.run(main())