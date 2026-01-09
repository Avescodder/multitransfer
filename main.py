import asyncio
from config import config
from typing import List, Dict, Any
from qr_generator import create_qr


async def generate_qr_batch(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = await asyncio.gather(*[
        create_qr(
            amount=task["amount"],
            card_number=task["card_number"],
            card_country=task.get("card_country", "TJK"),
            proxy=config.PROXY
        )
        for task in tasks
    ], return_exceptions=True)
    
    processed_results = []
    for result in results:
        if isinstance(result, Exception):
            processed_results.append({"error": str(result), "success": False})
        elif result is None:
            processed_results.append({"error": "Generation failed", "success": False})
        else:
            processed_results.append({**result, "success": True})
    
    return processed_results


async def main():
    tasks = [
        {"amount": 1000, "card_number": "5058270855938719"},
        {"amount": 1500, "card_number": "5058270855938719"},
        {"amount": 2000, "card_number": "5058270855938719"}
    ]
    
    results = await generate_qr_batch(tasks)
    
    for i, result in enumerate(results, 1):
        print(f"\nTask {i}:")
        if result.get("success"):
            print(f"  Transfer ID: {result['transfer_id']}")
            print(f"  Transfer Num: {result['transfer_num']}")
            qr_payload = result.get('qr_payload')
            print(f"  QR Payload: {qr_payload}" if qr_payload else "  QR Payload: None")
        else:
            print(f"  Failed: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())