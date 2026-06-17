"""Smoke tests for the experimental Component-Model engine (rustledger #1384).

Skipped unless ``wasmtime`` is installed *and* the wasip2 component artifact is
locatable (bundled next to the engine, or via ``RUSTLEDGER_COMPONENT_WASM``).
Build the component with::

    cargo build -p rustledger-ffi-component --target wasm32-wasip2 --release
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from rustfava.rustledger.engine import RustledgerEngine

pytest.importorskip("wasmtime")

# Imported after `importorskip` so the module skips cleanly when the optional
# `wasmtime` dependency is absent (the component engine imports it eagerly).
from rustfava.rustledger import component_engine
from rustfava.rustledger.component_engine import _default_wasm_path
from rustfava.rustledger.component_engine import RustledgerComponentEngine
from rustfava.rustledger.engine import RustledgerError
from rustfava.rustledger.options import options_from_json
from rustfava.rustledger.types import directives_from_json
from rustfava.rustledger.types import directives_to_json


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


# Two transactions either side of a clamp window, the in-window one carrying
# user metadata, a tag/link, and a posting cost — the round-trip's hard cases.
SRC_CLAMP = (
    "2023-01-01 open Assets:Cash USD\n"
    "2023-01-01 open Expenses:Food USD\n"
    '2023-06-15 * "Old"\n'
    "  Expenses:Food  5 USD\n"
    "  Assets:Cash\n"
    '2024-02-10 * "Coffee" #tag ^link\n'
    '  category: "groceries"\n'
    "  rank: 3\n"
    "  Expenses:Food  7 USD {2 USD}\n"
    "  Assets:Cash  -14 USD\n"
)
_CLAMP_BEGIN, _CLAMP_END = "2024-01-01", "2024-12-31"


def test_clamp_entries_round_trips_directives(
    engine: RustledgerComponentEngine,
) -> None:
    """``clamp_entries`` marshals already-loaded directives back into the
    component (via ``_unmarshal``) and preserves metadata, tags, and cost."""
    entries = engine.load(SRC_CLAMP)["entries"]
    clamped = engine.clamp_entries(entries, _CLAMP_BEGIN, _CLAMP_END)[
        "entries"
    ]

    # The in-window transaction survives, with user metadata, tag/link, and
    # the posting cost intact through the dict -> typed -> dict round-trip.
    coffee = next(e for e in clamped if e.get("narration") == "Coffee")
    assert coffee["meta"]["category"] == "groceries"
    # Numeric metadata round-trips as a decimal string — matching the JSON-RPC
    # surface, which also emits `MetaValue::Number` as a string for precision.
    assert coffee["meta"]["rank"] == "3"
    assert coffee["tags"] == ["tag"]
    assert coffee["links"] == ["link"]
    cost = coffee["postings"][0]["cost"]
    # Cost number is `kind`-tagged (matching the JSON-RPC surface, which Fava's
    # `cost_number_values` reads); emitting the generic `type` here silently
    # drops the cost basis downstream.
    assert cost["number"] == {"kind": "per_unit", "value": "2"}
    assert cost["currency"] == "USD"

    # Output still parses through the real downstream directive parser.
    assert list(directives_from_json(clamped))


def test_clamp_entries_via_directives_to_json_preserves_cost(
    engine: RustledgerComponentEngine,
) -> None:
    """Exercise the *real* caller's path: ``core/filters.py`` feeds
    ``directives_to_json(entries)`` (not raw ``load`` output) into
    ``clamp_entries``. Regression for the cost-basis loss caused by the
    ``type`` vs ``kind`` discriminator mismatch — the round-trip below dropped
    the cost number entirely before the fix."""
    loaded = engine.load(SRC_CLAMP)["entries"]
    fava_entries = list(directives_from_json(loaded))
    prod_input = directives_to_json(fava_entries)  # what filters.py passes

    # The load -> from_json -> to_json chain must keep the cost number.
    in_coffee = next(e for e in prod_input if e.get("narration") == "Coffee")
    assert in_coffee["postings"][0]["cost"]["number"] == "2"

    clamped = engine.clamp_entries(prod_input, _CLAMP_BEGIN, _CLAMP_END)[
        "entries"
    ]
    coffee = next(e for e in clamped if e.get("narration") == "Coffee")
    assert coffee["postings"][0]["cost"]["number"] == {
        "kind": "per_unit",
        "value": "2",
    }
    assert coffee["meta"]["category"] == "groceries"


def test_clamp_entries_synthesizes_opening_balance(
    engine: RustledgerComponentEngine,
) -> None:
    """The pre-window transaction is folded into opening-balance directives at
    the boundary rather than appearing verbatim."""
    entries = engine.load(SRC_CLAMP)["entries"]
    clamped = engine.clamp_entries(entries, _CLAMP_BEGIN, _CLAMP_END)[
        "entries"
    ]

    narrations = [
        e.get("narration") for e in clamped if e["type"] == "transaction"
    ]
    assert "Old" not in narrations  # the 2023 txn is summarized, not kept
    # Opening-balance summary directives are synthesized at the window start.
    assert any(n == "Opening balance" for n in narrations)
    assert all(
        e["date"] >= _CLAMP_BEGIN
        for e in clamped
        if e["type"] == "transaction"
    )


def test_clamp_entries_matches_jsonrpc_engine() -> None:
    """Cross-engine parity: component ``clamp_entries`` must agree with the
    JSON-RPC engine. Skipped when the wasmtime CLI (JSON-RPC backend) is
    unavailable — the component path is still covered by the tests above."""
    try:
        jsonrpc = RustledgerEngine.get_instance()
        jr_clamped = jsonrpc.clamp_entries(
            jsonrpc.load(SRC_CLAMP)["entries"], _CLAMP_BEGIN, _CLAMP_END
        )["entries"]
    except Exception as exc:  # noqa: BLE001 - CLI absence is the expected skip
        pytest.skip(f"JSON-RPC engine unavailable: {exc}")

    component = RustledgerComponentEngine()
    co_clamped = component.clamp_entries(
        component.load(SRC_CLAMP)["entries"], _CLAMP_BEGIN, _CLAMP_END
    )["entries"]

    def _norm(entries: object) -> str:
        return json.dumps(entries, sort_keys=True, default=str)

    assert _norm(co_clamped) == _norm(jr_clamped)


def test_load_full_returns_host_paths(
    engine: RustledgerComponentEngine,
    tmp_path: Path,
) -> None:
    """``load_full`` must map WASI guest paths back to real host paths.

    The component sees files under the ``/work`` pre-open mount; Fava opens the
    returned ``meta.filename`` to edit entries, so a ``/work/...`` path would
    not exist on disk (regression: file edits hit FileNotFoundError)."""
    main = tmp_path / "main.bean"
    main.write_text("2024-01-01 open Assets:Cash USD\n")
    result = engine.load_full(str(main))

    filenames = {e["meta"]["filename"] for e in result["entries"]}
    assert filenames == {str(main)}
    assert not any(f.startswith("/work") for f in filenames)


def test_custom_typed_values_use_jsonrpc_shape(
    engine: RustledgerComponentEngine,
) -> None:
    """``custom`` directive args marshal to the JSON-RPC ``{type, value}``
    shape (amount un-nested), which Fava's ``RLCustomValue`` reads. The generic
    record marshalling would emit ``{value_type, value: {type: ...}}``."""
    src = (
        "2024-01-01 open Expenses:Groceries USD\n"
        '2024-01-01 custom "budget" Expenses:Groceries "weekly" 100.00 USD\n'
    )
    custom = next(
        e for e in engine.load(src)["entries"] if e["type"] == "custom"
    )
    assert custom["values"] == [
        {"type": "account", "value": "Expenses:Groceries"},
        {"type": "string", "value": "weekly"},
        {"type": "amount", "value": {"number": "100.00", "currency": "USD"}},
    ]


def test_clamp_preserves_custom_typed_values(
    engine: RustledgerComponentEngine,
) -> None:
    """A ``custom`` directive round-trips through ``clamp_entries`` (the
    ``typed-value`` unmarshal path) with its typed args intact."""
    src = (
        "2024-01-01 open Expenses:Groceries USD\n"
        '2024-06-01 custom "budget" Expenses:Groceries "weekly" 50.00 USD\n'
    )
    entries = engine.load(src)["entries"]
    clamped = engine.clamp_entries(entries, "2024-01-01", "2024-12-31")[
        "entries"
    ]
    custom = next(e for e in clamped if e["type"] == "custom")
    assert {
        "type": "amount",
        "value": {"number": "50.00", "currency": "USD"},
    } in (custom["values"])


def test_query_entries_matches_source_query(
    engine: RustledgerComponentEngine,
) -> None:
    """`query_entries` queries an already-loaded directive set directly (the
    typed alternative to re-rendering entries to source), matching `query`."""
    entries = engine.load(SRC)["entries"]
    via_entries = engine.query_entries(entries, "SELECT account, position")
    via_source = engine.query(SRC, "SELECT account, position")
    assert via_entries["errors"] == []
    assert via_entries["rows"]
    assert len(via_entries["rows"]) == len(via_source["rows"])
    assert [c["name"] for c in via_entries["columns"]] == [
        c["name"] for c in via_source["columns"]
    ]


def test_open_session_runs_query_filter_clamp(
    engine: RustledgerComponentEngine,
) -> None:
    """`open_session` holds the booked ledger; query/filter/clamp run against
    it server-side (no re-parse, no directive round-trip), and clamp keeps the
    cost basis (it runs on the held core directives)."""
    session = engine.open_session(SRC_CLAMP)

    info = session.info()
    assert info["errors"] == []
    assert len(info["entries"]) == len(engine.load(SRC_CLAMP)["entries"])

    q = session.query("SELECT account, position")
    assert q["errors"] == []
    assert q["rows"]

    kept = session.filter(_CLAMP_BEGIN, _CLAMP_END)
    narrs = [e.get("narration") for e in kept if e["type"] == "transaction"]
    assert "Coffee" in narrs
    assert "Old" not in narrs

    clamped = session.clamp(_CLAMP_BEGIN, _CLAMP_END)
    coffee = next(e for e in clamped if e.get("narration") == "Coffee")
    assert coffee["postings"][0]["cost"]["number"] == {
        "kind": "per_unit",
        "value": "2",
    }


def test_open_session_file_returns_host_paths(
    engine: RustledgerComponentEngine,
    tmp_path: Path,
) -> None:
    """A file-loaded session resolves WASI guest paths back to host paths in
    `info()`, just like `load_full`."""
    main = tmp_path / "main.bean"
    main.write_text("2024-01-01 open Assets:Cash USD\n")
    session = engine.open_session_file(str(main))
    info = session.info()
    assert {e["meta"]["filename"] for e in info["entries"]} == {str(main)}


def test_missing_wasm_download_fallback_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A missing wasm whose download fails surfaces a clear build-from-source
    error (e.g. when the pinned release predates the component artifact)."""
    monkeypatch.delenv("RUSTLEDGER_COMPONENT_WASM", raising=False)
    missing = tmp_path / "absent.wasm"
    monkeypatch.setattr(
        component_engine,
        "_default_wasm_path",
        lambda: missing,
    )
    # Simulate a failed/404 download that leaves no file behind.
    monkeypatch.setattr(
        component_engine,
        "_download_component_wasm",
        lambda _p: None,
    )
    with pytest.raises(RustledgerError, match="wasm32-wasip2"):
        component_engine.RustledgerComponentEngine()
