# MultiTransfer QR Generator

Автоматическая генерация QR-кодов для переводов через MultiTransfer API.

## Установка

```bash
uv sync
```

## Настройка

### 1. API ключи

В файле `.env` укажите ваши ключи:

```python
CAPTCHA_API_KEY = "ваш_ключ_от_rucaptcha_или_от_2captcha"
PROXY=http://user:pass@host:port
```

Структуру файла .env можете скопировать с .env.example
По умолчанию установлена конфигурация 2captcha, с ней производительность возрастает в 2-2.5 раза.

## Использование

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
- Проверьте баланс Rucaptcha или 2captcha
- Проверьте качество прокси

**502 - Bad Gateway**
- Сервер перегружен
- Проверьте прокси
- Попробуйте снизить attempts

## Структура проекта

```
config/config.py          - Конфигурация и фиксированные данные паспортов
captcha_solver.py         - 2Captcha и Rucaptcha интеграция
http_client.py            - HTTP клиент
build_id_fetcher.py       - Автоматическое получение BUILD_ID
qr_generator_race.py      - Race-режим генерации (несколько попыток параллельно)
main.py                   - Точка входа
```



## Поддержка

Страны: Таджикистан (TJK), Узбекистан (UZB), Кыргызстан (KGZ)

Способ перевода: Все карты (ANONYMOUS_CARD)