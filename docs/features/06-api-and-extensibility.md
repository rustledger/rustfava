# 06 — API & extensibility

## The JSON API

Everything the frontend does goes through a JSON API under
`/<ledger>/api/…`, which is therefore available to the user's own tooling.
Capabilities, grouped:

- **Report data**: `income_statement`, `balance_sheet`, `trial_balance`,
  `account_report`, `journal` / `journal_page` (paginated), `events`,
  `documents`, `commodities`, `options`, `statistics` — all honoring the
  same filter/conversion/interval query parameters as the UI.
- **Query**: `query?query_string=…` returns typed columns + rows;
  `download-query/query_result.<csv|xlsx|ods>` streams exports.
- **Source access**: `source` (read file), `source` PUT (write with
  sha256 conflict check), `source_slice` GET/PUT/DELETE (entry-level),
  `format_source`, `context` (entry with before/after balances).
- **Entry creation**: `add_entries` (structured JSON entries written to
  the ledger), `attach_document`, `add_document` (upload),
  `upload_import_file`, `move` (rename/move a file), `delete_document`.
- **Autocomplete data**: `payee_accounts`, `payee_transaction`,
  `narration_transaction`, `narrations`.
- **Import**: `imports` (candidate files), `extract` (run an importer).
- **Change polling**: `changed` (has the ledger changed on disk?) — the
  UI polls this; third parties can too.
- Errors return structured JSON with an error string and proper HTTP
  status codes.

## Extension system

Users can write Python extensions declared in the ledger
(`custom "fava-extension" "my_ext" "{config}"`), which can:

- Add whole **new reports** (a sidebar entry + a Jinja2-templated page).
- Ship **JavaScript modules** loaded into the frontend.
- Expose **custom endpoints** under `/extension/<name>/…`.
- **Hook lifecycle events**: after an entry is inserted, after a file is
  saved, etc. (the bundled `auto_commit` uses these to git-commit changes).

Bundled extensions: `auto_commit` (git-commit on change),
`portfolio_list` (portfolio table report; example of a report extension).

## URL contract

Stable, user-visible URL scheme: `/<ledger-slug>/<report>/…` with filter
state in query parameters (`time`, `account`, `filter`, `conversion`,
`interval`) — links are shareable and long-lived; `/jump` re-targets a URL
across ledgers. A `--prefix` option supports serving behind a reverse
proxy path.
