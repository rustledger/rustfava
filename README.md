<div align="center">

# rustfava

**A beautiful desktop app for [rustledger](https://github.com/rustledger/rustledger)**

Manage your finances with plain text accounting.

[![CI](https://github.com/rustledger/rustfava/actions/workflows/ci.yml/badge.svg)](https://github.com/rustledger/rustfava/actions/workflows/ci.yml)
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

| Platform | Download |
|----------|----------|
| **macOS** | [`rustfava_0.1.0_aarch64.dmg`](https://github.com/rustledger/rustfava/releases/download/v0.1.0/rustfava_0.1.0_aarch64.dmg) |
| **Windows** | [`rustfava_0.1.0_x64-setup.exe`](https://github.com/rustledger/rustfava/releases/download/v0.1.0/rustfava_0.1.0_x64-setup.exe) |
| **Linux** | [`rustfava_0.1.0_amd64.AppImage`](https://github.com/rustledger/rustfava/releases/download/v0.1.0/rustfava_0.1.0_amd64.AppImage) |
| **Docker** | `docker run -p 5000:5000 -v /path/to/ledger:/data ghcr.io/rustledger/rustfava /data/main.beancount` |
| **PyPI** | `uv tool install rustfava` (requires Python 3.13+ and [wasmtime](https://wasmtime.dev/)) |

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
