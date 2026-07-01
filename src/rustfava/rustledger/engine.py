"""Shared rustledger FFI constants, errors, and api_version validation.

The in-process Component-Model engine
(:mod:`rustfava.rustledger.component_engine`) is the sole rustledger backend.
This module holds the pieces that are not specific to it: the pinned release
version, the error types, and the ``api_version`` compatibility check. The
legacy wasmtime-CLI JSON-RPC engine was removed once the wasip1 JSON-RPC
embedding surface (and its ``rustledger-ffi-wasi-*.wasm`` release artifact) was
retired upstream (rustledger #1419 / rustfava #173).
"""

from __future__ import annotations

# The major version of the rustledger FFI ``api_version`` this build of
# rustfava understands. Minor versions are additive and backward compatible,
# so a higher minor (e.g. 3.1 against an expected 3.0) is accepted; a different
# major is a wire-format break and is rejected. Tracks the
# ``rustledger:ledger`` WIT package major (major-on-break, negotiated from the
# component's ``version()``).
SUPPORTED_API_MAJOR = 3

# Rustledger release this build is pinned to. The component wasm
# (``rustledger-ffi-component-<version>.wasm``) is downloaded lazily from this
# release by ``component_engine``. Bumped by ``update-rustledger.yml``.
RUSTLEDGER_VERSION = "v0.18.0"


class RustledgerError(Exception):
    """Error from rustledger execution."""


class RustledgerAPIVersionError(RustledgerError):
    """Incompatible API version from rustledger."""


def _check_api_version(api_version: object) -> None:
    """Validate the FFI ``api_version`` carried on a response.

    Minor versions are additive and backward compatible, so any version that
    shares :data:`SUPPORTED_API_MAJOR` is accepted (a higher minor such as
    ``3.1`` against an expected ``3.0`` is fine). A different major is a
    wire-format break and is rejected. Responses without an ``api_version``
    (not every method returns one) are left unchecked.

    Raises:
        RustledgerAPIVersionError: If the major version is incompatible or
            cannot be parsed.
    """
    if api_version is None:
        return
    major_token = str(api_version).split(".", 1)[0]
    try:
        major = int(major_token)
    except ValueError:
        msg = (
            f"Unparseable rustledger API version {api_version!r}; "
            f"this rustfava build supports {SUPPORTED_API_MAJOR}.x"
        )
        raise RustledgerAPIVersionError(msg) from None
    if major != SUPPORTED_API_MAJOR:
        msg = (
            f"Unsupported rustledger API version {api_version!r}; "
            f"this rustfava build supports {SUPPORTED_API_MAJOR}.x"
        )
        raise RustledgerAPIVersionError(msg)
