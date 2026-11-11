"""Fixed rules for turning data into bytes and fingerprints.

Every computer must produce the exact same bytes for the same data,
otherwise fingerprints would not match. See SPEC.md, section "Canonical form".
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from typing import Any


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        # Same text typed on Windows and Mac must hash the same.
        text = value.replace("\r\n", "\n").replace("\r", "\n")
        return unicodedata.normalize("NFC", text)
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, float):
        raise TypeError("Floats are not allowed in signed data; use integers.")
    return value


def canonical_bytes(data: Any) -> bytes:
    """Sorted keys, no extra spaces, UTF-8, normalized text, no floats."""
    return json.dumps(
        _normalize(data), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(data: Any) -> str:
    return sha256_hex(canonical_bytes(data))


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def short(fp: str, n: int = 8) -> str:
    return fp[:n] if fp else ""
