# GPM на новом компьютере без приватного архива

Актуальная ветка сохранённой работы: `work/tester-feedback-2026-10-13`.
GitHub содержит исходники, тесты и документацию. Архив, действующие локальные
настройки, SSH-ключи, базы, логи и сборки остались на прежнем компьютере.
Подробная точка продолжения — `PROJECT_HANDOFF_2026-10-13_GITHUB_TRANSFER.md`.

Дополнение 15.10: создан отдельный encrypted production backup с проверенным
восстановлением БД. Он не добавлялся в старый полный ZIP. См.
`PRODUCTION_BACKUP_STATUS_2026-10-15.md` и `PRODUCTION_BACKUPS.md`.
При потере прежнего компьютера manual `Recover encrypted backup` позволяет
получить копию под новым локальным age-ключом без публикации прежнего ключа.

## Скачать и подготовить

Нужны Git, Flutter **3.38.5**, Python 3.10+ и Chrome. PHP нужен только для
изолированных проверок CRM-пакета. Использовать ASCII-путь: Flutter shaders
на прежнем Windows-компьютере не собирались в каталоге с кириллицей.

```powershell
git clone --branch work/tester-feedback-2026-10-13 https://github.com/tonimasite-dotcom/gpm_platform.git C:\src\gpm_platform
Set-Location C:\src\gpm_platform
git status --short
git branch --show-current
git log -3 --oneline
```

Ожидается чистая нужная ветка. Для существующей копии сначала проверить и
сохранить её местные изменения; clone поверх непустой папки не выполнять.
Не использовать старую August setup-инструкцию как текущую production-опору.

## Запуск и проверки без секретов

В чистой новой копии создать только публичную demo-конфигурацию. Если `.env`
уже существует, сначала изучить его назначение без вывода секретов; не затирать.

```powershell
if (!(Test-Path -LiteralPath '.env')) {
  Set-Content -LiteralPath '.env' -Value 'GPM_APP_MODE=demo' -Encoding ascii
}
flutter pub get
flutter analyze --no-pub
flutter test --no-pub
flutter run -d chrome --web-port 8090
```

Demo использует локальные вымышленные данные. Backend-проверки используют
временные синтетические БД, не требуют копии действующей SQLite или production.
Для Python удобно отдельное окружение:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-api.lock
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

Локально без `GPM_TEST_POSTGRES_URL` два PostgreSQL-теста пропускаются.
Полная проверка в CI использует отдельную PostgreSQL 17 БД. Локальный DSN
задавать только для изолированной тестовой БД, никогда production.

При установленном PHP:

```powershell
php integrations/workstaff-test-crm/tests/sync_plan_test.php
php integrations/workstaff-test-crm/tests/sync_service_test.php
```

Эти проверки не загружают реальную CRM и не обращаются к её БД/сети.
На старом компьютере `flutter.bat` иногда подвисал; при необходимости можно
запустить Dart/Flutter tools напрямую из установленного SDK (пути локальной
установки определить заново). Release web build также требует обычного
`flutter build web --release --base-href /` после успешных тестов.

`.venv` — локальное окружение, оно игнорируется Git. Не публиковать его.
Токены/пароли/ключи backend никогда не добавлять в Flutter `.env`, который
попадает в публичный asset сборки.

## Где приватные данные

Прежний компьютер: `C:\Users\Юра\Desktop\gpm_platform\gpm_platform`.
Закрытый комплект `.tmp/full-project-snapshot-20261013/`, единый архив:
`GPM_FULL_SNAPSHOT_2026-10-13.zip` (4,55 ГБ), SHA-256:
`aba3bfee2233a3508a9d8c77da59c5612d8785d6bf5fec4ef7f840be51ed4480`.
В комплекте project ZIP/Git bundle, согласованная SQLite, SQL-дамп/файлы/
загрузки тестовой CRM, её Nginx config, manifest и restore-инструкция.
Свежая production-БД GPM в этот комплект не попала из-за отказа SSH.

Ключ `C:\Users\Юра\.ssh\id_ed25519` вне проекта остался на прежнем компьютере,
в архив не включён. Чтобы работать с серверами/реальными аккаунтами, получить
отдельно защищённый доступ; секреты не отправлять в чат или Git. Полный архив
для запуска demo и работы с кодом не нужен.

Для нового чата использовать `CONTINUE_PROJECT_PROMPT_2026-10-13_NEW_COMPUTER.md`.
Настройка production, создание тестового контура, merge в main и включение
CRM sync не входят в первоначальный локальный запуск.
