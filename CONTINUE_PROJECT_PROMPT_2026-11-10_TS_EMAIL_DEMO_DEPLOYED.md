# Продолжение после успешного выпуска TS demo-06

git fetch origin; ветка work/ts-resume-2026-11-09, worktree
C:/Users/Юра/Desktop/gpm_platform/gpm_platform/.tmp/ts-resume-20261110.
Исходный checkout на старом HEAD 6764992, .vscode пользовательская — не трогать.
Прочитать AGENTS.md, README.md,
PROJECT_HANDOFF_2026-11-10_TS_EMAIL_DEMO_DEPLOYED.md,
audits/crm-ts-demo-email-2026-11-10/ и baseline/demo-email/README.md.

Владелец отменил локальное окно кодов: оставить обычные коды входа на email и
текущий механизм входа. Исключены LoginController/JWT/валидация кода и local inbox.
Не возвращать прежние auth-исправления автоматически и не просить повторного
согласования уже выполненного выпуска.

Code c4e5ef28f9a2c382fea9409989a1e4d9290aea93, CI 42802391274 SUCCESS backend/flutter.
Новый docs SHA смотреть git log. TS demo-06 УЖЕ УСТАНОВЛЕН, deployment PASS,
2,274 секунды, maintenance снят. Manifest
58113c74d2a7f18b349ebf1ee172418fcf3a1744c22d61ac753312aae06f3c32, 25 файлов.
Четыре debt guards сохранены; общий mail null/отказ, только существующий
sendVerifyMessage использует отдельный Mailer с прежними SMTP филиала/шаблоном.
Отправка кода не меняет глобальный Mail facade. Бизнес-каналы остаются демо.

79 transport/email и 29 installation/resume PASS, PHP 7.4 lint 25+4, Python/JSON,
fresh read-only preflight. Искусственный SMTP внутри отдельной network namespace
получил одно письмо входа, реальной почты владельцу не посылали. FPM auth/GPM
enabled, default mail/broadcast null, отдельный login SMTP, DB connections 0.
FPM и public HTTPS /200 и /api/user401, marker ts-demo-20261110-06, TLS проверен.
Опкеш сброшен только адресно для 25 TS-файлов, shared reload/reset не было.
Старые 14 auth-тестов исправленного контроллера НЕ применимы; GPM 11+16+35
переиспользованы по точным SHA, не выдавать за новый прогон/живую приемку.

Checkpoint /root/gpm-ts-update/20261110-demo-06,
tools /root/gpm-ts-update/demo-email-tools-20261110.
Encrypted CODE backup code-backup/ts-demo-code-before.tar.gz.age, 39318 bytes,
SHA 66557b00eea1a772c379bdec09d82b8ced5b323d7fc47e0d64385a9581a1187d.
23 файла восстановлены локально в worktree/.tmp/demo-code-backup-06/restored-code,
все SHA совпали, отсутствие двух новых учтено. Ключ отдельно в исходном checkout
.tmp/production-backup-20261015/age-identity.txt; значения не выводить.
Это не полная SQL/files-копия. БД, миграций, seed и запуска рабочих заданий не было.

Владелец подтвердил получение кода на email: «Код приходит для входа, все ок».
Осталась ручная сквозная приемка предназначенной тестовой заявки TS → приложение →
изменение → обратная синхронизация/ставка/права/повторы без дублей.
Не просить код/пароль/JWT
в чат. Если проявятся прежние auth-дефекты — отдельный конкретный объем,
не расширять текущий выпуск автоматически. Ответы коллег по новым sync-правилам
есть, это отдельная задача. Не dispatch живой sync как smoke и не менять
произвольные настоящие заявки.

Старые demo-01..05, debt-off-01, W/S, private datadir и backup сохранены.
Не rerun init/prepare/merge/restore/migrations/cleanup в существующие каталоги.
Live-install-state complete; повторный apply не нужен. Не использовать старые
manifest c350/b99. Не откатывать автоматически отправляющий SMTP/debt baseline.
Новый пакет требует новой точки, свежих before SHA/backup и проверок.

Обязательные ограничения:
- Основную CRM только читать для сверки: никаких правок файлов/настроек/БД,
  запуска Laravel/заданий/миграций/sync и переноса данных/секретов. Будущий выпуск
  на основную отдельно явно согласуется после тестов. В этой итерации основная
  не читалась/не менялась; соседний test и общие FPM/master/cron/MySQL не трогали.
- Очистка заявок не разрешает удаление таблиц/схемы/кода/аккаунтов/профилей/auth/
  приглашений/аудита/конфигурации/секретов/backup/инфраструктуры, даже в репетиции.
  Для жизненно важных компонентов отдельная задача, объекты, последствия,
  восстановление, явное согласование. Старое разрешение трех backup-дубликатов
  исполнено; новых удалений не разрешает. В этом выпуске auth-контроллер/проверки,
  аккаунты, данные и схема не менялись; изменен только mailer существующего
  метода отправки кода согласно поручению. Debt-off обязателен в новых пакетах.

Статус сохранять в Git/README/новом handoff с code/CI/deploy/backup/проверками,
ручным остатком и границами систем. Секреты/OTP/JWT/plaintext backups не публиковать.
