# MultiTransfer QR Generator

Автоматическая генерация QR-кодов для переводов через MultiTransfer API.

## Установка

```bash
uv sync
```

```bash
# Linux/macOS
redis-server

# Docker
docker run -d -p 6379:6379 redis:alpine
```

## Настройка

### 1. API ключи

В файле `.env` укажите ваши ключи:

```python
CAPTCHA_API_KEY=your_2captcha_api_key
PROXY=http://user:pass@host:port

# Redis (опционально, по умолчанию localhost:6379)
REDIS_URL=redis://localhost:6379

# Настройки пула токенов
TOKEN_POOL_SIZE=10      # Размер пула токенов
TOKEN_LIFETIME=8        # Время жизни токена в секундах (токены живут ~10с, ставим 8 для запаса)
```

Структуру файла .env можете скопировать с .env.example
По умолчанию установлена конфигурация 2captcha, с ней производительность возрастает в 2-2.5 раза.

### 2. Запустите Redis

```bash
# Linux/macOS
redis-server

# Docker
docker run -d -p 6379:6379 redis:alpine
```

## Использование

### Базовое использование

```python
from qr_generator_race import generate_qr_race

result = await generate_qr_race(
    proxy="http://user:pass@host:port",
    amount=1000,
    card_number="5058270855938719",
    card_country="TJK",
    attempts=3  # Количество параллельных попыток
)
```

### С пулом токенов

```python
from captcha_token_pool import CaptchaTokenPool
from qr_generator_race import generate_qr_race

# Инициализация пула
token_pool = CaptchaTokenPool(
    redis_url="redis://localhost:6379",
    pool_size=10,
    token_lifetime=8,
    captcha_key="your_captcha_key"
)

await token_pool.connect()
await token_pool.start_generator()

# Генерация QR с использованием пула
result = await generate_qr_race(
    proxy="http://user:pass@host:port",
    amount=1000,
    card_number="5058270855938719",
    card_country="TJK",
    attempts=3,
    token_pool=token_pool  # Передаем пул токенов
)

# Остановка пула
await token_pool.stop_generator()
await token_pool.disconnect()
```

## Запуск

```bash
python main.py
```

## Результат

Успешный запрос возвращает:
- `transfer_id` - ID перевода для дальнейшей работы
- `transfer_num` - номер перевода
- `qr_payload` - полная ссылка на QR код (формат: https://qr.nspk.ru/...)

## Пример ответа

```json
{
  "transfer_id": "ea9bc1d1-35ad-479d-a4ce-d6dda79f8a3b",
  "transfer_num": "857031673348",
  "qr_payload": "https://qr.nspk.ru/AD1000335H8JL66G9UARA4HTATPPMO8D?type=02&bank=100000000017&sum=1000......"
}
```

## Возможные ошибки

**423 - Дата паспорта некорректна**
- Проблема с генерацией паспортных данных

**402 - Не удалось проверить данные**
- Проблема с captcha token
- Проверьте баланс 2captcha/Rucaptcha
- Проверьте качество прокси
- Проверьте что Redis запущен

**502 - Bad Gateway**
- Сервер перегружен
- Проверьте прокси
- Попробуйте снизить attempts

**Connection refused to Redis**
- Redis не запущен
- Проверьте `REDIS_URL` в .env

## Структура проекта

```
config/config.py          - Конфигурация и данные паспортов
captcha_solver.py         - 2Captcha и Rucaptcha интеграция
captcha_token_pool.py     - Пул токенов капчи в Redis
http_client.py            - HTTP клиент
build_id_fetcher.py       - Автоматическое получение BUILD_ID
qr_generator_race.py      - Race-режим генерации (параллельные попытки)
main.py                   - Точка входа
test_token_lifetime.py    - Тестирование времени жизни токена
```

## Определение времени жизни токена

Для определения реального lifetime токена используйте:

```bash
python test_token_lifetime.py
```

Скрипт протестирует токен в разные моменты времени и определит когда он истекает.

## Поддержка

Страны: Таджикистан (TJK), Узбекистан (UZB), Кыргызстан (KGZ)

Способ перевода: Все карты (ANONYMOUS_CARD)