# 05 — Query & exports

## The Query report (BQL)

An interactive SQL-like console over the ledger, honoring the global
filters (the query runs against the filtered entry set).

### Language surface

- `SELECT <targets> [FROM …] [WHERE …] [GROUP BY …] [ORDER BY … [ASC|DESC]]
  [LIMIT n]`, with `DISTINCT`, aliases (`AS`), and aggregate functions
  `SUM`, `COUNT` (column and `*` semantics differ per SQL), `FIRST`,
  `LAST`, `MIN`, `MAX`, `AVG`.
- Posting-level columns: `date`, `flag`, `payee`, `narration`, `account`,
  `position`, `units`, `cost`, `price`, `weight`, `balance` (running),
  `number`, `currency`, `cost_currency`, `cost_date`, `cost_number`,
  `tags`, `links`, metadata via `META`/`posting_meta`/`open_meta`, plus
  entry identity (`id`, `filename`, `lineno`).
- Entry-set functions usable in `FROM`/as tables: `entries`, `postings`,
  `transactions`, `prices`, `balances`, `documents`, `notes`, `events`,
  `commodities`, `accounts`.

### Functions (67)

- **Dates**: `YEAR MONTH DAY QUARTER WEEKDAY YMONTH DATE DATE_ADD
  DATE_DIFF DATE_PART DATE_TRUNC DATE_BIN PARSE_DATE TODAY INTERVAL
  OPEN_DATE CLOSE_DATE`
- **Strings**: `UPPER LOWER TRIM LENGTH SUBST SUBSTRING SPLITCOMP JOINSTR
  MAXWIDTH STARTSWITH ENDSWITH GREP GREPN STR`
- **Accounts**: `PARENT LEAF ROOT ACCOUNT_DEPTH ACCOUNT_SORTKEY OPEN_META`
- **Amounts/inventories**: `NUMBER CURRENCY UNITS COST VALUE CONVERT
  GETPRICE ONLY FILTER_CURRENCY EMPTY POSSIGN WEIGHT NEG ABS ROUND SAFEDIV`
- **Casts/util**: `INT DECIMAL BOOL COALESCE GET POSTING_META`
- NULL propagates through scalar functions and arithmetic
  (SQL semantics); `SAFEDIV` yields 0 on zero divisors.

### Results

- Rendered as a sortable table; inventory/amount cells rendered with
  currency formatting; account cells linked.
- When the result groups by a time-like column, an automatic **chart** is
  offered (line/bar), like any report chart.
- `journal`-style queries (selecting entries) render as a journal, not a
  table.

### Saved queries

- `query` directives in the ledger appear in the sidebar and on the Query
  page for one-click execution.

## Exports

- Query results download as **CSV**, and as **XLSX** or **ODS** when the
  spreadsheet extra is installed. Exported numbers are exact decimals.
- **Journal download**: the filtered journal exports as ledger-format text.
- Every report is a URL; the JSON API (06) provides all report data
  machine-readably.
