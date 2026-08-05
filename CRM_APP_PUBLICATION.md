# CRM App Order Publication

Test CRM:

```text
https://ts.workstaffcrm.ru
```

The CRM publishes orders to the GPM backend. The Flutter app reads published
orders from the same backend.

```text
CRM -> GPM backend -> Flutter logist app
```

## Endpoints

Publish or update an order:

```http
POST /app-api/orders
X-GPM-App-Token: <token>
Content-Type: application/json
```

Read published orders:

```http
GET /app-api/orders
X-GPM-App-Token: <token>
```

Health check:

```http
GET /health
```

Server process:

```bash
uvicorn app.app_orders_api:app --host 127.0.0.1 --port 8081
```

## Payload

```json
{
  "telegram_username": "logist_gpm",
  "client_phone": "+79990000000",
  "client_email": "client@example.com",
  "city": "Москва",
  "order_data": {
    "order_number": "TS-12345",
    "completion_date": {
      "date": "2026-08-05T12:00:00+03:00"
    },
    "timezone": "Europe/Moscow",
    "loaders": {
      "loader_count": 2
    },
    "info": {
      "address": "Москва, ул. Складская, 18",
      "address_street": "ул. Складская",
      "address_number": "18",
      "address_lat": 55.7912,
      "address_lon": 37.5589,
      "metro_station": "Динамо",
      "additional": "Только РФ, нужен пропуск"
    },
    "note": "Комментарий по заявке",
    "min_time": 4,
    "hours": 4,
    "worker_category": "loader",
    "work_mode": "rate",
    "price_per_hour": 450,
    "price_regular": 450,
    "price_state": 500,
    "individual_price": 2200,
    "legal_price": 2600
  }
}
```

Required fields:

- `order_data.order_number`
- `order_data.completion_date.date`
- `order_data.loaders.loader_count`
- `order_data.info`

Publishing the same `order_number` again updates the stored app order.
