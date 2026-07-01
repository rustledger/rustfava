"""Regression: held-at-cost lots must net on economic identity, not on the
derived ``number_total`` field (correctness plan, C3).

rustledger emits a lot's cost number in three shapes — ``per_unit``, ``total``,
and ``per_unit_from_total`` — the last populating ``RLCost.number_total`` while
a plain ``per_unit`` leg leaves it ``None``. If ``number_total`` takes part
in cost equality/hash, two economically identical lots key to different
inventory slots and never cancel, so a fully-closed position shows spurious
``+N`` / ``-N {cost}`` ghost lots that render identically (``cost_to_string``
ignores ``number_total``) — a wrong balance the user cannot diagnose.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

import pytest

beancount_loader = pytest.importorskip("beancount.loader")

from rustfava.core.tree import Tree  # noqa: E402
from rustfava.rustledger import loader as rf_loader  # noqa: E402

# Buy 2 units with a *total* cost ({{100 USD}} -> per_unit_from_total, so the
# lot carries number_total=100), then sell them per-unit ({50 USD},
# number_total=None). Same (number, currency, date, label); differs only in the
# derived number_total. Economically nets to an empty position.
_LEDGER = (
    "2020-01-01 open Assets:Stock\n"
    "2020-01-01 open Assets:Cash USD\n"
    '2020-02-01 * "buy at total cost"\n'
    "  Assets:Stock   2 STK {{100 USD}}\n"
    "  Assets:Cash  -100 USD\n"
    '2020-02-01 * "sell at per-unit cost"\n'
    "  Assets:Stock  -2 STK {50 USD}\n"
    "  Assets:Cash   100 USD\n"
)


def test_closed_position_nets_to_empty() -> None:
    """The fully-closed position must hold nothing (no ghost lots)."""
    entries, errors, _ = rf_loader.load_string(_LEDGER, "<c3>")
    assert not errors
    balance = Tree(entries).get("Assets:Stock").balance
    assert dict(balance) == {}, f"ghost lots remain: {dict(balance)}"


def test_closed_position_matches_beancount() -> None:
    """Booked position agrees with beancount's ground truth (empty)."""
    bc_entries, _, _ = beancount_loader.load_string(_LEDGER)
    rf_entries, _, _ = rf_loader.load_string(_LEDGER, "<c3>")

    def stock_units(entries: object) -> dict[tuple[str, object], Decimal]:
        acc: dict[tuple[str, object], Decimal] = defaultdict(Decimal)
        for entry in entries:  # type: ignore[attr-defined]
            for posting in getattr(entry, "postings", []):
                if posting.account != "Assets:Stock" or posting.units is None:
                    continue
                cost = posting.cost
                key = (
                    posting.units.currency,
                    None
                    if cost is None
                    else (cost.number, cost.currency, cost.date, cost.label),
                )
                acc[key] += Decimal(posting.units.number)
        return {k: v for k, v in acc.items() if v != 0}

    assert stock_units(rf_entries) == stock_units(bc_entries) == {}
