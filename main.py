import asyncio
import time
from config import config
from qr_generator_race import generate_qr_race
from captcha_token_pool import CaptchaTokenPool
from build_id_fetcher import get_build_id
import httpx
import random


async def get_captcha_key() -> str:
    build_id = await get_build_id()
    if not build_id:
        raise RuntimeError("Failed to get build_id")
    
    user_agent = random.choice(config.USER_AGENTS)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://multitransfer.ru/_next/data/{build_id}/ru/transfer/tajikistan/sender-details.json",
            params={"country": "tajikistan"},
            headers={"User-Agent": user_agent}
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Failed to get captcha_key: {response.status_code}")
        
        data = response.json()
        captcha_key = data.get("pageProps", {}).get("captcha_key")
        
        if not captcha_key:
            raise RuntimeError("No captcha_key in response")
        
        return captcha_key


async def main():
    print("[Main] Getting captcha_key...")
    captcha_key = await get_captcha_key()
    print(f"[Main] Captcha key: {captcha_key}")
    
    token_pool = CaptchaTokenPool(
        redis_url=config.REDIS_URL,
        pool_size=config.TOKEN_POOL_SIZE,
        token_lifetime=config.TOKEN_LIFETIME,
        captcha_key=captcha_key
    )
    
    try:
        await token_pool.connect()
        await token_pool.start_generator()
        
        print("[Main] Waiting 10s for tokens to generate...")
        await asyncio.sleep(10)
        
        pool_size = await token_pool.get_pool_size()
        print(f"[Main] Token pool size: {pool_size}/{config.TOKEN_POOL_SIZE}")
        
        proxy = config.PROXY
        amount = 1000
        card_number = "5058270855938719"
        card_country = "TJK"
        attempts = 3
        
        start_time = time.time()
        
        result = await generate_qr_race(
            proxy=proxy,
            amount=amount,
            card_number=card_number,
            card_country=card_country,
            attempts=attempts,
            token_pool=token_pool
        )
        
        elapsed = time.time() - start_time
        
        print(f"\n[Main] Total time: {elapsed:.2f}s")
        
        if result:
            print(f"[Main] Transfer ID: {result['transfer_id']}")
            print(f"[Main] Transfer Num: {result['transfer_num']}")
            print(f"[Main] QR Payload: {result.get('qr_payload', 'N/A')}")
        else:
            print("[Main] Failed")
        
        final_pool_size = await token_pool.get_pool_size()
        print(f"\n[Main] Final token pool size: {final_pool_size}/{config.TOKEN_POOL_SIZE}")
    
    finally:
        await token_pool.stop_generator()
        await token_pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())