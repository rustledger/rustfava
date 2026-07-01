"""Valuation must never crash on a cost that lacks a per-unit number (R3).

The engine accepts a bare ``{CUR}`` cost (currency only, no amount) with **no
error**, producing a Position whose ``cost.number`` is ``None``. The valuation
helpers compute ``cost.number * units`` and previously raised
``TypeError: NoneType * Decimal`` — and since ``AT_COST`` runs unconditionally
in tree serialisation / ``cap`` / ``net_profit``, one such posting 500'd the
whole balance-sheet / net-worth render. These lock in the "valuation never
crashes on user data" invariant and its units fallback.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from rustfava.beans.prices import RustfavaPriceMap
from rustfava.core.conversion import AT_COST
from rustfava.core.conversion import convert_position
from rustfava.core.conversion import get_cost
from rustfava.core.conversion import get_market_value
from rustfava.core.inventory import _Amount
from rustfava.core.inventory import _Cost
from rustfava.core.inventory import _Position
from rustfava.core.tree import Tree
from rustfava.rustledger import loader as rf_loader

_UNITS = _Amount(Decimal(10), "ABC")
_D = date(2020, 1, 1)
# A bare ``{USD}`` cost: currency only, no per-unit number. The engine really
# produces this (cost.number None) despite the ``Decimal`` field annotation.
_BARE_COST = _Cost(None, "USD", _D, None)  # type: ignore[arg-type]

# Every cost shape valuation must tolerate, including the bare ``{USD}`` cost
# (number=None) and a zero-unit position carrying one.
POSITIONS = [
    pytest.param(_Position(_UNITS, None), id="no-cost"),
    pytest.param(
        _Position(_UNITS, _Cost(Decimal(5), "USD", _D, None)), id="normal-cost"
    ),
    pytest.param(
        _Position(_UNITS, _BARE_COST),
        id="bare-currency-cost",
    ),
    pytest.param(
        _Position(_Amount(Decimal(0), "ABC"), _BARE_COST),
        id="zero-units-bare-cost",
    ),
]


@pytest.mark.parametrize("pos", POSITIONS)
def test_valuation_never_raises(pos: _Position) -> None:
    """No valuation helper may raise, whatever the cost shape."""
    prices = RustfavaPriceMap([])
    get_cost(pos)
    get_market_value(pos, prices)
    convert_position(pos, "EUR", prices)


def test_bare_currency_cost_falls_back_to_units() -> None:
    """With no computable cost value, valuation yields the raw units."""
    pos = _Position(_UNITS, _BARE_COST)
    prices = RustfavaPriceMap([])
    assert get_cost(pos) == _UNITS
    assert get_market_value(pos, prices) == _UNITS


def test_bare_currency_cost_balance_sheet_renders() -> None:
    """A ledger with a bare ``{CUR}`` cost renders at cost without a 500."""
    src = (
        "2020-01-01 open Assets:X\n"
        "2020-01-01 open Assets:Cash\n"
        '2020-02-01 * "buy at unspecified cost"\n'
        "  Assets:X   10 ABC {USD}\n"
        "  Assets:Cash  -50 USD\n"
    )
    entries, _errors, _ = rf_loader.load_string(src, "<r3>")
    node = Tree(entries).get("Assets:X")
    # AT_COST runs unconditionally in the balance-sheet render; must not raise.
    reduced = AT_COST.apply(node.balance)
    assert dict(reduced) == {"ABC": Decimal(10)}
