"""Browser smoke test for authentication, navigation, and booking."""

from __future__ import annotations

import asyncio
import os
import time

from playwright.async_api import async_playwright


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


async def main() -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.locator("#display-name").fill("Browser Smoke Test")
        await page.locator("#email").fill(f"smoke-{int(time.time())}@example.com")
        await page.locator("#password").fill("BrowserSmokePassword!2026")
        await page.locator("#auth-submit").click()
        await page.locator("#workspace-shell").wait_for(state="visible")
        await page.locator("#sample").select_option("0")
        await page.locator("#patient-form button[type=submit]").click()
        await page.locator(".book-button").first.wait_for(state="visible")
        await page.locator(".book-button").first.click()
        await page.locator("#appointments .status-pill").wait_for(state="visible")
        assert await page.locator("#stats").get_by_text("50").count() >= 1
        assert "confirmed" in (await page.locator("#appointments").inner_text()).lower()
        print("Browser smoke test passed: auth -> navigate -> book -> audit UI")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
