"""Tests for ``rustfava.rustledger.query._entries_to_source``.

Regression coverage for https://github.com/rustledger/rustfava/issues/144 —
the query-time serializer used to ignore the in-tree ``to_string``
formatter and silently drop tags, links, metadata, posting flags, cost
basis, prices, booking methods, and balance tolerance.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import cast
from typing import TYPE_CHECKING

import pytest

from rustfava.beans import create
from rustfava.rustledger.query import _convert_row_value
from rustfava.rustledger.query import _entries_to_source
from rustfava.rustledger.query import CompilationError
from rustfava.rustledger.query import connect
from rustfava.rustledger.query import ParseError
from rustfava.rustledger.query import RLCursor
from rustfava.rustledger.query import SessionCache
from rustfava.rustledger.types import RLCustom
from rustfava.rustledger.types import RLCustomValue
from rustfava.rustledger.types import RLOpen

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rustfava.beans.abc import Directive
    from rustfava.beans.types import BeancountOptions
    from rustfava.rustledger.query import RLConnection


def test_entries_to_source_preserves_transaction_tags_links_and_metadata() -> (
    None
):
    postings = [
        create.posting(
            "Assets:US:Bank",
            "-1000.00 USD",
            flag="!",
            meta={"confidence": "high"},
        ),
        create.posting(
            "Assets:DE:Bank",
            "900.00 EUR",
            price="1.1111 USD",
        ),
    ]
    txn = create.transaction(
        {"category": "international"},
        datetime.date(2024, 2, 15),
        "*",
        "Wise",
        "USD->EUR transfer",
        tags=frozenset({"fx-2024"}),
        links=frozenset({"transfer-batch-12"}),
        postings=postings,
    )

    source = _entries_to_source([txn])

    # Tags + links must appear on the header.
    assert "#fx-2024" in source
    assert "^transfer-batch-12" in source
    # Directive metadata must survive.
    assert 'category: "international"' in source
    # Posting metadata must survive.
    assert 'confidence: "high"' in source
    # Per-posting flag must survive.
    assert "! Assets:US:Bank" in source
    # Per-posting price must survive (rustledger normalizes @@ to @).
    assert "@ 1.1111 USD" in source


def test_entries_to_source_preserves_cost_basis() -> None:
    postings = [
        create.posting(
            "Assets:US:Brokerage",
            "10 AAPL",
            cost=create.cost(
                Decimal("170.50"), "USD", datetime.date(2024, 3, 20)
            ),
        ),
        create.posting("Assets:US:Bank", "-1705.00 USD"),
    ]
    txn = create.transaction(
        {},
        datetime.date(2024, 3, 20),
        "*",
        "Schwab",
        "Buy 10 AAPL",
        postings=postings,
    )

    source = _entries_to_source([txn])

    # `{price currency, date}` is what makes capital-gains math possible.
    assert "{170.50 USD, 2024-03-20}" in source


def test_entries_to_source_preserves_balance_tolerance() -> None:
    bal = create.balance(
        {},
        datetime.date(2024, 12, 31),
        "Assets:DE:Bank",
        "900.00 EUR",
        tolerance=Decimal("0.05"),
    )

    source = _entries_to_source([bal])

    assert "balance Assets:DE:Bank" in source
    assert "900.00 ~ 0.05 EUR" in source


def test_entries_to_source_preserves_open_booking_method() -> None:
    opn = RLOpen(
        meta={},
        date=datetime.date(2024, 1, 1),
        account="Assets:US:Brokerage",
        currencies=(),
        booking="STRICT",
    )

    # rustledger ``RL*`` directives are a parallel hierarchy to
    # ``abc.Directive``
    # that ``_entries_to_source``/``to_string`` accept via singledispatch
    # duck-typing; cast to satisfy the static signature.
    source = _entries_to_source(cast("Sequence[Directive]", [opn]))

    assert "open Assets:US:Brokerage" in source
    assert '"STRICT"' in source


def test_entries_to_source_skips_fava_custom_directives() -> None:
    # `custom "fava-option" ...` is not parseable by rledger and was
    # explicitly skipped in the old serializer; keep that behavior.
    fava_custom = RLCustom(
        meta={},
        date=datetime.date(2024, 1, 1),
        type="fava-option",
        values=(
            RLCustomValue("title", dtype=str),
            RLCustomValue("Test", dtype=str),
        ),
    )
    other_custom = RLCustom(
        meta={},
        date=datetime.date(2024, 1, 1),
        type="budget",
        values=(RLCustomValue("Expenses:Food", dtype=str),),
    )

    source = _entries_to_source(
        cast("Sequence[Directive]", [fava_custom, other_custom])
    )

    assert "fava-option" not in source
    assert "budget" in source


_INVENTORY_COL = {"name": "balance", "datatype": "Inventory"}


def test_inventory_sums_same_currency_cost_lots() -> None:
    """Regression for https://github.com/rustledger/rustfava/issues/155.

    Now that the serializer preserves cost basis, a balances query returns
    several positions of the same currency at different cost lots. Flattening
    the inventory to ``{currency: number}`` must accumulate; the old
    assignment kept only the last lot (e.g. 60 ITOT collapsed to 2).
    """
    value = {
        "positions": [
            {"units": {"number": "2", "currency": "ITOT"}},
            {"units": {"number": "3", "currency": "ITOT"}},
        ]
    }

    assert _convert_row_value(value, _INVENTORY_COL) == {"ITOT": Decimal(5)}


def test_inventory_mixed_currencies_and_lots() -> None:
    value = {
        "positions": [
            {"units": {"number": "2", "currency": "ITOT"}},
            {"units": {"number": "3", "currency": "ITOT"}},
            {"units": {"number": "100.00", "currency": "USD"}},
        ]
    }

    assert _convert_row_value(value, _INVENTORY_COL) == {
        "ITOT": Decimal(5),
        "USD": Decimal("100.00"),
    }


# -- cursor / conversion / connection unit coverage ---------------------------

_AMOUNT_COL = {"name": "market_value", "datatype": "Amount"}


def test_amount_column_with_inventory_shaped_payload() -> None:
    """The engine sometimes declares Amount but ships an Inventory payload
    (rustledger#1701, found by the route-smoke suite): marshalling must
    flatten it rather than crash the whole query with a KeyError."""
    value = {"positions": [{"units": {"currency": "USD", "number": "0"}}]}
    assert _convert_row_value(value, _AMOUNT_COL) == {"USD": Decimal(0)}


def test_convert_row_value_scalars_and_fallbacks() -> None:
    assert _convert_row_value(None, _AMOUNT_COL) is None
    decimal_col = {"name": "n", "datatype": "Decimal"}
    assert _convert_row_value("3.14", decimal_col) == Decimal("3.14")
    set_col = {"name": "tags", "datatype": "set"}
    assert _convert_row_value(["a", "b"], set_col) == frozenset({"a", "b"})
    unknown_col = {"name": "x", "datatype": "something-new"}
    assert _convert_row_value("as-is", unknown_col) == "as-is"


def test_cursor_description_fetch_and_unpack() -> None:
    cursor = RLCursor(
        columns=[
            {"name": "account", "datatype": "str"},
            {"name": "total", "datatype": "Decimal"},
        ],
        rows=[["Assets:Cash", "1.00"], ["Equity:Open", "-1.00"]],
    )
    name, datatype = cursor.description[1]
    assert (name, datatype) == ("total", Decimal)
    assert cursor.fetchone() == ("Assets:Cash", Decimal("1.00"))
    assert cursor.fetchone() == ("Equity:Open", Decimal("-1.00"))
    assert cursor.fetchone() is None
    assert cursor.fetchall() == []


class _ComponentStyleEngine:
    """Engine stub exposing the component's ``query_entries``."""

    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.queries: list[str] = []

    def query_entries(
        self, _directives_json: str, query: str
    ) -> dict[str, object]:
        self.queries.append(query)
        return self.result


class _LegacyStyleEngine:
    """Engine stub with only the legacy source-text ``query``."""

    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.sources: list[str] = []

    def query(self, source: str, _query: str) -> dict[str, object]:
        self.sources.append(source)
        return self.result


def _connection(engine: object) -> RLConnection:
    options = cast("BeancountOptions", {})
    conn = connect("beancount:", [], [], options)
    conn._engine = engine
    return conn


def test_execute_via_component_engine() -> None:
    engine = _ComponentStyleEngine(
        {"columns": [{"name": "account", "datatype": "str"}], "rows": [["A"]]}
    )
    cursor = _connection(engine).execute("SELECT account")
    assert cursor.fetchall() == [("A",)]
    assert engine.queries == ["SELECT account"]


def test_execute_via_legacy_engine_serialises_entries_once() -> None:
    engine = _LegacyStyleEngine({"columns": [], "rows": []})
    conn = _connection(engine)
    conn.execute("SELECT account")
    conn.execute("SELECT account")
    assert engine.sources == ["", ""]  # no entries -> empty source, reused


def test_execute_via_legacy_engine_honours_set_source() -> None:
    engine = _LegacyStyleEngine({"columns": [], "rows": []})
    conn = _connection(engine)
    conn.set_source("2020-01-01 open Assets:Cash\n")
    conn.execute("SELECT account")
    assert engine.sources == ["2020-01-01 open Assets:Cash\n"]


def test_execute_raises_parse_and_compilation_errors() -> None:
    parse_engine = _ComponentStyleEngine(
        {"errors": [{"message": "cannot parse query"}]}
    )
    with pytest.raises(ParseError):
        _connection(parse_engine).execute("SELEKT")
    compile_engine = _ComponentStyleEngine(
        {"errors": [{"message": "column 'x' not found"}]}
    )
    with pytest.raises(CompilationError):
        _connection(compile_engine).execute("SELECT x")
    empty_message_engine = _ComponentStyleEngine({"errors": [{}]})
    with pytest.raises(CompilationError, match="Unknown error"):
        _connection(empty_message_engine).execute("SELECT x")


def test_cursor_is_iterable() -> None:
    cursor = RLCursor(
        columns=[{"name": "account", "datatype": "str"}], rows=[["A"], ["B"]]
    )
    assert list(cursor) == [("A",), ("B",)]


def test_inventory_position_without_currency_is_skipped() -> None:
    value = {
        "positions": [
            {"units": {"number": "1"}},
            {"units": {"currency": "USD", "number": "2"}},
        ]
    }
    assert _convert_row_value(value, _INVENTORY_COL) == {"USD": Decimal(2)}


def test_entries_to_source_skips_entries_that_render_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "rustfava.rustledger.query.to_string", lambda _entry: ""
    )
    entry = create.transaction(
        meta={},
        date=datetime.date(2020, 1, 1),
        flag="*",
        payee=None,
        narration="x",
        tags=frozenset(),
        links=frozenset(),
        postings=[],
    )
    assert _entries_to_source([entry]) == ""


# ===== SessionCache (#249) =====


class _FakeSession:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def query(self, query_string: str) -> dict[str, object]:
        self.queries.append(query_string)
        return {"columns": [], "rows": [], "errors": []}


class _FakeEngine:
    """Engine double with open_session_entries; counts opens."""

    def __init__(self, *, fail: bool = False) -> None:
        self.opens = 0
        self._fail = fail

    def open_session_entries(
        self, _entries_json: list[dict[str, object]]
    ) -> _FakeSession:
        self.opens += 1
        if self._fail:
            msg = "no from-entries export"
            raise RuntimeError(msg)
        return _FakeSession()


class _NoSessionEngine:
    """Engine double without the capability (JSON-RPC shape)."""


def test_session_cache_identity_hit_and_miss() -> None:
    cache = SessionCache()
    engine = _FakeEngine()
    entries_a: list[Directive] = []
    entries_b: list[Directive] = []
    first = cache.get(engine, entries_a)
    assert first is not None
    # Same object: cache hit, no new open.
    assert cache.get(engine, entries_a) is first
    assert engine.opens == 1
    # Different object (filter change / reload): fresh session.
    second = cache.get(engine, entries_b)
    assert second is not first
    assert engine.opens == 2


def test_session_cache_disabled_without_capability() -> None:
    cache = SessionCache()
    assert cache.get(_NoSessionEngine(), []) is None


def test_session_cache_disables_permanently_on_open_failure() -> None:
    cache = SessionCache()
    engine = _FakeEngine(fail=True)
    entries: list[Directive] = []
    assert cache.get(engine, entries) is None
    # Second call must NOT retry the failing open.
    assert cache.get(engine, entries) is None
    assert engine.opens == 1


def test_connection_prefers_held_session() -> None:
    conn = connect(
        "rustledger:",
        entries=[],
        errors=[],
        options=cast("BeancountOptions", {}),
    )
    session = _FakeSession()
    conn.set_session(session)
    cursor = conn.execute("SELECT account")
    assert session.queries == ["SELECT account"]
    assert list(cursor) == []
