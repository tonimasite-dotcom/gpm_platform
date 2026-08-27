# Подключение DaData для адресных подсказок

Текущий provider адресов — DaData. Для API подсказок нужен один API-ключ; secret
key сервиса стандартизации для этой интеграции не используется.

Production environment:

```text
GPM_ADDRESS_SUGGESTION_PROVIDER=dadata
DADATA_API_KEY=<секрет>
```

Реальный ключ хранится только в `/root/gpm-app-env`. Не добавлять его в Git,
Flutter `.env`, tracked YAML, тикеты, документацию или сообщения чата.

Production-настройка и синтетическая ручная проверка выполнены 27.08.2026:

1. ввод города, улицы и дома вернул варианты;
2. выбранный дом был нормализован;
3. координаты были определены;
4. backend health после restart вернулся в `ok`/`postgres`.

Официальная документация:

- https://dadata.ru/api/suggest/address/
- https://dadata.ru/profile/#info
- https://dadata.ru/pricing/
