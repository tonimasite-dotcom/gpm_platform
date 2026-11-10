# Продолжить после отдельного отключения дебиторки TS

Сначала git fetch origin и перейти к актуальной ветке work/ts-resume-2026-11-09
в отдельном worktree C:/Users/Юра/Desktop/gpm_platform/gpm_platform/.tmp/ts-resume-20261110.
Не делать вывод по старому HEAD 6764992 основного checkout, не reset/stash чужие
правки и пользовательскую .vscode. Прочитать AGENTS.md, README.md,
PROJECT_HANDOFF_2026-11-10_TS_DEBT_AUTOMATION_DISABLED.md и safe audits/crm-ts-debt-off-2026-11-10/.

Точное состояние: по прямому поручению владельца ОТДЕЛЬНО выпущено отключение
дебиторки/писем должникам на TS. Код 497943c9b185a916b99b748d59434899b2b98312,
CI 42791198145 SUCCESS backend/flutter; deployment PASS, install+checks 0.209 сек,
maintenance снят. Изменены только CheckDebit.php(handle/sendMail),
CheckCustomerDebit.php(handle), WebKlexMailClient.php(sendDebitMessage).
Реальные команды: debit:check_debit и command:checkCustomerDebit; debit:notify
на текущей TS отсутствует. Оба расчета/письма выходят до DB/mail и при прямом вызове.

Kernel/cron, GPM minute sync, env/SMTP, вход/обычные письма входа, AppServiceProvider,
LoginController, routes, роли/учетки и рабочие данные не менялись. Все protected SHA
сошлись. Четыре handlers реально вызваны в TS FPM без Laravel bootstrap/DB/mail,
также частно в net namespace; failure injection на четырех границах PASS.
HTTPS TS: главная 200, /api/user без JWT 401, чужие редиректы не выполнялись.
Основная/соседний test не трогались, общие сервисы не перезапускались.

Manifest 9281c7aec1cf5ca3489e5b06f9e0c76eb2c76590fc42b130097f7bff0c6254b2,
server /root/gpm-ts-update/20261110-debt-off-01,
tools /root/gpm-ts-update/debt-off-tools-20261110. Backup исходников входит в
проверенный demo-04/code-backup/ts-demo-code-before.tar.gz.age,
SHA 4d1555014fd01a636d21444076a5aabdfc95236ad7e2cee17e3198c0d621cc01.
Расшифрование/restore проверены; перед выпуском свежесть/три before SHA сверены.
Ключ отдельно в исходном checkout .tmp/production-backup-20261015/age-identity.txt,
локально encrypted backup/restore в worktree/.tmp/demo-code-backup-04.
Это code-only backup, не новая SQL-копия; в выпуске нет SQL/migrate/seed.

Первоначальная большая задача подготовки безопасных тестов приложения остается:
владелец хочет также входить через браузер на ts.workstaffcrm.ru и сверять заявки.
Полный пакет b24a97d (27 файлов, encrypted local inbox/JWT fixes/demo transports)
еще НЕ применен и отдельно не согласован как изменение авторизации/доставки кодов.
Его прежний manifest c350b699... уже УСТАРЕЛ ПО before SHA трех файлов после
данного узкого выпуска. Не применять вслепую; сделать адресный rebase/checkpoint
на текущие guarded файлы, сохранив вечный запрет дебиторки/писем. Не повторять все
старые 80/14/62/31/7 проверки без изменений соответствующих компонентов.
Старые source/candidate/demo-01/02/03/04/W/S/SQL-copy/data/backup не удалять,
не запускать init/prepare/merge/restore/migrations поверх существующих отчетов.

Не считать весь деморежим live уже включенным: SMTP/Pusher остаются прежними;
достоверно отключены именно debtor check/email. Не переносить main cron,
debit:calculate/debit:notify или общий Kernel/37 миграций автоматически.
Живой gpm:sync-orders как smoke не запускать и cron не отключать вслепую.
Новые sync-правила отдельны; ответы коллег есть, не писать «ждем ответов».
Локальное окно кодов пока подготовлено, не активировано; пароль/captcha/code/JWT
не обходить. Ручная приемка аккаунта/тестовой заявки в живой связке остается.

Обязательные ограничения:
- Основную CRM только читать для сверки. Без ее правок файлов/настроек/БД,
  загрузки Laravel/заданий/миграций/sync и переноса данных/секретов. Будущий выпуск
  на основную отдельно явно согласуется после тестов. В этом этапе основная не
  читалась/не менялась; жизненно важные live компоненты и auth не менялись.
- Очистка заявок не разрешает удаления схемы/таблиц/кода/аккаунтов/профилей/auth/
  приглашений/аудита/конфигурации/секретов/backup/инфраструктуры, также в репетиции.
  Для жизненно важных объектов нужны отдельная задача, перечень/последствия/
  восстановление/явное согласование. Старое разрешение трех backup-дубликатов
  исполнено и новых удалений не разрешает. Автоматически возвращать debt-enabled
  старые файлы из backup нельзя. При сбое держать TS maintenance и адресно чинить.

Фиксировать этапы в Git/README/новом handoff с commit/CI/deploy/backup/проверками,
ручным остатком и границами систем. Секреты, коды входа, JWT, plaintext backup
не выводить в чат/Git/логи. Писать кратко, использовать е.
