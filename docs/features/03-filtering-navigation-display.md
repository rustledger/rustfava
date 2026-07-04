# 03 — Filtering, navigation & display

Global controls that apply across reports.

## The filter bar

Three cooperating filters, kept in the URL (so every filtered view is a
shareable/bookmarkable link):

1. **Time filter.** Accepts: years (`2024`), quarters (`2024-Q1`), months
   (`2024-06`), weeks, days; ranges with `-` (`2023 - 2024-06`); relative
   keywords `year`, `quarter`, `month`, `week`, `day` with offsets
   (`year-1`, `month-2`); fiscal years `FY2024`, `FY2024-Q2` honoring the
   `fiscal_year_end` option (including year-crossing fiscal years).
2. **Account filter.** An account name (with autocomplete); matches the
   account and its descendants; regular expressions supported.
3. **Advanced filter.** A small expression language over entries:
   `#tag`, `^link`, `payee:"…"` (regex), `narration:"…"`, `number:…`,
   metadata `key:value` matches, `any(…)` / `all(…)` over postings
   (e.g. `any(account:"Assets:.*")`), negation with `-`, conjunction by
   juxtaposition. Malformed filters produce a visible, non-fatal error.

## Conversion / valuation modes

A global selector that re-values every report: **units** (raw commodity
amounts), **at cost** (book value), **at market value** (via latest prices),
or **converted to a specific currency** (any currency seen in the ledger, or
those whitelisted by `conversion_currencies`).

## Intervals

Bar charts and per-interval tables can be grouped by **year, quarter,
month, week, or day**.

## Sidebar & navigation

- Ledger switcher when multiple files are served.
- Navigation to all reports; error count badge; upcoming events count
  (within `upcoming_events` days); user-saved `query` directives listed for
  one-click running (up to `sidebar_show_queries`).
- Add-transaction button and other quick actions.
- Extension reports appear as additional sidebar entries.

## Keyboard control

- `?` opens a shortcut overlay; two-key sequences navigate between reports
  (g then a letter); j/k style movement in journals; Enter/Escape and
  save-shortcut in dialogs and the editor.

## Display & theming

- Light and dark theme following the OS preference.
- Numbers formatted per-currency to the ledger's inferred or declared
  precision; optional thousands separators (`render_commas`); locale-aware
  formatting via the `locale` fava-option.
- Charts: line, stacked interval bars, treemap, sunburst, scatter; all with
  tooltips; chart type toggles remembered per report; charts can be hidden.
- Income/gain-loss color conventions, optionally inverted
  (`invert_gains_losses_colors`, `invert_income_liabilities_equity`).

## Internationalization

Interface translations bundled for: Bulgarian, Catalan, German, Spanish,
Persian, French, Japanese, Korean, Dutch, Portuguese, Brazilian Portuguese,
Russian, Slovak, Swedish, Ukrainian, Chinese (Simplified), Chinese
(Traditional, Taiwan). Language auto-detected from the browser or forced
via the `language` fava-option.

## Auto-reload

- The browser reloads report data when ledger files change on disk
  (file-watcher based; `--poll-watcher` for filesystems without inotify);
  full auto page reload opt-in via the `auto_reload` fava-option; a
  "changed on disk" indicator otherwise.
