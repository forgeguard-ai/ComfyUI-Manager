---
title: ForgeGuard changes
description: Every behavioral delta this fork carries against upstream ComfyUI-Manager.
---

# ForgeGuard changes

Enforced mechanically by `tests/test_forgeguard_egress.py` and
`tests/test_forgeguard_downloads.py`.

## Removed

| Surface | Upstream location | Notes |
|---|---|---|
| Share backend (ComfyWorkflows presigned-S3 uploads, Matrix room posts) | `glob/share_3rdparty.py` | Uploads included the workflow, a full `pip freeze`, and SHA-256 digests of every model used; sessions ran `verify_ssl=False` |
| Share frontends (OpenArt, YouML, Copus, eSheep) + share button, share settings combo, workflow-gallery site menu, per-node "Share Output" | `js/comfyui-share-*.js`, `js/comfyui-manager.js` | Fully excised |
| Remote notice board (github.com wiki HTML fetched on every menu open, `verify_ssl=False`, no network_mode guard) | `glob/manager_server.py` | Replaced by a locally rendered notice with the same version/status footer |
| `matrix-nio`, `PyGithub` runtime deps | `requirements.txt` | PyGithub remains needed only by the maintainer-side `scanner.py` |

## Changed

| Behavior | Upstream | This fork |
|---|---|---|
| ComfyRegistry (`api.comfy.org`) install/version calls | Unguarded, fired even in offline mode | Honor `network_mode`; blocked unless `public` |
| Startup catalog prefetch (5 JSON fetches + full registry crawl with a `comfyui_version` + OS `form_factor` query fingerprint) | Unconditional unless `network_mode=offline` | Skipped entirely when `db_mode=local` (the shipped default in ComfyUI-Foundry) |
| Model install validation | Catalog match ignored the URL for `.safetensors` names; the agent downloader had no host restriction | Catalog match pins the URL; non-catalog URLs require https + `model_download_allowed_hosts` (default: huggingface.co, civitai.com, github.com, raw.githubusercontent.com) |
| Agent download path | Whole file buffered in RAM via urllib | Chunked `.part` streaming, Range resume, free-space check, atomic rename |
| `get_bool()` | Ignored its default: any key missing from an existing `config.ini` read `False` | Honors documented defaults; `allow_git_url_install`/`allow_pip_install` stay fail-closed |
| Default channel / catalog URLs | `raw.githubusercontent.com/ltdrdata/ComfyUI-Manager` | This fork (which carries and syncs the same node/model database) |
| GitPython install-failure help link | Upstream Matrix room | This fork's issue tracker |

## Added

| Feature | Details |
|---|---|
| Gated-model tokens | `HF_TOKEN` (huggingface.co and `HF_ENDPOINT` mirror) and `CIVITAI_TOKEN` (civitai.com) attached as `Authorization: Bearer` for their hosts only, across direct/agent/aria2/HF-repo download paths; never logged |
| `model_download_allowed_hosts` config key | Comma-separated host allowlist for non-catalog model URLs |
| Egress canary tests | Fail the suite if any removed cloud surface reappears in runtime code |

## Explicitly unchanged

Node install/update/disable flows, snapshots, cm-cli, security levels, the install queue,
component system, and the catalog data model.
