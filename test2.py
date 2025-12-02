import asyncio
import json
import re
import time
import requests
from playwright.async_api import async_playwright

# 🔧 CONFIGURATION
SOURCE_CHANNEL_URL = "https://discord.com/channels/1432250238319726664/1432380508846821496"
WEBHOOK_URL = "https://discord.com/api/webhooks/1434226344010580011/ORais6S74LP47UkMFYORiQzc1KC9NvDVzlxmnUqWJpV9dc1ZQakEpfMuq8N4bjXGe-XI"

# optional: add regex or formatting rules
def format_message(raw_text):
    """
    You can modify this function to adjust the content
    (e.g., remove tags, clean mentions, add timestamps)
    """
    cleaned = re.sub(r'<:\w+:\d+>', '', raw_text)  # remove emoji tags
    cleaned = re.sub(r'@\w+', '', cleaned)         # remove @mentions
    cleaned = cleaned.strip()
    return f"💬 {cleaned}" if cleaned else None


async def fetch_latest_message(page):
    """
    Extracts the latest visible message in the chat list.
    You can modify selector depending on Discord's DOM changes.
    """
    try:
        message_elems = await page.query_selector_all("li[data-list-item-id^='chat-messages']")
        if not message_elems:
            return None

        last_message_elem = message_elems[-1]
        message_text = await last_message_elem.inner_text()
        return message_text.strip()
    except Exception as e:
        print(f"⚠️ Error fetching message: {e}")
        return None


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(SOURCE_CHANNEL_URL)
        print("✅ Logged in manually once, then let the monitor run.")

        last_message = ""
        print("👀 Monitoring source server for new messages...")

        while True:
            message_text = await fetch_latest_message(page)

            if message_text and message_text != last_message:
                last_message = message_text
                formatted = format_message(message_text)

                if formatted:
                    payload = {"content": formatted}
                    try:
                        r = requests.post(WEBHOOK_URL, json=payload)
                        if r.status_code == 204:
                            print(f"✅ Message relayed instantly at {time.strftime('%H:%M:%S')}")
                        else:
                            print(f"⚠️ Webhook returned status {r.status_code}")
                    except Exception as e:
                        print(f"❌ Failed to send message: {e}")

            await asyncio.sleep(0.2)  # short polling interval for speed (200 ms)


if __name__ == "__main__":
    asyncio.run(main())
