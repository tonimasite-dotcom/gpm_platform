# GPM Platform Handoff Snapshot - 2026-07-01

## Current State

Project path:

```text
C:\Users\Юра\Desktop\gpm_platform\gpm_platform
```

Repository:

```text
https://github.com/tonimasite-dotcom/gpm_platform.git
```

Current local branch:

```text
main
```

Git status at snapshot time:

```text
## main...origin/main
```

No local uncommitted changes were present when this handoff file was created.

Latest commits:

```text
8a8c02e (HEAD -> main, origin/main) Add order-based chat MVP
62bb2db Add branded order form shell
70b47b6 Initial project commit
```

Remote branch SHAs:

```text
main     8a8c02e6a495142a3ceeb473420fd2e93a5dcf85
gh-pages 03283371aba2ed8a150a9c0941ba25dc68dd00dc
```

## What Was Built

The app is a Flutter web/mobile prototype for GPM Platform with role switching:

- Client
- Worker / performer
- Logist

The app currently uses demo/local behavior, not production backend auth or realtime sync.

## Brand/UI Work Completed

The application was adapted toward the GPM visual style:

- Red primary accent
- Yellow CTA buttons
- White cards
- Light gray page background
- Black bold typography
- GPM header with logo and role switcher
- The top gray contact strip was removed at the user's request

Important theme file:

```text
lib/theme/gpm_theme.dart
```

## Chat MVP Completed

Order-based chat MVP was implemented and committed in:

```text
8a8c02e Add order-based chat MVP
```

New/important files:

```text
lib/models/chat_models.dart
lib/services/chat_service.dart
lib/screens/chats/chat_threads_screen.dart
lib/screens/chats/chat_conversation_screen.dart
lib/main.dart
lib/screens/client/client_home_screen.dart
lib/screens/logist/logist_home_screen.dart
lib/screens/worker/worker_home_screen.dart
```

Chat design logic:

- Chats are attached to orders, not to free-form user-to-user conversations.
- Chat thread types:
  - client-logist
  - worker-logist
  - client-worker
  - support / dispute channel
- Client sees chats for own order flow.
- Worker sees relevant worker/logist and assigned order chats.
- Logist sees all operational/support chats.
- A client-worker chat has a support/escalation action to call a logist.
- Logist can close attention signals.
- Archived/completed order chats are read-only.
- System messages are included for audit/context.
- Demo chat data is stored in localStorage via existing demo storage wrappers.

Legal/product reasoning captured in conversation:

- In production, chats likely contain personal data under Russian law.
- Need policy/consent/offers and clear notice that GPM/logists may access order chats for quality control and dispute resolution.
- Production data for Russian citizens should be treated with localization/security requirements in mind.
- Avoid direct phone exchange as primary flow; keep chat inside platform for audit/control.
- Demo is safe as a prototype only; not production messaging infrastructure.

## Checks Performed

Analyzer passed:

```text
flutter analyze
No issues found
```

Release web build passed when output was written to an ASCII-only path:

```text
flutter build web --release --base-href /gpm_platform/ --output C:\tmp\gpm_platform_web
```

Build output folder:

```text
C:\tmp\gpm_platform_web
```

Build folder contents include:

```text
assets
canvaskit
icons
.last_build_id
.nojekyll
favicon.png
flutter.js
flutter_bootstrap.js
flutter_service_worker.js
index.html
main.dart.js
manifest.json
version.json
```

Important Windows/Flutter note:

- `flutter build web` to the project `build` folder previously failed because the project path contains Cyrillic characters: `C:\Users\Юра\...`
- Building to `C:\tmp\gpm_platform_web` works.

## GitHub Pages Deployment State

The `gh-pages` branch was created and pushed successfully.

Public URL intended for demo:

```text
https://tonimasite-dotcom.github.io/gpm_platform/
```

At last check, this URL returned `404`.

GitHub API for Pages also returned `404`, which means GitHub Pages is probably not enabled yet for the repository, even though the `gh-pages` branch exists.

Manual action still needed:

1. Open:

```text
https://github.com/tonimasite-dotcom/gpm_platform/settings/pages
```

2. In **Build and deployment**, set:

```text
Source: Deploy from a branch
Branch: gh-pages
Folder: / (root)
```

3. Click **Save**.

4. Wait 1-3 minutes.

5. Check:

```text
https://tonimasite-dotcom.github.io/gpm_platform/
```

## Security Note

`pubspec.yaml` includes `.env` as an asset:

```yaml
flutter:
  assets:
    - .env
```

For Flutter web, this means `.env` is public in the deployed build under assets.

Current `.env` contains Supabase URL and publishable anon key. Do not put secrets, Bitrix webhooks, private API keys, service-role keys, or tokens in `.env` for web deployment.

## Useful Commands

Check state:

```powershell
git status --short --branch --untracked-files=all
git log -5 --oneline --decorate
flutter analyze
```

Run app locally:

```powershell
flutter run -d chrome --web-port 5050
```

Build demo for GitHub Pages:

```powershell
flutter build web --release --base-href /gpm_platform/ --output C:\tmp\gpm_platform_web
```

Check public demo:

```powershell
Invoke-WebRequest -Uri https://tonimasite-dotcom.github.io/gpm_platform/ -UseBasicParsing -TimeoutSec 20
```

## Suggested Next Steps

1. Enable GitHub Pages from the `gh-pages` branch in repository settings.
2. Verify public demo link.
3. Continue improving chat UX:
   - unread counters;
   - latest message preview;
   - filter for "requires logist attention";
   - role-specific empty states;
   - better mobile layout;
   - message timestamps with date;
   - attachments placeholder policy.
4. Add a product/legal screen:
   - demo disclaimer;
   - personal data note;
   - support access notice.
5. Plan real backend:
   - user auth;
   - order permissions;
   - chat participants;
   - message storage;
   - audit log;
   - data retention;
   - РФ-compliant hosting/storage strategy.

## Continuation Prompt For New Chat

Copy/paste this into a new Codex chat:

```text
We are continuing work on the Flutter project GPM Platform.

Project path:
C:\Users\Юра\Desktop\gpm_platform\gpm_platform

Repository:
https://github.com/tonimasite-dotcom/gpm_platform.git

Current known state:
- Local branch is main.
- main is pushed to origin/main at commit 8a8c02e: "Add order-based chat MVP".
- Working tree was clean when the handoff was created.
- gh-pages branch was pushed at SHA 0328337 with a Flutter web build.
- Intended public demo URL is https://tonimasite-dotcom.github.io/gpm_platform/
- Last check returned 404 because GitHub Pages likely was not enabled in repo settings yet.

Important completed work:
- Branded GPM theme added in lib/theme/gpm_theme.dart.
- Top gray contact strip was removed from the header.
- Role switcher remains in the main header.
- Order-based chat MVP was added:
  - lib/models/chat_models.dart
  - lib/services/chat_service.dart
  - lib/screens/chats/chat_threads_screen.dart
  - lib/screens/chats/chat_conversation_screen.dart
- Chat tabs were added to client, worker, and logist home screens.
- Chat model:
  - client-logist
  - worker-logist
  - client-worker
  - support/dispute channel
- Chats are order-based, stored in localStorage for demo, and include support escalation to logist.
- flutter analyze passed with no issues.
- Release web build works when output is C:\tmp\gpm_platform_web.
- Regular build inside the project path can fail because the Windows path contains Cyrillic characters.

Need to continue from here:
1. First check git status and logs.
2. Check whether GitHub Pages is now enabled and whether https://tonimasite-dotcom.github.io/gpm_platform/ works.
3. If Pages still returns 404, guide me to enable Pages from branch gh-pages / root in GitHub settings, or find another way to enable it if tools allow.
4. After public demo is available, continue improving the chat MVP and demo presentation without breaking existing functionality.

Important security note:
pubspec.yaml includes .env as a Flutter asset, so it is public in web builds. Do not put secrets, private Bitrix webhooks, service-role keys, or private tokens in .env for the web demo.

Please proceed carefully: inspect the repo first, preserve user changes, run flutter analyze after code changes, and prefer small safe commits.
```
