import asyncio
from config import config
from qr_pool import QRGeneratorPool


async def main():
    tasks = [
        {"amount": 1000, "card_number": "5058270855938719"},
        {"amount": 1500, "card_number": "5058270855938719"},
        {"amount": 2000, "card_number": "5058270855938719"},
        {"amount": 2500, "card_number": "5058270855938719"},
        {"amount": 3000, "card_number": "5058270855938719"},
    ]
    
    pool = QRGeneratorPool(
        proxy=config.PROXY,
        max_concurrent=10  
    )
    
    try:
        results = await pool.generate_batch(tasks)
        
        for i, result in enumerate(results, 1):
            print(f"Task {i}:")
            if result.get("success"):
                print(f"  Transfer ID: {result['transfer_id']}")
                print(f"  Transfer Num: {result['transfer_num']}")
                qr_payload = result.get('qr_payload')
                print(f"  QR Payload: {qr_payload}" if qr_payload else "  QR Payload: None")
            else:
                print(f"  Failed: {result.get('error', 'Unknown error')}")
            print()
    
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())