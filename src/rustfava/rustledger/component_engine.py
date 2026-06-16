"""Rustledger engine backed by the WASI Preview 2 / Component-Model component.

The successor to :class:`rustfava.rustledger.engine.RustledgerEngine` (which
spawns the ``wasmtime`` CLI with JSON-RPC over stdin/stdout). This driver loads
``rustledger-ffi-component`` (rustledger #1384) once, in-process, via
``wasmtime-py``'s component API and calls its **typed** exports directly — no
subprocess per call, no hand-mirrored JSON DTOs.

It is wired in behind a flag (see ``rustfava.rustledger.get_engine``); the
JSON-RPC engine stays the default until the component ships as a release
artifact (``publish = false`` upstream — rustledger ADR-0006 Phase 3).

Results are marshalled from the component's typed `Record`/`Variant`/`list`
values into plain Python by a generic, *type-driven* converter
(:func:`_marshal`) that walks the component's own type metadata
(`RecordType.fields`, `VariantType.cases`), so no per-type field lists are
hand-maintained. Variants render as ``{"type": <case>, ...}`` (discriminated),
mirroring the JSON-RPC surface's tagged unions.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from wasmtime import DirPerms
from wasmtime import Engine
from wasmtime import FilePerms
from wasmtime import Store
from wasmtime import WasiConfig
from wasmtime.component import Component
from wasmtime.component import Linker
from wasmtime.component import ListType
from wasmtime.component import OptionType
from wasmtime.component import Record
from wasmtime.component import RecordType
from wasmtime.component import ResultType
from wasmtime.component import TupleType
from wasmtime.component import Variant
from wasmtime.component import VariantType

from rustfava.rustledger.engine import _check_api_version
from rustfava.rustledger.engine import RustledgerError

# The four exported WIT interfaces (package ``rustledger:ledger@2.1.0``).
_LEDGER = "rustledger:ledger/ledger@2.1.0"
_BUILDER = "rustledger:ledger/builder@2.1.0"
_UTIL = "rustledger:ledger/util@2.1.0"
_FORMAT = "rustledger:ledger/format@2.1.0"


def _default_wasm_path() -> Path:
    """Locate the bundled component wasm (overridable for local builds)."""
    override = os.environ.get("RUSTLEDGER_COMPONENT_WASM")
    if override:
        return Path(override)
    return Path(__file__).parent / "rustledger_ffi_component.wasm"


def _snake(name: str) -> str:
    """WIT identifiers are kebab-case; the JSON-RPC surface is snake_case."""
    return name.replace("-", "_")


def _is_pair_list(vtype: Any) -> bool:
    """Whether ``vtype`` is ``list<tuple<_, _>>`` (WIT's string-keyed map)."""
    return (
        isinstance(vtype, ListType)
        and isinstance(vtype.element, TupleType)
        and len(vtype.element.elements) == 2
    )


def _unwrap_meta_value(value: Any) -> Any:
    """Flatten a marshalled ``meta-value`` variant to its scalar/plain form.

    User metadata values are a ``meta-value`` variant (text/number/boolean/
    amount/...). The JSON-RPC surface emitted them as plain scalars (or, for
    amounts, a bare ``{number, currency}`` object), not discriminated unions —
    so unwrap to match. (Directive and query-cell variants stay tagged.)
    """
    if isinstance(value, dict) and "type" in value:
        if set(value) == {"type", "value"}:
            return value["value"]
        return {k: v for k, v in value.items() if k != "type"}
    return value


def _marshal(value: Any, vtype: Any) -> Any:  # noqa: PLR0911, PLR0912
    """Convert a component value into plain Python, driven by its WIT type.

    Output matches the JSON-RPC engine's shapes so the same downstream
    (``loader``/``types``/``options``) parses both backends identically:

    - `Record` -> ``dict`` with **snake_case** keys (WIT names are kebab-case).
      A ``user`` field (``meta``'s user-metadata map) is **flattened** into the
      parent, mirroring the JSON-RPC ``Meta``'s ``#[serde(flatten)]``.
    - `Variant` -> ``{"type": <snake case>, ...}`` (discriminated; record
      payloads spread, other payloads under ``"value"``, unit cases bare).
    - `list<tuple<string, V>>` -> ``dict`` (WIT has no map type; the JSON-RPC
      surface emitted these — ``display-precision``, ``meta.user``, … — as
      objects). Other lists -> ``list``.
    - `option`/`result`/`tuple` unwrap; `enum`/primitives pass through.
    """
    if isinstance(vtype, RecordType):
        out: dict[str, Any] = {}
        for name, ftype in vtype.fields:
            marshalled = _marshal(getattr(value, name), ftype)
            if name == "user" and isinstance(marshalled, dict):
                # `meta.user` carries arbitrary user metadata; the JSON-RPC
                # `Meta` flattened it into the meta object (scalar values), so
                # do the same.
                out.update(
                    {k: _unwrap_meta_value(v) for k, v in marshalled.items()}
                )
            else:
                out[_snake(name)] = marshalled
        return out
    if isinstance(vtype, VariantType):
        cases = dict(vtype.cases)
        tag = value.tag
        payload_type = cases.get(tag)
        out_tag = _snake(tag)
        if payload_type is None or value.payload is None:
            return {"type": out_tag}
        payload = _marshal(value.payload, payload_type)
        if isinstance(payload, dict):
            return {"type": out_tag, **payload}
        return {"type": out_tag, "value": payload}
    if isinstance(vtype, ListType):
        items = [_marshal(item, vtype.element) for item in value]
        if _is_pair_list(vtype) and all(
            isinstance(p, list) and len(p) == 2 and isinstance(p[0], str)
            for p in items
        ):
            return {p[0]: p[1] for p in items}
        return items
    if isinstance(vtype, OptionType):
        return None if value is None else _marshal(value, vtype.payload)
    if isinstance(vtype, TupleType):
        return [
            _marshal(v, t) for v, t in zip(value, vtype.elements, strict=False)
        ]
    if isinstance(vtype, ResultType):
        # `result<ok, err>` lifts to a Variant(tag="ok"|"err"); wasmtime-py
        # does NOT raise. Surface `err` as an exception, unwrap `ok`.
        if value.tag == "err":
            err = _marshal(value.payload, vtype.err) if vtype.err else None
            msg = str(err) if err is not None else "component error"
            raise RustledgerError(msg)
        return _marshal(value.payload, vtype.ok) if vtype.ok else None
    # Fallback: an un-typed Record/Variant, an enum (lifts to str), or a
    # primitive.
    if isinstance(value, Record):
        return {
            _snake(k): getattr(value, k)
            for k in dir(value)
            if not k.startswith("_")
        }
    if isinstance(value, Variant):
        return {"type": _snake(value.tag), "value": value.payload}
    return value


class RustledgerComponentEngine:
    """In-process driver for the typed rustledger wasip2 component."""

    def __init__(self, wasm_path: Path | None = None) -> None:
        self._wasm_path = wasm_path or _default_wasm_path()
        if not self._wasm_path.exists():
            msg = (
                f"rustledger component not found at {self._wasm_path}. Build "
                "it with: cargo build -p rustledger-ffi-component "
                "--target wasm32-wasip2 --release"
            )
            raise RustledgerError(msg)
        self._engine = Engine()
        self._component = Component.from_file(
            self._engine,
            str(self._wasm_path),
        )
        # Shared instance for source-based calls (load/query/validate/...);
        # the component holds no cross-call state for these. ``load_full``
        # builds a fresh instance with a pre-opened dir.
        self._store, self._inst = self._instantiate()
        self._iface_cache: dict[str, Any] = {}
        self._version_checked = False
        # The shared store/instance is reused across source-based calls and
        # wasmtime's `Store` is not concurrency-safe; serialize access since
        # Fava serves requests on multiple threads. (`load_full` uses a fresh
        # per-call instance and needs no lock.)
        self._lock = threading.Lock()

    # -- instantiation -----------------------------------------------------

    def _instantiate(
        self,
        preopen: tuple[str, str] | None = None,
    ) -> tuple[Store, Any]:
        store = Store(self._engine)
        wasi = WasiConfig()
        wasi.inherit_stdout()
        wasi.inherit_stderr()
        if preopen is not None:
            host, guest = preopen
            wasi.preopen_dir(
                host,
                guest,
                DirPerms.READ_ONLY,
                FilePerms.READ_ONLY,
            )
        store.set_wasi(wasi)
        linker = Linker(self._engine)
        linker.add_wasip2()
        inst = linker.instantiate(store, self._component)
        return store, inst

    def _iface(self, name: str) -> Any:
        idx = self._iface_cache.get(name)
        if idx is None:
            idx = self._component.get_export_index(name)
            self._iface_cache[name] = idx
        return idx

    # -- typed calls -------------------------------------------------------

    def _call(self, iface: str, func_name: str, args: list[Any]) -> Any:
        """Call ``iface.func_name(*args)`` on the shared instance (locked)."""
        with self._lock:
            return self._call_on(
                self._store, self._inst, iface, func_name, args
            )

    def _call_on(
        self,
        store: Store,
        inst: Any,
        iface: str,
        func_name: str,
        args: list[Any],
    ) -> Any:
        """Call a func on a specific store/instance, marshalling the result."""
        fidx = self._component.get_export_index(func_name, self._iface(iface))
        func = inst.get_func(store, fidx)
        raw = func(store, *args)
        return _marshal(raw, func.type(store).result)

    def _ensure_version(self) -> None:
        if self._version_checked:
            return
        _check_api_version(self._call(_LEDGER, "version", []))
        self._version_checked = True

    # -- public API (mirrors RustledgerEngine) -----------------------------

    def version(self) -> str:
        """Return the component's ``api_version`` string (e.g. ``"2.1"``)."""
        return self._call(_LEDGER, "version", [])

    def load(self, source: str, filename: str = "<stdin>") -> dict[str, Any]:  # noqa: ARG002
        """Parse + book ``source``; returns entries/errors/options/....

        ``filename`` is accepted for API parity with the JSON-RPC engine; the
        WIT ``load(source)`` has no filename param, so it is unused here.
        """
        self._ensure_version()
        return self._call(_LEDGER, "load", [source])

    def query(self, source: str, query_string: str) -> dict[str, Any]:
        """Run a BQL query over ``source``; returns columns/rows/errors."""
        self._ensure_version()
        return self._call(_LEDGER, "query", [source, query_string])

    def validate(self, source: str) -> dict[str, Any]:
        """Validate ``source``; returns ``valid`` + ``errors``."""
        self._ensure_version()
        return self._call(_LEDGER, "validate", [source])

    def format_entries(self, source: str) -> str:
        """Canonically reformat beancount ``source``."""
        self._ensure_version()
        return self._call(_FORMAT, "format-source", [source])

    def get_account_type(self, account: str) -> str:
        """Return the lowercased root type of ``account`` (or ``unknown``)."""
        return self._call(_UTIL, "get-account-type", [account])

    def is_encrypted(self, filepath: str) -> bool:
        """Return whether ``filepath`` looks like a ``.gpg``/``.asc`` file."""
        return self._call(_UTIL, "is-encrypted", [filepath])

    def load_full(
        self,
        path: str,
        *,
        allow_unrestricted_includes: bool = False,
        plugins: list[str] | None = None,
    ) -> dict[str, Any]:
        """Load a file (resolving includes/plugins) via the component.

        Unlike the source-based calls this needs filesystem access, so it runs
        on a fresh instance with the file's directory pre-opened into the WASI
        sandbox at ``/work`` and the path rewritten accordingly.

        Note: only the entry file's own directory tree is granted to the WASI
        sandbox, so ``include`` targets must live at or below it — cross-tree
        (``../``) includes are unreachable here regardless of
        ``allow_unrestricted_includes`` (WASI denies the access before the
        loader's path-security check applies). A wider pre-open root would be
        needed to support them.
        """
        self._ensure_version()
        host_path = Path(path).resolve()
        guest_path = f"/work/{host_path.name}"
        store, inst = self._instantiate(
            preopen=(str(host_path.parent), "/work"),
        )
        return self._call_on(
            store,
            inst,
            _LEDGER,
            "load-file",
            [guest_path, allow_unrestricted_includes, plugins or []],
        )


_INSTANCE: RustledgerComponentEngine | None = None


def get_component_engine(
    wasm_path: Path | None = None,
) -> RustledgerComponentEngine:
    """Return the process-wide singleton component engine."""
    global _INSTANCE  # noqa: PLW0603
    if _INSTANCE is None:
        _INSTANCE = RustledgerComponentEngine(wasm_path)
    return _INSTANCE
