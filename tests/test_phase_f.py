import html
import json
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from inpace import integrations
from inpace.vault import Vault


@pytest.mark.skipif(not shutil.which("git"), reason="git not installed")
def test_git_project_as_proof(tmp_path):
    repo = tmp_path / "proj"
    repo.mkdir()
    run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
    run("init", "-q")
    run("-c", "user.name=Omar", "-c", "user.email=o@x", "commit", "-q", "--allow-empty", "-m", "First step")
    name, data = integrations.git_summary(str(repo))
    assert name.startswith("git-proj-") and b"First step" in data and b"Omar" in data
    with pytest.raises(RuntimeError):
        integrations.git_summary(str(tmp_path))  # not a git project


def test_ai_through_a_local_ollama(tmp_path):
    class Fake(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = json.dumps({"response": f"echo:{body['model']}:{body['prompt'][:5]}"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    v = Vault(tmp_path / "v")
    v.setup("A")
    with pytest.raises(RuntimeError):
        integrations.ask_ai(v, "hi")  # off by default
    integrations.save_ai_settings(v, "ollama", "", f"http://127.0.0.1:{srv.server_port}", None)
    assert integrations.ask_ai(v, "Hello world") == "echo:llama3.1:Hello"
    srv.shutdown()
