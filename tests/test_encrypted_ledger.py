"""GPG-encrypted ledger handling.

Since rustledger v0.19.0 (WIT 3.2.0) the WASI component delegates decryption to
the host: rustfava provides a ``decrypt`` capability that runs the system
``gpg --batch --decrypt`` (keyring + gpg-agent). Encrypted ledgers therefore
load end-to-end when the keyring can decrypt them; when it cannot, loading must
fail **cleanly** (an error in the result, never a crash or silently-empty
success), and detection (``is-encrypted``) must work regardless.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from rustfava.rustledger import is_encrypted_file
from rustfava.rustledger import loader
from rustfava.rustledger.component_engine import _host_decrypt

_ENCRYPTED = Path(__file__).parent / "ledgers" / "encrypted.beancount.gpg"


def test_encrypted_file_is_detected() -> None:
    assert is_encrypted_file(str(_ENCRYPTED)) is True
    assert is_encrypted_file(__file__) is False


def test_undecryptable_ledger_fails_cleanly() -> None:
    """A ledger the keyring cannot decrypt yields an error, not a crash."""
    entries, errors, _ = loader.load_uncached(str(_ENCRYPTED))
    assert not entries
    assert errors
    assert any(
        "decrypt" in str(getattr(e, "message", e)).lower() for e in errors
    )


def test_encrypted_ledger_roundtrip(tmp_path: Path) -> None:
    """An encrypted ledger the keyring CAN decrypt loads end-to-end."""
    if shutil.which("gpg") is None:
        pytest.skip("gpg not installed")
    gnupg = tmp_path / "gnupg"
    gnupg.mkdir(mode=0o700)
    env = {"GNUPGHOME": str(gnupg), "PATH": "/usr/bin:/bin"}
    gen = subprocess.run(
        [  # noqa: S607
            "gpg",
            "--batch",
            "--pinentry-mode",
            "loopback",
            "--passphrase",
            "",
            "--quick-gen-key",
            "rustfava-test@example.invalid",
            "default",
            "default",
        ],
        env=env,
        capture_output=True,
        check=False,
    )
    if gen.returncode != 0:
        pytest.skip(
            f"cannot create test key: {gen.stderr.decode(errors='replace')}"
        )

    source = (
        "2026-01-01 open Assets:Cash\n"
        "2026-01-01 open Equity:Open\n"
        '2026-01-02 * "encrypted entry"\n'
        "  Assets:Cash  1.00 USD\n"
        "  Equity:Open  -1.00 USD\n"
    )
    ledger = tmp_path / "ledger.beancount.gpg"
    enc = subprocess.run(
        [  # noqa: S607
            "gpg",
            "--batch",
            "--encrypt",
            "--recipient",
            "rustfava-test@example.invalid",
            "--trust-model",
            "always",
            "--output",
            str(ledger),
        ],
        input=source.encode(),
        env=env,
        capture_output=True,
        check=False,
    )
    assert enc.returncode == 0, enc.stderr.decode(errors="replace")

    old = os.environ.get("GNUPGHOME")
    os.environ["GNUPGHOME"] = str(gnupg)
    try:
        entries, errors, _ = loader.load_uncached(str(ledger))
    finally:
        if old is None:
            os.environ.pop("GNUPGHOME", None)
        else:
            os.environ["GNUPGHOME"] = old
    assert not errors, [str(e) for e in errors]
    assert entries, "encrypted ledger produced no entries"


def test_host_decrypt_gpg_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """gpg not being runnable surfaces as an err result, not an exception."""

    def boom(*_args: object, **_kwargs: object) -> object:
        message = "gpg not found"
        raise OSError(message)

    monkeypatch.setattr(subprocess, "run", boom)
    result = _host_decrypt(None, b"data")
    assert result.tag == "err"
    assert "failed to run gpg" in str(result.payload)


def test_host_decrypt_non_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    """Decrypted bytes that are not UTF-8 surface as an err result."""

    class FakeProc:
        returncode = 0
        stdout = b"\xff\xfe\x00binary"
        stderr = b""

    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: FakeProc())
    result = _host_decrypt(None, b"data")
    assert result.tag == "err"
    assert "not valid UTF-8" in str(result.payload)


def test_host_decrypt_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful gpg output surfaces as an ok result with the plaintext."""

    class FakeProc:
        returncode = 0
        stdout = b"2026-01-01 open Assets:Cash\n"
        stderr = b""

    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: FakeProc())
    result = _host_decrypt(None, b"ciphertext")
    assert result.tag == "ok"
    assert "Assets:Cash" in str(result.payload)


def test_host_decrypt_gpg_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A gpg failure surfaces its stderr as the err payload."""

    class FakeProc:
        returncode = 2
        stdout = b""
        stderr = b"gpg: decryption failed: No secret key\n"

    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: FakeProc())
    result = _host_decrypt(None, b"ciphertext")
    assert result.tag == "err"
    assert "No secret key" in str(result.payload)
