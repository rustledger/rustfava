# 02 — Reports

Every page in the web interface and what the user sees and can do there.
All reports respect the global filter bar, conversion mode and interval
(see 03) unless noted.

## Tree reports (Income Statement, Balance Sheet, Trial Balance)

- Hierarchical account tables with per-account and rolled-up subtotals,
  one column per operating currency plus an "Other" column.
- Rows expand/collapse; a `collapse_pattern` option pre-collapses matching
  accounts; closed/zero accounts can be hidden via options.
- Every account name links to its Account report; every balance links to
  the journal filtered to that account and period.
- **Income Statement**: net profit row; income/expense sections; optional
  sign inversion via `invert_income_liabilities_equity`.
- **Balance Sheet**: assets/liabilities/equity sections; net worth summary;
  opening balances synthesized at the period start when a time filter cuts
  the ledger (`Unrealized`/conversion accounts named by options).
- **Trial Balance**: all accounts, debit/credit style totals.
- Charts atop each: net-worth/total **line chart** over time, per-interval
  **bar chart** (stacked by currency, with budgets overlaid where defined),
  and **hierarchy charts** (treemap and sunburst per currency) for the
  account breakdown. Chart mode toggles persist.

## Account report (`/account/<name>/`)

- Everything about one account: balances chart over time, per-interval
  bars, and its journal.
- Tabs/modes: journal, balances table (per interval), changes table
  (per interval).
- Includes sub-accounts by default (`account_journal_include_children`).
- Up-to-date indicators: colored dots show whether the account's last
  balance assertion is recent (green/yellow/red, greying after
  `uptodate_indicator_grey_lookback_days`).

## Journal

- Chronological entry list: transactions, balances (with pass/fail
  coloring), notes, documents, events, queries, pads, open/close.
- Per-row expansion shows postings and metadata; toggle buttons filter by
  entry type (open/close/transaction/balance/note/document/…) and by
  transaction flag (`*`, `!`, `P`); toggles for showing metadata and
  postings.
- Every tag/link/payee is clickable and becomes a filter; file/line links
  open the editor at the entry.
- New-entry button opens the add-transaction dialog anywhere.

## Holdings

- Current lots held, with units, acquisition cost, acquisition date, price,
  book value, market value and unrealized profit percentage.
- Four groupings, each its own page: flat lot list, **by account**,
  **by currency**, **by cost currency**; grouped views show aggregate
  average cost and totals.

## Commodities

- Every commodity pair with price history: latest price, price chart over
  time, and the price table.

## Events

- All `event` directives grouped by type, with a scatter plot over time and
  per-type listing.

## Statistics

- Postings-per-account table, entries by type, activity by month
  (update activity heat), number of directives/accounts/commodities.

## Options

- Read-only display of all active Beancount options and all Fava options,
  with the values in effect.

## Errors

- Every error with message and source location, linked to the editor.

## Editor, Query, Documents, Import

Covered in their own documents (04, 05, 04 respectively).

## Help

- Bundled documentation pages rendered in-app (index plus topic pages,
  e.g. filter syntax, options reference, budgets), showing the running
  version.

## Not present (a rewrite should not assume them)

- No global full-text search (the filter bar is the search).
- No price fetching (prices come from the ledger).
- No multi-user accounts, authentication or permissions (see 07 for
  read-only/incognito serving modes).
