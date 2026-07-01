"""Number-precision at the JSON boundary (Layer 2 of the correctness plan).

The JSON API now serialises every ``Decimal`` as an **exact number literal**
(``core/charts.py`` uses ``simplejson`` with ``use_decimal``), so the wire
carries full precision — a decimal-aware consumer (an exact API client, or a
future frontend decimal type) recovers the exact ledger value, and
custom/budget amounts no longer leak as ``float`` (R8).

A float-parsing consumer (plain ``JSON.parse`` in the browser, or stdlib
``json.loads``) still narrows to float64 on read — that residual is the
frontend-decimal step, tracked separately. The frontend renders through
``Intl.NumberFormat`` at display precision, so typical values are unaffected in
the UI regardless.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import simplejson

from rustfava.core.charts import dumps
from rustfava.core.charts import loads


def _wire_value(value: Decimal) -> Decimal:
    """The exact Decimal an exact consumer recovers from the wire."""
    parsed = simplejson.loads(dumps({"n": value}), use_decimal=True)
    return Decimal(parsed["n"])


# A spread of real-ledger and adversarial magnitudes: 2dp fiat, 8dp crypto,
# division results (conversions / unrealized %), large magnitudes, and values
# well beyond float64's ~16 significant digits.
VALUES = [
    "0",
    "100.00",
    "-1234.56",
    "0.00801",
    "0.12345678",  # 8dp crypto
    "12345678.12345678",  # 16 significant digits
    "88.571428571428571428571429",  # 26 sig digits (e.g. 620/7)
    "123456789012.123456",  # 18 significant digits
    "9999999999999999.01",  # would round to 1e16 as a float
]


@pytest.mark.parametrize("literal", VALUES)
def test_values_cross_the_wire_exactly(literal: str) -> None:
    """Every value survives the wire exactly, at any precision."""
    value = Decimal(literal)
    assert _wire_value(value) == value


@pytest.mark.parametrize(
    "literal", ["88.571428571428571428571429", "9999999999999999.01"]
)
def test_float_parsing_consumer_still_rounds(literal: str) -> None:
    """A float-parsing read still narrows to float64 (the residual gap).

    Documents that plain ``json.loads``/``JSON.parse`` rounds high-precision
    values — the frontend-decimal step. Flips (this test's premise breaks) if a
    decimal-aware parser is adopted on the read side.
    """
    value = Decimal(literal)
    assert Decimal(str(loads(dumps({"n": value}))["n"])) != value


def test_api_numbers_are_json_numbers_not_strings() -> None:
    """Report numbers must serialise as JSON numbers, not quoted strings.

    A switch to string/tagged encoding must update this test, so the
    wire-format contract can't change silently.
    """
    wire = dumps({"n": Decimal("100.00")})
    assert '"n":100.00' in wire  # exact number literal, not "100.00" quoted
