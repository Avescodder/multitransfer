import asyncio
import time
from createQr import createQr


async def test_single():
    """Одиночный тест"""
    print("\n=== Single Request ===")
    
    start = time.time()
    
    try:
        result = await createQr(amount=1000)
        elapsed = time.time() - start
        
        if result.get("transfer_id"):
            print(f"OK: {result['transfer_id']} in {elapsed:.1f}s")
        else:
            print(f"FAIL: {result}")
            
    except Exception as e:
        elapsed = time.time() - start
        print(f"ERROR: {e} ({elapsed:.1f}s)")


async def test_sequential(n=3):
    """Последовательные тесты"""
    print(f"\n=== {n} Sequential Requests ===")
    
    results = []
    
    for i in range(n):
        print(f"\n[{i+1}/{n}]")
        start = time.time()
        
        try:
            result = await createQr(amount=1000 + i*100)
            elapsed = time.time() - start
            
            success = bool(result.get("transfer_id"))
            results.append({"success": success, "time": elapsed})
            
            print(f"{'OK' if success else 'FAIL'}: {elapsed:.1f}s")
            
        except Exception as e:
            elapsed = time.time() - start
            results.append({"success": False, "time": elapsed})
            print(f"ERROR: {e} ({elapsed:.1f}s)")
    
    success_count = sum(1 for r in results if r["success"])
    avg_time = sum(r["time"] for r in results) / len(results)
    
    print(f"\nResults: {success_count}/{n} success, avg {avg_time:.1f}s")


async def test_parallel(n=3):
    """Параллельные тесты"""
    print(f"\n=== {n} Parallel Requests ===")
    
    start = time.time()
    
    tasks = [createQr(amount=1000 + i*100) for i in range(n)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start
    
    success_count = 0
    for i, result in enumerate(results, 1):
        if isinstance(result, Exception):
            print(f"[{i}] ERROR: {result}")
        elif result.get("transfer_id"):
            print(f"[{i}] OK: {result['transfer_id']}")
            success_count += 1
        else:
            print(f"[{i}] FAIL")
    
    print(f"\nResults: {success_count}/{n} success in {elapsed:.1f}s")


async def main():
    choice = input("\nTest: 1=single, 2=sequential(3), 3=parallel(3), 4=all: ")
    
    if choice == "1":
        await test_single()
    elif choice == "2":
        await test_sequential(3)
    elif choice == "3":
        await test_parallel(3)
    elif choice == "4":
        await test_single()
        await test_sequential(3)
        await test_parallel(3)
    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())