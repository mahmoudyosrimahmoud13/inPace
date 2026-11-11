"""A person's signing key. The private part never leaves their computer."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from .canon import canonical_bytes


class Identity:
    def __init__(self, signing_key: SigningKey):
        self._sk = signing_key

    @property
    def id(self) -> str:
        return self._sk.verify_key.encode().hex()

    def sign(self, data: Any) -> str:
        return self._sk.sign(canonical_bytes(data)).signature.hex()

    @classmethod
    def create(cls) -> "Identity":
        return cls(SigningKey.generate())

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._sk.encode().hex(), encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:  # Windows ignores this; fine.
            pass

    @classmethod
    def load(cls, path: Path) -> "Identity":
        return cls(SigningKey(bytes.fromhex(path.read_text(encoding="utf-8").strip())))


def verify(person_id: str, data: Any, signature_hex: str) -> bool:
    try:
        VerifyKey(bytes.fromhex(person_id)).verify(canonical_bytes(data), bytes.fromhex(signature_hex))
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False
