# 07 — Deployment & platforms

## The CLI / server

`rustfava [OPTIONS] FILE...` serves one or more ledgers over HTTP.

| Flag | User capability |
|---|---|
| `-p/--port`, `--host` | bind address (default localhost:5000) |
| `--prefix` | serve under a URL prefix (reverse-proxy friendly) |
| `--incognito` | all numbers rendered as XXX (demo/screenshot mode) |
| `--read-only` | every mutating endpoint disabled |
| `--poll-watcher` | polling change detection for filesystems without notify |
| `-d/--debug`, `--profile`, `--profile-dir` | diagnostics |

- Serving multiple files gives a ledger switcher in the UI.
- The `BEANCOUNT_FILE` environment variable can supply the file argument.
- Changes on disk are detected live (see 03, auto-reload).

## Desktop application

A native desktop app (Windows `.msi`/`.exe`, macOS `.dmg` for Intel and
Apple Silicon, Linux `.AppImage`/`.deb`/`.rpm`) that:

- Bundles the whole server (no Python required on the machine).
- Opens ledger files via a native file dialog / OS file association and
  shows the UI in a native window.
- Ships the engine fully embedded, working offline.
- Reports its real version in Help.
- Release artifacts only ship after every platform's binary passes an
  automated start-serve-and-answer-engine-query smoke test.

## Distribution channels

- **PyPI**: `pip/pipx/uv install rustfava` (pure-Python wheel; the engine
  artifact is bundled or fetched on first run).
- **Docker/GHCR**: `ghcr.io/rustledger/rustfava:<version>` (no `v` prefix).
- **COPR** (Fedora), **Nix flake** (`nix run github:rustledger/rustfava`,
  desktop variant included), **FlakeHub**.
- Desktop installers attached to GitHub releases.

## Runtime requirements

- Python 3.13+ for the PyPI package (the desktop app needs nothing).
- System `gpg` only if encrypted ledgers are used.
- Optional extras: spreadsheet export (`excel`), beancount-compat
  (Python plugin/importer interop), ingest tooling.

## Compatibility posture a rewrite must decide on

- Ledger files are 100% standard Beancount syntax — users can move between
  beancount, fava and rustfava freely; nothing rustfava writes locks them in.
- The UI, URL scheme and options are Fava-compatible (rustfava is a Fava
  fork); users coming from Fava expect their bookmarks, options and habits
  to keep working.
- Engine behavior is differentially tested against reference beancount;
  intentional divergences are limited to: native plugin implementations,
  Python-module plugins requiring installation, and exact-decimal JSON.
