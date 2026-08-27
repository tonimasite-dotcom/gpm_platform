# Как продолжить GPM на новом устройстве

## 1. Что перенести

Переносите отдельно:

1. Код — через GitHub.
2. Пароли — через менеджер паролей или зашифрованный носитель.
3. SSH-ключ — только если нужен прямой доступ к серверу.

Не копируйте старую рабочую папку как источник истины. Не отправляйте секреты
по почте, в чат или обычное облако.

Для штатного деплоя локальный SSH-ключ не нужен: GitHub Actions уже использует
secrets environment `production`.

## 2. Установить инструменты

Нужны:

- Git;
- Flutter `3.38.5`;
- Python `3.10+`;
- Chrome;
- редактор кода;
- доступ к GitHub-репозиторию.

Проверка:

```powershell
git --version
flutter --version
python --version
```

## 3. Скачать проект

Выберите обычный ASCII-путь. Это избавит Flutter Web от ошибки шейдеров на
Windows.

```powershell
New-Item -ItemType Directory -Force C:\src
Set-Location C:\src
git clone https://github.com/tonimasite-dotcom/gpm_platform.git
Set-Location C:\src\gpm_platform
git checkout main
git pull --ff-only origin main
```

Проверка:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
git log -5 --oneline
```

Ожидается чистый `main`. HEAD будет не ниже frontend production-коммита
`b9ebdfa`. Документационный snapshot-коммит может быть новее и не требует
redeploy. Backend production остаётся на `a6fac5c`, пока не опубликовано более
новое backend-изменение.

## 4. Прочитать точку продолжения

В этом порядке:

```text
PROJECT_HANDOFF_2026-08-27_WORKER_DESIGN_RELEASE.md
CONTINUE_PROJECT_PROMPT_2026-08-27_WORKER_DESIGN_RELEASE.md
README.md
PROJECT_AUDIT_2026-08-25.md
LEGAL_READINESS_RU.md
PRODUCTION_DEPLOYMENT.md
```

Старые handoff-файлы нужны только для истории.

## 5. Проверить проект

```powershell
flutter pub get
flutter analyze --no-pub
flutter test --no-pub
python -m pip install -r requirements-api.lock
python -m unittest discover -s tests -p "test_*.py" -v
git diff --check
```

PostgreSQL integration test полностью выполняется в GitHub CI. Локально без
`GPM_TEST_POSTGRES_URL` один тест будет пропущен.

## 6. Запустить frontend против production API

Создайте локальный `.env` только с публичными значениями:

```text
GPM_APP_MODE=api
GPM_APP_API_URL=https://app-api.gpmbot.ru
```

Запуск:

```powershell
flutter run -d chrome --web-port 8090
```

Production CORS разрешает `http://localhost:8090` и
`http://127.0.0.1:8090`.

Не добавляйте в Flutter `.env` пароль, токен, JWT secret или API secret: web
asset видит любой посетитель.

## 7. Получить тестовые логины

Username ролей:

```text
client
worker
logist
```

Паролей в Git нет. Возьмите их из менеджера паролей. Если защищённой копии нет,
сначала получите разрешение владельца, затем восстановите значения из закрытого
server storage напрямую в защищённый буфер. Не выводите их в терминал или чат.

Server locations указаны только как ориентир администратору:

```text
/root/gpm-app-login.txt
/root/gpm-app-env
```

## 8. Начать работу

```powershell
git checkout main
git pull --ff-only origin main
git checkout -b feature/<короткое-имя-задачи>
```

Работайте одной задачей. Перед коммитом:

```powershell
python -m unittest discover -s tests -p "test_*.py"
flutter analyze --no-pub
flutter test --no-pub
git diff --check
git status --short
```

После push дождитесь зелёного CI. Не сливайте красную ветку.

## 9. Production-деплой

Только по явному запросу владельца:

1. Убедиться, что `main` чист и совпадает с `origin/main`.
2. Зафиксировать текущий production SHA.
3. Перед схемой/данными создать и проверить отдельный `pg_dump`.
4. Открыть GitHub → Actions → Deploy production.
5. Выбрать branch `main`, target `all`, `backend` или `frontend`.
6. Дождаться `success`.
7. Проверить frontend, `/health`, входы и изменённые ролевые endpoints.
8. Записать run ID и пути backup в handoff.

Workflow хранит rollback кода, venv и frontend. Он не заменяет backup БД.

## 10. Если новый чат ничего не знает

Откройте файл:

```text
CONTINUE_PROJECT_PROMPT_2026-08-27_WORKER_DESIGN_RELEASE.md
```

Скопируйте его целиком в новый чат. После read-only проверки выберите одну
следующую задачу.
