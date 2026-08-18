# GPM App Order Publication

Test external system:

```text
https://ts.workstaffcrm.ru
```

The external order system publishes orders to the GPM backend. Human app users
read published orders from the same backend after logging in.

```text
External order system -> GPM backend -> PostgreSQL -> Flutter logist app
```

## Endpoints

Publish or update an order:

```http
POST /app-api/orders
X-GPM-App-Token: <token>
Content-Type: application/json
```

Read published orders with the server-side integration token:

```http
GET /app-api/orders
X-GPM-App-Token: <token>
```

Update an app order:

```http
PATCH /app-api/orders/{order_id}
X-GPM-App-Token: <token>
Content-Type: application/json
```

```json
{
  "status": "PROCESSED"
}
```

Log in as a human app user:

```http
POST /app-api/auth/login
Content-Type: application/json
```

```json
{
  "username": "logist",
  "password": "<password>"
}
```

Read orders as the logged-in app user:

```http
GET /app-api/me/orders
Authorization: Bearer <access_token>
```

Update an order as the logged-in app user:

```http
PATCH /app-api/me/orders/{order_id}
Authorization: Bearer <access_token>
Content-Type: application/json
```

Health check:

```http
GET /health
```

Server process:

```bash
uvicorn app.app_orders_api:app --host 127.0.0.1 --port 8081
```

## Production storage

Use PostgreSQL for production data. Set the database URL through the server
environment, not in the repository:

```bash
GPM_APP_DATABASE_URL=postgresql://user:password@host:5432/database
GPM_APP_API_TOKEN=<server-side token>
GPM_APP_JWT_SECRET=<server-side JWT signing secret>
GPM_APP_LOGIST_USERNAME=logist
GPM_APP_LOGIST_PASSWORD=<temporary logist password>
GPM_APP_ALLOWED_ORIGINS=https://your-app-domain.ru
```

Flutter production builds should contain only public settings:

```bash
GPM_APP_MODE=api
GPM_APP_API_URL=https://app-api.gpmbot.ru
```

If `GPM_APP_DATABASE_URL` is not set, the API falls back to local SQLite for
development.

## Payload

```json
{
  "source_system": "workstaff",
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
