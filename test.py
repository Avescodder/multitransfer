import asyncio
import time
from qr_api import create_qr, create_qr_batch


async def test_single():
    print("\n[Single QR]")
    
    start = time.time()
    try:
        result = await create_qr(1000)
        elapsed = time.time() - start
        
        print(f"✓ {elapsed:.1f}s")
        print(f"  ID: {result['transfer_id']}")
        print(f"  QR: {result['qr_payload']}")
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"✗ {elapsed:.1f}s: {e}")


async def test_batch(n=3):
    print(f"\n[Batch {n} QRs]")
    
    start = time.time()
    amounts = [1000 + i*100 for i in range(n)]
    
    try:
        results = await create_qr_batch(amounts, max_concurrent=2)
        elapsed = time.time() - start
        
        success = sum(1 for r in results if r.success)
        avg = sum(r.duration for r in results) / len(results)
        
        print(f"✓ {elapsed:.1f}s total, {avg:.1f}s avg")
        print(f"  Success: {success}/{n}")
        
        for i, r in enumerate(results, 1):
            if r.success:
                print(f"  #{i}: {r.transfer_id}")
                print(f"       {r.qr_payload}")
            else:
                print(f"  #{i}: FAILED - {r.error}")
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"✗ {elapsed:.1f}s: {e}")


async def main():
    print("QR Generation Tests")
    print("=" * 50)
    
    choice = input("\n1=Single | 2=Batch | 3=Both: ")
    
    if choice == "1":
        await test_single()
    elif choice == "2":
        await test_batch(3)
    elif choice == "3":
        await test_single()
        await test_batch(3)
    else:
        print("Invalid")


if __name__ == "__main__":
    asyncio.run(main())