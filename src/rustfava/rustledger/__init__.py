"""Rustledger WASM integration for Fava.

This module provides a Python interface to rustledger via wasmtime-py,
replacing beancount for parsing, validation, and querying.
"""

from __future__ import annotations

from rustfava.rustledger.backend import get_engine
from rustfava.rustledger.loader import load_string
from rustfava.rustledger.loader import load_uncached


def is_encrypted_file(path: str) -> bool:
    """Check if a file is GPG encrypted.

    Args:
        path: Path to file

    Returns:
        True if file is encrypted
    """
    return bool(get_engine().is_encrypted(path))


__all__ = [
    "get_engine",
    "is_encrypted_file",
    "load_string",
    "load_uncached",
]
