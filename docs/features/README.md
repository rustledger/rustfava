# Rustfava feature inventory

A complete inventory of what rustfava does **from the user's point of view**,
written as a requirements baseline for reimplementing the application. It
deliberately describes *what* the user can do, never *how* the code does it.

Extracted from the actual code surfaces (reports, routes, API, options,
engine) at v1.31/main, 2026-07.

| Document | Covers |
|---|---|
| [01 — Ledger input & engine](01-ledger-and-engine.md) | Accepted file format, directives, booking, plugins, encryption, error reporting |
| [02 — Reports](02-reports.md) | Every page/report in the web UI and what it shows |
| [03 — Filtering, navigation & display](03-filtering-navigation-display.md) | The filter bar, time syntax, conversion modes, intervals, sidebar, i18n, shortcuts |
| [04 — Editing, documents & import](04-editing-documents-import.md) | The editor, file mutations, document management, the import workflow |
| [05 — Query & exports](05-query-and-exports.md) | The BQL query language surface and export formats |
| [06 — API & extensibility](06-api-and-extensibility.md) | The JSON API as a user capability, the extension system |
| [07 — Deployment & platforms](07-deployment-and-platforms.md) | CLI, serving modes, desktop app, distribution channels |

## Scope rules used throughout

- A "feature" is anything a user can observe, invoke, configure, or depend on.
- Engine behavior is included where the user can see it (error messages,
  booking outcomes, plugin effects), excluded where they cannot.
- Anything marked **(differs from beancount/fava)** is a deliberate or known
  divergence a rewrite must decide whether to preserve.
