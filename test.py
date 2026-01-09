import asyncio
import time
import multiprocessing as mp
from qr_api import create_qr, create_qr_batch
from qr_multiprocess import create_qr_batch_multiprocess


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
        
        print(f"✓ {elapsed:.1f}s")
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


async def test_multiprocess(n=10, workers=3):
    print(f"\n[Multiprocess {n} QRs / {workers} workers]")
    
    start = time.time()
    amounts = [1000 + i*100 for i in range(n)]
    
    results = await create_qr_batch_multiprocess(amounts, num_workers=workers)
    
    elapsed = time.time() - start
    success = sum(1 for r in results if r['success'])
    
    print(f"✓ {elapsed:.1f}s")
    print(f"  Success: {success}/{n}")
    
    for r in results:
        if r['success']:
            print(f"  #{r['task_id']+1} [W{r['worker_id']}]: {r['transfer_id']}")
            print(f"       {r['qr_payload']}")
        else:
            print(f"  #{r['task_id']+1} [W{r['worker_id']}]: FAILED - {r['error']}")


async def main():
    print("QR Generation Tests")
    print("=" * 50)
    
    choice = input("\n1=Single | 2=Batch | 3=Multiprocess | 4=All: ")
    
    if choice == "1":
        await test_single()
    elif choice == "2":
        await test_batch(3)
    elif choice == "3":
        n = int(input("QRs: ") or "10")
        w = int(input("Workers: ") or "3")
        await test_multiprocess(n, w)
    elif choice == "4":
        await test_single()
        await test_batch(3)
        await test_multiprocess(10, 3)
    else:
        print("Invalid")


if __name__ == "__main__":
    mp.set_start_method('spawn', force=True)
    asyncio.run(main())