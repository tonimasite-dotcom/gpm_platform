# Продолжить с актуального demo-05 пакета

git fetch origin. Работать в work/ts-resume-2026-11-09, отдельный worktree
C:/Users/Юра/Desktop/gpm_platform/gpm_platform/.tmp/ts-resume-20261110.
Не ориентироваться на старый HEAD 6764992 исходного checkout; пользовательскую
.vscode и чужие правки не reset/stash/commit. Прочитать AGENTS.md, README.md,
PROJECT_HANDOFF_2026-11-10_TS_DEMO_REBASED_READY.md и
audits/crm-ts-demo-rebase-2026-11-10/.

По последнему поручению выполнена актуализация пакета, НЕ live auth deployment.
Code d8b8ff3bfd422e23353865b0d16b82e5bb35a06e, CI 42798190912 SUCCESS backend/flutter.
Новейший docs commit смотреть git log. На live TS остается только ранее выпущенное
отключение дебиторки/писем должникам (497943c, CI 42791198145, deployment PASS).
Обычные SMTP/Pusher/доставка кода входа пока прежние; полный деморежим не объявлять
уже включенным. Основная и жизненно важные live компоненты в этой итерации не менялись.

Новый manifest b99e16ea5017191df337537018d1c28ae2b9f160984bf7a4d2c2ca73f855adac,
27 файлов. Before изменены только у трех live debt файлов. В after сохранены
точные четыре standalone guards; четвертый новый after — только профиль/версия Policy.
Auth/GPM логика побайтно прежняя относительно demo-04. Старый c350b699... не применять.
В новом пакете нельзя ослабить запрет debt check/email, даже в partial/rollback состоянии.

Свежие проверки: 80 transport/inbox, 31 install/resume с debt retention, 27 целей
PHP 7.4 lint, 13 helper PHP 7.4 lint, Python/JSON, live before/cron/checker, новый
SSH-путь local inbox. PASS. Прежние actual auth 14 и GPM 11+16+35 закреплены по
эквивалентности кода с SHA исходных отчетов, это НЕ новый запуск. Private MySQL
не запускался, process count 0. Не повторять старые тесты без изменения компонента.
Формы/compiled assets не менялись; ручной ввод адреса и независимость Save от
геокодера подтверждены по текущему исходному коду, не браузерной приемкой.

Новая encrypted CODE копия уже включает текущие debt guards:
/root/gpm-ts-update/20261110-demo-05/code-backup/ts-demo-code-before.tar.gz.age,
40983 bytes, SHA a27ec1bf78624ea99be495952ec44f3146b265856d504821fc04f6ace6358ab3.
24 файла восстановлены в новую worktree/.tmp/demo-code-backup-05/restored-code,
SHA совпали, отсутствие трех новых учтено. Ключ отдельно в исходном checkout
.tmp/production-backup-20261015/age-identity.txt. Никакие значения не печатать.
Это не новая SQL/files-копия; в apply нет SQL/migrate/seed/правок рабочих строк.

Новый overlay /root/gpm-ts-update/20261110-demo-05/runtime,
tools /root/gpm-ts-update/demo-tools-20261110-v05. Старые demo-01/02/03/04,
debt-off-01 и W/S/data/backup не перезаписывались. prepare_demo.py теперь только
библиотека; одноразовая новая сборка rebase_after_debt_off.py. Не rerun имеющиеся
init/prepare/merge/restore/migrations/rehearsal/cleanup поверх состояния/отчетов.

Перед live изменением входа/доставки кодов остается отдельное точечное
согласование этого состава по AGENTS.md. Общие условия TS-only/сохранности/короткой
остановки уже согласованы. Если после данного handoff владелец одобрил выпуск
описанного пакета, не спрашивать повторно: свежий dry-run, проверить backup age/
before SHA, затем новый v05 apply_code.py --apply --approved-manifest <новый SHA>.
Никаких shared FPM/master/cron/MySQL reload/reset и никаких правок основной.

Выпуск: свой TS maintenance, 27 atomic swaps с правами/owner, только TS opcache
invalidate через /var/run/ts.workstaffcrm.ru.sock, реальный guarded FPM probe,
401 /api/user без JWT и 200 / с marker ts-demo-20261110-05. При отказе держать/вернуть
свой maintenance и resume того же SHA; не откатывать автоматически к отправляющей
SMTP/debt версии. Existing minute gpm:sync-orders не менять и как smoke не запускать.

После успешного выпуска открыть local_login_inbox.py владельцу. Обычный
пароль/captcha он вводит сам, код берет в закрытом окне 127.0.0.1 через root SSH,
нового HTTP endpoint кодов на CRM нет. Пароль/код/JWT не выводить в чат/Git/логи.
Живой сквозной сценарий подготовленной тестовой заявки и ручная браузерная
приемка еще остаются. Новые sync-бизнес-правила отдельно; ответы коллег есть,
не писать «ждем ответов» и не придумывать содержание.

Обязательные ограничения:
- Основную CRM только читать для сверки, без правок файлов/настроек/БД, запуска
  Laravel/заданий/миграций/sync и переноса данных/секретов. Будущий выпуск на нее
  отдельно явно согласуется после тестов. Сейчас основная не читалась/не менялась,
  auth и прочие жизненно важные live компоненты TS в этой итерации не менялись.
- Очистка заявок не разрешает удаления схемы/таблиц/кода/аккаунтов/профилей/auth/
  приглашений/аудита/конфигурации/секретов/backup/инфраструктуры, также в репетиции.
  Нужны отдельная задача, перечень/последствия/восстановление/явное согласование.
  Старое разрешение трех backup-дубликатов исполнено; новых удалений не разрешает.

Сохранять этапы в Git/README/новом handoff с commit/CI/deploy/backup/проверками/
ручным остатком/границами систем. Писать кратко, использовать е.
