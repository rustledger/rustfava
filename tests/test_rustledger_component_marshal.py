"""Unit coverage for the component engine's marshalling helpers.

Part of the coverage burn-down that reclaimed
``src/rustfava/rustledger/component_engine.py`` into the 100% gate: these
exercise the pure helpers and error/edge branches that the integration tests
(differential corpus, smoke suite) do not reach.
"""

from __future__ import annotations

import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from wasmtime.component import Bool
from wasmtime.component import ListType
from wasmtime.component import OptionType
from wasmtime.component import Record
from wasmtime.component import RecordType
from wasmtime.component import ResultType
from wasmtime.component import String
from wasmtime.component import TupleType
from wasmtime.component import Variant
from wasmtime.component import VariantType

import rustfava.rustledger.component_engine as ce
from rustfava.rustledger.component_engine import _default_wasm_path
from rustfava.rustledger.component_engine import _download_component_wasm
from rustfava.rustledger.component_engine import _drop_none
from rustfava.rustledger.component_engine import _finalize_query_result
from rustfava.rustledger.component_engine import _meta_value_json
from rustfava.rustledger.component_engine import _unwrap_query_value
from rustfava.rustledger.component_engine import RustledgerComponentEngine
from rustfava.rustledger.constants import Missing
from rustfava.rustledger.engine import RustledgerError


def test_wasm_path_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUSTLEDGER_COMPONENT_WASM", "/somewhere/custom.wasm")
    assert _default_wasm_path() == Path("/somewhere/custom.wasm")


def test_download_component_writes_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_retrieve(_url: str, path: str) -> None:
        Path(path).write_bytes(b"wasm")

    monkeypatch.setattr(urllib.request, "urlretrieve", fake_retrieve)
    target = tmp_path / "nested" / "component.wasm"
    _download_component_wasm(target)
    assert target.read_bytes() == b"wasm"


def test_download_component_failure_leaves_no_partial_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_retrieve(_url: str, path: str) -> None:
        Path(path).write_bytes(b"partial")
        message = "network down"
        raise OSError(message)

    monkeypatch.setattr(urllib.request, "urlretrieve", fake_retrieve)
    target = tmp_path / "component.wasm"
    _download_component_wasm(target)
    assert not target.exists()


def test_unwrap_query_value_kinds() -> None:
    assert _unwrap_query_value("plain") == "plain"
    assert _unwrap_query_value({"no-type": 1}) == {"no-type": 1}
    assert _unwrap_query_value({"type": "null"}) is None


def test_drop_none_recurses_lists_and_dicts() -> None:
    assert _drop_none([{"a": 1, "b": None}, None]) == [{"a": 1}, None]


def test_finalize_query_result_without_rows() -> None:
    assert _finalize_query_result({"errors": []}) == {"errors": []}


def test_meta_value_json_scalars() -> None:
    assert _meta_value_json(Decimal("1.5")) == {
        "type": "number",
        "value": "1.5",
    }
    assert _meta_value_json(value=True) == {"type": "boolean", "value": True}
    assert _meta_value_json(None) == {"type": "null"}
    assert _meta_value_json("txt") == {"type": "text", "value": "txt"}
    assert _meta_value_json({"number": "2", "currency": "USD"}) == {
        "type": "amount",
        "number": "2",
        "currency": "USD",
    }
    assert _meta_value_json({"odd": "shape"}) == {"type": "null"}


@pytest.fixture(scope="module")
def engine() -> RustledgerComponentEngine:
    return RustledgerComponentEngine()


def test_validate_and_format_entries(
    engine: RustledgerComponentEngine,
) -> None:
    source = '2020-01-01 open Assets:Cash\n2020-01-02 *  "x"  ""\n'
    result = engine.validate(source)
    assert "valid" in result
    formatted = engine.format_entries("2020-01-01  open   Assets:Cash\n")
    assert "Assets:Cash" in formatted


def _builder_func_type(engine: RustledgerComponentEngine, name: str) -> Any:
    """Fetch a real wasmtime function type from the component's builder."""
    fidx = engine._component.get_export_index(name, engine._iface(ce._BUILDER))
    func = engine._inst.get_func(engine._store, fidx)
    return func.type(engine._store)


def test_marshal_result_err_raises(engine: RustledgerComponentEngine) -> None:
    """result<ok, err> lifting: err surfaces as RustledgerError, ok unwraps.

    Uses the real ResultType from the component's builder ``create`` (its
    ok is the directive variant; a None payload short-circuits marshalling,
    so no Record needs fabricating).
    """
    result_type = _builder_func_type(engine, "create").result
    with pytest.raises(RustledgerError, match="boom"):
        ce._marshal(Variant("err", "boom"), result_type)
    case_tag = next(iter(dict(result_type.ok.cases)))
    ok_value = Variant("ok", Variant(case_tag, None))
    assert ce._marshal(ok_value, result_type) == {"type": ce._snake(case_tag)}


def test_cost_number_from_json_shapes() -> None:
    v = ce._cost_number_from_json(
        {"kind": "per_unit_from_total", "per_unit": "2", "total": "10"}
    )
    assert (v.tag, v.payload) == ("per-unit-from-total", ("2", "10"))
    v = ce._cost_number_from_json({"type": "total", "value": "10"})
    assert (v.tag, v.payload) == ("total", "10")
    v = ce._cost_number_from_json("3.5")
    assert (v.tag, v.payload) == ("per-unit", "3.5")


def test_query_entries_roundtrips_meta_scalars(
    engine: RustledgerComponentEngine,
) -> None:
    """Entries with number/bool/null meta survive the typed input marshalling
    (exercises the meta-value tagging branches on the way into the
    component)."""
    loaded = engine.load(
        "2020-01-01 open Assets:Cash\n"
        '2020-01-02 * "n"\n'
        "  n: 42\n"
        "  b: TRUE\n"
        '  s: "text"\n'
        "  Assets:Cash  1.00 USD\n"
        "2020-01-03 open Equity:Open\n"
    )
    result = engine.query_entries(loaded["entries"], "SELECT account")
    assert result.get("rows"), result


def test_unwrap_query_value_position_and_json() -> None:
    pos = {"type": "position", "units": {"number": "1", "currency": "X"}}
    assert _unwrap_query_value(pos) == {
        "units": {"currency": "X", "number": "1"}
    }
    assert _unwrap_query_value({"type": "json", "value": "[1, 2]"}) == [1, 2]


def test_marshal_untyped_fallbacks() -> None:
    rec = Record()
    rec.some_field = 1  # type: ignore[attr-defined]
    assert ce._marshal(rec, object()) == {"some_field": 1}
    assert ce._marshal(Variant("a-tag", 2), object()) == {
        "type": "a_tag",
        "value": 2,
    }
    assert ce._marshal("bare", object()) == "bare"


def _harvest_types(vtype: Any, found: dict[str, Any]) -> None:
    """Walk a wasmtime type tree collecting one instance per type class."""
    found.setdefault(type(vtype).__name__, vtype)
    if isinstance(vtype, RecordType):
        for _name, field in vtype.fields:
            _harvest_types(field, found)
    elif isinstance(vtype, VariantType):
        for _name, case in vtype.cases:
            if case is not None:
                _harvest_types(case, found)
    elif isinstance(vtype, (ListType, OptionType)):
        _harvest_types(
            vtype.element if isinstance(vtype, ListType) else vtype.payload,
            found,
        )
    elif isinstance(vtype, TupleType):
        for element in vtype.elements:
            _harvest_types(element, found)
    elif isinstance(vtype, ResultType) and vtype.ok is not None:
        _harvest_types(vtype.ok, found)


@pytest.fixture(scope="module")
def component_types(
    engine: RustledgerComponentEngine,
) -> dict[str, Any]:
    found: dict[str, Any] = {}
    ftype = _builder_func_type(engine, "create")
    for _name, param in ftype.params:
        _harvest_types(param, found)
    _harvest_types(ftype.result, found)
    return found


def test_default_for_every_type_class(
    component_types: dict[str, Any],
) -> None:
    expected: Any
    for name, expected in [
        ("OptionType", None),
        ("ListType", []),
        ("String", ""),
        ("Bool", False),
    ]:
        vtype = component_types.get(name)
        if vtype is None:
            pytest.skip(f"component exposes no {name}")
        got = ce._default_for(vtype)
        assert got == expected, name
        assert isinstance(vtype, (String, Bool)) or got == expected
    record = component_types.get("RecordType")
    assert record is not None
    assert isinstance(ce._default_for(record), object)
    # numeric fallback
    numeric = component_types.get("U32") or component_types.get("S64")
    if numeric is not None:
        assert ce._default_for(numeric) == 0


def test_clamp_roundtrip_with_rich_shapes(
    engine: RustledgerComponentEngine,
) -> None:
    """Entries with total-cost lots, posting metadata, and typed custom
    values survive the unmarshal -> component -> marshal round trip
    (covers the variant/pair-list edge branches on both directions)."""
    loaded = engine.load(
        "2020-01-01 open Assets:Cash\n"
        "2020-01-01 open Assets:Brokerage\n"
        '2020-01-02 * "buy with total cost"\n'
        "  Assets:Brokerage  2 VTI {5.00 # 10.00 USD}\n"
        '    lot-note: "kept"\n'
        "  Assets:Cash  -10.00 USD\n"
        '2020-01-03 custom "budget" 42 TRUE "text"\n'
    )
    # No assertion on load errors: the engine's `#`-cost balance weighing is
    # currently wrong in both directions (rustledger#1700); this test targets
    # marshalling, and the posting carries the correct per-unit-from-total
    # cost shape either way.
    entries = loaded["entries"]
    txn = next(e for e in entries if e.get("type") == "transaction")
    cost_in = txn["postings"][0]["cost"]["number"]
    assert cost_in["kind"] == "per_unit_from_total"
    result = engine.clamp_entries(entries, "2020-01-01", "2021-01-01")
    out = next(e for e in result["entries"] if e.get("type") == "transaction")
    cost_out = out["postings"][0]["cost"]["number"]
    assert cost_out == {
        "kind": "per_unit_from_total",
        "per_unit": "5.00",
        "total": "10.00",
    }


def test_unwrap_query_value_interval_fallback() -> None:
    cell = {"type": "interval", "begin": "2020-01-01", "end": "2020-02-01"}
    assert _unwrap_query_value(cell) == {
        "begin": "2020-01-01",
        "end": "2020-02-01",
    }


def test_rewrite_guest_paths_edge_shapes() -> None:
    result: dict[str, Any] = {
        "entries": [
            {"meta": {"filename": "/work/main.beancount"}},
            {"meta": {"lineno": 1}},  # no filename
            {"meta": None},  # non-dict meta
        ],
        "includes": [
            {"path": "/work/inc.beancount"},
            {"other": "shape"},  # no path
        ],
    }
    RustledgerComponentEngine._rewrite_guest_paths(result, Path("/host"))
    assert result["entries"][0]["meta"]["filename"] == "/host/main.beancount"
    assert result["includes"][0]["path"] == "/host/inc.beancount"
    assert result["includes"][1] == {"other": "shape"}


def test_clamp_accepts_mutated_edge_json(
    engine: RustledgerComponentEngine,
) -> None:
    """Edge shapes a host may feed back into clamp: typed custom values
    (number/null), an already-kebab cost kind, and null meta values —
    exercising the input-unmarshal tolerance branches with real types."""
    loaded = engine.load(
        "2020-01-01 open Assets:Cash\n"
        "2020-01-01 open Assets:B\n"
        '2020-01-02 * "x"\n'
        "  Assets:B  2 VTI {5.00 USD}\n"
        "  Assets:Cash  -10.00 USD\n"
        '2020-01-03 custom "budget" "seed"\n'
    )
    entries = loaded["entries"]
    txn = next(e for e in entries if e.get("type") == "transaction")
    # already-kebab cost kind (the tag-tolerance branch)
    txn["postings"][0]["cost"]["number"] = {
        "kind": "per-unit",
        "value": "5.00",
    }
    # meta with a null value (meta-value variant, payload-less case)
    txn["meta"]["note"] = None
    custom = next(e for e in entries if e.get("type") == "custom")
    # typed custom values: number and null
    custom["values"] = [
        {"type": "number", "value": 42},
        {"type": "null", "value": None},
    ]
    result = engine.clamp_entries(entries, "2020-01-01", "2021-01-01")
    assert result["entries"]


def _find_meta_pair_list(vtype: Any) -> Any | None:
    """Locate the ``list<tuple<string, meta-value>>`` type in a type tree."""
    if ce._is_pair_list(vtype) and ce._is_meta_value(
        ce._pair_value_type(vtype)
    ):
        return vtype
    if isinstance(vtype, RecordType):
        children = [field for _n, field in vtype.fields]
    elif isinstance(vtype, VariantType):
        children = [case for _n, case in vtype.cases if case is not None]
    elif isinstance(vtype, ListType):
        children = [vtype.element]
    elif isinstance(vtype, OptionType):
        children = [vtype.payload]
    else:
        children = []
    for child in children:
        found = _find_meta_pair_list(child)
        if found is not None:
            return found
    return None


@pytest.fixture(scope="module")
def meta_pair_list(engine: RustledgerComponentEngine) -> Any:
    ftype = _builder_func_type(engine, "create")
    for _name, param in ftype.params:
        found = _find_meta_pair_list(param)
        if found is not None:
            return found
    pytest.skip("component exposes no meta pair-list type")


def test_unmarshal_meta_dict_into_pair_list(meta_pair_list: Any) -> None:
    """A dict-shaped meta map re-tags scalars as meta-value variants."""
    pairs = ce._unmarshal({"note": "hi", "n": Decimal(2)}, meta_pair_list)
    assert [(k, v.tag) for k, v in pairs] == [
        ("note", "text"),
        ("n", "number"),
    ]


def test_unmarshal_non_meta_pair_list(
    meta_pair_list: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A string-keyed map whose values are NOT meta-values unmarshals each
    value by its actual type (the plain pair-list branch)."""
    monkeypatch.setattr(ce, "_is_meta_value", lambda _vtype: False)
    pairs = ce._unmarshal(
        {"note": {"type": "text", "value": "hi"}}, meta_pair_list
    )
    assert [(k, v.tag) for k, v in pairs] == [("note", "text")]


def test_unmarshal_unknown_variant_tag_raises(meta_pair_list: Any) -> None:
    """An unknown variant tag survives the kebab-tolerance step and then
    fails loudly on case lookup."""
    vtype = ce._pair_value_type(meta_pair_list)
    with pytest.raises(KeyError):
        ce._unmarshal({"type": "no_such_case"}, vtype)


def test_unmarshal_pair_list_as_list_of_tuples(meta_pair_list: Any) -> None:
    """A pair list arriving as an actual list of ``[key, value]`` pairs
    unmarshals each pair through the tuple branch."""
    pairs = ce._unmarshal(
        [["note", {"type": "text", "value": "hi"}]], meta_pair_list
    )
    assert [(k, v.tag) for k, v in pairs] == [("note", "text")]


def test_missing_sentinel_is_falsy_singleton() -> None:
    assert Missing() is Missing()
    assert repr(Missing()) == "MISSING"
    assert not Missing()
