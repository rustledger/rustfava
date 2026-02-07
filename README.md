<div align="center">

# rustfava

**A beautiful desktop app for [rustledger](https://github.com/rustledger/rustledger)**

Manage your finances with plain text accounting.

[![CI](https://github.com/rustledger/rustfava/actions/workflows/test.yml/badge.svg)](https://github.com/rustledger/rustfava/actions/workflows/test.yml)
[![GitHub Release](https://img.shields.io/github/v/release/rustledger/rustfava)](https://github.com/rustledger/rustfava/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/rustfava)](https://pypi.org/project/rustfava/)

![rustfava dashboard](docs/screenshot.png)

</div>

---

## Why rustfava?

| | |
|---|---|
| **Native app** | Double-click to launch, no terminal required |
| **Fava interface** | The familiar Fava web UI you know and love |
| **rustledger backend** | Blazing fast parsing via WebAssembly |
| **Cross-platform** | Linux, macOS (Intel & Apple Silicon), Windows |
| **Offline first** | Your financial data stays on your machine |
| **Multiple files** | Open multiple ledgers in tabs |

## Install

### Desktop App

Download the latest release for your platform from the [Releases page](https://github.com/rustledger/rustfava/releases/latest).

| Platform | Format |
|----------|--------|
| **macOS** | `.dmg` (Intel & Apple Silicon) |
| **Windows** | `.exe` installer or `.msi` |
| **Linux** | `.AppImage`, `.deb`, `.rpm`, or `.tar.gz` |

> **Note for Linux deb/rpm users**: The server component requires [wasmtime](https://wasmtime.dev/). Install it with:
> ```bash
> curl https://wasmtime.dev/install.sh -sSf | bash
> ```

### Other Installation Methods

| Method | Command |
|--------|---------|
| **Docker** | `docker run -p 5000:5000 -v /path/to/ledger:/data ghcr.io/rustledger/rustfava /data/main.beancount` |
| **PyPI** | `uv tool install rustfava` (requires Python 3.13+ and [wasmtime](https://wasmtime.dev/)) |
| **Nix** | `nix run github:rustledger/rustfava#desktop` |

<sub>Missing your platform? [Open an issue](https://github.com/rustledger/rustfava/issues/new) to request it.</sub>

## Quick Start

### Desktop App

1. Download the app for your platform
2. Double-click to launch
3. Open your `.beancount` file

### Command Line

```bash
rustfava ledger.beancount
# Then visit http://localhost:5000
```

## What is this?

rustfava is a fork of [Fava](https://github.com/beancount/fava) that replaces the Python beancount parser with [rustledger](https://github.com/rustledger/rustledger), compiled to WebAssembly for faster parsing and processing.

The desktop app bundles everything into a native application using [Tauri](https://tauri.app/), so you get a fast, lightweight app with no dependencies.

## Links

- **Website**: https://rustledger.github.io/rustfava/
- **Documentation**: https://rustledger.github.io/rustfava/docs/
- **rustledger**: https://github.com/rustledger/rustledger

## License

MIT License - see [LICENSE](LICENSE) for details.
