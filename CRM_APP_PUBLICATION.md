# GPM App Order Publication

Test external system:

```text
https://ts.workstaffcrm.ru
```

The test CRM publishes order data to GPM. The prepared `gpm-crm-sync-v1`
integration synchronizes common order fields in both directions; moderation,
applications, assignments, attendance, statuses, and chats remain inside GPM.
The CRM portion is installed with synchronization disabled until the matching
GPM backend release is deployed.

```text
Test CRM <-> GPM backend <-> PostgreSQL <-> Flutter logist app
```

## Endpoints

Create or refresh a moderation draft:

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

Read a linked test CRM order's content and opaque revision:

```http
GET /app-api/integration/order-sync/{order_id}
X-GPM-App-Token: <token>
```

Write common fields only if that revision is still current:

```http
PATCH /app-api/integration/order-sync/{order_id}
X-GPM-App-Token: <token>
Content-Type: application/json
```

```json
{
  "source_instance": "https://ts.workstaffcrm.ru",
  "revision": "<64-character revision from GET>",
  "fields": {"price_per_hour": 600}
}
```

Both sync routes require the server-side integration token and a persisted
test-CRM binding. A stale revision returns HTTP 409; the bridge reads again on
its next attempt. Workflow fields cannot be written through this protocol.
See [test CRM installation and field mapping](integrations/workstaff-test-crm/README.md).

Update an app order from a trusted server-side integration:

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

Publish a draft as the logged-in logist:

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

`GPM_APP_API_TOKEN` is a server-to-server secret. It must not be embedded in a
Flutter build, sent to a browser, placed in documentation, or committed to Git.

If `GPM_APP_DATABASE_URL` is not set, the API falls back to local SQLite for
development.

## Payload

```json
{
  "source_system": "workstaff",
  "source_instance": "https://ts.workstaffcrm.ru",
  "logist_phone": "+79990000001",
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

- `logist_phone` — phone from the target active GPM logist profile
- `order_data.order_number`
- `order_data.completion_date.date`
- `order_data.loaders.loader_count`
- `order_data.info`

Publishing the same `order_number` again updates the stored app order.
When explicitly linking a legacy test order, the trusted publisher can send
`preserve_existing_content: true`: GPM retains existing app content and the
assigned owner before linking. The bridge then reconciles common fields using
app values on conflicts. Human app users cannot request this integration option.
An order already bound to another CRM instance cannot be claimed by test CRM.

GPM resolves `logist_phone` to a single active logist account when the CRM POST
is accepted. The assigned account ID, rather than browser storage, controls all
logist reads and mutations. A missing phone, an unknown phone, or a phone shared
by multiple active logist profiles is rejected. CRM orders never enter a shared
logist queue.

Workers receive a published `PROCESSED` order only when its normalized `city`
matches one of the values in the worker profile `cities` list. The list may
contain multiple cities. Direct application requests enforce the same rule.

## Internal publication flow

1. CRM sends the payload to `POST /app-api/orders`.
2. GPM stores a new order with status `NEW`.
3. GPM requires `logist_phone`, resolves it to one active server-backed logist
   account, and rejects missing, unknown, or ambiguous values.
4. Only that assigned logist can review the draft or its applications.
5. While the order is active (`NEW`, `PROCESSED`, `IN_PROCESS`, `DONE_PENDING`),
   that logist may correct operational fields such
   as the city, schedule, address, worker count, work mode and rates. The CRM
   order number, source and assigned logist remain server-owned.
6. The logist presses `Опубликовать`; GPM changes the status to `PROCESSED`.
7. Only workers whose profile contains the order city can discover it.
8. The assigned logist may press `Завершить поиск исполнителей` after confirming
   at least one worker, even if fewer workers were found in GPM than requested.
   GPM changes the order to `IN_PROCESS`, stops new applications, rejects any
   still-pending applications, and preserves confirmed workers' access to the
   order, chat, and completion flow. Workers recruited through other sources
   remain outside GPM.

Clients and non-CRM logists create their own `NEW` drafts inside the GPM app
and publish them from the app. Clients edit only their own `NEW` drafts;
logists may also edit their own active orders. They cannot see, edit or publish
CRM orders assigned to another logist. Closed (`CONVERTED`, `JUNK`) order
content is preserved to protect financial history.

Republishing the same CRM order number updates operational fields and rates
on active orders. GPM preserves its status, assigned logist, applications,
assigned workers and recorded hours. Reducing the worker count below the
number already assigned is rejected. This requires the CRM publisher to send
an updated payload. The API does not poll CRM: the test CRM bridge runs
`gpm:sync-orders` at one-minute intervals after activation and writes accepted
app edits to the corresponding test CRM columns. If both sides change one
field, app values win; different changed fields merge. Activation, native field
mapping and app-only fields are documented in the integration README above.
An accepted checkout records whole payable hours rounded upward;
when every assigned worker has checked out, the order enters `DONE_PENDING`.

The active integration does not call a Telegram bot and does not use messenger
usernames as routing identifiers. See `INDEPENDENT_PLATFORM_ARCHITECTURE.md`.
