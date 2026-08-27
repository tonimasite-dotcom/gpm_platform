# GPM: delta-handoff после основного CRM recovery snapshot

Дата: 28.08.2026. Часовой пояс: Europe/Moscow.

Этот файл фиксирует только прогресс после коммита:

```text
a5a9220 Add August 28 CRM recovery handoff
```

В новом чате сначала вставить целиком основной файл:

```text
CONTINUE_PROJECT_PROMPT_2026-08-28_CRM_PUBLICATION_RECOVERY.md
```

Затем вставить целиком этот delta-handoff отдельным сообщением. При конфликте по
текущей точке остановки этот delta новее основного снапшота.

## 1. Что проверено после снапшота

Владелец создал тестовую заявку в `https://ts.workstaffcrm.ru/` и нажал действие
публикации в приложение. Workstaff показал ошибку:

```text
Не удалось опубликовать в приложении
```

Для закрытой разработки владелец разрешил использовать собственный рабочий
телефон как тестовый. Сам номер намеренно не повторяется и не добавляется в Git,
документацию или автотесты.

На GPM backend выполнена минимальная проверка журнала:

```bash
journalctl -u gpm-app-api.service --since "10 minutes ago" --no-pager -o short-iso | awk '/POST \/app-api\/orders/ {print $1, $(NF-1), $NF}'
```

Результат:

```text
2026-08-27T22:20:32+00:00 401 Unauthorized
```

Вывод: webhook/кнопка Workstaff существуют и запрос доходит до GPM. Ошибка
возникает на server-to-server авторизации до обработки payload.

## 2. Workstaff CRM server

DNS:

```text
ts.workstaffcrm.ru   -> 5.183.191.222
test.workstaffcrm.ru -> 5.183.191.222
```

SSH-проверка владельцем:

```text
host: 5.183.191.222
user: root
hostname: sad0a47f6.fastvps-server.com
```

Корень приложения:

```text
/var/www/gruzpiter/data/www/ts.workstaffcrm.ru
```

## 3. Найденная действующая реализация Workstaff → GPM

Read-only поиск нашёл:

```text
/var/www/gruzpiter/data/www/ts.workstaffcrm.ru/.env
/var/www/gruzpiter/data/www/ts.workstaffcrm.ru/app/Services/Order/GpmAppOrderPublisher.php
/var/www/gruzpiter/data/www/ts.workstaffcrm.ru/app/Services/Order/GpmAppOrderPublisher.php.backup_before_button_20260812_094651
/var/www/gruzpiter/data/www/ts.workstaffcrm.ru/app/Services/Order/GpmAppOrderPublisher.php.backup_before_button_20260812_091128
/var/www/gruzpiter/data/www/ts.workstaffcrm.ru/app/Http/Controllers/Order/ManagerOrderController.php
/var/www/gruzpiter/data/www/ts.workstaffcrm.ru/resources/js/pages/app/orders/logist_orders/index.vue
```

Активный publisher читает:

```php
env('GPM_APP_API_URL', '')
env('GPM_APP_API_TOKEN', '')
```

и добавляет header:

```text
X-GPM-App-Token
```

Workstaff `.env` содержит обе переменные:

```text
GPM_APP_API_URL=<redacted>
GPM_APP_API_TOKEN=<redacted>
```

Значения token ни разу не выводились в чат или документацию.

## 4. Сравнение безопасных отпечатков

На Workstaff проверены URL, длина и первые 12 hex SHA-256 без вывода token:

```text
URL=https://app-api.gpmbot.ru
TOKEN_LENGTH=64
TOKEN_FP=c3b10d89a775
```

На GPM backend `46.149.71.147` активная переменная и отпечаток:

```text
TOKEN_KEY=GPM_APP_API_TOKEN
TOKEN_LENGTH=64
TOKEN_FP=bcc12c793afd
```

Доказанный диагноз:

```text
Workstaff GPM_APP_API_TOKEN != GPM backend GPM_APP_API_TOKEN
```

Именно это вызывает `401 Unauthorized`. Endpoint, URL, publisher и кнопка не
утрачены. Payload пока не проверялся, потому что запрос отклоняется раньше.

## 5. Неудачная попытка прямой безопасной передачи

Планировалось передать актуальный token напрямую с GPM backend на Workstaff по
SSH без вывода в терминал.

С GPM-сервера была выполнена только read-only проверка:

```bash
ssh -o ConnectTimeout=10 root@5.183.191.222 'hostname; test -f /var/www/gruzpiter/data/www/ts.workstaffcrm.ru/.env && echo WORKSTAFF_ENV_OK'
```

Результат:

```text
Warning: Permanently added '5.183.191.222' (ECDSA) to the list of known hosts.
root@5.183.191.222's password:
Connection closed by 5.183.191.222 port 22
```

Состояние после попытки:

- host key Workstaff добавлен в root `known_hosts` GPM-сервера;
- SSH-команда на Workstaff не выполнилась;
- token не передавался;
- `.env` обоих серверов не менялись;
- services не перезапускались;
- повторять межсерверный SSH сейчас не нужно.

## 6. Выбранный безопасный способ исправления

Следующий способ — совместная ротация обоих концов через новый случайный token,
созданный локально на Windows и помещённый в clipboard без отображения.

На момент создания delta эта команда ещё НЕ выполнена:

```powershell
$tokenBytes = New-Object byte[] 32; $tokenRng = [System.Security.Cryptography.RandomNumberGenerator]::Create(); $tokenRng.GetBytes($tokenBytes); $newGpmToken = ([BitConverter]::ToString($tokenBytes)).Replace('-', '').ToLowerInvariant(); Set-Clipboard -Value $newGpmToken; Write-Output ('TOKEN_COPIED_LENGTH=' + $newGpmToken.Length); $tokenRng.Dispose(); Remove-Variable tokenBytes,tokenRng,newGpmToken
```

Ожидаемый безопасный вывод:

```text
TOKEN_COPIED_LENGTH=64
```

Token остаётся только в clipboard и не должен появляться в чате, terminal
scrollback, Git или документации.

## 7. Точная следующая точка

1. В обычном Windows PowerShell выполнить команду генерации выше.
2. Ничего другого не копировать, чтобы не перезаписать clipboard.
3. После подтверждения `TOKEN_COPIED_LENGTH=64` дать владельцу одну команду для
   Workstaff server `5.183.191.222`, которая:
   - скрыто запросит вставку token через `read -s`;
   - проверит длину 64;
   - создаст timestamped backup `.env` через `cp -a`;
   - атомарно заменит только `GPM_APP_API_TOKEN`;
   - сохранит owner/mode;
   - выполнит Laravel `php artisan config:clear`;
   - покажет только новый короткий fingerprint.
4. Затем дать отдельную команду для GPM backend `46.149.71.147`, которая:
   - скрыто запросит тот же token из clipboard;
   - создаст timestamped backup `/root/gpm-app-env`;
   - атомарно заменит только `GPM_APP_API_TOKEN`;
   - сохранит owner/mode `600`;
   - перезапустит `gpm-app-api.service`;
   - проверит active/health;
   - покажет только fingerprint.
5. Отпечатки должны совпасть.
6. Повторить публикацию той же или новой синтетической заявки Workstaff.
7. Проверить journal: требуется `200 OK`.
8. Только после `200` проверять payload/появление `NEW` у логиста.

## 8. Порядок обновления и rollback

Рекомендуемый порядок:

```text
Workstaff .env -> Laravel cache clear -> GPM env -> GPM service restart
```

Существующий поток уже возвращает `401`, поэтому краткий период несовпадения при
ротации не ухудшает рабочее состояние.

До изменения обязательно создать отдельные backups с timestamp. Не удалять
старые `.backup_before_button_*` файлы Workstaff.

Если после изменения требуется rollback:

- вернуть соответствующий новый timestamped `.env` backup на Workstaff;
- вернуть парный timestamped `/root/gpm-app-env` backup на GPM;
- очистить Laravel config cache;
- перезапустить GPM service;
- проверить health и fingerprints.

Нельзя откатывать только одну сторону: token должен совпадать на обоих концах.

## 9. Что не менять

- Не менять URL `https://app-api.gpmbot.ru`.
- Не восстанавливать исторический token из Git.
- Не использовать Telegram `/api/telegram/`.
- Не возвращать demo-кнопку `Из CRM` в GPM.
- Не менять payload/code до прохождения авторизации.
- Не менять дизайн и цвета приложения.
- Не смешивать CRM recovery с `feature/address-provider-switch`.
- Не сливать и не deploy `30b2bca` до отдельного решения владельца.

## 10. Git/production остаются без изменений

На момент этого delta:

```text
main = origin/main = 92624b7
feature/crm-logist-publication до delta = a5a9220
production frontend = b9ebdfa
production backend = a6fac5c
```

После основного снапшота владелец создал/изменил тестовую заявку в Workstaff и
запустил её неуспешную публикацию. На инфраструктуре единственным изменением
стало добавление SSH host key в `known_hosts` GPM root. Production code, GPM DB
и env обоих серверов не менялись.

Этот delta является документационным дополнением и сам по себе не требует
production deployment.
