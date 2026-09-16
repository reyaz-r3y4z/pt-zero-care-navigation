"""Record a roughly 30-second end-to-end showcase as WebM."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from playwright.async_api import async_playwright


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "artifacts"))


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(OUTPUT_DIR),
            record_video_size={"width": 1440, "height": 900},
        )
        page = await context.new_page()
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_timeout(2500)

        unique_email = f"showcase-{int(time.time())}@example.com"
        await page.locator("#display-name").fill("PT Zero Reviewer")
        await page.locator("#email").fill(unique_email)
        await page.locator("#password").fill("ShowcasePassword!2026")
        await page.wait_for_timeout(1500)
        await page.locator("#auth-submit").click()
        await page.locator("#workspace").wait_for(state="visible")
        await page.wait_for_timeout(2500)

        await page.locator("#sample").select_option("0")
        await page.wait_for_timeout(1800)
        await page.locator("#patient-form button[type=submit]").click()
        await page.locator(".doctor").first.wait_for(state="visible")
        await page.wait_for_timeout(4500)
        await page.screenshot(
            path=str(OUTPUT_DIR / "pt-zero-showcase.png"), full_page=True
        )
        await page.locator("#trace-panel summary").click()
        await page.wait_for_timeout(3500)

        await page.locator("#sample").select_option("4")
        await page.wait_for_timeout(1500)
        await page.locator("#patient-form button[type=submit]").click()
        await page.locator(".alert").wait_for(state="visible")
        await page.wait_for_timeout(7500)

        video = page.video
        await context.close()
        await browser.close()
        if video:
            recorded = Path(await video.path())
            final = OUTPUT_DIR / "pt-zero-30s-showcase.webm"
            if final.exists():
                final.unlink()
            recorded.replace(final)
            print(f"Recorded showcase: {final}")


if __name__ == "__main__":
    asyncio.run(main())
