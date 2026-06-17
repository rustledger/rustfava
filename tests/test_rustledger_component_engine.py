"""Smoke tests for the experimental Component-Model engine (rustledger #1384).

Skipped unless ``wasmtime`` is installed *and* the wasip2 component artifact is
locatable (bundled next to the engine, or via ``RUSTLEDGER_COMPONENT_WASM``).
Build the component with::

    cargo build -p rustledger-ffi-component --target wasm32-wasip2 --release
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

pytest.importorskip("wasmtime")

# Imported after `importorskip` so the module skips cleanly when the optional
# `wasmtime` dependency is absent (the component engine imports it eagerly).
from rustfava.rustledger.component_engine import _default_wasm_path
from rustfava.rustledger.component_engine import RustledgerComponentEngine
from rustfava.rustledger.options import options_from_json
from rustfava.rustledger.types import directives_from_json


def _component_available() -> bool:
    return _default_wasm_path().exists()


pytestmark = pytest.mark.skipif(
    not _component_available(),
    reason="rustledger wasip2 component artifact not found",
)


@pytest.fixture(scope="module")
def engine() -> RustledgerComponentEngine:
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


# Source with multi-word WIT fields that exercise the marshaller's kebab->snake
# key mapping, the list<tuple>->map conversion, and meta-user flattening.
SRC_RICH = (
    'option "operating_currency" "USD"\n'
    "2024-01-01 open Assets:Cash USD\n"
    "2024-01-01 open Expenses:Food USD\n"
    '2024-01-02 * "Cafe" "Coffee"\n'
    '  category: "dining"\n'
    "  Expenses:Food  5 USD\n"
    "  Assets:Cash\n"
    '2024-01-03 custom "fava-option" "indent" "2"\n'
)


def test_options_marshal_parses_downstream(
    engine: RustledgerComponentEngine,
) -> None:
    """``options`` must use snake_case keys and map shapes that
    ``options_from_json`` accepts (kebab keys / list<tuple> would crash it)."""
    result = engine.load(SRC_RICH)
    opts = result["options"]
    # snake_case key (WIT field is ``operating-currency``).
    assert opts["operating_currency"] == ["USD"]
    # ``display-precision`` is a WIT list<tuple<string,u32>> -> must marshal to
    # a dict so ``options_from_json``'s ``.items()`` does not raise.
    assert isinstance(opts.get("display_precision", {}), dict)
    # The whole object must round-trip through the real downstream parser.
    parsed = options_from_json(opts)
    assert "USD" in parsed["operating_currency"]


def test_entries_marshal_parse_downstream(
    engine: RustledgerComponentEngine,
) -> None:
    """Marshalled entries must parse via ``directives_from_json`` and carry
    flattened user metadata (the JSON-RPC ``meta`` shape)."""
    result = engine.load(SRC_RICH)
    entries = list(directives_from_json(result["entries"]))
    assert entries  # parses without KeyError

    txn = next(e for e in result["entries"] if e["type"] == "transaction")
    # meta.user is flattened into meta (not nested under a "user" key).
    assert txn["meta"]["category"] == "dining"
    assert "user" not in txn["meta"]
    # multi-word fields survive as snake_case where present.
    assert "lineno" in txn["meta"]
