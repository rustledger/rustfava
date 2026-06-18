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
from typing import Any

from rustfava.rustledger.engine import RustledgerEngine

# Values of ``RUSTFAVA_RUSTLEDGER_BACKEND`` that select the legacy engine.
_JSONRPC_ALIASES = frozenset({"jsonrpc", "json-rpc", "json"})


def get_engine() -> Any:
    """Return the engine selected by ``RUSTFAVA_RUSTLEDGER_BACKEND``.

    The component engine is the default; ``jsonrpc`` (or ``json-rpc``/``json``)
    selects the legacy JSON-RPC engine. If ``wasmtime`` can't be imported the
    component engine is unavailable, so fall back to JSON-RPC rather than crash.
    """
    backend = os.environ.get("RUSTFAVA_RUSTLEDGER_BACKEND", "").lower()
    if backend in _JSONRPC_ALIASES:
        return RustledgerEngine.get_instance()
    try:
        from rustfava.rustledger.component_engine import (  # noqa: PLC0415
            get_component_engine,
        )
    except ImportError:
        return RustledgerEngine.get_instance()
    return get_component_engine()
