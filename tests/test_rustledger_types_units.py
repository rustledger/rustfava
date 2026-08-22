"""Unit coverage for ``rustfava.rustledger.types`` edge branches.

Coverage burn-down phase 2: FrozenDict semantics, cost-number wire-format
tolerance (v0.20 list / v0.19 fields / flat scalar), typed custom values,
and the directive JSON adapters' error paths.
"""

from __future__ import annotations

import copy
import datetime
from decimal import Decimal
from typing import Any
from typing import cast
from typing import ClassVar

import pytest

from rustfava.rustledger.types import _amount_to_json
from rustfava.rustledger.types import _cost_to_json
from rustfava.rustledger.types import _parse_meta
from rustfava.rustledger.types import cost_number_values
from rustfava.rustledger.types import directive_from_json
from rustfava.rustledger.types import directive_to_json
from rustfava.rustledger.types import FrozenDict
from rustfava.rustledger.types import RLAmount
from rustfava.rustledger.types import RLCost
from rustfava.rustledger.types import RLCustom
from rustfava.rustledger.types import RLCustomValue
from rustfava.rustledger.types import RLPosition


def test_frozen_dict_is_immutable_but_copyable() -> None:
    frozen = FrozenDict({"b": [1, {"z": 2}], "a": 1})
    with pytest.raises(TypeError, match="immutable"):
        frozen["c"] = 3
    with pytest.raises(TypeError, match="immutable"):
        del frozen["a"]
    assert isinstance(hash(frozen), int)
    assert hash(frozen) == hash(FrozenDict({"a": 1, "b": [1, {"z": 2}]}))
    assert copy.copy(frozen) == {"a": 1, "b": [1, {"z": 2}]}
    deep = copy.deepcopy(frozen)
    assert deep == frozen
    assert isinstance(deep, dict)
    assert not isinstance(deep, FrozenDict)


def test_cost_number_values_wire_formats() -> None:
    # v0.20: type-tagged, pair as list
    assert cost_number_values(
        {"type": "per_unit_from_total", "value": ["2", "10"]}
    ) == (Decimal(2), Decimal(10))
    # v0.19: kind-tagged, pair spread as fields
    assert cost_number_values(
        {"kind": "per_unit_from_total", "per_unit": "3", "total": "9"}
    ) == (Decimal(3), Decimal(9))
    assert cost_number_values({"kind": "total", "value": "7"}) == (
        None,
        Decimal(7),
    )
    # WIT 3.3 compound `{a # b}` (rustledger#1700): per-unit + LUMP —
    # pre-booking surfaces only (rustfava#234)
    assert cost_number_values({"type": "compound", "value": ["5", "10"]}) == (
        Decimal(5),
        Decimal(10),
    )
    # unknown kind degrades to no cost number
    assert cost_number_values({"kind": "mystery", "value": "1"}) == (
        None,
        None,
    )
    # flat scalar (JSON-RPC era) is a per-unit cost
    assert cost_number_values("4.5") == (Decimal("4.5"), None)
    assert cost_number_values(None) == (None, None)


def test_cost_from_json_computes_per_unit_from_total() -> None:
    cost = RLCost.from_json(
        {"number_total": "10", "currency": "USD"},
        units_number=Decimal(4),
    )
    assert cost is not None
    assert cost.number == Decimal("2.5")


def test_position_requires_units() -> None:
    with pytest.raises(ValueError, match="requires units"):
        RLPosition.from_json({"units": None})


def test_custom_value_typed_dict_branches() -> None:
    amount = RLCustomValue.from_raw(
        {"type": "amount", "value": {"number": "20.00", "currency": "EUR"}}
    )
    assert amount.value == RLAmount(number=Decimal("20.00"), currency="EUR")
    amount_str = RLCustomValue.from_raw({"type": "amount", "value": "5 USD"})
    assert amount_str.value == RLAmount(number=Decimal(5), currency="USD")
    odd_amount = RLCustomValue.from_raw(
        {"type": "amount", "value": "just-text"}
    )
    assert odd_amount.value == "just-text"
    account = RLCustomValue.from_raw(
        {"type": "account", "value": "Expenses:Books"}
    )
    assert account.value == "Expenses:Books"
    a_date = RLCustomValue.from_raw({"type": "date", "value": "2020-01-02"})
    assert a_date.value == datetime.date(2020, 1, 2)
    null_date = RLCustomValue.from_raw({"type": "date", "value": None})
    assert null_date.value is None
    unknown = RLCustomValue.from_raw({"type": "wobble", "value": 9})
    assert unknown.value == 9


def test_custom_value_untyped_fallbacks() -> None:
    assert RLCustomValue.from_raw(Decimal(3)).value == Decimal(3)
    parsed = RLCustomValue.from_raw("12.5 CHF")
    assert parsed.value == RLAmount(number=Decimal("12.5"), currency="CHF")
    # two tokens that are not an amount stay a string
    assert RLCustomValue.from_raw("hello world").value == "hello world"
    assert RLCustomValue.from_raw("plain").value == "plain"
    assert str(RLCustomValue.from_raw("plain")) == "plain"


def test_directive_json_unknown_types_raise() -> None:
    with pytest.raises(ValueError, match="Unknown directive type"):
        directive_from_json({"type": "no-such-directive"})

    class NotADirective:
        date = datetime.date(2020, 1, 1)

    with pytest.raises(ValueError, match="Unknown directive type"):
        directive_to_json(NotADirective())  # type: ignore[arg-type]


def test_position_meta_normalization_and_cost() -> None:
    pos = RLPosition.from_json(
        {
            "units": {"number": "1", "currency": "USD"},
            "cost": {"number": "2", "currency": "EUR", "date": "2020-01-01"},
        }
    )
    assert pos.cost is not None
    assert pos.cost.number == Decimal(2)


def test_custom_value_int_bool_and_two_token_currency_check() -> None:
    assert RLCustomValue.from_raw(
        {"type": "int", "value": 10}
    ).value == Decimal(10)
    truthy = RLCustomValue.from_raw({"type": "bool", "value": True})
    assert truthy.value is True
    # two tokens whose second part is not an UPPERCASE currency stay a string
    assert RLCustomValue.from_raw("5 apples").value == "5 apples"
    # non-decimal first token falls through the amount parse
    assert RLCustomValue.from_raw("five USD").value == "five USD"


def test_amount_and_cost_json_serializers() -> None:
    assert _amount_to_json(None) is None
    assert _amount_to_json(RLAmount(number=Decimal(1), currency="USD")) == {
        "number": "1",
        "currency": "USD",
    }
    assert _cost_to_json(None) is None
    full = RLCost(
        number=Decimal(2),
        currency="EUR",
        date=datetime.date(2020, 1, 1),
        label="lot",
    )
    assert _cost_to_json(full) == {
        "number": "2",
        "currency": "EUR",
        "date": "2020-01-01",
        "label": "lot",
    }
    empty = cast("Any", RLCost)(
        number=None, currency=None, date=None, label=None
    )
    assert _cost_to_json(empty) is None


def test_directive_to_json_transaction_and_custom_values() -> None:
    class Transaction:
        """Duck-typed beancount-style transaction: exercises the class-name
        fallback in type resolution and the tolerance/diff_amount getattrs
        (RLTransaction has neither field)."""

        meta: ClassVar[dict[str, Any]] = {"filename": "f", "lineno": 1}
        date = datetime.date(2020, 1, 2)
        flag = "*"
        payee = None
        narration = "n"
        tags: frozenset[str] = frozenset()
        links: frozenset[str] = frozenset()
        postings: ClassVar[list[object]] = []

    out = directive_to_json(Transaction())  # type: ignore[arg-type]
    assert out["type"] == "transaction"
    assert out["flag"] == "*"
    assert out["postings"] == []

    class Balance:
        meta: ClassVar[dict[str, Any]] = {"filename": "f", "lineno": 5}
        date = datetime.date(2020, 1, 4)
        account = "Assets:Cash"
        amount = RLAmount(number=Decimal(3), currency="USD")
        tolerance = Decimal("0.005")
        diff_amount = RLAmount(number=Decimal(1), currency="USD")

    out = directive_to_json(Balance())  # type: ignore[arg-type]
    assert out["tolerance"] == "0.005"
    assert out["diff_amount"] == {"number": "1", "currency": "USD"}

    custom: Any = RLCustom(
        meta={"filename": "f", "lineno": 2},
        date=datetime.date(2020, 1, 3),
        type="budget",
        values=[
            RLCustomValue(
                RLAmount(number=Decimal(5), currency="USD"), dtype=object
            ),
            RLCustomValue("txt"),
            cast("Any", "bare"),
        ],
    )
    out = directive_to_json(custom)
    assert out["values"][0] == {
        "type": "amount",
        "number": "5",
        "currency": "USD",
    }
    assert out["values"][1] == {"type": "string", "value": "txt"}
    assert out["values"][2] == "bare"


def test_parse_meta_fills_and_coerces() -> None:
    bare = _parse_meta({})
    assert bare["filename"] == "<unknown>"
    assert bare["lineno"] == 0
    coerced = _parse_meta({"meta": {"filename": "f", "lineno": "7"}})
    assert coerced["lineno"] == 7


def test_directive_to_json_metaless_and_asdict_values() -> None:
    class Custom:
        date = datetime.date(2020, 1, 5)
        type = "budget"
        values: ClassVar[list[Any]] = []

    out = directive_to_json(Custom())  # type: ignore[arg-type]
    assert "meta" not in out
    assert out["values"] == []

    class AsDictValue:
        @staticmethod
        def _asdict() -> dict[str, Any]:
            return {"shape": "asdict"}

    Custom.values = [AsDictValue()]
    out = directive_to_json(Custom())  # type: ignore[arg-type]
    assert out["values"] == [{"shape": "asdict"}]
