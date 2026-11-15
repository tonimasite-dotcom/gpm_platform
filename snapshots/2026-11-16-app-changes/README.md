# Компактная точка продолжения GPM

Состав: изменения приложения и контекст. Полных копий TS/CRM/серверов и БД нет.
Актуальное состояние и ограничения описаны в корневом handoff от 16 ноября.
Доступ к GitHub и отдельный recovery-ключ необходимы для частного архива.
Ключ `RECOVERY-KEY-KEEP-SEPARATELY.txt` хранится у владельца отдельно;
его нет в GitHub. Переносите его безопасно, не через сообщения чата.

Сначала получите ветку репозитория обычным git clone/checkout.
Для архива установите age из официального https://github.com/FiloSottile/age/releases.
Git Credential Manager должен иметь доступ к репозиторию; допустим GH_TOKEN
в окружении. Скрипт не выводит credential и не передает его хранилищу редиректа.

Из корня чистого checkout:

```powershell
python scripts/download_session_snapshot.py --manifest snapshots/2026-11-16-app-changes/ARTIFACTS.json --directory .tmp/session-download
```

Проверка/восстановление в НОВУЮ пустую директорию (замените пути к age и ключу):

```powershell
python scripts/session_snapshot.py unpack --archive .tmp/session-download/GPM_APPLICATION_CHANGES_CONTEXT_20261116.tar.gz.age --sha256 d5544e5ba55fda438933351d82ac64adf24757eafb93c849b1167aeafb910d95 --age C:/tools/age.exe --identity C:/private/RECOVERY-KEY-KEEP-SEPARATELY.txt --directory .tmp/session-restored
```

Сначала выполняется полная проверка SHA/объектов, затем восстанавливаются обычные
файлы. Существующие файлы не перезаписываются, symlinks не активируются,
приложение/БД не запускаются. На Windows создается закрытая ACL-директория.

Откройте `session/SESSION_PRIVATE.md`, затем `session/changes/*/STATE.json`,
STATUS.txt и UNCOMMITTED.patch. Исходный HEAD у каждого рабочего дерева свой.
Файлы в `files/` — непринятые изменения, не автоматический набор для production.
Сопоставьте их с нужным HEAD в отдельном worktree, прежде чем применять.
Полный Git bundle не требуется: исходная история остается в репозитории.
Точные частные пути остались в зашифрованной записке; доступ сервера с другого
устройства предоставляется существующим разрешенным подключением владельца.
