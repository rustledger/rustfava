"""Differential correctness tests: rustfava (rustledger engine) vs beancount.

rustfava aims for beancount compatibility, so beancount's own loader is a
ground-truth *oracle* that the snapshot tests lack — a snapshot only proves the
output did not change, not that it is correct. These tests load the same ledger
through both engines and assert the booked results agree, so a booking or
balance-handling divergence fails loudly instead of being frozen into a
snapshot.

This is Layer 1 of the correctness testing plan. Start here when a report shows
a wrong number: if the booked inventories already differ from beancount, the
bug is in loading/booking, not in the report layer.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# beancount is the ground-truth oracle (installed via the `beancount-compat`
# test extra). Skip cleanly rather than fail if it is somehow absent.
beancount_loader = pytest.importorskip("beancount.loader")

from rustfava.rustledger import loader as rf_loader  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Iterable

DATA = Path(__file__).parent / "data"

# Fixtures whose booking rustfava must reproduce exactly. These span
# held-at-cost lots, prices, multiple currencies, a pad/balance pair (example)
# and a date-boundary case (off-by-one); long-example alone has ~193 cost lots.
LEDGERS = ["example", "long-example", "query-example", "off-by-one"]

# Type of `cost` normalized to beancount's 4-tuple identity — deliberately
# dropping rustfava's extra ``number_total`` field so two engines' economically
# equal lots compare equal here (that extra field leaking into lot identity is
# a separate defect; this oracle should not be sensitive to it).
CostKey = tuple[Decimal | None, str | None, object, str | None]
AccountInventory = dict[tuple[str | None, CostKey | None], Decimal]


def _cost_key(cost: object) -> CostKey | None:
    if cost is None:
        return None
    number = getattr(cost, "number", None)
    return (
        Decimal(number) if number is not None else None,
        getattr(cost, "currency", None),
        getattr(cost, "date", None),
        getattr(cost, "label", None),
    )


def _account_inventories(
    entries: Iterable[object],
) -> dict[str, AccountInventory]:
    """Fold every posting into ``{account: {(currency, cost): Decimal}}``.

    Works for both engines because rustfava registers its directive/posting
    types against beancount's ABCs, so the ``postings``/``units``/``cost``
    attribute shape is identical.
    """
    inv: dict[str, AccountInventory] = defaultdict(
        lambda: defaultdict(Decimal)
    )
    for entry in entries:
        for posting in getattr(entry, "postings", []):
            units = posting.units
            if units is None or units.number is None:
                continue
            key = (units.currency, _cost_key(posting.cost))
            inv[posting.account][key] += Decimal(units.number)
    # Drop keys/accounts that net to exactly zero.
    return {
        account: {k: v for k, v in lots.items() if v != 0}
        for account, lots in inv.items()
        if any(v != 0 for v in lots.values())
    }


@pytest.mark.parametrize("ledger", LEDGERS)
def test_booked_inventories_match_beancount(ledger: str) -> None:
    """Per-account booked inventories must equal beancount's, to the cent."""
    path = str(DATA / f"{ledger}.beancount")
    bc_entries, _bc_errors, _ = beancount_loader.load_file(path)
    rf_entries, _rf_errors, _ = rf_loader.load_uncached(path)

    bc_inv = _account_inventories(bc_entries)
    rf_inv = _account_inventories(rf_entries)

    # Compare per account for a readable diff on failure.
    assert set(rf_inv) == set(bc_inv), (
        f"account set differs: only-rustfava={set(rf_inv) - set(bc_inv)}, "
        f"only-beancount={set(bc_inv) - set(rf_inv)}"
    )
    for account in sorted(bc_inv):
        assert rf_inv[account] == bc_inv[account], (
            f"inventory mismatch for {account}: "
            f"rustfava={rf_inv[account]} beancount={bc_inv[account]}"
        )


@pytest.mark.xfail(
    reason="rustledger#1663: the load() path does not surface balance "
    "assertion failures (only validate() does), so a failing `balance` is "
    "silent. Remove this xfail once the engine emits balance errors on load "
    "(or the loader calls validate and merges them).",
    strict=False,
)
def test_failing_balance_assertion_is_surfaced() -> None:
    """A failing `balance` directive must produce an error.

    beancount reports ``Balance failed for ...``; rustfava's display load path
    currently returns no error, so the journal shows the assertion as passed.
    """
    src = (
        "2024-01-01 open Assets:Cash USD\n"
        "2024-01-01 open Expenses:X USD\n"
        '2024-01-02 * "t"\n'
        "  Expenses:X   5 USD\n"
        "  Assets:Cash\n"
        "2024-01-03 balance Assets:Cash   999 USD\n"
    )
    _entries, errors, _ = rf_loader.load_string(src, "<differential>")
    assert any(
        "balance" in str(getattr(e, "message", e)).lower() for e in errors
    ), "a failing balance assertion produced no error"
