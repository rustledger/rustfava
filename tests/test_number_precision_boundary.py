"""Number-precision boundary characterization (Layer 2 of correctness plan).

The JSON API serializes every ``Decimal`` via ``float()``
(``core/charts.py:_json_default``), so exact ledger Decimals cross the wire as
IEEE-754 float64. The frontend has no decimal type and renders numbers through
``Intl.NumberFormat`` at display precision, so **typical currency values are
unaffected in the rendered UI** — but the float rounding is visible to raw JSON
API consumers, CSV/Excel export (``util/excel.py`` also does ``float()``), and
column sorting, and it silently corrupts high-precision values.

These tests pin the boundary so it can't regress and so a future fix is
measurable:

* ``test_typical_values_are_lossless`` — currency and reasonable crypto
  magnitudes must survive the wire exactly (they do today: float64 holds ~15-16
  significant digits). This guards the common case.
* ``test_high_precision_is_lost`` — documents, as an ``xfail``, that values
  beyond float64's precision are rounded on the wire. It flips to passing once
  numbers are emitted exactly, which requires an exact JSON encoder (e.g.
  ``simplejson`` with ``use_decimal``) **and** frontend decimal support — the
  wire change alone also regenerates every snapshot, so it belongs with that
  epic, not in isolation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from rustfava.core.charts import dumps
from rustfava.core.charts import loads


def _round_trip(value: Decimal) -> Decimal:
    """Serialize a Decimal through the real API provider and read it back."""
    wire = dumps({"n": value})
    return Decimal(str(loads(wire)["n"]))


# Values a real ledger produces: 2dp fiat, 8dp crypto, large-but-bounded share
# counts, small residues. All within float64's ~15-16 significant digits.
LOSSLESS = [
    "0",
    "100.00",
    "-1234.56",
    "0.00801",
    "1234567.89",
    "0.12345678",  # 8dp crypto
    "12345678.12345678",  # 16 significant digits
    "-9876543.21",
]


@pytest.mark.parametrize("literal", LOSSLESS)
def test_typical_values_are_lossless(literal: str) -> None:
    """Currency and reasonable-precision values must cross the wire exactly."""
    value = Decimal(literal)
    assert _round_trip(value) == value


# Values beyond float64 precision: a division result (conversions / unrealized
# %), a large magnitude with decimals, and a high-precision large number.
LOSSY = [
    "88.571428571428571428571429",  # 26 significant digits (e.g. 620/7)
    "123456789012.123456",  # 18 significant digits
    "9999999999999999.01",  # rounds catastrophically to 1e16
]


@pytest.mark.parametrize("literal", LOSSY)
@pytest.mark.xfail(
    reason="Decimal->float64 at the JSON boundary (core/charts.py) rounds "
    "beyond ~16 significant digits. Fixing end-to-end needs an exact JSON "
    "encoder plus frontend decimal support (and regenerates all snapshots); "
    "see the correctness plan. Flips green when numbers are emitted exactly.",
    strict=True,
)
def test_high_precision_is_lost(literal: str) -> None:
    """High-precision values are currently rounded on the wire (documented)."""
    value = Decimal(literal)
    assert _round_trip(value) == value


def test_api_numbers_are_json_numbers_not_strings() -> None:
    """Pin the current wire contract: report numbers serialize as JSON numbers.

    A deliberate switch to exact string/tagged encoding must update this test,
    so the wire-format change can't happen silently.
    """
    wire = dumps({"n": Decimal("100.00")})
    assert '"n":100' in wire  # a bare JSON number, not "100.00" quoted
