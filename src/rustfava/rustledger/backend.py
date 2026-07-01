"""Resolve the rustledger engine backend.

The in-process component engine (WASI Preview 2 / Component Model, rustledger
#1384) is the only backend. The legacy wasmtime-CLI JSON-RPC engine was removed
once its wasip1 embedding surface was retired upstream (rustledger #1419 /
rustfava #173), so ``RUSTFAVA_RUSTLEDGER_BACKEND`` is no longer consulted.

This lives in its own module — not the package ``__init__`` — so call sites can
import :func:`get_engine` at module level without a circular import through the
package.
"""

from __future__ import annotations

from typing import Any

from rustfava.rustledger.engine import RustledgerError


def get_engine() -> Any:
    """Return the in-process rustledger component engine."""
    try:
        from rustfava.rustledger.component_engine import (  # noqa: PLC0415
            get_component_engine,
        )
    except ImportError as exc:
        # The component backend needs the `wasmtime` Python package, a required
        # rustfava dependency. A missing import means a broken install rather
        # than a configuration choice — fail with an actionable message.
        msg = (
            "The rustledger component backend is unavailable: the `wasmtime` "
            "package could not be imported. Reinstall rustfava (wasmtime is a "
            "required dependency)."
        )
        raise RustledgerError(msg) from exc
    return get_component_engine()
