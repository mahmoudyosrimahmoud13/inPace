"""Optional connections: AI to write courses, and Git projects as proof of work.

Both are off unless the user turns them on. Nothing else in inPace uses the network.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from .vault import Vault

PROVIDERS = {
    "": "Off: copy and paste with any AI chat (nothing leaves this computer)",
    "ollama": "Ollama on this computer (offline)",
    "anthropic": "Claude API (sends your topic to Anthropic)",
    "openai": "OpenAI-compatible API (sends your topic to that service)",
}
DEFAULT_MODELS = {"ollama": "llama3.1", "anthropic": "claude-sonnet-5-5", "openai": "gpt-4o-mini"}


def ai_settings(v: Vault) -> dict:
    return {"provider": v._meta("ai_provider", "") or "", "model": v._meta("ai_model", "") or "",
            "base_url": v._meta("ai_base_url", "") or "", "has_key": bool(v._meta("ai_key", ""))}


def save_ai_settings(v: Vault, provider: str, model: str, base_url: str, key: str | None) -> None:
    if provider not in PROVIDERS:
        provider = ""
    v._set_meta("ai_provider", provider)
    v._set_meta("ai_model", model.strip() or DEFAULT_MODELS.get(provider, ""))
    v._set_meta("ai_base_url", base_url.strip())
    if key is not None and key.strip():
        v._set_meta("ai_key", key.strip())


def _post(url: str, body: dict, headers: dict, timeout: int = 600) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"The AI service said no ({e.code}). {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Couldn't reach the AI service ({e.reason}). Is it running, and is the address right?")


def ask_ai(v: Vault, prompt: str) -> str:
    s = ai_settings(v)
    p, model = s["provider"], s["model"] or DEFAULT_MODELS.get(s["provider"], "")
    if p == "ollama":
        base = s["base_url"] or "http://127.0.0.1:11434"
        out = _post(f"{base.rstrip('/')}/api/generate", {"model": model, "prompt": prompt, "stream": False}, {})
        return out.get("response", "")
    key = v._meta("ai_key", "") or ""
    if not key:
        raise RuntimeError("Add your API key in Settings first.")
    if p == "anthropic":
        out = _post("https://api.anthropic.com/v1/messages",
                    {"model": model, "max_tokens": 16000, "messages": [{"role": "user", "content": prompt}]},
                    {"x-api-key": key, "anthropic-version": "2023-06-01"})
        return "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
    if p == "openai":
        base = s["base_url"] or "https://api.openai.com/v1"
        out = _post(f"{base.rstrip('/')}/chat/completions",
                    {"model": model, "messages": [{"role": "user", "content": prompt}]},
                    {"Authorization": f"Bearer {key}"})
        return out["choices"][0]["message"]["content"]
    raise RuntimeError("AI isn't turned on. Choose a provider in Settings.")


def git_summary(folder: str, limit: int = 30) -> tuple[str, bytes]:
    """Read a Git project's recent history and turn it into a small proof file."""
    if not shutil.which("git"):
        raise RuntimeError("Git isn't installed on this computer.")
    path = Path(folder.strip().strip('"')).expanduser()
    if not path.is_dir():
        raise RuntimeError("That folder wasn't found. Copy its full path and paste it here.")

    def git(*args: str) -> str:
        r = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise RuntimeError("That folder isn't a Git project.")
        return r.stdout.strip()

    head = git("rev-parse", "HEAD")
    log = git("log", f"-n{limit}", "--date=iso-strict", "--format=%H | %ad | %an | %s")
    remote = ""
    try:
        remote = git("remote", "get-url", "origin")
    except RuntimeError:
        pass
    name = path.name
    text = (f"Git project: {name}\nLatest commit: {head}\n" + (f"Remote: {remote}\n" if remote else "") +
            f"\nLast {limit} commits (commit | date | author | message):\n{log}\n")
    return f"git-{name}-{head[:8]}.txt", text.encode("utf-8")


def pick_folder(title: str = "Choose a folder") -> str:
    """Open this computer's own "choose folder" window and return the folder, or "" if cancelled.
    inPace runs on the same computer as the person, so the window opens right in front of them."""
    import os
    import shutil
    import subprocess
    import sys
    from .window import _clean_env
    env = _clean_env()
    try:
        if sys.platform == "win32":
            ps = ("Add-Type -AssemblyName System.Windows.Forms;"
                  "$f = New-Object System.Windows.Forms.FolderBrowserDialog;"
                  f"$f.Description = '{title.replace(chr(39), '')}';"
                  "$f.ShowNewFolderButton = $false;"
                  "$w = New-Object System.Windows.Forms.Form; $w.TopMost = $true;"
                  "if ($f.ShowDialog($w) -eq 'OK') { [Console]::OutputEncoding = [Text.Encoding]::UTF8; $f.SelectedPath }")
            r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps], capture_output=True, text=True,
                               encoding="utf-8", timeout=600, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        elif sys.platform == "darwin":
            script = f'POSIX path of (choose folder with prompt "{title.replace(chr(34), "")}")'
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=600, env=env)
        else:
            if shutil.which("zenity"):
                cmd = ["zenity", "--file-selection", "--directory", f"--title={title}"]
            elif shutil.which("kdialog"):
                cmd = ["kdialog", "--getexistingdirectory", os.path.expanduser("~"), "--title", title]
            else:
                return ""
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (r.stdout or "").strip().rstrip("/\\") if r.returncode == 0 else ""
