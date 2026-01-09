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
RUCAPTCHA_API_KEY = "ваш_ключ_от_rucaptcha"
PROXY=http://user:pass@host:port
```

Структуру файла .env можете скопировать с .env.example

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

## Производительность

- **Многопоточность**: до 10 одновременных запросов
- **Success rate**: 80-95% (зависит от качества прокси)

## Возможные ошибки

**423 - Дата паспорта некорректна**
- Исправьте данные паспорта

**402 - Не удалось проверить данные**
- Проблема с captcha token
- Проверьте баланс Rucaptcha
- Проверьте качество прокси

**502 - Bad Gateway**
- Сервер перегружен
- Используется автоматический retry (3 попытки)
- Проверьте прокси

## Структура проекта

```
config/config.py          - Конфигурация и генерация данных
captcha_solver.py         - Интеграция с Rucaptcha
http_client.py            - HTTP клиент с пулом соединений
build_id_fetcher.py       - Автоматическое получение BUILD_ID
qr_generator.py           - Основная логика генерации
main.py                   - Точка входа
```

## API Response

Полный ответ `qr_data` содержит:
```json
{
  "externalData": {
    "payload": "https://qr.nspk.ru/...",
    "type": "QR"
  }
}
```

## Поддержка

Страны: Таджикистан (TJK), Узбекистан (UZB), Кыргызстан (KGZ)

Способ перевода: Все карты (ANONYMOUS_CARD)