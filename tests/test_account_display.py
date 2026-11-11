"""Tests for Chinese account display names derived from alias metadata."""

from __future__ import annotations

import pytest

from rustfava import account_display


class _Entry:
    """Minimal stand-in for an open directive (or any entry with a meta)."""

    def __init__(self, account: str, alias: str | None = None) -> None:
        self.account = account
        self.meta: dict[str, object] = {}
        if alias is not None:
            self.meta["alias"] = alias


def _entries() -> list[_Entry]:
    return [
        _Entry("Assets", "\u8d44\u4ea7"),
        _Entry("Assets:Bank", "\u94f6\u884c"),
        _Entry("Assets:Bank:MainAccount", "\u57fa\u672c\u6237"),
        _Entry("Expenses:Project", "\u9879\u76ee"),
        _Entry("Expenses:Project:Dev", "\u5f00\u53d1"),
    ]


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RUSTFAVA_ACCOUNT_ALIAS", raising=False)
    account_display.reset()


def test_display_composes_one_alias_per_level() -> None:
    account_display.register(_entries())  # type: ignore[arg-type]
    assert account_display.display("Assets:Bank:MainAccount") == (
        "\u8d44\u4ea7:\u94f6\u884c:\u57fa\u672c\u6237"
    )


def test_display_translates_known_prefix_of_unknown_account() -> None:
    """Generated subaccounts still get their known prefix translated."""
    account_display.register(_entries())  # type: ignore[arg-type]
    assert account_display.display("Income:Unknown") == (
        "\u6536\u5165:Unknown"
    )
    assert account_display.display("NotAnAccount") == "NotAnAccount"


def test_display_falls_back_to_root_names() -> None:
    """Root types are often not opened explicitly."""
    account_display.register([_Entry("Assets:Bank:MainAccount", "x")])
    assert account_display.display("Liabilities") == "\u8d1f\u503a"


def test_display_collapses_duplicated_root_segment() -> None:
    """tree.cap() prepends the equity root to an already-rooted account."""
    account_display.register([_Entry("Equity", "\u6743\u76ca")])
    assert account_display.display("Equity:Equity:Earnings") == (
        "\u6743\u76ca:\u7559\u5b58\u6536\u76ca"
    )


def test_display_translates_generated_segments() -> None:
    """Reporting synthesises accounts that can never carry an alias."""
    account_display.register([_Entry("Equity", "\u6743\u76ca")])
    assert account_display.display("Equity:Unrealized") == (
        "\u6743\u76ca:\u672a\u5b9e\u73b0\u635f\u76ca"
    )
    assert account_display.display("Equity:Equity:Earnings:Current") == (
        "\u6743\u76ca:\u7559\u5b58\u6536\u76ca:\u672c\u671f"
    )


def test_resolve_accepts_display_real_name_and_leaf_alias() -> None:
    account_display.register(_entries())  # type: ignore[arg-type]
    real = "Assets:Bank:MainAccount"
    display = account_display.display(real)
    assert account_display.resolve(display) == real
    assert account_display.resolve(real) == real
    assert account_display.resolve("\u57fa\u672c\u6237") == real


def test_resolve_leaves_unambiguous_misses_alone() -> None:
    account_display.register(_entries())  # type: ignore[arg-type]
    assert account_display.resolve("nothing like an account") == (
        "nothing like an account"
    )


def test_kill_switch_disables_all_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUSTFAVA_ACCOUNT_ALIAS", "0")
    account_display.register(_entries())  # type: ignore[arg-type]
    assert not account_display.has_mapping()
    assert account_display.display("Assets:Bank") == "Assets:Bank"