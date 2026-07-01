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

import datetime
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any
from typing import TYPE_CHECKING

import pytest

# beancount is the ground-truth oracle (installed via the `beancount-compat`
# test extra). Skip cleanly rather than fail if it is somehow absent.
beancount_loader = pytest.importorskip("beancount.loader")

from rustfava.rustledger import loader as rf_loader  # noqa: E402
from rustfava.rustledger.backend import get_engine  # noqa: E402
from rustfava.rustledger.types import directives_from_json  # noqa: E402
from rustfava.rustledger.types import directives_to_json  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Iterable

DATA = Path(__file__).parent / "data"

# Fixtures whose booking rustfava must reproduce exactly. These span
# held-at-cost lots, prices, multiple currencies, a pad/balance pair (example)
# and a date-boundary case (off-by-one); long-example alone has ~193 cost lots.
# The stress-* fixtures add constructs the others lack: `@@` total prices,
# multiple lots of one commodity with a partial reduction, and pad->balance.
LEDGERS = [
    "example",
    "long-example",
    "query-example",
    "off-by-one",
    "stress-total-price",
    "stress-many-lots",
    "stress-pad-balance",
]

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


def _balance_dirs(entries: Iterable[object]) -> list[Any]:
    return [e for e in entries if type(e).__name__ in {"Balance", "RLBalance"}]


def test_failing_balance_assertion_is_surfaced() -> None:
    """A failing `balance` must produce an error AND a non-zero diff.

    Regression for rustledger#1663 / the C1 gap: `load()` (the display path)
    previously reported no error for a failing assertion, so the journal showed
    it as passed. rustledger 3.1.0 (v0.18.0) reports balance failures on load
    and carries `diff` on the directive; the journal's red/green keys off a
    present ``diff_amount``.
    """
    src = (
        "2024-01-01 open Assets:Cash USD\n"
        "2024-01-01 open Expenses:X USD\n"
        '2024-01-02 * "t"\n'
        "  Expenses:X   5 USD\n"
        "  Assets:Cash\n"
        "2024-01-03 balance Assets:Cash   999 USD\n"
    )
    entries, errors, _ = rf_loader.load_string(src, "<differential>")
    assert any(
        "balance" in str(getattr(e, "message", e)).lower() for e in errors
    ), "a failing balance assertion produced no error"
    (bal,) = _balance_dirs(entries)
    # Real balance is -5, asserted 999 -> non-zero diff -> renders as failed.
    assert bal.diff_amount is not None
    assert bal.diff_amount.number != 0


def test_passing_balance_assertion_is_green() -> None:
    """A passing `balance` must be silent: no error, and no diff_amount.

    Guards the zero-diff mapping — the engine sends `diff = 0` on a passing
    assertion, and carrying that through would mark every passing balance
    ``diff_amount`` (i.e. failed) in the journal.
    """
    src = (
        "2024-01-01 open Assets:Cash USD\n"
        "2024-01-01 open Expenses:X USD\n"
        '2024-01-02 * "t"\n'
        "  Expenses:X   5 USD\n"
        "  Assets:Cash\n"
        "2024-01-03 balance Assets:Cash   -5 USD\n"
    )
    entries, errors, _ = rf_loader.load_string(src, "<differential>")
    assert errors == []
    (bal,) = _balance_dirs(entries)
    assert bal.diff_amount is None


def test_clamped_totals_match_beancount_balance_at_cutoff() -> None:
    """The time-filter (engine clamp) opening balances must reconstruct the
    correct closing totals — the path that rustledger#1656 broke.

    Clamping to ``[begin, end)`` yields synthesized opening balances plus
    in-window postings; summed per account that equals the ledger's balance as
    of ``end`` (every posting dated before ``end``). Cross-check that against
    beancount, per account and per (currency, cost) lot. The synthesized
    ``Equity:Opening-Balances`` contra is clamp-specific, so exclude it.
    """
    path = str(DATA / "long-example.beancount")
    begin, end = "2014-01-01", "2015-01-01"
    cutoff = datetime.date(2015, 1, 1)
    opening = "Equity:Opening-Balances"

    rf_entries, _, _ = rf_loader.load_uncached(path)
    clamped = directives_from_json(
        get_engine().clamp_entries(
            directives_to_json(list(rf_entries)), begin, end
        )["entries"]
    )
    rf_inv = {
        a: v
        for a, v in _account_inventories(clamped).items()
        if a != opening
    }

    bc_entries, _, _ = beancount_loader.load_file(path)
    before_cutoff = [
        e
        for e in bc_entries
        if getattr(e, "date", cutoff) < cutoff
    ]
    bc_inv = {
        a: v
        for a, v in _account_inventories(before_cutoff).items()
        if a != opening
    }

    assert set(rf_inv) == set(bc_inv)
    for account in sorted(bc_inv):
        assert rf_inv[account] == bc_inv[account], (
            f"clamped total mismatch for {account}: "
            f"rustfava={rf_inv[account]} beancount={bc_inv[account]}"
        )


def test_stress_fixtures_hand_verified() -> None:
    """Explicit expected numbers for the stress fixtures.

    The differential tests above already cross-check these against beancount;
    this pins the values by hand as a second, oracle-independent check of the
    constructs the fixtures were added for.
    """
    d = datetime.date

    # @@ total price: A drains 7 USD, B gains 10 EUR; the sold posting's price
    # is the per-unit 10/7, and no cost is created.
    entries, errors, _ = rf_loader.load_uncached(
        str(DATA / "stress-total-price.beancount")
    )
    assert not errors
    inv = _account_inventories(entries)
    assert inv["Assets:USD"] == {("USD", None): Decimal(-7)}
    assert inv["Assets:EUR"] == {("EUR", None): Decimal(10)}
    (usd_posting,) = [
        p
        for e in entries
        for p in getattr(e, "postings", [])
        if getattr(p, "account", "") == "Assets:USD"
    ]
    assert usd_posting.cost is None
    assert usd_posting.price is not None
    # per-unit = 10 EUR / 7 USD = 1.4286 (to 4dp); the engine keeps full
    # precision, so compare at a sane scale rather than bit-for-bit.
    assert round(usd_posting.price.number, 4) == Decimal("1.4286")

    # Many lots: after selling 5 of the 50-lot, 5 HOOL @ {50} + 10 HOOL @ {60}.
    entries, errors, _ = rf_loader.load_uncached(
        str(DATA / "stress-many-lots.beancount")
    )
    assert not errors
    stock = _account_inventories(entries)["Assets:Stock"]
    assert stock == {
        ("HOOL", (Decimal(50), "USD", d(2020, 2, 1), None)): Decimal(5),
        ("HOOL", (Decimal(60), "USD", d(2020, 3, 1), None)): Decimal(10),
    }

    # pad -> balance: the pad fills Cash to the asserted 500, spend leaves 400,
    # and both balance assertions pass (no errors, diff_amount None).
    entries, errors, _ = rf_loader.load_uncached(
        str(DATA / "stress-pad-balance.beancount")
    )
    assert not errors
    assert _account_inventories(entries)["Assets:Cash"] == {
        ("USD", None): Decimal(400)
    }
    for bal in _balance_dirs(entries):
        assert bal.diff_amount is None
