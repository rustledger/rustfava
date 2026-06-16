"""Smoke tests for the experimental Component-Model engine (rustledger #1384).

Skipped unless ``wasmtime`` is installed *and* the wasip2 component artifact is
locatable (bundled next to the engine, or via ``RUSTLEDGER_COMPONENT_WASM``).
Build the component with::

    cargo build -p rustledger-ffi-component --target wasm32-wasip2 --release
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("wasmtime")

if TYPE_CHECKING:
    from rustfava.rustledger.component_engine import RustledgerComponentEngine


def _component_available() -> bool:
    from rustfava.rustledger.component_engine import (  # noqa: PLC0415
        _default_wasm_path,
    )

    return _default_wasm_path().exists()


pytestmark = pytest.mark.skipif(
    not _component_available(),
    reason="rustledger wasip2 component artifact not found",
)


@pytest.fixture(scope="module")
def engine() -> RustledgerComponentEngine:
    from rustfava.rustledger.component_engine import (  # noqa: PLC0415
        RustledgerComponentEngine,
    )

    return RustledgerComponentEngine()


SRC = (
    "2024-01-01 open Assets:Cash USD\n"
    "2024-01-01 open Expenses:Food USD\n"
    '2024-01-02 * "Coffee"\n'
    "  Expenses:Food  5 USD\n"
    "  Assets:Cash\n"
)


def test_version(engine: RustledgerComponentEngine) -> None:
    assert engine.version() == "2.1"


def test_load_marshals_typed_directives(
    engine: RustledgerComponentEngine,
) -> None:
    result = engine.load(SRC)
    assert set(result) >= {"entries", "errors", "options"}
    assert len(result["entries"]) == 3
    assert result["errors"] == []
    # The generic marshaller renders the directive variant as a tagged dict.
    txn = next(e for e in result["entries"] if e["type"] == "transaction")
    assert txn["narration"] == "Coffee"
    assert len(txn["postings"]) == 2


def test_query(engine: RustledgerComponentEngine) -> None:
    result = engine.query(SRC, "SELECT account, position")
    assert [c["name"] for c in result["columns"]] == ["account", "position"]
    assert len(result["rows"]) >= 1
    # Each cell is a discriminated ``{"type": ...}`` value.
    assert result["rows"][0][0]["type"] == "text"


def test_get_account_type(engine: RustledgerComponentEngine) -> None:
    assert engine.get_account_type("Assets:Cash") == "assets"
    assert engine.get_account_type("Frobnicate:X") == "unknown"


def test_load_full_resolves_includes(
    engine: RustledgerComponentEngine,
) -> None:
    with tempfile.TemporaryDirectory() as d:
        Path(d, "sub.bean").write_text("2024-01-01 open Assets:Bank USD\n")
        Path(d, "main.bean").write_text(
            'include "sub.bean"\n2024-01-02 open Expenses:Rent USD\n',
        )
        result = engine.load_full(str(Path(d, "main.bean")))
    assert result["errors"] == []
    assert len(result["entries"]) >= 2  # include resolved over WASI preopen
