import asyncio
import time
from config import config
from qr_generator_race import generate_qr_race
from captcha_token_pool import CaptchaTokenPool


async def main():
    token_pool = CaptchaTokenPool(
        redis_url=config.REDIS_URL,
        pool_size=config.TOKEN_POOL_SIZE,
        token_lifetime=config.TOKEN_LIFETIME,
        captcha_key="<будет получен автоматически>"  # TODO: получать динамически
    )
    
    try:
        await token_pool.connect()
        
        await token_pool.start_generator()
        
        await asyncio.sleep(10)
        
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
        
        print(f"Total time: {elapsed:.2f} seconds")
        
        if result:
            print(f"Transfer ID: {result['transfer_id']}")
            print(f"Transfer Num: {result['transfer_num']}")
            print(f"QR Payload: {result.get('qr_payload', 'N/A')}")
        else:
            print("Failed")
        
        pool_size = await token_pool.get_pool_size()
        print(f"\nToken pool size: {pool_size}/{config.TOKEN_POOL_SIZE}")
    
    finally:
        await token_pool.stop_generator()
        await token_pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())