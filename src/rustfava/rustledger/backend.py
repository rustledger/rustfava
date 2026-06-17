"""Select the rustledger engine backend.

The legacy JSON-RPC engine is still the **default**; set
``RUSTFAVA_RUSTLEDGER_BACKEND=component`` to opt into the in-process component
engine (WASI Preview 2 / Component Model, rustledger #1384) during the
dual-ship window. Flipping the default is tracked in #173.

This lives in its own module — not the package ``__init__`` — so call sites can
import :func:`get_engine` at module level without a circular import through the
package.
"""

from __future__ import annotations

import os
from typing import Any

from rustfava.rustledger.engine import RustledgerEngine


def get_engine() -> Any:
    """Return the engine selected by ``RUSTFAVA_RUSTLEDGER_BACKEND``.

    ``component`` selects the in-process component engine (needs the optional
    ``wasmtime`` dependency); anything else keeps the JSON-RPC engine, which
    stays the default during the dual-ship window. If ``wasmtime`` is missing
    the component engine can't be imported, so fall back to JSON-RPC.
    """
    backend = os.environ.get("RUSTFAVA_RUSTLEDGER_BACKEND", "").lower()
    if backend != "component":
        return RustledgerEngine.get_instance()
    try:
        from rustfava.rustledger.component_engine import (  # noqa: PLC0415
            get_component_engine,
        )
    except ImportError:
        return RustledgerEngine.get_instance()
    return get_component_engine()
