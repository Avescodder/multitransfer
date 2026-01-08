from typing import Optional
import asyncio
import httpx
import time


async def solve_captcha_with_playwright(
    captcha_key: str,
    proxy: Optional[str],
    user_agent: str,
    cookies: Optional[dict],
    rucaptcha_api_key: str,
) -> str:
    
    if not rucaptcha_api_key:
        raise ValueError("RuCaptcha API key required")
    
    start = time.time()
    
    async with httpx.AsyncClient(timeout=120) as client:
        
        resp = await client.post(
            "https://rucaptcha.com/in.php",
            data={
                "key": rucaptcha_api_key,
                "method": "yandex",
                "sitekey": captcha_key,
                "pageurl": "https://multitransfer.ru",
                "json": 1,
            }
        )
        
        result = resp.json()
        
        if result.get("status") != 1:
            raise RuntimeError(f"RuCaptcha submit failed: {result.get('request')}")
        
        captcha_id = result["request"]
        
        wait_times = [2] * 3 + [3] * 37  # 6s + 111s = 117s total
        
        for i, wait in enumerate(wait_times):
            await asyncio.sleep(wait)
            
            resp = await client.get(
                "https://rucaptcha.com/res.php",
                params={
                    "key": rucaptcha_api_key,
                    "action": "get",
                    "id": captcha_id,
                    "json": 1
                }
            )
            
            result = resp.json()
            
            if result.get("status") == 1:
                elapsed = time.time() - start
                print(f"[Captcha] Solved in {elapsed:.1f}s")
                return result["request"]
            
            if result.get("request") == "CAPCHA_NOT_READY":
                continue
            
            raise RuntimeError(f"RuCaptcha error: {result.get('request')}")
        
        raise RuntimeError("RuCaptcha timeout (120s)")


def solve_captcha(
    captcha_key: str,
    proxy: Optional[str],
    user_agent: str,
    cookies: Optional[dict],
    rucaptcha_api_key: str,
) -> str:
    """Синхронная обёртка"""
    return asyncio.run(
        solve_captcha_with_playwright(
            captcha_key=captcha_key,
            proxy=proxy,
            user_agent=user_agent,
            cookies=cookies,
            rucaptcha_api_key=rucaptcha_api_key,
        )
    )