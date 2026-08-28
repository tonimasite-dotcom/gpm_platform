Продолжаем работу над GPM platform (Flutter web/Android + FastAPI + PostgreSQL,
репозиторий `tonimasite-dotcom/gpm_platform`).

Полный контекст — в `PROJECT_HANDOFF_2026-08-28_LOGIST_PROFILE_LIVE_CRM_OWNERSHIP_PENDING.md`
в корне репозитория. Прочитай его целиком первым делом, это главный источник
истины. Более старые `PROJECT_HANDOFF_2026-08-28_CRM_LOGIST_CITY_VISIBILITY_AND_PROFILE_UI.md`
и `PROJECT_HANDOFF_2026-08-28_CURRENT_PRODUCTION_AND_CRM_RECOVERY.md` — история,
на них ссылается новый файл, отдельно читать не обязательно.

Коротко, что нужно знать сразу:

1. Задача «убрать Telegram из профиля логиста, сделать Email и Города/районы
   необязательными» — выполнена, закоммичена и уже развёрнута в production
   (`main` @ `411561b01eb5104779b2439296594249aa222008`). Production проверен
   в конце прошлой сессии: backend health ok/postgres, frontend 200.
2. Отдельная, более ранняя фича «CRM ownership по телефону логиста + city
   visibility для исполнителя» (коммиты `5913e64`, `a443399`) существует
   только в ветке `feature/crm-logist-city-visibility`, НЕ в main, НЕ в
   production. Не мержить и не разворачивать без отдельного явного запроса
   владельца — это не следующий шаг по умолчанию.
3. Регистрация логистов — отложена по прямой просьбе владельца, не начинать
   без нового запроса.
4. `DESIGN_FREEZE.md` действует: не менять палитру, навигацию, типографику,
   карточки без отдельного решения владельца.
5. GitHub CLI (`gh`) на машине не установлен. Для GitHub API (например,
   ручной запуск `workflow_dispatch` у `deploy-production.yml`) можно
   использовать токен из git credential manager — см. раздел 3 handoff-файла,
   способ получить токен через `git credential fill` не печатая его значение.
6. Локальный `flutter run -d chrome` для ручной проверки против production API
   обязательно с `--web-port=8090` — backend разрешает CORS только для
   `localhost:8090`/`127.0.0.1:8090`, на другом порту будет `Failed to fetch`.

Первым сообщением, после самостоятельной read-only проверки `git status` /
`git log` / текущей ветки: кратко подтверди, что видишь то же самое (main на
`411561b`, working tree чист), и спроси владельца, что делаем дальше — не
начинай мерж CRM ownership и не предлагай его как следующий шаг по умолчанию.
