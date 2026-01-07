from typing import Optional, Dict
from playwright.async_api import async_playwright
import asyncio
import json
import pathlib


BASE_DIR = pathlib.Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"


async def solve_captcha_with_playwright(
    captcha_key: str,
    proxy: Optional[str],
    user_agent: str,
    cookies: Optional[Dict[str, str]],
) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={"server": proxy} if proxy else None,
        )

        context = await browser.new_context(
            user_agent=user_agent,
        )

        if cookies:
            await context.add_cookies(
                [
                    {
                        "name": k,
                        "value": v,
                        "domain": ".example.com",
                        "path": "/",
                    }
                    for k, v in cookies.items()
                ]
            )

        page = await context.new_page()

        html_path = TEMPLATES_DIR / "captcha.html"
        await page.goto(f"file://{html_path}")

        await page.evaluate(
            """
            (key) => {
                window.captchaKey = key;
            }
            """,
            captcha_key,
        )

        await page.wait_for_function(
            "window.captchaToken !== undefined",
            timeout=30_000,
        )

        token = await page.evaluate("window.captchaToken")

        await context.close()
        await browser.close()

        if not token:
            raise RuntimeError("captcha solve failed")

        return token


def solve_captcha(
    captcha_key: str,
    proxy: Optional[str],
    user_agent: str,
    cookies: Optional[Dict[str, str]],
) -> str:
    return asyncio.run(
        solve_captcha_with_playwright(
            captcha_key=captcha_key,
            proxy=proxy,
            user_agent=user_agent,
            cookies=cookies,
        )
    )
