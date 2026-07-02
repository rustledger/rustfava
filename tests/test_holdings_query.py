"""The Holdings report's query compiles and returns cost-dated lots.

Regression coverage for https://github.com/rustledger/rustfava/issues/190 —
the query orders by ``cost_date``, a raw column that is aliased in the SELECT
(``cost_date as acquisition_date``). rustledger's compiler used to drop the
hidden sort column for aliased raw columns and every Holdings render failed
with ``column 'cost_date' not found`` (rustledger/rustledger#1627, fixed in
rustledger/rustledger#1631, shipped in v0.17.0).

The query below must stay in sync with
``frontend/src/reports/holdings/index.ts``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from rustfava.core import RustfavaLedger
from rustfava.core.inventory import SimpleCounterInventory
from rustfava.core.query import QueryResultTable

if TYPE_CHECKING:
    from pathlib import Path

_HOLDINGS_QUERY = """
SELECT
  account,
  units(sum(position)) as units,
  cost_number as cost,
  first(getprice(currency, cost_currency)) as price,
  cost(sum(position)) as book_value,
  value(sum(position)) as market_value,
  safediv((abs(sum(number(value(position))))
           - abs(sum(number(cost(position))))),
          sum(number(cost(position)))) * 100 as unrealized_profit_pct,
  cost_date as acquisition_date
WHERE account_sortkey(account) ~ "^[01]"
GROUP BY account, cost_date, currency, cost_currency, cost_number,
         account_sortkey(account)
ORDER BY account_sortkey(account), currency, cost_date
""".strip()

_LEDGER = """
2020-01-01 open Assets:Bank:Checking      USD
2020-01-01 open Assets:Brokerage          USD,AAPL,VTI
2024-01-20 * "Brokerage" "Buy index fund"
  Assets:Brokerage         10 VTI {450.00 USD, 2024-01-20}
  Assets:Bank:Checking  -4500.00 USD
2024-01-21 * "Brokerage" "Buy index fund"
  Assets:Brokerage         20 VTI {400.00 USD, 2024-01-21}
  Assets:Bank:Checking  -8000.00 USD
"""


def test_holdings_query_compiles_with_cost_dated_lots(tmp_path: Path) -> None:
    """The exact repro from #190: two cost-dated lots of the same commodity."""
    path = tmp_path / "holdings.beancount"
    path.write_text(_LEDGER)
    ledger = RustfavaLedger(str(path))

    result = ledger.query_shell.execute_query_serialised(
        ledger.all_entries, _HOLDINGS_QUERY
    )

    assert isinstance(result, QueryResultTable)
    units: list[Decimal] = []
    for row in result.rows:
        inventory = row[1]
        if row[0] == "Assets:Brokerage" and isinstance(
            inventory, SimpleCounterInventory
        ):
            vti = inventory.get("VTI")
            if vti is not None:
                units.append(vti)
    assert sorted(units) == [Decimal(10), Decimal(20)], (
        "expected the two VTI lots to survive the GROUP BY on cost_date"
    )
