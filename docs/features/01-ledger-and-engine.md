# 01 — Ledger input & engine capabilities

What the user can put in their files and what the system does with it.

## Accepted input

- Plain-text Beancount-syntax ledger files, UTF-8.
- Multiple files: `include` directives are followed; the web UI treats the
  whole tree as one ledger and knows which file each entry came from.
- Multiple independent ledgers can be served at once (each gets its own
  URL slug, derived from the ledger's `title` option or the file name).
- **GPG-encrypted ledgers** (`.gpg`/`.asc`): decrypted transparently via the
  system `gpg` (user's keyring and gpg-agent). Detection is automatic; a
  ledger the keyring cannot decrypt fails with a clear error, never a crash.
- Files with invalid Unicode degrade gracefully (pages render, errors shown).

## Directives

All Beancount directive types are understood and displayed:
`open` (with currency constraints and per-account booking method), `close`,
`transaction` (flags, payee, narration, tags, links, metadata, postings with
cost/price), `balance` (with tolerance), `pad`, `note`, `document`, `price`,
`event`, `commodity`, `query` (named queries appear in the UI), `custom`
(including `fava-option` and budget entries), `option`, `plugin`, `include`,
`pushtag`/`poptag`.

Posting-level capabilities the user can rely on:

- Costs: per-unit `{1.00 USD}`, total `{# 10.00 USD}`, compound
  `{1.00 # 5.00 USD}` (weighs N·per-unit + total), cost dates, lot labels,
  empty `{}` / bare-currency `{USD}` costs (inferred from the residual).
- Prices: per-unit `@` and total `@@`.
- Amount interpolation (one posting may omit its amount).
- Arithmetic in amounts (`(1/3)` etc.), comma thousands separators.
- Metadata on entries and on individual postings (strings, numbers,
  booleans, dates, amounts, accounts).

## Booking

Per-account (via `open`) or global (via the `booking_method` option):
`STRICT` (default), `STRICT_WITH_SIZE`, `FIFO`, `LIFO`, `HIFO`, `AVERAGE`,
`NONE`. Ambiguous reductions, oversells and mismatched lots produce errors
pointing at the offending entry. Padding (`pad`) synthesizes balancing
transactions, flagged `P`, before the corresponding `balance` assertion.

## Plugins

- **31 built-in plugins** run natively when declared with `plugin "name"`:
  `auto_accounts`, `auto_tag`, `box_accrual`, `capital_gains_classifier`,
  `check_average_cost`, `check_closing`, `check_commodity`, `check_drained`,
  `close_tree`, `coherent_cost`, `commodity_attr`, `currency_accounts`,
  `document_discovery`, `effective_date`, `forecast`,
  `generate_base_ccy_prices`, `implicit_prices`, `leaf_only`,
  `no_duplicates`, `no_unused`, `one_commodity`, `pedantic`,
  `rename_accounts`, `rx_txn`, `sell_gains`, `split_expenses`,
  `unique_prices`, `unrealized`, `utils`, `valuation`, `zerosum`.
  Beancount-namespaced names (`beancount.plugins.auto_accounts`) map to the
  same implementations.
- **Arbitrary Python plugins** also run, if importable, with their config
  strings, and their errors surface in the Errors report.
  **(differs from beancount)**: module-based Python plugins work only when a
  native implementation exists or the Python module is installed alongside.

## Options honored

Beancount options that change user-visible behavior are honored, including:
`title`, `operating_currency` (drives report columns and charts),
`name_assets`/`name_liabilities`/`name_equity`/`name_income`/`name_expenses`
(root account renaming), `booking_method`, `render_commas`,
`display_precision` / inferred precision per currency (drives all number
formatting), balance-assertion tolerance options, `documents` (directories
scanned for document discovery).

## Error reporting

- Parse errors, booking errors, validation errors, plugin errors and
  balance-assertion failures are collected (not fatal) and shown in the
  Errors report with file/line, clickable through to the editor.
- The error count is always visible in the sidebar.

## Fidelity guarantees a rewrite must match

- Amounts are exact decimals end to end: query results, JSON API responses
  and spreadsheet exports carry exact decimal values, never float64
  approximations.
- Booking outcomes are verified against reference beancount behavior by a
  differential corpus (held-at-cost lots, multi-currency, pad/balance
  interactions, date boundary cases, ~200 cost lots in one fixture).
