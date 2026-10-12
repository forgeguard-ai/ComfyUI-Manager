"""Egress canary: fails if removed cloud surfaces reappear in Manager code.

Scans runtime code (glob/*.py, js/*.js, the entrypoints) — not the catalog
JSONs, whose data legitimately mentions third-party node names.
"""
import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

BANNED = (
    "comfyworkflows.com",
    "openart.ai",
    "youml.com",
    "copus.io",
    "esheep.com",
    "matrix.org",  # upstream share/support endpoints
    "ltdrdata.github.io/wiki",  # the notice-board fetch; bare domain links are fine
    "raw.githubusercontent.com/ltdrdata",
)

CODE_FILES = (
    list((REPO_ROOT / "glob").glob("*.py"))
    + list((REPO_ROOT / "js").glob("*.js"))
    + [REPO_ROOT / "__init__.py", REPO_ROOT / "prestartup_script.py", REPO_ROOT / "cm-cli.py"]
)


def test_share_modules_stay_removed():
    assert not (REPO_ROOT / "glob" / "share_3rdparty.py").exists()
    assert not list((REPO_ROOT / "js").glob("comfyui-share-*.js"))


def test_no_banned_hosts_in_runtime_code():
    offenders = []
    for path in CODE_FILES:
        content = path.read_text(encoding="utf-8", errors="ignore").lower()
        for fragment in BANNED:
            if fragment in content:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {fragment}")
    assert not offenders, "banned cloud references found:\n" + "\n".join(offenders)


def test_api_comfy_org_only_in_guarded_cnr_module():
    for path in CODE_FILES:
        if path.name == "cnr_utils.py":
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        assert "api.comfy.org" not in content, f"api.comfy.org outside cnr_utils: {path}"
    cnr = (REPO_ROOT / "glob" / "cnr_utils.py").read_text(encoding="utf-8")
    assert "_registry_blocked" in cnr, "network_mode guard missing from cnr_utils"


def test_notice_board_makes_no_network_calls():
    """The upstream notice board fetched remote HTML; the fork renders it locally.
    Replaces upstream's NoticeWiringTest (skipped in conftest.py)."""
    source = (REPO_ROOT / "glob" / "manager_server.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    funcs = [n for n in ast.walk(tree)
             if isinstance(n, ast.AsyncFunctionDef) and n.name == "get_notice"]
    assert len(funcs) == 1, "get_notice handler not found"
    body = ast.get_source_segment(source, funcs[0])
    for needle in ("ClientSession", "requests.", "urlopen", "aiohttp.", "session.get", "fetch("):
        assert needle not in body, f"get_notice performs network I/O ({needle})"


ALLOWED_WORKFLOWS = {"forgeguard-ci.yml", "ruff.yml"}


def test_only_allowlisted_workflows():
    """Upstream's publish workflows (Comfy Registry, PyPI) are removed; a new
    upstream workflow must be an explicit keep/remove decision at sync time."""
    present = {p.name for p in (REPO_ROOT / ".github" / "workflows").iterdir()
               if p.suffix in (".yml", ".yaml")}
    unexpected = sorted(present - ALLOWED_WORKFLOWS)
    assert not unexpected, "workflows not on the fork allowlist: " + ", ".join(unexpected)
