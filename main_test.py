"""
Тестовый скрипт для проверки createQr
Запуск: python test_createQr.py
"""
import asyncio
import time
from createQr import createQr


async def test_single_request():
    """Тест одиночного запроса"""
    print("=" * 60)
    print("ТЕСТ: Одиночный запрос")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        result = await createQr(amount=1000)
        
        elapsed = time.time() - start_time
        
        if result.get("transfer_id"):
            print(f"\n✅ УСПЕХ!")
            print(f"   Transfer ID: {result['transfer_id']}")
            print(f"   Transfer Num: {result.get('transfer_num', 'N/A')}")
            print(f"   QR Payload: {result.get('qr_payload', 'N/A')[:50]}...")
            print(f"   Время: {elapsed:.1f} сек")
        else:
            print(f"\n❌ ОШИБКА!")
            print(f"   Результат: {result}")
            print(f"   Время: {elapsed:.1f} сек")
            
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ ИСКЛЮЧЕНИЕ!")
        print(f"   Ошибка: {e}")
        print(f"   Время: {elapsed:.1f} сек")
        import traceback
        traceback.print_exc()


async def test_multiple_sequential():
    """Тест нескольких последовательных запросов"""
    print("\n" + "=" * 60)
    print("ТЕСТ: 3 последовательных запроса")
    print("=" * 60)
    
    results = []
    
    for i in range(3):
        print(f"\n[{i+1}/3] Запрос...")
        start = time.time()
        
        try:
            result = await createQr(amount=1000 + i*100)
            elapsed = time.time() - start
            
            success = bool(result.get("transfer_id"))
            results.append({
                "index": i+1,
                "success": success,
                "time": elapsed,
                "transfer_id": result.get("transfer_id")
            })
            
            status = "✅" if success else "❌"
            print(f"   {status} Завершён за {elapsed:.1f} сек")
            
        except Exception as e:
            elapsed = time.time() - start
            results.append({
                "index": i+1,
                "success": False,
                "time": elapsed,
                "error": str(e)
            })
            print(f"   ❌ Ошибка: {e}")
    
    # Итоги
    print("\n" + "=" * 60)
    print("ИТОГИ:")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r["success"])
    avg_time = sum(r["time"] for r in results) / len(results)
    
    print(f"Успешных: {success_count}/3")
    print(f"Среднее время: {avg_time:.1f} сек")
    
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"  {status} Запрос {r['index']}: {r['time']:.1f} сек")


async def test_parallel():
    """Тест параллельных запросов"""
    print("\n" + "=" * 60)
    print("ТЕСТ: 3 параллельных запроса")
    print("=" * 60)
    
    start_time = time.time()
    
    tasks = [
        createQr(amount=1000 + i*100)
        for i in range(3)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    
    # Анализ результатов
    success_count = 0
    for i, result in enumerate(results, 1):
        if isinstance(result, Exception):
            print(f"❌ Запрос {i}: {result}")
        elif result.get("transfer_id"):
            print(f"✅ Запрос {i}: {result['transfer_id']}")
            success_count += 1
        else:
            print(f"❌ Запрос {i}: Неизвестная ошибка")
    
    print(f"\n{'=' * 60}")
    print(f"Успешных: {success_count}/3")
    print(f"Общее время: {elapsed:.1f} сек")
    print(f"{'=' * 60}")


async def main():
    """Главная функция"""
    
    print("\n🚀 ЗАПУСК ТЕСТОВ createQr")
    print("\n⚠️  ВАЖНО: Для работы нужны:")
    print("   - Рабочие прокси")
    print("   - Доступ к multitransfer.ru")
    print("   - Установленный Playwright (playwright install)")
    
    choice = input("\nВыберите тест:\n1. Одиночный запрос\n2. Последовательные (3 шт)\n3. Параллельные (3 шт)\n4. Все тесты\n\nВыбор (1-4): ")
    
    if choice == "1":
        await test_single_request()
    elif choice == "2":
        await test_multiple_sequential()
    elif choice == "3":
        await test_parallel()
    elif choice == "4":
        await test_single_request()
        await test_multiple_sequential()
        await test_parallel()
    else:
        print("❌ Неверный выбор")
        return
    
    print("\n✅ Тесты завершены!")


if __name__ == "__main__":
    asyncio.run(main())