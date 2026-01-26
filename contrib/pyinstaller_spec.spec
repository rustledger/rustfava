# vim: set ft=python:
"""Pyinstaller spec file for building a binary from rustfava's cli.py

This spec works without pip installing rustfava - it uses the source directly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

# Get the project root (parent of contrib/)
spec_dir = Path(SPECPATH)
project_root = spec_dir.parent
src_dir = project_root / "src"
rustfava_dir = src_dir / "rustfava"

# Add src/ to path so PyInstaller can find rustfava
sys.path.insert(0, str(src_dir))

# Collect data files from source directory
datas = []

# Static files (CSS, JS, etc.)
static_dir = rustfava_dir / "static"
if static_dir.exists():
    for f in static_dir.rglob("*"):
        if f.is_file():
            rel_path = f.relative_to(rustfava_dir)
            datas.append((str(f), f"rustfava/{rel_path.parent}"))

# Templates
templates_dir = rustfava_dir / "templates"
if templates_dir.exists():
    for f in templates_dir.rglob("*"):
        if f.is_file():
            rel_path = f.relative_to(rustfava_dir)
            datas.append((str(f), f"rustfava/{rel_path.parent}"))

# Translations (.mo files)
translations_dir = rustfava_dir / "translations"
if translations_dir.exists():
    for f in translations_dir.rglob("*.mo"):
        rel_path = f.relative_to(rustfava_dir)
        datas.append((str(f), f"rustfava/{rel_path.parent}"))

# WASM file for rustledger
wasm_file = rustfava_dir / "rustledger" / "rustledger-wasi.wasm"
if wasm_file.exists():
    datas.append((str(wasm_file), "rustfava/rustledger"))

# Help files
help_dir = rustfava_dir / "help"
if help_dir.exists():
    for f in help_dir.rglob("*"):
        if f.is_file():
            rel_path = f.relative_to(rustfava_dir)
            datas.append((str(f), f"rustfava/{rel_path.parent}"))

# Hidden imports
hiddenimports = [
    "rustfava",
    "rustfava.application",
    "rustfava.cli",
    "rustfava.core",
    "rustfava.rustledger",
    "rustfava.serialisation",
]

# Optionally add beancount for legacy plugin support
try:
    hiddenimports += collect_submodules("beancount")
    datas += collect_data_files("beancount")
except Exception:
    pass

a = Analysis(
    [str(rustfava_dir / "cli.py")],
    pathex=[str(src_dir)],
    datas=datas,
    hiddenimports=hiddenimports,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="rustfava",
    upx=True,
)
