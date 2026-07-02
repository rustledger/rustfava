Automated update of rustledger to v0.19.0 — **held for human review** (draft, no auto-merge) because:


- release notes contain a conventional-commit breaking marker ( / BREAKING CHANGE)

## What the bot already did
- Bumped `RUSTLEDGER_VERSION` and refreshed the vendored component (sha256-verified)
- Bumped `_WIT_VERSION` to `3.2.0` (if it changed)

## What a human must check
- [ ] New/changed WIT **imports**: does the component need host bindings the linker doesn't define yet? (`wasm-tools component wit` the vendored file; see the `host` interface handling in `component_engine.py`)
- [ ] Run the rustledger test suites locally (`just test-py`)
- [ ] Update marshalling for any changed WIT types

See [rustledger v0.19.0 release notes](https://github.com/rustledger/rustledger/releases/tag/v0.19.0). Context: #218 / #219 / #220.
