"""Unit coverage for the small rustledger support modules.

Part of the coverage burn-down phase 2 (backend.py, options.py, loader.py
edges) — these were exempt from the 100% gate until now.
"""

from __future__ import annotations

import builtins
from decimal import Decimal
from typing import Any

import pytest

from rustfava.rustledger.backend import get_engine
from rustfava.rustledger.engine import RustledgerError
from rustfava.rustledger.options import _RLCurrencyContext
from rustfava.rustledger.options import RLBooking
from rustfava.rustledger.options import RLDisplayContext
from rustfava.rustledger.options import RLDisplayFormatter


def test_get_engine_missing_wasmtime_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken install (no component engine import) raises RustledgerError
    with a reinstall hint, not a bare ImportError."""
    real_import = builtins.__import__

    def block_component(name: str, *args: Any, **kwargs: Any) -> Any:
        if "component_engine" in name:
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", block_component)
    with pytest.raises(RustledgerError, match="wasmtime"):
        get_engine()


def test_display_formatter_precision_and_commas() -> None:
    ctx = RLDisplayContext(
        {"display_precision": {"USD": 2, "JPY": 0}, "render_commas": True}
    )
    formatter = ctx.build()
    assert formatter.format(Decimal("1234567.891"), "USD") == "1,234,567.89"
    assert formatter.format(Decimal("1234567.891"), "JPY") == "1,234,568"
    # unknown currency falls back to 2 decimal places
    assert formatter.format(Decimal("1.005"), "XXX") == "1.00"


def test_display_formatter_without_commas_and_quantize() -> None:
    formatter = RLDisplayFormatter({"USD": 2}, render_commas=False)
    assert formatter.format(Decimal("1234.5"), "USD") == "1234.50"
    assert formatter.quantize(Decimal("1.005"), "USD") == Decimal("1.00")
    assert formatter.quantize(Decimal("1.005"), "ZZZ") == Decimal("1.00")


def test_booking_equality_semantics() -> None:
    strict = RLBooking("STRICT")
    assert strict == "strict"
    assert strict == RLBooking("STRICT")
    assert strict != RLBooking("FIFO")
    assert strict != 42


def test_booking_str_hash_and_currency_context() -> None:
    assert str(RLBooking("FIFO")) == "FIFO"
    # __eq__ without __hash__ makes RLBooking unhashable (beancount's
    # Booking enum IS hashable) — documented current behavior.
    with pytest.raises(TypeError, match="unhashable"):
        hash(RLBooking("FIFO"))
    assert _RLCurrencyContext(4).get_fractional() == 4
