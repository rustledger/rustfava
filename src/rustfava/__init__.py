"""Rustfava - A web interface for rustledger."""

from __future__ import annotations

LOCALES = [
    "bg",
    "ca",
    "de",
    "es",
    "fa",
    "fr",
    "ja",
    "nl",
    "pt",
    "pt_BR",
    "ru",
    "sk",
    "sv",
    "uk",
    "zh",
    "zh_Hant_TW",
]


def _resolve_version() -> str:
    """Resolve the rustfava version without raising.

    Installed wheels expose the version via ``importlib.metadata``. Packaged
    builds (PyInstaller sidecar, ``.deb``) ship the source without dist-info
    metadata, so fall back to the setuptools_scm-generated ``_version.py`` and
    finally to a sentinel rather than raising ``PackageNotFoundError`` (which
    previously 500'd the help page, see issue #191).
    """
    try:
        from importlib.metadata import version as metadata_version

        return metadata_version("rustfava")
    except Exception:  # noqa: BLE001, S110 - any metadata failure falls through
        pass
    try:
        from ._version import version as scm_version

        return str(scm_version)
    except Exception:  # noqa: BLE001
        return "unknown"


def __getattr__(name: str) -> str:
    if name == "__version__":
        return _resolve_version()
    raise AttributeError(name)
