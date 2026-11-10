"""NGZR fork: Chinese display names for accounts.

Beancount account names must be ASCII ([A-Z][A-Za-z0-9-]*(:...)*), so a
Chinese name can only live outside the name itself. This ledger keeps one in
the "alias" metadata of every open directive. This module maps a real account
name to a composed display path (one alias per level) and resolves display
strings back to real names, so the UI reads Chinese while links, filters and
account pages keep round-tripping.

Design notes
------------
* Display only. The loaded ledger keeps real (ASCII) names, so engine calls,
  BQL queries, balance maths and file editing are untouched.
* Every place that puts an account name into JSON for the frontend must map it
  through display(); every place that takes one back from the frontend must map
  it through resolve().
* Kill switch: RUSTFAVA_ACCOUNT_ALIAS=0 disables the feature and the UI falls
  back to the real names.

Known limitation: BQL query results (#postings etc.) are produced by the
rustledger engine and stay in the real names.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence

    from rustfava.beans.abc import Directive

# Fallback display for the five root account types (their own open directive
# may not carry an alias).
_ROOTS: dict[str, str] = {
    "Assets": "资产",
    "Liabilities": "负债",
    "Equity": "权益",
    "Income": "收入",
    "Expenses": "支出",
}

# Fallback display for the segments that reporting synthesises rather than
# the ledger declaring them. tree.cap() prepends the equity root to
# options["account_current_earnings"] / account_current_conversions, and the
# unrealized-gains placeholder comes from Fava's own option, so none of those
# accounts appear in an open directive and can never carry an alias.
_SEGMENTS: dict[str, str] = {
    "Earnings": "留存收益",
    "Current": "本期",
    "Conversions": "汇兑损益",
    "Unrealized": "未实现损益",
}

#: Real account name -> alias of that single level.
_alias: dict[str, str] = {}
#: Real account name -> composed display path.
_display: dict[str, str] = {}
#: Composed display path -> real account name (only unambiguous entries).
_resolve: dict[str, str] = {}
#: Leaf alias (e.g. "基本户") -> real account name, when unambiguous.
_resolve_leaf: dict[str, str] = {}
#: Every known real account name (to detect "already a real name").
_known: set[str] = set()


def enabled() -> bool:
    """Whether Chinese account display names are enabled."""
    return os.environ.get("RUSTFAVA_ACCOUNT_ALIAS", "1").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def reset() -> None:
    """Clear all maps (called on every ledger load)."""
    _alias.clear()
    _display.clear()
    _resolve.clear()
    _resolve_leaf.clear()
    _known.clear()


def _compose(account: str) -> str:
    """Compose the display path for one account from per-level aliases."""
    parts = [
        segment
        for index, segment in enumerate(account.split(":"))
        # Fava's tree.cap() prepends the equity root to the (already
        # root-prefixed) earnings account, producing Equity:Equity:... - drop
        # the accidental repeat so the display path stays readable.
        if not (index > 0 and segment in _ROOTS)
    ]
    out: list[str] = []
    for index, segment in enumerate(parts):
        prefix = ":".join(parts[: index + 1])
        out.append(
            _alias.get(prefix)
            or _ROOTS.get(prefix)
            or _SEGMENTS.get(segment)
            or segment,
        )
    return ":".join(out)


def register(entries: Sequence[Directive]) -> None:
    """Collect alias metadata and rebuild the display/resolve maps.

    Called right after the ledger is loaded; entries keep their real names.
    """
    reset()
    if not enabled():
        return

    for entry in entries:
        account = getattr(entry, "account", None)
        if not isinstance(account, str) or not account:
            continue
        # A Transaction exposes accounts only through its postings and would
        # pollute the map with its own (absent) meta.
        if getattr(entry, "postings", None):
            continue
        _known.add(account)
        meta = getattr(entry, "meta", None)
        if isinstance(meta, Mapping):
            alias = meta.get("alias")
            if isinstance(alias, str) and alias.strip():
                _alias[account] = alias.strip()

    if not _alias:
        return

    for account in set(_alias) | _known:
        _display[account] = _compose(account)

    ambiguous: set[str] = set()
    for account, shown in _display.items():
        if shown in _resolve and _resolve[shown] != account:
            ambiguous.add(shown)
        else:
            _resolve[shown] = account
    for shown in ambiguous:
        _resolve.pop(shown, None)

    leaf_candidates: dict[str, list[str]] = {}
    for account, alias in _alias.items():
        if ":" in account:
            leaf_candidates.setdefault(alias, []).append(account)
    for alias, accounts in leaf_candidates.items():
        if len(accounts) == 1:
            _resolve_leaf[alias] = accounts[0]


def display(account: str) -> str:
    """Display name for a real account name (identity when unknown)."""
    if not _display:
        return account
    mapped = _display.get(account)
    if mapped is not None:
        return mapped
    # Accounts synthesised while reporting (tree.cap() inserts and the
    # unrealized-gains placeholder) never appear in an open directive, so they
    # are missing from the maps - compose on demand instead. That also applies
    # the builtin root and generated-segment names.
    return _compose(account)


def resolve(text: str) -> str:
    """Real account name for a display name, real name, or unique leaf alias."""
    if not _display or not text:
        return text
    if text in _resolve:
        return _resolve[text]
    if text in _known:
        return text
    return _resolve_leaf.get(text, text)


def has_mapping() -> bool:
    """Whether any alias was registered (useful for diagnostics)."""
    return bool(_display)
