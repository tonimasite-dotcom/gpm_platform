# GPM Platform

Flutter prototype for the GPM Platform demo.

## Production Direction

The production app should use the GPM backend and its own database as the source
of truth:

```text
External order system -> GPM backend -> PostgreSQL -> Flutter app
```

Bitrix24 is not the core order workflow for this app. See
`PRODUCTION_READINESS.md` for the current transition checklist.

Tracked `app/config.yml` contains placeholders only. Use server environment
variables or ignored `app/config.local.yml` for real credentials. Rotate the
previously tracked credentials listed in `SECRET_ROTATION.md`.

## Live Demo

The demo is intended to be continuously available through GitHub Pages:

```text
https://tonimasite-dotcom.github.io/gpm_platform/
```

Deployment is handled by `.github/workflows/deploy-demo.yml`.

How updates reach the demo:

1. Push changes to `main`.
2. GitHub Actions runs Flutter analyze and builds the web app.
3. The generated `build/web` artifact is published to GitHub Pages.

GitHub repository settings required once:

- Pages source: GitHub Actions.
- Optional repository secret: `DEMO_ENV`.

If `DEMO_ENV` is not set, CI creates an empty `.env` file and the app runs in bundled demo mode.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.
