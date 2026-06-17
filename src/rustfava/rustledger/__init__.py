"""Rustledger WASM integration for Fava.

This module provides a Python interface to rustledger via wasmtime-py,
replacing beancount for parsing, validation, and querying.
"""

from __future__ import annotations

import os
from typing import Any

from rustfava.rustledger.engine import RustledgerEngine
from rustfava.rustledger.loader import load_string
from rustfava.rustledger.loader import load_uncached


def get_engine() -> Any:
    """Return the engine named by ``RUSTFAVA_RUSTLEDGER_BACKEND``.

    ``component`` selects the experimental in-process WASI Preview 2 /
    Component-Model engine (needs the ``component`` extra: ``wasmtime``);
    anything else (the default) keeps the JSON-RPC :class:`RustledgerEngine`.
    The component module — and so ``wasmtime`` — is imported lazily, so the
    default path keeps no extra dependency.
    """
    backend = os.environ.get("RUSTFAVA_RUSTLEDGER_BACKEND", "").lower()
    if backend == "component":
        from rustfava.rustledger.component_engine import (  # noqa: PLC0415
            get_component_engine,
        )

        return get_component_engine()
    return RustledgerEngine.get_instance()


def is_encrypted_file(path: str) -> bool:
    """Check if a file is GPG encrypted.

    Args:
        path: Path to file

    Returns:
        True if file is encrypted
    """
    return RustledgerEngine.get_instance().is_encrypted(path)


__all__ = [
    "RustledgerEngine",
    "get_engine",
    "is_encrypted_file",
    "load_string",
    "load_uncached",
]
