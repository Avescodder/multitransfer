import asyncio
import time
import os
from typing import List
from qr_api import create_qr, create_qr_batch
from qr_core import ProxyPool


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)


def print_result(result, index: int = None):
    """Print formatted result."""
    prefix = f"  #{index}: " if index else "  "
    
    if hasattr(result, 'success'):
        # QRResult object
        if result.success:
            print(f"{prefix}✓ SUCCESS ({result.duration:.2f}s, {result.attempts} attempts)")
            print(f"       ID: {result.transfer_id}")
            print(f"       QR: {result.qr_payload[:50]}...")
            if result.proxy_used:
                print(f"       Proxy: {result.proxy_used[:30]}...")
        else:
            print(f"{prefix}✗ FAILED ({result.duration:.2f}s)")
            print(f"       Error: {result.error}")
    else:
        # Dict result
        print(f"{prefix}✓ SUCCESS ({result['duration']:.2f}s, {result['attempts']} attempts)")
        print(f"       ID: {result['transfer_id']}")
        print(f"       QR: {result['qr_payload'][:50]}...")


async def test_single():
    """Test single QR generation."""
    print_header("Test 1: Single QR Generation")
    
    start = time.time()
    try:
        result = await create_qr(1000)
        elapsed = time.time() - start
        
        print(f"\n  Total time: {elapsed:.2f}s")
        print_result(result)
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n  ✗ FAILED ({elapsed:.2f}s)")
        print(f"  Error: {e}")


async def test_batch(n: int = 3):
    """Test batch QR generation."""
    print_header(f"Test 2: Batch Generation ({n} QRs)")
    
    amounts = [1000 + i*100 for i in range(n)]
    
    start = time.time()
    try:
        results = await create_qr_batch(amounts, max_concurrent=2)
        elapsed = time.time() - start
        
        success_count = sum(1 for r in results if r.success)
        avg_time = sum(r.duration for r in results) / len(results)
        
        print(f"\n  Total time: {elapsed:.2f}s")
        print(f"  Success: {success_count}/{n}")
        print(f"  Avg per QR: {avg_time:.2f}s")
        print(f"\n  Results:")
        
        for i, r in enumerate(results, 1):
            print_result(r, i)
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n  ✗ FAILED ({elapsed:.2f}s)")
        print(f"  Error: {e}")


async def test_with_proxies(n: int = 5):
    """Test with proxy rotation."""
    print_header(f"Test 3: Proxy Rotation ({n} QRs)")
    
    # Load proxies from environment
    proxy_list_str = os.getenv('PROXY_LIST', '')
    
    if not proxy_list_str:
        print("\n  ⚠ SKIPPED: No PROXY_LIST in .env")
        print("  Add PROXY_LIST='proxy1,proxy2,proxy3' to test")
        return
    
    proxies = [p.strip() for p in proxy_list_str.split(',')]
    print(f"\n  Using {len(proxies)} proxies")
    
    amounts = [1000 + i*100 for i in range(n)]
    
    start = time.time()
    try:
        results = await create_qr_batch(
            amounts,
            max_concurrent=2,
            proxies=proxies
        )
        elapsed = time.time() - start
        
        success_count = sum(1 for r in results if r.success)
        avg_time = sum(r.duration for r in results) / len(results)
        
        # Proxy usage stats
        proxy_usage = {}
        for r in results:
            if r.proxy_used:
                proxy_key = r.proxy_used[:30] + "..."
                proxy_usage[proxy_key] = proxy_usage.get(proxy_key, 0) + 1
        
        print(f"\n  Total time: {elapsed:.2f}s")
        print(f"  Success: {success_count}/{n}")
        print(f"  Avg per QR: {avg_time:.2f}s")
        
        if proxy_usage:
            print(f"\n  Proxy usage:")
            for proxy, count in proxy_usage.items():
                print(f"    {proxy}: {count} requests")
        
        print(f"\n  Results:")
        for i, r in enumerate(results, 1):
            print_result(r, i)
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n  ✗ FAILED ({elapsed:.2f}s)")
        print(f"  Error: {e}")


async def test_stress(n: int = 10, concurrent: int = 3):
    """Stress test with many concurrent requests."""
    print_header(f"Test 4: Stress Test ({n} QRs, {concurrent} concurrent)")
    
    amounts = [1000 + i*50 for i in range(n)]
    
    start = time.time()
    try:
        results = await create_qr_batch(amounts, max_concurrent=concurrent)
        elapsed = time.time() - start
        
        success_count = sum(1 for r in results if r.success)
        failed_count = n - success_count
        avg_time = sum(r.duration for r in results) / len(results)
        
        # Error analysis
        errors = {}
        for r in results:
            if not r.success:
                errors[r.error] = errors.get(r.error, 0) + 1
        
        print(f"\n  Total time: {elapsed:.2f}s")
        print(f"  Throughput: {n/elapsed:.2f} QR/s")
        print(f"  Success: {success_count}/{n} ({success_count/n*100:.1f}%)")
        print(f"  Failed: {failed_count}/{n}")
        print(f"  Avg per QR: {avg_time:.2f}s")
        
        if errors:
            print(f"\n  Error breakdown:")
            for error, count in sorted(errors.items(), key=lambda x: x[1], reverse=True):
                print(f"    {error[:50]}: {count}")
        
        # Show only first 3 and last 3 results
        print(f"\n  Sample results (first 3):")
        for i, r in enumerate(results[:3], 1):
            print_result(r, i)
        
        if n > 6:
            print(f"\n  Sample results (last 3):")
            for i, r in enumerate(results[-3:], n-2):
                print_result(r, i)
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n  ✗ FAILED ({elapsed:.2f}s)")
        print(f"  Error: {e}")


async def test_performance_target():
    """Test if meets 10 second requirement."""
    print_header("Test 5: Performance Target (<10s)")
    
    print(f"\n  Target: Generate QR in under 10 seconds")
    print(f"  Running 5 attempts...\n")
    
    times = []
    
    for i in range(5):
        start = time.time()
        try:
            result = await create_qr(1000 + i*100)
            elapsed = time.time() - start
            times.append(elapsed)
            
            status = "✓" if elapsed < 10 else "✗"
            print(f"  Attempt {i+1}: {status} {elapsed:.2f}s")
            
        except Exception as e:
            print(f"  Attempt {i+1}: ✗ FAILED - {e}")
    
    if times:
        avg = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)
        
        print(f"\n  Statistics:")
        print(f"    Avg: {avg:.2f}s")
        print(f"    Min: {min_time:.2f}s")
        print(f"    Max: {max_time:.2f}s")
        
        if max_time < 10:
            print(f"\n  ✓ PASSED: All attempts under 10 seconds")
        else:
            print(f"\n  ✗ FAILED: Some attempts exceeded 10 seconds")


async def main():
    """Main test runner."""
    print("\n" + "="*60)
    print("  QR Generation - Production Test Suite")
    print("="*60)
    
    print("\nSelect test:")
    print("  1. Single QR")
    print("  2. Batch (3 QRs)")
    print("  3. Proxy Rotation (5 QRs)")
    print("  4. Stress Test (10 QRs)")
    print("  5. Performance Target")
    print("  6. Run All Tests")
    
    choice = input("\nChoice (1-6): ").strip()
    
    if choice == "1":
        await test_single()
    elif choice == "2":
        await test_batch(3)
    elif choice == "3":
        await test_with_proxies(5)
    elif choice == "4":
        n = input("Number of QRs (default 10): ").strip()
        n = int(n) if n else 10
        await test_stress(n, concurrent=3)
    elif choice == "5":
        await test_performance_target()
    elif choice == "6":
        await test_single()
        await test_batch(3)
        await test_with_proxies(5)
        await test_stress(10, concurrent=3)
        await test_performance_target()
    else:
        print("Invalid choice")
    
    print("\n" + "="*60)
    print("  Tests Complete")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())