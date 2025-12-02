import asyncio
import json
from playwright.async_api import async_playwright


async def diagnose_chrome():
    test_url = "https://www.google.com"

    print("🚀 Launching Chromium diagnostic session...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # Set True if you want headless mode
            args=[
                "--enable-logging",
                "--v=1",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-gpu",  # Toggle this ON/OFF to test GPU impact
                "--disable-software-rasterizer",
            ],
        )

        context = await browser.new_context()
        page = await context.new_page()

        # --- Capture console logs ---
        page.on(
            "console",
            lambda msg: print(f"⚠️ [Console {msg.type()}] {msg.text()}") 
            if msg.type() in ["error", "warning"]
            else None
        )

        # --- Capture JS page errors ---
        page.on("pageerror", lambda err: print(f"🔥 [Page Error] {err.message}"))

        # --- Capture failed network requests ---
        page.on(
            "requestfailed",
            lambda req: print(
                f"❌ [Network Fail] {req.url} → {req.failure.error_text if req.failure else 'Unknown'}"
            ),
        )

        print(f"🌐 Navigating to: {test_url}")
        start = asyncio.get_event_loop().time()

        try:
            await page.goto(test_url, wait_until="load", timeout=45000)
        except Exception as e:
            print(f"⚠️ Navigation error: {e}")
        end = asyncio.get_event_loop().time()
        print(f"⏱️ Total Page Load Time: {round(end - start, 2)}s")

        # --- Timing breakdown from performance API ---
        try:
            timing_json = await page.evaluate("JSON.stringify(performance.timing)")
            t = json.loads(timing_json)
            print("📊 Timing Breakdown (ms):", {
                "DNS": t["domainLookupEnd"] - t["domainLookupStart"],
                "Connect": t["connectEnd"] - t["connectStart"],
                "TTFB": t["responseStart"] - t["requestStart"],
                "Load": t["loadEventEnd"] - t["navigationStart"],
            })
        except Exception as e:
            print(f"⚠️ Failed to extract timing: {e}")

        # --- Optional: GPU/Renderer process log (Chrome internals) ---
        print("🔍 Checking GPU & Renderer process logs...")
        browser_version = await browser.version()
        print(f"🧩 Browser version: {browser_version}")

        await browser.close()
        print("✅ Diagnostic session finished.")


if __name__ == "__main__":
    asyncio.run(diagnose_chrome())
