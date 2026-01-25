# Welcome to rustfava!

rustfava is a web interface for double-entry bookkeeping, powered by
[rustledger](https://github.com/rustledger/rustledger), a Rust-based parser for
the Beancount file format compiled to WebAssembly for fast processing.

rustfava is a fork of [Fava](https://beancount.github.io/fava/) that replaces
the Python Beancount parser with rustledger for improved performance. Your
existing Beancount files are fully compatible.

![rustfava dashboard](screenshot.png)

If you are new to rustfava or Beancount-format files, begin with the
[Getting Started](usage.md) guide.

## Quick Start

### Desktop App (Recommended)

Download the desktop app from [GitHub Releases](https://github.com/rustledger/rustfava/releases) - no installation required, just double-click to run.

### Command Line

```bash
uv tool install rustfava
rustfava ledger.beancount
```

Then visit [http://localhost:5000](http://localhost:5000).

### Docker

```bash
docker run -p 5000:5000 -v /path/to/ledger:/data ghcr.io/rustledger/rustfava /data/main.beancount
```
