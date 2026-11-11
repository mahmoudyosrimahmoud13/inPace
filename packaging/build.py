"""Build a double-click app for the current system.

    python packaging/build.py

Output in dist/:
  Windows  inPace-windows.zip   (inPace.exe inside)
  macOS    inPace-mac.dmg       (drag inPace.app to Applications)
  Linux    inPace-linux.tar.gz  (run ./inPace)
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "inpace"
DIST = ROOT / "dist"
SEP = ";" if sys.platform == "win32" else ":"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def main() -> None:
    system = platform.system()
    data = [f"{PKG / d}{SEP}inpace/{d}" for d in ("templates", "static", "sample_courses", "locales")]
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--name", "inPace",
           "--paths", str(ROOT), "--collect-submodules", "inpace", "--collect-submodules", "uvicorn",
           "--hidden-import", "_cffi_backend", "--collect-all", "nacl",
           "--collect-submodules", "pygments"]
    for d in data:
        cmd += ["--add-data", d]
    try:  # the app window library, when installed (Windows and Mac builds)
        import webview  # noqa: F401
        cmd += ["--collect-all", "webview"]
    except Exception:
        pass
    if system == "Windows":
        cmd += ["--onefile", "--windowed", "--icon", str(ROOT / "packaging" / "icon.ico")]
    elif system == "Darwin":
        cmd += ["--windowed", "--icon", str(ROOT / "packaging" / "icon.icns"),
                "--osx-bundle-identifier", "org.inpace.app"]
    else:
        cmd += ["--onefile"]
    cmd.append(str(ROOT / "packaging" / "launcher.py"))
    run(cmd)

    if system == "Windows":
        out = DIST / "inPace-windows.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(DIST / "inPace.exe", "inPace.exe")
    elif system == "Darwin":
        out = DIST / "inPace-mac.dmg"
        stage = DIST / "dmg"
        shutil.rmtree(stage, ignore_errors=True)
        stage.mkdir()
        shutil.copytree(DIST / "inPace.app", stage / "inPace.app", symlinks=True)
        (stage / "Applications").symlink_to("/Applications")
        run(["hdiutil", "create", "-volname", "inPace", "-srcfolder", str(stage), "-ov", "-format", "UDZO", str(out)])
    else:
        out = DIST / "inPace-linux.tar.gz"
        with tarfile.open(out, "w:gz") as tf:
            tf.add(DIST / "inPace", arcname="inPace/inPace")
            tf.add(ROOT / "packaging" / "icon.png", arcname="inPace/icon.png")
    print(f"\nBuilt {out}")


if __name__ == "__main__":
    main()
