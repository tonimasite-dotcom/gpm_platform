# GPM — оплата за час или за смену, 21.10.2026

Опубликованы backend и frontend версии
`472990aa78dc5886ce49aa5b9edd4e30fd473419`.

- В форме создания заказа добавлен выбор «Ставка в час» / «Смена».
  Поле суммы и сообщение проверки соответствуют выбранному режиму.
- У логиста полностью скрыт блок «Предполагаемая стоимость»; клиентский
  бюджет из этой формы для логиста не отправляется. У клиента блок сохранён.
- Используются существующие поля `work_mode` (`rate` / `shift`) и
  `price_per_hour`: в режиме `shift` сумма означает оплату за одну смену
  одному исполнителю. Новых полей и миграций БД нет.
- Карточка логиста показывает ставку за смену. Карточка исполнителя,
  backend-начисление и демо-финансы не умножают ставку за смену на часы.

## Проверки и публикация

- [CI 39599881631](https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/39599881631):
  success; backend с PostgreSQL, CRM regression checks, Flutter analyze,
  Flutter tests и release web build.
- [Deploy production 39600248812](https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/39600248812):
  `all`, success; опубликован именно `472990a` из `main`.
  Во время выпуска прошли 111 backend tests; frontend также повторно
  проверен и собран штатным workflow.
- Проверки workflow после обновления: service active, публичный API
  `/health` возвращает `status=ok`, `storage=postgres`; сайт и публичная
  конфигурация frontend доступны с runner.
- Прямые HTTP-проверки с локального компьютера завершились таймаутами
  соединения; содержимое публичного JS локально не проверено.
  Ручная приёмка формы владельцем после обновления страницы остаётся.

## Резервные копии

- [Backup 39568615811](https://github.com/tonimasite-dotcom/gpm_platform/actions/runs/39568615811),
  21.10.2026: success; расшифровка, хеши файлов и восстановление 17 таблиц
  в изолированном PostgreSQL проверены. Artifact
  `gpm-production-encrypted-39568615811-1` доступен на момент выпуска.
- Backend code rollback: `/opt/gpm/backups/20261021_123338`.
- Frontend code rollback: `/opt/gpm/front-backups/20261021_123424`.
- Предыдущий frontend: `/var/www/gpm-app-previous-20261021_123424`.

CRM в этом выпуске не изменялась. Рабочие заказы для проверки не создавались.
