"""GPG-encrypted ledger handling.

The engine detects encrypted files (``is-encrypted``) but currently cannot
*decrypt* them: the WASI component only pre-opens the ledger's own
directory, so it cannot reach the GPG keyring, and load fails with a clear error
(rustledger upstream). This guards two things that must hold regardless:
detection works, and an undecryptable ledger fails **cleanly** (an error in the
result, never a crash or silently-empty success).
"""

from __future__ import annotations

from pathlib import Path

from rustfava.rustledger import is_encrypted_file
from rustfava.rustledger import loader

_ENCRYPTED = Path(__file__).parent / "ledgers" / "encrypted.beancount.gpg"


def test_encrypted_file_is_detected() -> None:
    assert is_encrypted_file(str(_ENCRYPTED)) is True
    assert is_encrypted_file(__file__) is False


def test_undecryptable_ledger_fails_cleanly() -> None:
    """Loading an undecryptable ledger yields an error, not a crash."""
    entries, errors, _ = loader.load_uncached(str(_ENCRYPTED))
    assert not entries
    assert errors
    assert any(
        "decrypt" in str(getattr(e, "message", e)).lower() for e in errors
    )
