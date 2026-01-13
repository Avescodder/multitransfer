# ============================================
# Файл: test_token_advanced.py (НОВЫЙ)
# ============================================

import asyncio
import time
import uuid
import random
import httpx
from typing import Optional

from captcha_solver import solve_captcha
from config import config
from http_client import generate_headers


async def test_scenario_1_same_ip():
    """
    СЦЕНАРИЙ 1: Та же прокси (тот же IP)
    Гипотеза: Токен привязан к IP, живет дольше при том же IP
    """
    print("\n" + "="*70)
    print("SCENARIO 1: SAME IP (Same Proxy)")
    print("="*70)
    
    token = await generate_token()
    if not token:
        return
    
    token_created_at = time.time()
    
    # Тестируем с ТОЙ ЖЕ прокси
    intervals = [10, 20, 30, 45, 60, 90, 120, 150, 180]
    last_valid = 0
    
    for interval in intervals:
        elapsed = time.time() - token_created_at
        wait_time = interval - elapsed
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        age = time.time() - token_created_at
        print(f"\n🧪 Test at {age:.0f}s (same proxy={config.PROXY[:30]}...)")
        
        is_valid = await test_token_new_session(
            token,
            proxy=config.PROXY  # ← ТА ЖЕ ПРОКСИ
        )
        
        if is_valid:
            print(f"   ✅ VALID after {age:.0f}s")
            last_valid = age
        else:
            print(f"   ❌ EXPIRED after {age:.0f}s")
            break
    
    print(f"\n📊 Result (Same IP): {last_valid:.0f}s")
    return last_valid


async def test_scenario_2_slow_usage():
    """
    СЦЕНАРИЙ 2: Медленное использование
    Гипотеза: Быстрое использование триггерит защиту
    """
    print("\n" + "="*70)
    print("SCENARIO 2: SLOW USAGE (Wait 60s before first test)")
    print("="*70)
    
    token = await generate_token()
    if not token:
        return
    
    token_created_at = time.time()
    
    # ЖДЕМ 60 секунд перед первым тестом
    print("\n⏳ Waiting 60s before first test (avoiding timing detection)...")
    await asyncio.sleep(60)
    
    # Тестируем
    intervals = [60, 90, 120, 150, 180, 210, 240]
    last_valid = 0
    
    for interval in intervals:
        elapsed = time.time() - token_created_at
        wait_time = interval - elapsed
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        age = time.time() - token_created_at
        print(f"\n🧪 Test at {age:.0f}s (slow usage)")
        
        is_valid = await test_token_new_session(token)
        
        if is_valid:
            print(f"   ✅ VALID after {age:.0f}s")
            last_valid = age
        else:
            print(f"   ❌ EXPIRED after {age:.0f}s")
            break
    
    print(f"\n📊 Result (Slow Usage): {last_valid:.0f}s")
    return last_valid


async def test_scenario_3_same_useragent():
    """
    СЦЕНАРИЙ 3: Тот же User-Agent
    Гипотеза: Токен привязан к User-Agent
    """
    print("\n" + "="*70)
    print("SCENARIO 3: SAME USER-AGENT")
    print("="*70)
    
    # Генерируем токен с определенным UA
    fixed_ua = random.choice(config.USER_AGENTS)
    print(f"📌 Fixed UA: {fixed_ua[:50]}...")
    
    token = await generate_token(user_agent=fixed_ua)
    if not token:
        return
    
    token_created_at = time.time()
    
    # Тестируем с ТЕМ ЖЕ UA
    intervals = [10, 20, 30, 45, 60, 90, 120, 150, 180]
    last_valid = 0
    
    for interval in intervals:
        elapsed = time.time() - token_created_at
        wait_time = interval - elapsed
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        age = time.time() - token_created_at
        print(f"\n🧪 Test at {age:.0f}s (same UA)")
        
        is_valid = await test_token_new_session(
            token,
            user_agent=fixed_ua  # ← ТОТ ЖЕ UA
        )
        
        if is_valid:
            print(f"   ✅ VALID after {age:.0f}s")
            last_valid = age
        else:
            print(f"   ❌ EXPIRED after {age:.0f}s")
            break
    
    print(f"\n📊 Result (Same UA): {last_valid:.0f}s")
    return last_valid


async def test_scenario_4_combined():
    """
    СЦЕНАРИЙ 4: Комбинированный (Same IP + Same UA + Slow)
    Гипотеза: Комбинация факторов дает максимальный lifetime
    """
    print("\n" + "="*70)
    print("SCENARIO 4: COMBINED (Same IP + Same UA + Slow)")
    print("="*70)
    
    fixed_ua = random.choice(config.USER_AGENTS)
    print(f"📌 Fixed UA: {fixed_ua[:50]}...")
    print(f"📌 Fixed Proxy: {config.PROXY[:30]}...")
    
    token = await generate_token(user_agent=fixed_ua)
    if not token:
        return
    
    token_created_at = time.time()
    
    # Ждем 30 сек перед первым тестом
    print("\n⏳ Waiting 30s before first test...")
    await asyncio.sleep(30)
    
    intervals = [30, 60, 90, 120, 150, 180, 210, 240]
    last_valid = 0
    
    for interval in intervals:
        elapsed = time.time() - token_created_at
        wait_time = interval - elapsed
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        age = time.time() - token_created_at
        print(f"\n🧪 Test at {age:.0f}s (combined)")
        
        is_valid = await test_token_new_session(
            token,
            proxy=config.PROXY,
            user_agent=fixed_ua
        )
        
        if is_valid:
            print(f"   ✅ VALID after {age:.0f}s")
            last_valid = age
        else:
            print(f"   ❌ EXPIRED after {age:.0f}s")
            break
    
    print(f"\n📊 Result (Combined): {last_valid:.0f}s")
    return last_valid


# ============================================
# Helper functions
# ============================================

async def generate_token(user_agent: Optional[str] = None) -> Optional[str]:
    """Сгенерировать токен капчи"""
    from build_id_fetcher import get_build_id
    
    build_id = await get_build_id()
    if not build_id:
        print("❌ Failed to get build_id")
        return None
    
    ua = user_agent or random.choice(config.USER_AGENTS)
    
    async with httpx.AsyncClient(proxy=config.PROXY, timeout=30.0) as client:
        response = await client.get(
            f"https://multitransfer.ru/_next/data/{build_id}/ru/transfer/таджикистан/sender-details.json",
            params={"country": "таджикистан"},
            headers={"User-Agent": ua}
        )
        
        if response.status_code != 200:
            print("❌ Failed to get captcha_key")
            return None
        
        data = response.json()
        captcha_key = data.get("pageProps", {}).get("captcha_key")
        
        if not captcha_key:
            print("❌ No captcha_key found")
            return None
    
    print(f"\n🔄 Solving captcha (UA: {ua[:40]}...)...")
    token = await solve_captcha(captcha_key, priority=10)
    
    if not token:
        print("❌ Failed to generate token")
        return None
    
    print(f"✅ Token: {token[:30]}...")
    return token


async def test_token_new_session(
    token: str,
    proxy: Optional[str] = None,
    user_agent: Optional[str] = None
) -> bool:
    """Протестировать токен в новой сессии"""
    
    # Используем переданные параметры или генерируем новые
    test_proxy = proxy or config.PROXY
    test_ua = user_agent or random.choice(config.USER_AGENTS)
    test_fhpsessionid = str(uuid.uuid4())
    
    try:
        async with httpx.AsyncClient(
            proxy=test_proxy,
            timeout=60.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            transport=httpx.AsyncHTTPTransport(retries=0)
        ) as client:
            # Calc commissions
            country_data = config.CARD_COUNTRIES["TJK"]
            headers = generate_headers(test_ua, test_fhpsessionid)
            
            response = await client.post(
                "https://api.multitransfer.ru/anonymous/multi/multitransfer-fee-calc/v3/commissions",
                headers=headers,
                json={
                    "countryCode": country_data["countryCode"],
                    "range": "ALL_PLUS_LIMITS",
                    "money": {
                        "acceptedMoney": {
                            "amount": 1000,
                            "currencyCode": country_data["currencyFrom"]
                        },
                        "withdrawMoney": {
                            "currencyCode": country_data["currencyTo"]
                        }
                    }
                }
            )
            
            if response.status_code != 200:
                return False
            
            data = response.json()
            fees = data.get("fees", [])
            if not fees or not fees[0].get("commissions"):
                return False
            
            commission = fees[0]["commissions"][0]
            
            # Create transfer with token
            passport = random.choice(config.PASSPORT_DATES)
            transfer_headers = generate_headers(test_ua, test_fhpsessionid)
            transfer_headers["Fhptokenid"] = token
            
            response = await client.post(
                "https://api.multitransfer.ru/anonymous/multi/multitransfer-transfer-create/v3/anonymous/transfers/create",
                headers=transfer_headers,
                json={
                    "transfer": {
                        "service_name": "multitransfer",
                        "paymentSystemId": commission["paymentSystemId"],
                        "countryCode": country_data["countryCode"],
                        "beneficiaryAccountNumber": "5058270855938719",
                        "commissionId": commission["commissionId"],
                        "paymentInstrument": {"type": "ANONYMOUS_CARD"}
                    },
                    "sender": {
                        "lastName": random.choice(config.LAST_NAMES),
                        "firstName": random.choice(config.FIRST_NAMES),
                        "middleName": random.choice(config.MIDDLE_NAMES),
                        "birthDate": passport["date_birth"],
                        "phoneNumber": config.genPhone(),
                        "documents": [{
                            "type": "21",
                            "series": config.random_series(),
                            "number": config.random_number(),
                            "issueDate": passport["date_issue"],
                            "countryCode": "RUS"
                        }]
                    }
                }
            )
            
            if response.status_code == 201:
                return True
            elif response.status_code == 402:
                return False
            else:
                # Другие ошибки не связаны с токеном
                return True
    
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
        return False


async def main():
    """Запустить все сценарии"""
    print("\n" + "="*70)
    print("ADVANCED TOKEN LIFETIME TESTING")
    print("Testing different scenarios to find maximum lifetime")
    print("="*70)
    
    results = {}
    
    # Сценарий 1: Same IP
    try:
        results["same_ip"] = await test_scenario_1_same_ip()
    except Exception as e:
        print(f"\n❌ Scenario 1 failed: {e}")
        results["same_ip"] = 0
    
    await asyncio.sleep(5)
    
    # Сценарий 2: Slow usage
    try:
        results["slow_usage"] = await test_scenario_2_slow_usage()
    except Exception as e:
        print(f"\n❌ Scenario 2 failed: {e}")
        results["slow_usage"] = 0
    
    await asyncio.sleep(5)
    
    # Сценарий 3: Same UA
    try:
        results["same_ua"] = await test_scenario_3_same_useragent()
    except Exception as e:
        print(f"\n❌ Scenario 3 failed: {e}")
        results["same_ua"] = 0
    
    await asyncio.sleep(5)
    
    # Сценарий 4: Combined
    try:
        results["combined"] = await test_scenario_4_combined()
    except Exception as e:
        print(f"\n❌ Scenario 4 failed: {e}")
        results["combined"] = 0
    
    # Итоги
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    
    for scenario, lifetime in results.items():
        print(f"{scenario:15s}: {lifetime:6.0f}s ({lifetime/60:5.1f} min)")
    
    max_lifetime = max(results.values())
    best_scenario = max(results, key=results.get)
    
    print("\n" + "="*70)
    print(f"🏆 Best scenario: {best_scenario}")
    print(f"📊 Maximum lifetime: {max_lifetime:.0f}s ({max_lifetime/60:.1f} min)")
    print(f"📊 Recommended TOKEN_LIFETIME: {int(max_lifetime * 0.8)}s")
    print("="*70)


if __name__ == '__main__':
    asyncio.run(main())