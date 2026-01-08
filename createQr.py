import asyncio
import random
import dotenv
import uuid
import time
import os
from pathlib import Path
from datetime import datetime, timedelta

from playwright.async_api import async_playwright, Browser

from httpFlowRunner import FlowRunner, Step, ExtractRule
from config import config
from yamlManage import YamlManage
from config.config import CARD_COUNTRIES, DATES_PASSPORT

dotenv.load_dotenv()


class BrowserPool:
    _browser: Browser = None
    _playwright = None
    _lock = asyncio.Lock()
    
    @classmethod
    async def get_browser(cls):
        async with cls._lock:
            if cls._browser is None:
                cls._playwright = await async_playwright().start()
                cls._browser = await cls._playwright.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled']
                )
            return cls._browser
    
    @classmethod
    async def create_context(cls, proxy_host, proxy_port, proxy_user, proxy_pass, user_agent):
        browser = await cls.get_browser()
        return await browser.new_context(
            locale="ru-RU",
            timezone_id=random.choice(config.TIMEZONES),
            user_agent=user_agent,
            viewport={"width": random.choice(config.WIDTHS), "height": random.choice(config.HEIGHTS)},
            proxy={
                "server": f"http://{proxy_host}:{proxy_port}",
                "username": proxy_user,
                "password": proxy_pass
            }
        )

class CaptchaCache:
    _cache = {}
    _lock = asyncio.Lock()
    
    @classmethod
    async def get(cls, captcha_key):
        async with cls._lock:
            if captcha_key in cls._cache:
                token, expires = cls._cache[captcha_key]
                if datetime.now() < expires:
                    return token
                del cls._cache[captcha_key]
        return None
    
    @classmethod
    async def set(cls, captcha_key, token):
        async with cls._lock:
            expires = datetime.now() + timedelta(seconds=120)
            cls._cache[captcha_key] = (token, expires)


def write_captcha_html(captcha_key: str) -> None:
    with open("captcha/captcha.html", "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("__CAPTCHA_KEY__", captcha_key)
    with open("captcha/captcha_runtime.html", "w", encoding="utf-8") as f:
        f.write(html)


async def solve_captcha_fast(captcha_key, proxy_host, proxy_port, proxy_user, proxy_pass, user_agent):
    cached = await CaptchaCache.get(captcha_key)
    if cached:
        return cached
    
    t_start = time.perf_counter()
    
    html_path = Path("captcha/captcha_runtime.html").absolute()
    write_captcha_html(captcha_key)
    
    context = await BrowserPool.create_context(
        proxy_host, proxy_port, proxy_user, proxy_pass, user_agent
    )
    
    try:
        page = await context.new_page()
        
        await page.set_extra_http_headers({
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://multitransfer.ru/",
            "Origin": "https://multitransfer.ru",
        })
        
        async def route_handler(route):
            headers = route.request.headers.copy()
            headers["Referer"] = "https://multitransfer.ru/"
            headers["Origin"] = "https://multitransfer.ru"
            await route.continue_(headers=headers)
        
        await page.route("**/*", route_handler)
        await page.goto(f"file://{html_path}")
        await page.wait_for_selector(".smart-captcha", timeout=5_000)
        await page.click(".smart-captcha")
        
        event = asyncio.Event()
        result_data = {}
        checks_count = 0
        MAX_CHECKS = 2
        
        async def on_response(response):
            nonlocal checks_count
            if (response.url.startswith("https://smartcaptcha.cloud.yandex.ru/check") 
                and response.request.method == "POST"):
                checks_count += 1
                data = await response.json()
                
                if data.get("status") == "ok":
                    result_data.update(data)
                    event.set()
                elif checks_count >= MAX_CHECKS:
                    event.set()
        
        page.on("response", on_response)
        
        try:
            await asyncio.wait_for(event.wait(), timeout=30)
        except asyncio.TimeoutError:
            return None
        finally:
            try:
                page.remove_listener("response", on_response)
            except:
                pass
        
        token = result_data.get("spravka")
        
        elapsed = time.perf_counter() - t_start
        print(f"[Captcha] Решена за {elapsed:.1f}s")
        
        if token:
            await CaptchaCache.set(captcha_key, token)
        
        return token
        
    finally:
        await context.close()

async def createQr(amount: int, proxy: str = os.getenv('PROXY')):
    t_start = time.perf_counter()
    print(f"[0.0s] createQr (amount={amount})")
    
    user_agent = random.choice(config.USER_AGENTS)
    session_id = str(uuid.uuid4())
    
    runner = FlowRunner(
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
        },
        proxy=proxy,
    )
    
    runner.ctx["fhpsessionid"] = session_id
    
    country = CARD_COUNTRIES["TJK"]
    sender_details = YamlManage.get_path("api.link_details.sender_details")
    
    print(f"[{time.perf_counter() - t_start:.2f}s] 📡 Этап 1: Get captcha key")
    
    steps_init = [
        Step(
            name="Get captcha key",
            method="GET",
            url=f"https://multitransfer.ru/_next/data/{sender_details}/ru/transfer/tajikistan/sender-details.json",
            headers={"User-Agent": user_agent, "referer": "https://multitransfer.ru/"},
            params={"country": "tajikistan"},
            expect_status=200,
            extracts=[ExtractRule("captcha_key", "json", "pageProps.captcha_key")],
        ),
    ]
    
    runner.run(steps_init)
    
    if proxy and "@" in proxy:
        # http://user:pass@host:port
        parts = proxy.replace("http://", "").replace("https://", "").split("@")
        auth = parts[0].split(":")
        host_port = parts[1].split(":")
        proxy_user, proxy_pass = auth[0], auth[1]
        proxy_host, proxy_port = host_port[0], int(host_port[1])
    else:
        proxy_host = "proxy.example.com"
        proxy_port = 8080
        proxy_user = ""
        proxy_pass = ""
    
    captcha_token = await solve_captcha_fast(
        captcha_key=runner.ctx["captcha_key"],
        proxy_host=proxy_host,
        proxy_port=proxy_port,
        proxy_user=proxy_user,
        proxy_pass=proxy_pass,
        user_agent=user_agent
    )
    
    if not captcha_token:
        raise RuntimeError("Не удалось решить капчу")
    
    runner.ctx["captcha_token"] = captcha_token
    
    passport = random.choice(DATES_PASSPORT)
    
    steps_create = [
        Step(
            name="Calc fee",
            method="POST",
            url="https://api.multitransfer.ru/anonymous/multi/multitransfer-fee-calc/v3/commissions",
            headers={
                "client-id": "multitransfer-web-id",
                "fhpsessionid": session_id,
                "User-Agent": user_agent,
                "content-type": "application/json",
                "fhprequestid": str(uuid.uuid4()),
                "x-request-id": str(uuid.uuid4()),
            },
            json_body={
                "countryCode": country["countryCode"],
                "range": "ALL_PLUS_LIMITS",
                "money": {
                    "acceptedMoney": {
                        "amount": amount,
                        "currencyCode": country["currencyFrom"],
                    },
                    "withdrawMoney": {
                        "currencyCode": country["currencyTo"],
                    },
                },
            },
            expect_status=200,
            extracts=[
                ExtractRule("commission_id", "json", "fees.0.commissions.0.commissionId"),
                ExtractRule("payment_system_id", "json", "fees.0.commissions.0.paymentSystemId"),
            ],
        ),
        Step(
            name="Create transfer",
            method="POST",
            url="https://api.multitransfer.ru/anonymous/multi/multitransfer-transfer-create/v3/anonymous/transfers/create",
            headers={
                "client-id": "multitransfer-web-id",
                "content-type": "application/json",
                "fhpsessionid": session_id,
                "fhptokenid": "{{captcha_token}}",
                "fhprequestid": str(uuid.uuid4()),
                "x-request-id": str(uuid.uuid4()),
                "User-Agent": user_agent,
            },
            json_body={
                "transfer": {
                    "paymentSystemId": "{{payment_system_id}}",
                    "countryCode": "TJK",
                    "beneficiaryAccountNumber": "5058270855938719",
                    "commissionId": "{{commission_id}}",
                    "paymentInstrument": {"type": "ANONYMOUS_CARD"}
                },
                "sender": {
                    "lastName": random.choice(config.LAST_NAMES),
                    "firstName": random.choice(config.FIRST_NAMES),
                    "middleName": random.choice(config.MIDDLE_NAMES),
                    "birthDate": passport["birth_date"],
                    "phoneNumber": config.genPhone(),
                    "documents": [{
                        "type": "21",
                        "series": config.random_series(),
                        "number": config.random_number(),
                        "issueDate": passport["issue_date"],
                        "countryCode": "RUS",
                    }],
                },
            },
            expect_status=201,
            extracts=[ExtractRule("transfer_id", "json", "transferId")],
        ),
        Step(
            name="Confirm transfer (QR)",
            method="POST",
            url="https://api.multitransfer.ru/anonymous/multi/multitransfer-qr-processing/v3/anonymous/confirm",
            headers={
                "client-id": "multitransfer-web-id",
                "content-type": "application/json",
                "fhpsessionid": session_id,
                "fhprequestid": str(uuid.uuid4()),
                "x-request-id": str(uuid.uuid4()),
                "User-Agent": user_agent,
            },
            json_body={
                "transactionId": "{{transfer_id}}",
                "recordType": "transfer"
            },
            expect_status=200,
            extracts=[ExtractRule("qr_payload", "json", "externalData.payload")],
        ),
    ]
    
    runner.run(steps_create)
    runner.close()
    
    t3 = time.perf_counter()
    total = t3 - t_start

    print(f"Успех")
    print(f"TOTAL: {total:.2f}s")
    print(f"transfer_id: {runner.ctx.get('transfer_id')}")
    print(f"QR: {runner.ctx.get('qr_payload')}")
    
    return runner.ctx


async def test_parallel(n=3):
    print(f"\n=== {n} Parallel Requests ===\n")
    
    t_start = time.perf_counter()
    
    tasks = [createQr(amount=1000 + i*100) for i in range(n)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.perf_counter() - t_start
    
    success_count = 0
    for i, result in enumerate(results, 1):
        if isinstance(result, Exception):
            print(f"[{i}] ERROR: {result}")
        elif result.get("transfer_id"):
            print(f"[{i}] OK: {result['transfer_id']}")
            success_count += 1
        else:
            print(f"[{i}] FAIL")
    
    print(f"ИТОГ: {success_count}/{n} успешно за {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(test_parallel(3))