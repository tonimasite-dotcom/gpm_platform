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
2. GPM stores it as a `NEW` moderation draft.
3. The assigned logist reviews it in the GPM logist workspace.
4. Publishing changes the status to `PROCESSED` through the authenticated GPM
   endpoint `PATCH /app-api/me/orders/{order_id}`.
5. Workers discover the published order and apply inside GPM.
6. Assignments, lifecycle statuses, finance, notifications, and chats remain
   internal to GPM.

The integration token is server-side only and must never be embedded in the
Flutter application or committed to Git.

`logist_phone` may be supplied by the CRM to route a `NEW` draft to the matching
GPM logist profile. A draft without `logist_phone` is placed in the shared
logist moderation queue.

Legacy bot modules and legacy Telegram-shaped fields are not part of this
active workflow and must not be enabled or used as an integration transport.

## UI constraint

Functional work on this flow must preserve the frozen application design and
color scheme documented in `DESIGN_FREEZE.md`.
