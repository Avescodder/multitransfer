import asyncio
import time
from captcha_solver import solve_captcha
from qr_generator_race import QRGeneratorRace
from config import config


async def test_token_lifetime():
    from build_id_fetcher import get_build_id
    from http_client import AsyncHttpClient
    import random
    
    build_id = await get_build_id()
    if not build_id:
        print("Failed to get build_id")
        return
    
    client = AsyncHttpClient(proxy=config.PROXY)
    user_agent = random.choice(config.USER_AGENTS)
    
    response = await client.request(
        "GET",
        f"https://multitransfer.ru/_next/data/{build_id}/ru/transfer/таджикистан/sender-details.json",
        params={"country": "таджикистан"},
        headers={"User-Agent": user_agent}
    )
    
    await client.close()
    
    if response.status_code != 200:
        print("Failed to get captcha_key")
        return
    
    data = response.json()
    captcha_key = data.get("pageProps", {}).get("captcha_key")
    
    if not captcha_key:
        print("No captcha_key found")
        return
    
    print(f"\nCaptcha Key: {captcha_key}\n")
    
    token = await solve_captcha(captcha_key, priority=10)
    
    if not token:
        print("Failed to generate token")
        return
    
    print(f"Token generated: {token[:30]}")
    token_created_at = time.time()
    
    test_intervals = [
        10,
        15,
        20,
        30,
        45,
        60,    
        120,   
        180,   
        240,   
        300,   
        360,  
        420,   
        480,   
        540,   
        600,   
    ]
    
    last_valid_age = 0
    
    for interval in test_intervals:
        elapsed = time.time() - token_created_at
        wait_time = interval - elapsed
        
        if wait_time > 0:
            print(f"\nWaiting {wait_time:.0f}s")
            await asyncio.sleep(wait_time)
        
        token_age = time.time() - token_created_at
        print(f"\nTesting token (age: {token_age/60:.1f} minutes)")
        
        is_valid = await test_token_validity(token)
        
        if is_valid:
            print(f"Token still Valid after {token_age/60:.1f} minutes")
            last_valid_age = token_age
        else:
            print(f"Token Expired after {token_age/60:.1f} minutes")
            break
    
    print(f"Result: Token lifetime is approximately {last_valid_age/60:.1f} minutes")
    
    return int(last_valid_age)


async def test_token_validity(token: str) -> bool:
    try:
        generator = QRGeneratorRace(
            proxy=config.PROXY,
            amount=1000,
            card_number="5058270855938719",
            card_country="TJK",
            attempts=1
        )
        
        from http_client import AsyncHttpClient
        import random
        import uuid
        
        user_agent = random.choice(config.USER_AGENTS)
        client = AsyncHttpClient(proxy=config.PROXY)
        fhpsessionid = str(uuid.uuid4())
        
        commission_data = await generator._calc_commissions(
            client, user_agent, fhpsessionid
        )
        
        if not commission_data:
            await client.close()
            return False
        
        transfer_data = await generator._create_transfer(
            client, user_agent, fhpsessionid,
            commission_data, token  
        )
        
        await client.close()
        
        return transfer_data is not None
    
    except Exception as e:
        print(f"Error testing token: {e}")
        return False

if __name__ == '__main__':
    asyncio.run(test_token_lifetime())