"""Opening web addresses safely on every system, including phones.

Python checks a website's certificate against a list of trusted authorities that normally comes from the system.
Python inside the Android app has no such list, so every secure download (the course library, updates, video titles)
failed with a certificate error and looked like "no internet". We ship the standard list (certifi) and use it when the
system has none, or when the system's own check fails.
"""
from __future__ import annotations

import os
import ssl
import sys
import urllib.error
import urllib.request

_CONTEXTS: dict[str, ssl.SSLContext] = {}


def _certifi_file() -> str | None:
    try:
        import certifi
        path = certifi.where()
        return path if os.path.exists(path) else None
    except Exception:
        return None


def _on_phone() -> bool:
    return bool(os.environ.get("INPACE_MOBILE")) or hasattr(sys, "getandroidapilevel") or sys.platform in ("android", "ios")


def _system_has_certs() -> bool:
    paths = ssl.get_default_verify_paths()
    return any(p and os.path.exists(p) for p in (paths.cafile, paths.capath))


def context(bundled: bool = False) -> ssl.SSLContext:
    """The SSL settings to use. bundled=True always uses the shipped list."""
    use_bundle = bundled or _on_phone() or not _system_has_certs()
    key = "bundle" if use_bundle else "system"
    if key not in _CONTEXTS:
        cafile = _certifi_file() if use_bundle else None
        _CONTEXTS[key] = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
    return _CONTEXTS[key]


def _cert_problem(err: Exception) -> bool:
    reason = getattr(err, "reason", err)
    return isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(reason)


def urlopen(req, timeout: float = 15):
    """urllib.request.urlopen with certificates that work everywhere. Plain http (127.0.0.1) is passed through."""
    url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
    if not url.lower().startswith("https://"):
        return urllib.request.urlopen(req, timeout=timeout)
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=context())
    except urllib.error.URLError as e:
        if _cert_problem(e) and _certifi_file():
            return urllib.request.urlopen(req, timeout=timeout, context=context(bundled=True))
        raise
