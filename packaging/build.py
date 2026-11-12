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
           "--collect-submodules", "pygments",
           "--exclude-module", "PIL", "--exclude-module", "tkinter", "--exclude-module", "numpy"]
    for d in data:
        cmd += ["--add-data", d]
    if system != "Linux":  # the app window library (Linux uses the system's GTK window instead)
        try:
            import webview  # noqa: F401
            cmd += ["--collect-all", "webview"]
        except Exception:
            pass
    if system == "Windows":  # pywebview's Edge window talks to Windows through pythonnet
        for mod in ("clr_loader", "pythonnet"):
            try:
                __import__(mod)
                cmd += ["--collect-all", mod]
            except Exception:
                pass
        cmd += ["--hidden-import", "clr"]
    if system == "Darwin":
        cmd += ["--hidden-import", "WebKit", "--hidden-import", "AppKit", "--hidden-import", "Foundation"]
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
        import plistlib
        plist_path = DIST / "inPace.app" / "Contents" / "Info.plist"
        with open(plist_path, "rb") as f:
            info = plistlib.load(f)
        info["NSMicrophoneUsageDescription"] = "inPace uses the microphone only when you record a voice note for a task."
        # Tapping an inpace:// link in a chat, an email or the inPace website opens the app.
        info["CFBundleURLTypes"] = [{"CFBundleURLName": "org.inpace.link", "CFBundleURLSchemes": ["inpace"]}]
        with open(plist_path, "wb") as f:
            plistlib.dump(info, f)
        # Changing Info.plist breaks the app's built-in signature; sign it again (ad hoc) so it still opens.
        run(["codesign", "--force", "--deep", "--sign", "-", str(DIST / "inPace.app")])
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
        if shutil.which("dpkg-deb"):
            print(f"\nBuilt {build_deb()}")
    print(f"\nBuilt {out}")


def build_deb() -> Path:
    """Ubuntu / Debian package: installs to /opt/inpace, adds a menu entry and an `inpace` command."""
    import re as _re
    __version__ = _re.search(r'__version__ = "([^"]+)"', (PKG / "__init__.py").read_text()).group(1)

    stage = DIST / "deb"
    shutil.rmtree(stage, ignore_errors=True)
    (stage / "DEBIAN").mkdir(parents=True)
    (stage / "opt" / "inpace").mkdir(parents=True)
    (stage / "usr" / "bin").mkdir(parents=True)
    (stage / "usr" / "share" / "applications").mkdir(parents=True)
    icons = stage / "usr" / "share" / "icons" / "hicolor"
    shutil.copy2(DIST / "inPace", stage / "opt" / "inpace" / "inPace")
    (stage / "opt" / "inpace" / "inPace").chmod(0o755)
    (stage / "usr" / "bin" / "inpace").symlink_to("/opt/inpace/inPace")
    from PIL import Image
    src = Image.open(ROOT / "packaging" / "icon.png")
    for px in (48, 128, 256, 512):
        d = icons / f"{px}x{px}" / "apps"
        d.mkdir(parents=True)
        src.resize((px, px)).save(d / "inpace.png")
    (stage / "usr" / "share" / "applications" / "inpace.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=inPace\n"
        "Comment=Learn at your pace. Prove you kept it.\n"
        "Exec=/opt/inpace/inPace %u\nIcon=inpace\nTerminal=false\nCategories=Education;\n"
        "MimeType=x-scheme-handler/inpace;\n"
        "StartupWMClass=inpace\n"
        "Keywords=learning;study;course;accountability;\n", encoding="utf-8")
    size_kb = sum(p.stat().st_size for p in stage.rglob("*") if p.is_file() and not p.is_symlink()) // 1024
    (stage / "DEBIAN" / "control").write_text(
        f"Package: inpace\nVersion: {__version__}\nSection: education\nPriority: optional\n"
        f"Architecture: amd64\nInstalled-Size: {size_kb}\n"
        "Depends: python3, python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0\n"
        "Maintainer: Mahmoud Saad <noreply@github.com>\n"
        "Homepage: https://github.com/mahmoudyosrimahmoud13/inpace\n"
        "Description: Learn at your pace. Prove you kept it.\n"
        " A local, open-source learning app. Follow a course, save signed milestones,\n"
        " and let someone you trust check your progress. Everything stays on your computer.\n",
        encoding="utf-8")
    out = DIST / "inPace-linux.deb"
    run(["dpkg-deb", "--build", "--root-owner-group", str(stage), str(out)])
    return out


if __name__ == "__main__":
    main()
