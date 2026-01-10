import asyncio
import time
from config import config
from qr_generator_race import generate_qr_race


async def main():
    proxy = config.PROXY
    amount = 1000
    card_number = "5058270855938719"
    card_country = "TJK"
    attempts = 3 
    
    print(f"Starting QR generation with {attempts} parallel attempts")
    
    start_time = time.time()
    
    result = await generate_qr_race(
        proxy=proxy,
        amount=amount,
        card_number=card_number,
        card_country=card_country,
        attempts=attempts
    )
    
    elapsed = time.time() - start_time
    
    print(f"Total time: {elapsed:.2f} seconds")
    
    if result:
        print(f"Transfer ID: {result['transfer_id']}")
        print(f"Transfer Num: {result['transfer_num']}")
        print(f"QR Payload: {result.get('qr_payload', 'N/A')}")
    else:
        print(f"Failed all. {attempts} attempts unsuccessful")


if __name__ == "__main__":
    asyncio.run(main())