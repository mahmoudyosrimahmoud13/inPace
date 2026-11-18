"""Build a double-click app for the current system.

    python packaging/build.py

Output in dist/:
  Windows  inPace-setup.exe     (a normal installer; also inPace-windows.zip for copies that update from an old version)
  macOS    inPace-mac.dmg       (drag inPace.app to Applications)
  Linux    inPace-linux.tar.gz  (run ./inPace)  and inPace-linux.deb

    python packaging/build.py --full      (Linux only: needs `pip install PySide6-Essentials PySide6-Addons`)

  Linux    inPace-linux-full.tar.gz and inPace-linux-full.deb: the same app with its own page engine
           (Qt WebEngine, based on Chromium) inside, so its window doesn't depend on the system's WebKit.
           About 150 MB more. It's a folder, not one file, so it opens fast (nothing to unpack at each start).
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


FULL = "--full" in sys.argv


def main() -> None:
    system = platform.system()
    if FULL and system != "Linux":
        sys.exit("--full is only for Linux.")
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
        # A normal program folder, not one self-unpacking .exe (that's what virus scanners distrust),
        # with the name, maker and version Windows shows in the file's properties.
        cmd += ["--windowed", "--noupx", "--icon", str(ROOT / "packaging" / "icon.ico"),
                "--version-file", str(windows_version_file())]
    elif system == "Darwin":
        cmd += ["--windowed", "--icon", str(ROOT / "packaging" / "icon.icns"),
                "--osx-bundle-identifier", "org.inpace.app"]
    elif FULL:
        # Qt WebEngine for the window (PyInstaller's hooks bring its page process and resources).
        cmd += ["--hidden-import", "PySide6.QtWebEngineWidgets", "--hidden-import", "PySide6.QtWebEngineCore",
                "--exclude-module", "PySide6.Qt3DCore", "--exclude-module", "PySide6.QtCharts",
                "--exclude-module", "PySide6.QtDataVisualization", "--exclude-module", "PySide6.QtMultimedia",
                "--exclude-module", "PySide6.QtQuick3D", "--exclude-module", "PySide6.QtSql"]
    else:
        cmd += ["--onefile"]
    cmd.append(str(ROOT / "packaging" / "launcher.py"))
    run(cmd)

    if system == "Windows":
        out = build_windows_installer()
        # Copies of inPace 1.28.5 and older update themselves from inPace-windows.zip (one inPace.exe inside).
        # Keep making it for a while, so they reach this version; from here on, updates use the installer.
        legacy = cmd[:-1] + ["--onefile", "--distpath", str(DIST / "legacy"), "--workpath", str(ROOT / "build" / "legacy"),
                             cmd[-1]]
        legacy = [x for x in legacy if x != "--noupx"] + ["--noupx"]
        run(legacy)
        with zipfile.ZipFile(DIST / "inPace-windows.zip", "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(DIST / "legacy" / "inPace.exe", "inPace.exe")
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
    elif FULL:
        folder = DIST / "inPace"
        trim_qt(folder)
        (folder / "inpace-full").write_text("This copy of inPace has its own page engine (Qt WebEngine).\n")
        shutil.copy2(ROOT / "packaging" / "icon.png", folder / "icon.png")
        out = DIST / "inPace-linux-full.tar.gz"
        with tarfile.open(out, "w:gz") as tf:
            tf.add(folder, arcname="inPace")
        if shutil.which("dpkg-deb"):
            print(f"\nBuilt {build_deb(full=True)}")
        print(f"\nBuilt {build_appimage(full=True)}")
    else:
        out = DIST / "inPace-linux.tar.gz"
        with tarfile.open(out, "w:gz") as tf:
            tf.add(DIST / "inPace", arcname="inPace/inPace")
            tf.add(ROOT / "packaging" / "icon.png", arcname="inPace/icon.png")
        if shutil.which("dpkg-deb"):
            print(f"\nBuilt {build_deb()}")
        print(f"\nBuilt {build_appimage()}")
    print(f"\nBuilt {out}")


def _version() -> str:
    import re as _re
    return _re.search(r'__version__ = "([^"]+)"', (PKG / "__init__.py").read_text(encoding="utf-8")).group(1)


def windows_version_file() -> Path:
    """The details Windows shows for inPace.exe (Properties > Details): name, maker, version."""
    v = _version()
    nums = tuple((list(int(x) for x in v.split(".")[:3]) + [0, 0, 0])[:3]) + (0,)
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Mahmoud Yosri'),
      StringStruct('FileDescription', 'inPace'),
      StringStruct('FileVersion', '{v}'),
      StringStruct('InternalName', 'inPace'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 Mahmoud Yosri. MIT license.'),
      StringStruct('OriginalFilename', 'inPace.exe'),
      StringStruct('ProductName', 'inPace'),
      StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    out = ROOT / "build" / "windows-version.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


def build_windows_installer() -> Path:
    """inPace-setup.exe from the program folder (Inno Setup 6, free)."""
    import os
    iscc = shutil.which("iscc") or shutil.which("ISCC")
    for base in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", ""),
                 os.environ.get("LOCALAPPDATA", "") + "\\Programs"):
        p = Path(base) / "Inno Setup 6" / "ISCC.exe"
        if not iscc and base and p.exists():
            iscc = str(p)
    if not iscc:
        raise SystemExit("Inno Setup 6 is needed to make the Windows installer: https://jrsoftware.org/isdl.php")
    env = dict(os.environ, INPACE_VERSION=_version())
    print("+ ISCC packaging/inpace.iss", flush=True)
    subprocess.run([iscc, "/Q", str(ROOT / "packaging" / "inpace.iss")], check=True, cwd=ROOT, env=env)
    return DIST / "inPace-setup.exe"


def trim_qt(folder: Path) -> None:
    """Leave out the parts of Qt that inPace's window never uses (about 100 MB): other languages' screens
    of Qt itself, Qt Quick controls and 3D, and the libraries nothing left needs."""
    qt = folder / "_internal" / "PySide6" / "Qt"
    if not qt.exists():
        return
    tr = qt / "translations"
    for f in tr.glob("*.qm"):
        f.unlink()  # inPace has its own English and Arabic; these are Qt's own dialogs
    for f in (tr / "qtwebengine_locales").glob("*.pak"):
        if f.stem not in ("en-US", "ar"):
            f.unlink()
    shutil.rmtree(qt / "qml", ignore_errors=True)
    # Keep every library that the engine, the window and the plugins load; remove other Qt libraries.
    import re as _re
    lib = qt / "lib"
    keep: set[str] = set()
    todo = [p for p in (list(folder.rglob("*.so*")) + [qt / "libexec" / "QtWebEngineProcess"])
            if p.is_file() and not (p.parent == lib)]
    todo += [lib / n for n in ("libQt6WebEngineCore.so.6", "libQt6WebEngineWidgets.so.6") if (lib / n).exists()]
    while todo:
        f = todo.pop()
        try:
            out = subprocess.run(["readelf", "-d", str(f)], capture_output=True, text=True).stdout
        except OSError:
            return  # no readelf: keep everything
        for name in _re.findall(r"\(NEEDED\)\s+Shared library: \[([^\]]+)\]", out):
            if name not in keep and (lib / name).exists():
                keep.add(name)
                todo.append(lib / name)
    removed = 0
    for f in lib.iterdir():
        if f.name.startswith(("libQt6", "libicu")) and f.name not in keep and f.is_file():
            removed += f.stat().st_size
            f.unlink()
    print(f"Left out {removed // (1024 * 1024)} MB of unused Qt libraries")


def _appimagetool() -> str:
    """appimagetool makes the AppImage (one file that runs on most Linux systems, no install)."""
    tool = shutil.which("appimagetool")
    if tool:
        return tool
    tool_path = ROOT / "build" / "appimagetool"
    if not tool_path.exists():
        import urllib.request
        tool_path.parent.mkdir(parents=True, exist_ok=True)
        url = "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
        print("Downloading", url, flush=True)
        urllib.request.urlretrieve(url, tool_path)
        tool_path.chmod(0o755)
    return str(tool_path)


def build_appimage(full: bool = False) -> Path:
    """inPace-linux.AppImage / inPace-linux-full.AppImage: download, allow it to run, double-click."""
    app = DIST / ("AppDir-full" if full else "AppDir")
    shutil.rmtree(app, ignore_errors=True)
    (app / "usr" / "bin").mkdir(parents=True)
    if full:
        shutil.copytree(DIST / "inPace", app / "usr" / "lib" / "inpace", symlinks=True)
        target = "usr/lib/inpace/inPace"
    else:
        shutil.copy2(DIST / "inPace", app / "usr" / "bin" / "inPace")
        target = "usr/bin/inPace"
    (app / "AppRun").write_text('#!/bin/sh\nHERE="$(dirname "$(readlink -f "$0")")"\n'
                                f'exec "$HERE/{target}" "$@"\n', encoding="utf-8")
    (app / "AppRun").chmod(0o755)
    shutil.copy2(ROOT / "packaging" / "icon.png", app / "inpace.png")
    (app / ".DirIcon").symlink_to("inpace.png")
    (app / "inpace.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=inPace\nComment=Learn at your pace. Prove you kept it.\n"
        "Exec=inPace %u\nIcon=inpace\nTerminal=false\nCategories=Education;\n"
        "MimeType=x-scheme-handler/inpace;\nStartupWMClass=inpace\n", encoding="utf-8")
    out = DIST / ("inPace-linux-full.AppImage" if full else "inPace-linux.AppImage")
    env = dict(__import__("os").environ, ARCH="x86_64", APPIMAGE_EXTRACT_AND_RUN="1")
    print("+ appimagetool", app, out, flush=True)
    subprocess.run([_appimagetool(), "--no-appstream", str(app), str(out)], check=True, cwd=ROOT, env=env)
    return out


def build_deb(full: bool = False) -> Path:
    """Ubuntu / Debian package: installs to /opt/inpace, adds a menu entry and an `inpace` command.
    Both downloads are the package "inpace", so installing one replaces the other."""
    import re as _re
    __version__ = _re.search(r'__version__ = "([^"]+)"', (PKG / "__init__.py").read_text()).group(1)

    stage = DIST / "deb"
    shutil.rmtree(stage, ignore_errors=True)
    (stage / "DEBIAN").mkdir(parents=True)
    (stage / "opt" / "inpace").mkdir(parents=True)
    (stage / "usr" / "bin").mkdir(parents=True)
    (stage / "usr" / "share" / "applications").mkdir(parents=True)
    icons = stage / "usr" / "share" / "icons" / "hicolor"
    if full:
        shutil.rmtree(stage / "opt" / "inpace")
        shutil.copytree(DIST / "inPace", stage / "opt" / "inpace", symlinks=True)
    else:
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
        + (# What the bundled Qt engine needs from the system (most desktops already have these)
           "Depends: libnss3, libxcb-cursor0, libxkbcommon-x11-0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1,"
           " libxcb-render-util0, libxcb-xinerama0, libxcb-shape0, libegl1, libgl1, libxkbfile1, libxshmfence1,"
           " libasound2t64 | libasound2\n" if full else
           "Depends: python3, python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0\n")
        # The app window plays videos through GStreamer: without these, MP4 videos (H.264) and YouTube stay black.
        + ("" if full else "Recommends: gstreamer1.0-libav, gstreamer1.0-plugins-good, gstreamer1.0-plugins-bad, gstreamer1.0-gl\n")
        + "Maintainer: Mahmoud Saad Mahmoud Yosri <noreply@github.com>\n"
        "Homepage: https://github.com/mahmoudyosrimahmoud13/inpace\n"
        "Description: Learn at your pace. Prove you kept it.\n"
        " A local, open-source learning app. Follow a course, save signed milestones,\n"
        " and let someone you trust check your progress. Everything stays on your computer.\n",
        encoding="utf-8")
    out = DIST / ("inPace-linux-full.deb" if full else "inPace-linux.deb")
    run(["dpkg-deb", "--build", "--root-owner-group", str(stage), str(out)])
    return out


if __name__ == "__main__":
    main()
