# GPM standalone architecture

Status: active architectural constraint, 2026-08-28.

GPM is a standalone application. Its production workflows must not depend on
Telegram, another messenger, or a social network.

## CRM order flow

The CRM is only an external source of order data:

```text
CRM -- server-to-server API --> GPM backend --> PostgreSQL --> GPM applications
```

1. CRM sends an order to `POST /app-api/orders` with `X-Gpm-App-Token`.
2. GPM resolves the required `logist_phone` to exactly one active logist
   account and stores that account ID with the `NEW` draft.
3. Only the assigned logist can read, publish, or process applications for the
   CRM order.
4. Publishing changes the status to `PROCESSED` through the authenticated GPM
   endpoint `PATCH /app-api/me/orders/{order_id}`.
5. Workers discover the published order only when its city is one of the cities
   selected in their server-backed profile, and apply inside GPM.
6. After assigning at least one GPM worker, the logist may stop recruitment
   before every requested slot is filled. GPM changes the order to
   `IN_PROCESS`, rejects remaining pending applications, and keeps confirmed
   workers assigned so they can complete their work inside the order.
7. Assignments, lifecycle statuses, finance, notifications, and chats remain
   internal to GPM.

The integration token is server-side only and must never be embedded in the
Flutter application or committed to Git.

`logist_phone` is required for CRM publication. It must match exactly one active
GPM logist profile after Russian `+7`/`8` normalization. Missing, unknown, or
ambiguous phones are rejected; there is no shared CRM moderation queue.

Client-created orders are independent from the CRM flow. A client sees only
orders created by that account, can publish an own order directly to workers,
and can accept applications and completion only for that own order.

Legacy bot modules and legacy Telegram-shaped fields are not part of this active
workflow and must not be enabled or used as an integration transport.

## UI constraint

Functional work on this flow must preserve the frozen application design and
color scheme documented in `DESIGN_FREEZE.md`.
