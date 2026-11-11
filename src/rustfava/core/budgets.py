"""Parsing and computing budgets."""

from __future__ import annotations

import datetime
from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import NamedTuple
from typing import TYPE_CHECKING

from rustfava.core.module_base import FavaModule
from rustfava.helpers import BeancountError
from rustfava.util.date import days_in_daterange
from rustfava.util.date import INTERVALS

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping
    from collections.abc import Sequence

    from rustfava.beans.abc import Custom
    from rustfava.core import RustfavaLedger
    from rustfava.util.date import Interval


class Budget(NamedTuple):
    """A budget entry."""

    account: str
    date_start: datetime.date
    period: Interval
    number: Decimal
    currency: str


BudgetDict = dict[str, list[Budget]]
"""A map of account names to lists of budget entries."""


class BudgetError(BeancountError):
    """Error with a budget."""


class BudgetModule(FavaModule):
    """Parses budget entries."""

    def __init__(self, ledger: RustfavaLedger) -> None:
        super().__init__(ledger)
        self._budget_entries: BudgetDict = {}
        self.errors: Sequence[BudgetError] = []

    def load_file(self) -> None:  # noqa: D102
        self._budget_entries, self.errors = parse_budgets(
            self.ledger.all_entries_by_type.Custom,
        )

    @property
    def entries(self) -> BudgetDict:
        """The parsed budget directives, keyed by account."""
        return self._budget_entries

    def calculate(
        self,
        account: str,
        begin_date: datetime.date,
        end_date: datetime.date,
    ) -> Mapping[str, Decimal]:
        """Calculate the budget for an account in an interval."""
        return calculate_budget(
            self._budget_entries,
            account,
            begin_date,
            end_date,
        )

    def calculate_children(
        self,
        account: str,
        begin_date: datetime.date,
        end_date: datetime.date,
    ) -> Mapping[str, Decimal]:
        """Calculate the budget for an account including its children."""
        return calculate_budget_children(
            self._budget_entries,
            account,
            begin_date,
            end_date,
        )


def parse_budgets(
    custom_entries: Sequence[Custom],
) -> tuple[BudgetDict, Sequence[BudgetError]]:
    """Parse budget directives from custom entries.

    Args:
        custom_entries: the Custom entries to parse budgets from.

    Returns:
        A dict of accounts to lists of budgets.

    Example:
        2015-04-09 custom "budget" Expenses:Books "monthly" 20.00 EUR
    """
    budgets: BudgetDict = defaultdict(list)
    errors = []

    for entry in (entry for entry in custom_entries if entry.type == "budget"):
        try:
            interval = INTERVALS.get(str(entry.values[1].value).lower())
            if not interval:
                errors.append(
                    BudgetError(
                        entry.meta,
                        "Invalid interval for budget entry",
                        entry,
                    ),
                )
                continue
            budget = Budget(
                entry.values[0].value,
                entry.date,
                interval,
                entry.values[2].value.number,
                entry.values[2].value.currency,
            )
            budgets[budget.account].append(budget)
        except (IndexError, TypeError):
            errors.append(
                BudgetError(entry.meta, "Failed to parse budget entry", entry),
            )

    return budgets, errors


def _matching_budgets(
    budgets: Sequence[Budget],
    date_active: datetime.date,
) -> Mapping[str, Budget]:
    """Find matching budgets.

    Returns:
        The budget that is active on the specified date for the
        specified account.
    """
    last_seen_budgets = {}
    for budget in budgets:
        if budget.date_start <= date_active:
            last_seen_budgets[budget.currency] = budget
        else:
            break
    return last_seen_budgets


def calculate_budget(
    budgets: BudgetDict,
    account: str,
    date_from: datetime.date,
    date_to: datetime.date,
) -> Mapping[str, Decimal]:
    """Calculate budget for an account.

    Args:
        budgets: A list of :class:`Budget` entries.
        account: An account name.
        date_from: Starting date.
        date_to: End date (exclusive).

    Returns:
        A dictionary of currency to Decimal with the budget for the
        specified account and period.
    """
    budget_list = budgets.get(account, None)
    if budget_list is None:
        return {}

    currency_dict: dict[str, Decimal] = defaultdict(Decimal)

    for day in days_in_daterange(date_from, date_to):
        matches = _matching_budgets(budget_list, day)
        for budget in matches.values():
            days_in_period = budget.period.number_of_days(day)
            currency_dict[budget.currency] += budget.number / days_in_period
    return dict(currency_dict)


def calculate_budget_children(
    budgets: BudgetDict,
    account: str,
    date_from: datetime.date,
    date_to: datetime.date,
) -> Mapping[str, Decimal]:
    """Calculate budget for an account including budgets of its children.

    Args:
        budgets: A list of :class:`Budget` entries.
        account: An account name.
        date_from: Starting date.
        date_to: End date (exclusive).

    Returns:
        A dictionary of currency to Decimal with the budget for the
        specified account and period.
    """
    currency_dict: dict[str, Decimal] = Counter()  # type: ignore[assignment]

    for child in budgets:
        if child.startswith(account):
            currency_dict.update(
                calculate_budget(budgets, child, date_from, date_to),
            )
    return dict(currency_dict)

@dataclass(frozen=True)
class BudgetRowData:
    """One row of the budget overview."""

    account: str
    depth: int
    currency: str
    budgeted: Decimal
    actual: Decimal

    @property
    def remaining(self) -> Decimal:
        """What is left of the budget."""
        return self.budgeted - self.actual

    @property
    def used_pct(self) -> Decimal | None:
        """The share of the budget that has been spent, as a percentage."""
        if not self.budgeted:
            return None
        return (self.actual / self.budgeted * 100).quantize(Decimal("0.1"))

    @property
    def over_budget(self) -> bool:
        """Whether more than the budget has been spent."""
        return self.remaining < 0


BUDGET_WINDOWS = ("year", "ytd", "month")
"""The windows offered by the budget overview."""


def budget_window(
    name: str | None,
    today: datetime.date,
) -> tuple[datetime.date, datetime.date, str]:
    """Resolve a window name to a half-open date range.

    Args:
        name: One of ``BUDGET_WINDOWS`` (defaults to ``year``).
        today: The date the window is anchored on.

    Returns:
        The start (inclusive), the end (exclusive) and the resolved name.
    """
    if name == "ytd":
        return (
            datetime.date(today.year, 1, 1),
            today + datetime.timedelta(days=1),
            "ytd",
        )
    if name == "month":
        begin = datetime.date(today.year, today.month, 1)
        return (
            begin,
            (begin + datetime.timedelta(days=32)).replace(day=1),
            "month",
        )
    return (
        datetime.date(today.year, 1, 1),
        datetime.date(today.year + 1, 1, 1),
        "year",
    )


def budget_rows(
    ledger: RustfavaLedger,
    begin_date: datetime.date,
    end_date: datetime.date,
) -> tuple[list[BudgetRowData], list[BudgetRowData]]:
    """Collect the budget overview rows and the totals.

    Every account carrying a budget gets a row with its children-inclusive
    budget (the same value as ``calculate_children``) next to the spending
    booked in that account and its subaccounts within the window.

    Args:
        ledger: The ledger.
        begin_date: Start of the window (inclusive).
        end_date: End of the window (exclusive).

    Returns:
        The rows and the total rows. Only accounts without a budgeted
        ancestor are summed, so nothing is counted twice.
    """
    budgets = ledger.budgets
    accounts = sorted(budgets.entries)

    spending: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for entry in ledger.all_entries:
        if not begin_date <= entry.date < end_date:
            continue
        for posting in getattr(entry, "postings", ()):
            units = posting.units
            if units is None:  # pragma: no cover
                continue
            spending[(posting.account, units.currency)] += units.number

    def actual_for(account: str, currency: str) -> Decimal:
        prefix = account + ":"
        return sum(
            (
                value
                for (posting_account, posting_currency), value in spending.items()
                if posting_currency == currency
                and (
                    posting_account == account
                    or posting_account.startswith(prefix)
                )
            ),
            Decimal(0),
        )

    def rows_for(account: str) -> list[BudgetRowData]:
        depth = account.count(":")
        return [
            BudgetRowData(
                account,
                depth,
                currency,
                budget,
                actual_for(account, currency),
            )
            for currency, budget in sorted(
                budgets.calculate_children(account, begin_date, end_date).items(),
            )
        ]

    rows = [row for account in accounts for row in rows_for(account)]

    # Only accounts without a budgeted ancestor are summed into the total, so a
    # budgeted parent and its budgeted child are not counted twice.
    aggregated: dict[str, tuple[Decimal, Decimal]] = {}
    for account in accounts:
        if any(
            other != account and account.startswith(other + ":")
            for other in accounts
        ):
            continue
        for currency, budget in budgets.calculate_children(
            account,
            begin_date,
            end_date,
        ).items():
            budgeted, actual = aggregated.get(
                currency,
                (Decimal(0), Decimal(0)),
            )
            aggregated[currency] = (
                budgeted + budget,
                actual + actual_for(account, currency),
            )

    totals = [
        BudgetRowData("", 0, currency, budgeted, actual)
        for currency, (budgeted, actual) in sorted(aggregated.items())
    ]
    return rows, totals
