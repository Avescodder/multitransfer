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
По default установлена конфигурация 2captcha, с ней производительность возрастает 

## Запуск

```bash
python main.py
```

## Результат

Успешный запрос возвращает:
- `transfer_id` - ID перевода для дальнейшей работы
- `transfer_num` - номер перевода
- `qr_payload` - полная ссылка на QR код (формат: `https://qr.nspk.ru/...`)
- `qr_data` - полные данные ответа API

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

## Структура проекта

```
config/config.py          - Конфигурация и генерация данных
captcha_solver.py         - 2Captcha и Rucaptcha интеграция
http_client.py            - HTTP клиент с пулом соединений
build_id_fetcher.py       - Автоматическое получение BUILD_ID
qr_generator.py           - Основная логика генерации
qr_pool.py                - Connection pool и параллельная обработка
main.py                   - Точка входа
```

## API Response

Полный ответ `qr_data` содержит:
```json
{
  "success": true,
  "transfer_id": "ea9bc1d1-35ad-479d-a4ce-d6dda79f8a3b",
  "transfer_num": "857031673348",
  "qr_payload": "https://qr.nspk.ru/...",
  "qr_data": {
    "externalData": {
      "payload": "https://qr.nspk.ru/...",
      "type": "QR"
    }
  }
}
```

## Поддержка

Страны: Таджикистан (TJK), Узбекистан (UZB), Кыргызстан (KGZ)

Способ перевода: Все карты (ANONYMOUS_CARD)