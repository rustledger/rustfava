"""The Python-plugin runner's dispatch and error-conversion branches.

Coverage burn-down phase 2 for ``rustfava.rustledger.loader`` — the plugin
runner is host-side code the differential corpus doesn't reach (its fixtures
declare no Python plugins).
"""

from __future__ import annotations

import sys
import types
from typing import Any
from typing import cast
from typing import ClassVar
from typing import TYPE_CHECKING

from rustfava.helpers import BeancountError
from rustfava.rustledger import loader as loader_mod
from rustfava.rustledger.loader import _compute_display_precision
from rustfava.rustledger.loader import _errors_from_json
from rustfava.rustledger.loader import _run_plugins

if TYPE_CHECKING:
    import pytest


def _options() -> Any:
    return cast("Any", {})


def _entries(items: list[str]) -> Any:
    """Sentinel strings standing in for directives (opaque to plugins)."""
    return cast("Any", items)


def _install(monkeypatch: pytest.MonkeyPatch, name: str, **attrs: Any) -> None:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)


def test_auto_accounts_is_skipped() -> None:
    entries, errors = _run_plugins(
        [], [{"name": "auto_accounts"}, {"name": ""}], _options()
    )
    assert list(entries) == cast("Any", [])
    assert errors == []


def test_missing_plugin_reports_import_error() -> None:
    _, errors = _run_plugins(
        [], [{"name": "no.such.plugin.module"}], _options()
    )
    assert len(errors) == 1
    assert "Failed to import plugin" in errors[0].message


def test_plugin_via_dunder_plugins(monkeypatch: pytest.MonkeyPatch) -> None:
    def stamp(
        entries: list[Any], _options: Any
    ) -> tuple[list[Any], list[Any]]:
        return [*entries, "stamped"], []

    _install(monkeypatch, "fake_plugin_a", __plugins__=["stamp"], stamp=stamp)
    entries, errors = _run_plugins(
        _entries(["seed"]), [{"name": "fake_plugin_a"}], _options()
    )
    assert list(entries) == cast("Any", ["seed", "stamped"])
    assert errors == []


def test_plugin_via_module_name_fallback_and_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No __plugins__: the module-name function runs, receiving the config."""
    seen: list[Any] = []

    def tail(entries: list[Any], config: Any) -> tuple[list[Any], list[Any]]:
        seen.append(config)
        return entries, []

    _install(monkeypatch, "tail", tail=tail)
    _run_plugins(
        _entries([]), [{"name": "tail", "config": "cfg-string"}], _options()
    )
    assert seen == ["cfg-string"]


def test_plugin_missing_function_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, "fake_plugin_b", __plugins__=["absent"])
    entries, errors = _run_plugins(
        _entries(["seed"]), [{"name": "fake_plugin_b"}], _options()
    )
    assert list(entries) == cast("Any", ["seed"])
    assert errors == []


def test_plugin_errors_are_converted(monkeypatch: pytest.MonkeyPatch) -> None:
    """BeancountError passes through; foreign error objects are adapted;
    a raising plugin becomes an error entry rather than a crash."""
    native = BeancountError(
        source={"filename": "x", "lineno": 1}, message="native", entry=None
    )

    class ForeignError:
        message = "foreign"
        entry = None

    def emits(entries: list[Any], _o: Any) -> tuple[list[Any], list[Any]]:
        return entries, [native, ForeignError()]

    def boom(_entries: list[Any], _o: Any) -> tuple[list[Any], list[Any]]:
        message = "kaboom"
        raise RuntimeError(message)

    _install(
        monkeypatch,
        "fake_plugin_c",
        __plugins__=["emits", "boom"],
        emits=emits,
        boom=boom,
    )
    entries, errors = _run_plugins(
        _entries(["seed"]), [{"name": "fake_plugin_c"}], _options()
    )
    assert list(entries) == cast("Any", ["seed"])
    messages = [e.message for e in errors]
    assert messages[0] == "native"
    assert messages[1] == "foreign"
    assert "raised: kaboom" in messages[2]


def test_plugin_module_without_matching_function(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No __plugins__ and no module-name function: nothing runs, no error."""
    _install(monkeypatch, "inert_plugin")
    entries, errors = _run_plugins(
        _entries(["seed"]), [{"name": "inert_plugin"}], _options()
    )
    assert list(entries) == cast("Any", ["seed"])
    assert errors == []


def test_display_precision_skips_malformed_amounts() -> None:
    precision = _compute_display_precision(
        [
            {
                "type": "transaction",
                "postings": [
                    {"units": {"number": "1.25", "currency": "USD"}},
                    {"units": {"number": "", "currency": "USD"}},
                    {"units": {"number": "3", "currency": ""}},
                    {"units": None},
                    {"units": {"number": "7", "currency": "JPY"}},
                ],
            }
        ]
    )
    assert precision["USD"] == 2
    assert precision["JPY"] == 0


def test_errors_from_json_source_formats() -> None:
    old_format = {
        "message": "boom",
        "source": {"filename": "inc.beancount", "lineno": 7},
    }
    new_format = {"message": "pow", "line": 3}
    suppressed = {"message": "plugin x requires the python-plugins feature"}
    errors = _errors_from_json(
        [old_format, new_format, suppressed], filename="main.beancount"
    )
    assert len(errors) == 2
    assert errors[0].source == {"filename": "inc.beancount", "lineno": 7}
    source = errors[1].source
    assert source is not None
    assert source["filename"] == "main.beancount"


def test_display_precision_currency_without_samples() -> None:
    """A currency tracked but with no countable precisions is skipped."""
    assert (
        _compute_display_precision([{"type": "transaction", "postings": []}])
        == {}
    )


def test_load_string_keeps_ffi_display_precision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the engine provides display_precision, the workaround is skipped
    (no engine currently sends it — the branch guards the planned FFI
    field)."""

    class StubEngine:
        # a plugin spec exercises load_string's plugin dispatch;
        # auto_accounts is the no-op skip
        plugins: ClassVar[list[dict[str, Any]]] = [{"name": "auto_accounts"}]

        @classmethod
        def load(cls, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {
                "entries": [],
                "errors": [],
                "options": {"display_precision": {"USD": 2}},
                "plugins": cls.plugins,
            }

    monkeypatch.setattr(loader_mod, "get_engine", lambda: StubEngine())
    entries, errors, _options = loader_mod.load_string(
        "2020-01-01 open Assets:Cash\n", "<t>"
    )
    assert entries == []
    assert errors == []

    # and the no-plugins path
    StubEngine.plugins = []
    entries, errors, _options = loader_mod.load_string("", "<t>")
    assert entries == []


def test_load_uncached_keeps_ffi_display_precision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """load_uncached has its own copy of the precision workaround; the
    FFI-provided branch is engine-version-gated like load_string's."""
    class StubEngine:
        @staticmethod
        def load_full(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {
                "entries": [],
                "errors": [],
                "options": {"display_precision": {"USD": 2}},
                "plugins": [],
            }

        load = load_full

    monkeypatch.setattr(loader_mod, "get_engine", lambda: StubEngine())
    ledger = tmp_path / "t.beancount"
    ledger.write_text("")
    entries, _errors, _options = loader_mod.load_uncached(str(ledger))
    assert entries == []
