"""Auto-update: version checks, verified downloads, swapping the program file, and what the app shows."""
import hashlib
import html
import io
import json
import sys
import tarfile
import zipfile

import pytest

from inpace import updater
from tests.test_app import client


def test_versions():
    assert updater.newer("v1.7.0", "1.6.0") and updater.newer("1.10.0", "1.9.9")
    assert not updater.newer("v1.6.0", "1.6.0") and not updater.newer("1.5.9", "1.6.0")


def fake_release(tmp_path, monkeypatch, files: dict, sums_override=None):
    """Serve a pretend GitHub release from memory."""
    sums = "".join(f"{hashlib.sha256(b).hexdigest()}  {n}\n" for n, b in files.items())
    blobs = {**{f"https://dl/{n}": b for n, b in files.items()},
             "https://dl/SHA256SUMS": (sums_override or sums).encode()}
    api = json.dumps({"tag_name": "v99.0.0", "html_url": "https://x",
                      "assets": [{"name": n, "browser_download_url": f"https://dl/{n}"} for n in [*files, "SHA256SUMS"]]})

    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(updater, "_get", lambda url, timeout=15: R(api.encode() if url == updater.API else blobs[url]))


def test_folder_update_swaps_the_program(tmp_path, monkeypatch):
    new_bin = b"#!new inpace"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo("inPace/inPace"); info.size = len(new_bin); tf.addfile(info, io.BytesIO(new_bin))
    fake_release(tmp_path, monkeypatch, {"inPace-linux.tar.gz": buf.getvalue()})
    exe = tmp_path / "app" / "inPace"; exe.parent.mkdir(); exe.write_bytes(b"#!old")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "linux")
    v, c = client(tmp_path, "Omar")
    v._set_meta("updates", "auto")
    status = updater.run(v, force=True)
    assert status["state"] == "installed" and status["version"] == "99.0.0"
    assert exe.read_bytes() == new_bin and (exe.parent / "inPace.old").read_bytes() == b"#!old"
    page = c.get("/").text
    assert "Restart now" in html.unescape(page)
    updater.clean_old_copies()
    assert not (exe.parent / "inPace.old").exists()


def test_bad_checksum_installs_nothing(tmp_path, monkeypatch):
    fake_release(tmp_path, monkeypatch, {"inPace-windows.zip": b"PK..."}, sums_override="00" * 32 + "  inPace-windows.zip\n")
    with pytest.raises(RuntimeError, match="didn't match"):
        updater.download(updater.check(), "windows", tmp_path / "dl")
    assert not (tmp_path / "dl" / "inPace-windows.zip").exists()


def test_windows_zip_swap(tmp_path, monkeypatch):
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        zf.writestr("inPace.exe", b"MZnew")
    fake_release(tmp_path, monkeypatch, {"inPace-windows.zip": zbuf.getvalue()})
    exe = tmp_path / "inPace.exe"; exe.write_bytes(b"MZold")
    monkeypatch.setattr(sys, "executable", str(exe))
    f = updater.download(updater.check(), "windows", tmp_path / "dl")
    assert updater.install("windows", f) == "installed"
    assert exe.read_bytes() == b"MZnew" and (tmp_path / "inPace.old.exe").read_bytes() == b"MZold"


def test_deb_waits_for_password(tmp_path, monkeypatch):
    fake_release(tmp_path, monkeypatch, {"inPace-linux.deb": b"!<arch>deb"})
    monkeypatch.setattr(updater, "install_kind", lambda: "deb")
    v, c = client(tmp_path, "Omar")
    v._set_meta("updates", "auto")
    assert updater.run(v, force=True)["state"] == "ready"
    assert "Install and restart" in c.get("/").text


def test_asks_once_and_source_copies_never_ask(tmp_path, monkeypatch):
    v, c = client(tmp_path, "Omar")
    assert "Keep inPace up to date" not in c.get("/").text  # running from code: git pull instead
    monkeypatch.setattr(updater, "install_kind", lambda: "windows")
    monkeypatch.setattr(updater, "run", lambda *a, **k: {"state": "current"})
    assert "Keep inPace up to date" in html.unescape(c.get("/").text)
    c.post("/updates/setting", data={"choice": "off"}, headers={"referer": "http://testserver/"})
    assert v._meta("updates") == "off" and "Keep inPace up to date" not in c.get("/").text
    assert "Turn on" in c.get("/settings").text
