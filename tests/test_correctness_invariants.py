"""Correctness invariants (Layer 3 of the testing plan).

Property-style tests that must hold for *any* ledger or inventory, independent
of specific expected numbers. They generalise the point fixes: the
"render never raises" property below catches the whole R3 class (a cost shape
valuation can't handle), not just the bare-``{CUR}`` case that was found.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from typing import TYPE_CHECKING

import pytest

from rustfava.beans.prices import RustfavaPriceMap
from rustfava.core.conversion import AT_COST
from rustfava.core.conversion import AT_VALUE
from rustfava.core.conversion import UNITS
from rustfava.core.inventory import _Amount
from rustfava.core.inventory import _Cost
from rustfava.core.inventory import _Position
from rustfava.core.inventory import CounterInventory
from rustfava.core.tree import Tree
from rustfava.rustledger import loader as rf_loader

if TYPE_CHECKING:
    from collections.abc import Iterable

    from rustfava.core.conversion import Conversion

DATA = Path(__file__).parent / "data"
FIXTURES = ["example", "long-example", "query-example", "off-by-one"]
_END = date(2100, 1, 1)


def _price_map(entries: Iterable[Any]) -> RustfavaPriceMap:
    prices = [e for e in entries if type(e).__name__ in {"Price", "RLPrice"}]
    return RustfavaPriceMap(prices)


@pytest.mark.parametrize("ledger", FIXTURES)
@pytest.mark.parametrize(
    "conversion", [UNITS, AT_COST, AT_VALUE], ids=["units", "cost", "value"]
)
def test_report_render_never_raises(
    ledger: str, conversion: Conversion
) -> None:
    """Reducing every account balance under a conversion must never raise.

    This is the general form of R3: a posting whose cost/price shape valuation
    can't handle would 500 the balance-sheet / net-worth render. Exercising
    every account of every real fixture under units/at-cost/at-value guards the
    whole class, not one case.
    """
    entries, _errors, _ = rf_loader.load_uncached(
        str(DATA / f"{ledger}.beancount")
    )
    tree = Tree(entries)
    prices = _price_map(entries)
    for node in tree.values():
        conversion.apply(node.balance, prices, _END)
        conversion.apply(node.balance_children, prices, _END)


_LOT = _Cost(Decimal(50), "USD", date(2020, 1, 1), None)


def _pos(number: int, cost: _Cost | None = _LOT) -> _Position:
    return _Position(_Amount(Decimal(number), "HOOL"), cost)


def test_inventory_add_and_negation_net_to_empty() -> None:
    """Adding a position and its exact negation leaves an empty inventory."""
    inv = CounterInventory()
    inv.add_position(_pos(10))
    assert not inv.is_empty()
    inv.add_position(_pos(-10))
    assert inv.is_empty()


def test_inventory_add_is_order_independent() -> None:
    """Folding positions in any order yields the same inventory (a sum)."""
    positions = [_pos(3), _pos(-1, None), _pos(5), _pos(-2)]
    forward = CounterInventory()
    for p in positions:
        forward.add_position(p)
    backward = CounterInventory()
    for p in reversed(positions):
        backward.add_position(p)
    assert forward == backward


def test_inventory_conservation_across_a_balanced_ledger() -> None:
    """Every posting's weight (at cost) across a balanced ledger sums to zero.

    Double-entry's core invariant: all postings at cost net to nothing.
    """
    entries, errors, _ = rf_loader.load_uncached(
        str(DATA / "off-by-one.beancount")
    )
    assert not errors
    total = CounterInventory()
    for entry in entries:
        for posting in getattr(entry, "postings", []):
            if posting.units is None or posting.units.number is None:
                continue
            total.add_position(posting)
    assert AT_COST.apply(total).is_empty()
