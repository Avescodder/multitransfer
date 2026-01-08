"""
Решение Yandex SmartCaptcha через rucaptcha.com
Чисто, быстро, стабильно
"""

from typing import Optional, Dict
import asyncio
import httpx
import time


async def solve_captcha_with_playwright(
    captcha_key: str,
    proxy: Optional[str],
    user_agent: str,
    cookies: Optional[Dict[str, str]],
    rucaptcha_api_key: str,
) -> str:
    """
    Решает капчу через rucaptcha.com с максимальным приоритетом
    
    Args:
        captcha_key: Ключ Yandex SmartCaptcha
        proxy: Прокси (не используется, но оставлен для совместимости)
        user_agent: User-Agent (не используется)
        cookies: Cookies (не используются)
        rucaptcha_api_key: API ключ от rucaptcha.com
        
    Returns:
        Токен капчи
    """
    
    if not rucaptcha_api_key:
        raise ValueError("RuCaptcha API key is required!")
    
    print(f"\n{'='*60}")
    print(f"[RuCaptcha] Отправка капчи на решение (PRIORITY)")
    print(f"{'='*60}")
    
    start = time.time()
    
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            
            # Шаг 1: Отправляем капчу на решение
            print(f"[RuCaptcha] Отправка задачи...")
            
            resp = await client.post(
                "https://rucaptcha.com/in.php",  # ← RuCaptcha URL
                data={
                    "key": rucaptcha_api_key,
                    "method": "yandex",
                    "sitekey": captcha_key,
                    "pageurl": "https://multitransfer.ru",
                    "json": 1,
                    "pingback": 0,  # Без callback
                }
            )
            
            result = resp.json()
            
            if result.get("status") != 1:
                error_msg = result.get("request", "Unknown error")
                print(f"[RuCaptcha] ❌ Ошибка отправки: {error_msg}")
                raise RuntimeError(f"RuCaptcha submission failed: {error_msg}")
            
            captcha_id = result["request"]
            print(f"[RuCaptcha] ✅ Задача отправлена, ID: {captcha_id}")
            
            # Шаг 2: Ожидаем решения (проверяем каждые 3 секунды)
            print(f"[RuCaptcha] Ожидание решения...")
            
            for attempt in range(40):  # Макс 120 секунд (40 * 3)
                await asyncio.sleep(3)
                
                resp = await client.get(
                    "https://rucaptcha.com/res.php",  # ← RuCaptcha URL
                    params={
                        "key": rucaptcha_api_key,
                        "action": "get",
                        "id": captcha_id,
                        "json": 1
                    }
                )
                
                result = resp.json()
                elapsed = time.time() - start
                
                # Капча решена!
                if result.get("status") == 1:
                    token = result["request"]
                    
                    print(f"\n{'='*60}")
                    print(f"[RuCaptcha] ✅ РЕШЕНО за {elapsed:.1f} секунд!")
                    print(f"[RuCaptcha] Token: {token[:50]}...")
                    print(f"{'='*60}\n")
                    
                    return token
                
                # Ещё не готово
                if result.get("request") == "CAPCHA_NOT_READY":
                    print(f"[RuCaptcha] Попытка {attempt + 1}/40 ({elapsed:.1f}с)...")
                    continue
                
                # Ошибка решения
                error_msg = result.get("request", "Unknown error")
                print(f"[RuCaptcha] ❌ Ошибка решения: {error_msg}")
                raise RuntimeError(f"RuCaptcha solve failed: {error_msg}")
            
            # Timeout
            print(f"[RuCaptcha] ⚠️ Timeout 120 секунд")
            raise RuntimeError("RuCaptcha timeout")
            
    except httpx.HTTPError as e:
        print(f"[RuCaptcha] ❌ HTTP ошибка: {e}")
        raise RuntimeError(f"RuCaptcha HTTP error: {e}")
    
    except Exception as e:
        print(f"[RuCaptcha] ❌ Исключение: {e}")
        raise


def solve_captcha(
    captcha_key: str,
    proxy: Optional[str],
    user_agent: str,
    cookies: Optional[Dict[str, str]],
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