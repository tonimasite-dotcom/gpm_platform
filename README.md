# GPM Platform

Flutter prototype for the GPM Platform demo.

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
