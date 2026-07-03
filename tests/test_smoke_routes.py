"""Kitchen-sink smoke: every page and data source works for every ledger.

Motivated by #190 and #191 — failures that any real user hit within minutes
(the Holdings report 500'd for every ledger with cost-dated lots; the Help
page 500'd on every packaged install) but that no test exercised. Three
layers:

1. every server-rendered route and client-report shell returns 200,
2. every no-argument JSON API endpoint returns 200,
3. every BQL query embedded in the frontend report sources is executed via
   ``/api/query`` — the queries are extracted from ``frontend/src/reports``
   at test time, so a frontend query change cannot silently drift out of
   test coverage.

All layers run against every ledger in the corpus ``app`` fixture.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from rustfava.application import CLIENT_SIDE_REPORTS
from rustfava.help import HELP_PAGES

if TYPE_CHECKING:
    from flask.testing import FlaskClient

# Ledgers from the corpus `app` fixture (see tests/conftest.py). The errors
# and invalid-unicode ledgers are included deliberately: pages must degrade,
# not crash, on ledgers with load errors.
# NB: slugs derive from each ledger's `option "title"` when set — the
# extension example titles itself "Extension Report" -> slug extension-report.
LEDGER_SLUGS = [
    "long-example",
    "edit-example",
    "example",
    "extension-report",
    "import",
    "query-example",
    "errors",
    "off-by-one",
    "invalid-unicode",
]

HOLDINGS_AGGREGATION_KEYS = ["account", "currency", "cost_currency"]

# JSON API endpoints that take no parameters (parameterized endpoints like
# context/source_slice need entry hashes and are covered elsewhere).
API_ENDPOINTS = [
    "changed",
    "commodities",
    "documents",
    "events",
    "imports",
    "journal",
    "narrations",
    "options",
    "income_statement",
    "balance_sheet",
    "trial_balance",
]

_FRONTEND_REPORTS = (
    Path(__file__).parent.parent / "frontend" / "src" / "reports"
)

# Engine shortfalls tracked upstream: abs() (and possibly other typed scalar
# functions) type-error on NULL instead of propagating it like beanquery —
# https://github.com/rustledger/rustledger/issues/1699 (only() was fixed in
# v0.20.0; abs() still errors as of v0.20.1). Matched against the error BODY
# so queries are only excused for the known gap on the ledgers that trigger
# it. Remove entries when the engine fix ships — the guard test below
# enforces removal.
KNOWN_ENGINE_GAPS = [
    "ABS expects a number",
]


def _known_engine_gap(body: str) -> bool:
    return any(marker in body for marker in KNOWN_ENGINE_GAPS)


def _frontend_queries() -> list[str]:
    """Extract every BQL query string embedded in the frontend reports.

    Matches template literals and plain string literals containing a SELECT.
    Extraction happens at test time so the tested queries are always the
    shipped ones (#190 regressed exactly here: a query the frontend ran on
    every Holdings render that nothing on the Python side ever executed).
    """
    queries: list[str] = []
    for source in sorted(_FRONTEND_REPORTS.glob("*/index.ts")):
        text = source.read_text()
        candidates = re.findall(r"`([^`]+)`", text, flags=re.DOTALL)
        candidates += re.findall(r'"((?:[^"\\]|\\.)+)"', text)
        # Only strings that ARE a query (anchored SELECT): plain substring
        # matching also catches interstitial code when a file contains an odd
        # number of backticks before the query block.
        queries += [
            c.strip() for c in candidates if c.strip().startswith("SELECT")
        ]
    return queries


def test_frontend_query_extraction_finds_the_known_queries() -> None:
    """Guard the extractor itself: the Holdings + statistics queries exist."""
    queries = _frontend_queries()
    assert len(queries) >= 5, queries
    assert any("cost_date" in q for q in queries), (
        "the Holdings acquisition-date query (#190) was not extracted"
    )


@pytest.mark.parametrize("ledger", LEDGER_SLUGS)
def test_all_pages_render(test_client: FlaskClient, ledger: str) -> None:
    """Layer 1: every page shell and server-rendered page returns 200."""
    index = test_client.get(f"/{ledger}/")
    assert index.status_code == 302, (
        f"GET /{ledger}/ -> {index.status_code} (expected redirect to the "
        "default report)"
    )
    urls = [f"/{ledger}/{report}/" for report in CLIENT_SIDE_REPORTS]
    urls += [
        f"/{ledger}/holdings/by_{key}/" for key in HOLDINGS_AGGREGATION_KEYS
    ]
    urls += [f"/{ledger}/account/Assets/"]
    urls += [f"/{ledger}/help/"]
    urls += [
        # _index's canonical URL is /help/ (covered above); a direct hit 308s
        f"/{ledger}/help/{slug}"
        for slug in HELP_PAGES
        if slug != "_index"
    ]
    for url in urls:
        response = test_client.get(url)
        assert response.status_code == 200, (
            f"GET {url} -> {response.status_code}"
        )


@pytest.mark.parametrize("ledger", LEDGER_SLUGS)
def test_all_api_endpoints_respond(
    test_client: FlaskClient, ledger: str
) -> None:
    """Layer 2: every no-argument API endpoint returns 200."""
    for endpoint in API_ENDPOINTS:
        url = f"/{ledger}/api/{endpoint}"
        if endpoint == "journal":
            url = f"/{ledger}/api/journal_page?page=1&order=desc"
        response = test_client.get(url)
        assert response.status_code == 200, (
            f"GET {url} -> {response.status_code}"
        )


@pytest.mark.parametrize("ledger", LEDGER_SLUGS)
def test_all_frontend_queries_execute(
    test_client: FlaskClient, ledger: str
) -> None:
    """Layer 3: every query the frontend ships executes on every ledger.

    This is the regression class of #190: the Holdings page ran a query via
    ``/api/query`` that failed compilation on any ledger with cost-dated
    lots, and nothing server-side ever executed it.
    """
    for query in _frontend_queries():
        response = test_client.get(
            f"/{ledger}/api/query", query_string={"query_string": query}
        )
        if response.status_code != 200:
            body = response.get_data(as_text=True)
            assert _known_engine_gap(body), (
                f"query failed on {ledger} ({response.status_code}): "
                f"{query[:80]}\nbody: {body[:200]}"
            )


def test_known_engine_gaps_are_still_present(test_client: FlaskClient) -> None:
    """The gap list must shrink, not rot: when the engine fix ships, the
    fixed marker must be removed so the affected queries are asserted again.
    The errors-corpus ledger is the trigger for the abs()-on-NULL gap."""
    assert KNOWN_ENGINE_GAPS, "gap list is empty - delete this test too"
    hit: set[str] = set()
    for query in _frontend_queries():
        response = test_client.get(
            "/errors/api/query", query_string={"query_string": query}
        )
        if response.status_code != 200:
            body = response.get_data(as_text=True)
            hit.update(m for m in KNOWN_ENGINE_GAPS if m in body)
    for marker in KNOWN_ENGINE_GAPS:
        assert marker in hit, (
            f"engine gap {marker!r} appears FIXED - remove it from "
            "KNOWN_ENGINE_GAPS so the affected queries are asserted again"
        )
