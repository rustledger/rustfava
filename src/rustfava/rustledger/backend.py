"""Select the rustledger engine backend.

The in-process component engine (WASI Preview 2 / Component Model, rustledger
#1384) is the **default**; set ``RUSTFAVA_RUSTLEDGER_BACKEND=jsonrpc`` to opt
back into the legacy JSON-RPC engine. The flip is tracked in #173.

This lives in its own module — not the package ``__init__`` — so call sites can
import :func:`get_engine` at module level without a circular import through the
package.
"""

from __future__ import annotations

import os
import shutil
from typing import Any

from rustfava.rustledger.engine import RustledgerEngine
from rustfava.rustledger.engine import RustledgerError

# Values of ``RUSTFAVA_RUSTLEDGER_BACKEND`` that select the legacy engine.
_JSONRPC_ALIASES = frozenset({"jsonrpc", "json-rpc", "json"})


def get_engine() -> Any:
    """Return the engine selected by ``RUSTFAVA_RUSTLEDGER_BACKEND``.

    The in-process component engine is the default; ``jsonrpc`` (or
    ``json-rpc``/``json``) selects the legacy JSON-RPC engine.
    """
    backend = os.environ.get("RUSTFAVA_RUSTLEDGER_BACKEND", "").lower()
    if backend in _JSONRPC_ALIASES:
        return RustledgerEngine.get_instance()
    try:
        from rustfava.rustledger.component_engine import (  # noqa: PLC0415
            get_component_engine,
        )
    except ImportError as exc:
        # The default component backend needs the `wasmtime` Python package.
        # The legacy JSON-RPC engine instead needs an external `wasmtime` CLI
        # binary that most users don't have — silently falling back to it just
        # turns "component unavailable" into a cryptic "wasmtime not found" /
        # "Empty response" later (rustfava #136/#120). Only fall back if the
        # CLI is actually present; otherwise fail with an actionable message.
        if shutil.which("wasmtime"):
            return RustledgerEngine.get_instance()
        msg = (
            "The rustledger component backend is unavailable: the `wasmtime` "
            "package could not be imported. Reinstall rustfava (wasmtime is a "
            "required dependency), or install the wasmtime CLI and set "
            "RUSTFAVA_RUSTLEDGER_BACKEND=jsonrpc."
        )
        raise RustledgerError(msg) from exc
    return get_component_engine()
