# 04 — Editing, documents & import

Everything that mutates the user's files. All of it is disabled by the
`--read-only` serving mode.

## The editor

- Full source editor for every file in the ledger tree (file switcher for
  includes), with Beancount syntax highlighting, folding, and
  autocompletion of accounts, payees, tags, links and directive keywords.
- Save writes the file to disk (with conflict detection: saving stale
  content is rejected, using a content hash).
- **Format source**: one click canonically reformats the buffer (amount
  alignment to `currency_column` or fixed `indent`; deterministic layout).
- Jump-to-error: error listings open the editor at the exact line;
  jump-to-entry from any journal row.
- External editor mode (`use_external_editor`): links open
  `beancount://` URLs instead of the web editor.

## Entry manipulation without the editor

- **Add transaction dialog** (from any page): payee with autocomplete
  (recalling the payee's last transaction as a template), narration,
  arbitrary metadata, any number of postings with account autocomplete;
  saves into the correct file honoring `insert_entry` rules (regex-directed
  placement per account, before/after markers, date-aware).
- **Slice editing**: any existing entry can be edited in place as its raw
  source slice (with the same stale-write protection) or deleted outright.
- Context view for any entry: its source slice plus the account balances
  immediately before and after it.

## Documents

- `document` directives and files discovered in `documents` directories
  are listed in the Documents report, organized by account, previewable
  in-browser (PDF and images render inline).
- Upload documents from the browser (drag & drop): stored into the
  document directory by account and date-prefixed name.
- Attach a document to an existing entry (adds metadata linking it).
- Move/rename and delete document files from the UI.
- A transaction's `statement` metadata links the entry to its document.

## Import

- Configurable importer framework: a Python `import_config` file declares
  importers; `import_dirs` are scanned.
- The Import report lists candidate files per importer, with the account
  and date detected.
- **Extract & review**: importing shows the extracted entries for review
  and editing (same slice editor) before committing; duplicates against
  existing entries are flagged; imported entries are written to the right
  file per `insert_entry`.
- Files can be uploaded to the import directories from the browser, and
  moved/renamed into their documents location after import.
- Requires the `beancount-compat` extra for beangulp-based importers.

## Version control convenience

- Bundled `auto_commit` extension: when enabled in the ledger, every change
  made through the web UI is git-committed automatically.
