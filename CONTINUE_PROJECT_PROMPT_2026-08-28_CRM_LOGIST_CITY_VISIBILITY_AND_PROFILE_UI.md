# Промт для продолжения проекта GPM

Работай в репозитории:

```text
C:\Users\Юра\Desktop\gpm_platform\gpm_platform
```

Дата контекста: 28.08.2026, Europe/Moscow.

Сначала полностью прочитай:

```text
PROJECT_HANDOFF_2026-08-28_CRM_LOGIST_CITY_VISIBILITY_AND_PROFILE_UI.md
DESIGN_FREEZE.md
INDEPENDENT_PLATFORM_ARCHITECTURE.md
WORKER_PROFILE_VERIFICATION.md
CRM_APP_PUBLICATION.md
README.md
```

Старый файл
`PROJECT_HANDOFF_2026-08-28_CURRENT_PRODUCTION_AND_CRM_RECOVERY.md` используй
только как подробную историческую справку по production и инфраструктуре. Его
описание CRM token mismatch устарело: безопасная синхронная ротация уже
завершена, синтетический POST дал `200 OK`, секреты в документах отсутствуют.

## Обязательная стартовая read-only проверка

Выполни:

```powershell
git status --short --branch
git rev-parse HEAD
git rev-parse origin/feature/crm-logist-city-visibility
git rev-parse origin/main
git log --oneline --decorate -5
```

Ожидаемая точка до commit этого handoff:

```text
branch: feature/crm-logist-city-visibility
feature code HEAD: a4433992298fffccbd8b09b863e82fbffb3807ff
origin/main: d5fb364a8e8db2b3abba6aabb9106e70f4bc6832
```

Сам handoff будет добавлен следующим commit, поэтому фактический HEAD должен
быть потомком `a443399`. Working tree должен быть clean, local и remote feature
должны совпадать. Если это не так, сначала изучи расхождение и не стирай чужие
изменения.

Кратко сообщи владельцу результаты проверки и продолжи задачу ниже. Повторное
подтверждение реализации не требуется: пользователь уже явно её запросил.

## Текущая задача

В профиле логиста:

1. полностью убрать видимое поле Telegram;
2. Email оставить, но сделать необязательным;
3. «Города и районы» оставить, но пока сделать необязательным.

Активный UI-файл:

```text
lib/screens/logist/logist_profile_screen.dart
```

Уже установлено read-only инспекцией:

- `_telegramController` объявлен, загружается, сохраняется, dispose-ится и
  используется в `TextFormField`;
- Email имеет required-validator с текстом `Укажите email`;
- города имеют required-validator с текстом `Укажите зону работы`;
- `app/app_orders_api.py::_profile_completion` для логиста сейчас требует
  `display_name`, `email`, `cities`.

Реализуй без редизайна:

- удалить Telegram из UI и из patch, отправляемого при сохранении профиля;
- удалить controller/load/dispose Telegram;
- не делать массовую очистку исторических серверных значений без отдельного
  запроса;
- убрать required-validator с Email и городов логиста;
- при необходимости пометить labels как необязательные, сохранив существующий
  стиль;
- изменить backend completion логиста на обязательные `display_name` и `phone`,
  потому что телефон нужен для строгой CRM-привязки;
- не менять профиль исполнителя: его `cities` остаются обязательными для
  фильтрации доступных заказов;
- добавить/обновить тесты.

После изменения запусти:

```powershell
dart format lib/screens/logist/logist_profile_screen.dart
python -m unittest tests.test_app_orders_api
flutter analyze
flutter test --no-pub
flutter build web --release --output C:\tmp\gpm-logist-profile-optional-web
git diff --check
```

Если formatter зависнет из-за Flutter/Dart lock, безопасно диагностируй процесс
и не удаляй широкие каталоги. Release output находится вне репозитория.

Сделай отдельный commit в текущей feature-ветке, push и дождись green CI.
Не сливай в `main` и не выполняй production deploy без отдельного явного
подтверждения владельца.

## Уже реализовано в feature, не переделывать

- CRM-заказ строго привязывается к одному активному логисту по телефону профиля;
- каждый логист видит, изменяет и обсуждает только свои CRM-заказы;
- общей CRM-очереди нет;
- клиент видит только собственные заказы, публикует их, принимает/отклоняет
  отклики и принимает завершение;
- исполнитель видит опубликованные заказы только из выбранных им городов;
- несколько городов исполнителя поддерживаются;
- прямой API-отклик на заказ другого города запрещён;
- dashboard и чаты изолированы по ownership;
- реальная оплата пока не реализована.

Feature commits:

```text
5913e64 Restore CRM order publication by logist
a443399 Enforce order ownership and city visibility
```

Локальные проверки `a443399`: backend 26 passed/1 skipped, Flutter analyze clean,
Flutter tests 5 passed, release web build successful, GitHub CI passing.

## Production и CRM

Production code остаётся на `597a9d2`. `main` содержит более новый
documentation-only commit `d5fb364`. Feature ещё не развёрнута.

CRM token recovery завершён:

```text
both token lengths: 64
final fingerprint: be2eaccb8509
synthetic CRM POST: 200 OK
synthetic order status: NEW
```

Никогда не выводи сам token и не читай populated env в ответ. Не восстанавливай
исторические значения. Регистрация логистов явно отложена пользователем.

## Постоянные ограничения

- Действует `DESIGN_FREEZE.md`.
- Не менять цвета, навигацию, компоновку и визуальный язык.
- GPM работает самостоятельно без Telegram и других мессенджеров.
- Не включать legacy bot или `/api/telegram/`.
- Не возвращать Email в профиль исполнителя.
- Не использовать реальные ПДн до закрытия P0.
- Не добавлять secrets, токены, ключи и пароли в Git, вывод или документацию.
- Не трогать несвязанные пользовательские изменения.
- Production deploy — только по отдельному явному запросу.
