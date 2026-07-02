"""Version resolution never raises, whatever the packaging situation.

Regression coverage for https://github.com/rustledger/rustfava/issues/191 —
packaged builds (PyInstaller sidecar, ``.deb``) ship the source without
``*.dist-info`` metadata, and the help page 500'd with
``PackageNotFoundError`` on the unguarded ``importlib.metadata.version``
call. ``rustfava._resolve_version`` falls back to the setuptools_scm-generated
``_version.py`` and finally to a sentinel.
"""

from __future__ import annotations

import importlib.metadata
import sys
import types

import pytest

import rustfava


@pytest.fixture
def no_dist_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the ``importlib.metadata`` lookup fail like a packaged build."""

    def raise_not_found(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "version", raise_not_found)


def test_installed_wheel_reports_metadata_version() -> None:
    """The normal path: dist-info metadata is present (this test env)."""
    version = rustfava._resolve_version()
    assert version
    assert version != "unknown"


@pytest.mark.usefixtures("no_dist_metadata")
def test_falls_back_to_scm_version_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No metadata, but the setuptools_scm version file is bundled."""
    fake = types.ModuleType("rustfava._version")
    fake.version = "1.2.3+packaged"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "rustfava._version", fake)
    assert rustfava._resolve_version() == "1.2.3+packaged"


@pytest.mark.usefixtures("no_dist_metadata")
def test_falls_back_to_sentinel_when_nothing_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neither metadata nor a version file: a sentinel, never an exception."""
    monkeypatch.setitem(sys.modules, "rustfava._version", None)
    assert rustfava._resolve_version() == "unknown"


def test_module_getattr_serves_version_and_rejects_others() -> None:
    assert rustfava.__version__ == rustfava._resolve_version()
    with pytest.raises(AttributeError):
        _ = rustfava.no_such_attribute
