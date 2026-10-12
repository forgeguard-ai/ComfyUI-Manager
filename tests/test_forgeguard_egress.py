"""Egress canary: fails if removed cloud surfaces reappear in Manager code.

Scans runtime code (glob/*.py, js/*.js, the entrypoints) — not the catalog
JSONs, whose data legitimately mentions third-party node names.
"""
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
