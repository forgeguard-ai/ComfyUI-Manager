"""ForgeGuard download-hardening tests.

manager_downloader is imported directly (it needs only requests/tqdm/
huggingface_hub — no ComfyUI stack). The manager_server validation helper is
AST-extracted per the tests/test_csrf_content_type_helper.py precedent so the
PromptServer stack is never imported.
"""
import ast
import http.server
import os
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "glob"))

import manager_downloader  # noqa: E402


# ---------------------------------------------------------------- _auth_headers

def test_auth_headers_huggingface(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_secret")
    monkeypatch.delenv("CIVITAI_TOKEN", raising=False)
    headers = manager_downloader._auth_headers("https://huggingface.co/org/repo/resolve/main/a.safetensors")
    assert headers == {"Authorization": "Bearer hf_secret"}


def test_auth_headers_civitai(monkeypatch):
    monkeypatch.setenv("CIVITAI_TOKEN", "civ_secret")
    headers = manager_downloader._auth_headers("https://civitai.com/api/download/models/12345")
    assert headers == {"Authorization": "Bearer civ_secret"}


def test_auth_headers_never_leak_to_other_hosts(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_secret")
    monkeypatch.setenv("CIVITAI_TOKEN", "civ_secret")
    assert manager_downloader._auth_headers("https://github.com/x/y/raw/z.pth") == {}
    assert manager_downloader._auth_headers("https://evil.example/huggingface.co/x") == {}
    assert manager_downloader._auth_headers("https://nothuggingface.co/x") == {}


def test_auth_headers_absent_without_env(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("CIVITAI_TOKEN", raising=False)
    assert manager_downloader._auth_headers("https://huggingface.co/a/b") == {}


# ---------------------------------------------------------------- stream_download

PAYLOAD = os.urandom(300_000)


class RangeHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/missing":
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        start = 0
        status = 200
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            start = int(rng[len("bytes="):].rstrip("-"))
            status = 206
        body = PAYLOAD[start:]
        self.send_response(status)
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{len(PAYLOAD)-1}/{len(PAYLOAD)}")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture()
def http_url():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/file.bin"
    server.shutdown()


def test_stream_download_writes_atomically(tmp_path, http_url):
    dest = tmp_path / "models" / "file.bin"
    manager_downloader.stream_download(http_url, str(dest))
    assert dest.read_bytes() == PAYLOAD
    assert not dest.with_suffix(".bin.part").exists()


def test_stream_download_resumes_partial(tmp_path, http_url):
    dest = tmp_path / "file.bin"
    part = tmp_path / "file.bin.part"
    part.write_bytes(PAYLOAD[:100_000])
    manager_downloader.stream_download(http_url, str(dest))
    assert dest.read_bytes() == PAYLOAD


def test_stream_download_refuses_when_disk_full(tmp_path, http_url, monkeypatch):
    class Usage:
        free = 10  # bytes

    monkeypatch.setattr(manager_downloader.shutil, "disk_usage", lambda _: Usage)
    with pytest.raises(OSError, match="insufficient free space"):
        manager_downloader.stream_download(http_url, str(tmp_path / "file.bin"))
    assert not (tmp_path / "file.bin").exists()


def test_stream_download_http_error(tmp_path, http_url):
    with pytest.raises(Exception):
        manager_downloader.stream_download(http_url.replace("/file.bin", "/missing"), str(tmp_path / "x"))
    assert not (tmp_path / "x").exists()


# ------------------------------------------------- is_allowed_model_source (AST)

def _extract_is_allowed_model_source():
    source = (REPO_ROOT / "glob" / "manager_server.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "is_allowed_model_source":
            func_src = ast.get_source_segment(source, node)
            namespace = {
                "urlparse": urlparse,
                "core": type("Core", (), {"get_config": staticmethod(lambda: {
                    "model_download_allowed_hosts": "huggingface.co,civitai.com,github.com,raw.githubusercontent.com",
                })})(),
            }
            exec(func_src, namespace)  # noqa: S102 - controlled test extraction
            return namespace["is_allowed_model_source"]
    raise AssertionError("is_allowed_model_source not found in manager_server.py")


def test_is_allowed_model_source_matrix():
    allowed = _extract_is_allowed_model_source()
    assert allowed("https://huggingface.co/a/b/resolve/main/x.safetensors")
    assert allowed("https://cdn.civitai.com/x")          # subdomain of allowed host
    assert allowed("https://raw.githubusercontent.com/o/r/main/m.pth")
    assert not allowed("http://huggingface.co/a")        # https only
    assert not allowed("https://evil.example/x")
    assert not allowed("https://huggingface.co.evil.example/x")
    assert not allowed("")
    assert not allowed("file:///etc/passwd")
