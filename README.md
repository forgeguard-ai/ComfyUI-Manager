<div align="center">

# ComfyUI-Manager — ForgeGuard Fork

<!-- banner: docs/forgeguard/assets/banner-dark.png (asset pending) -->

**A hardened fork of [ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager) with all share/cloud integrations removed and model downloads hardened — the manager baked into [ComfyUI-Foundry](https://github.com/forgeguard-ai/comfyui-foundry) images.**

<a href="https://github.com/ltdrdata/ComfyUI-Manager"><img alt="Upstream" src="https://img.shields.io/badge/Upstream-ltdrdata%2FComfyUI--Manager-FFD700?style=for-the-badge"></a>
<a href="https://github.com/forgeguard-ai/comfyui-foundry"><img alt="Images" src="https://img.shields.io/badge/Images-ComfyUI--Foundry-111820?style=for-the-badge&logo=github"></a>
<a href="./LICENSE.txt"><img alt="License" src="https://img.shields.io/github/license/forgeguard-ai/ComfyUI-Manager?style=for-the-badge"></a>

</div>

> [!IMPORTANT]
> **ForgeGuard maintained fork of [`ltdrdata/ComfyUI-Manager`](https://github.com/ltdrdata/ComfyUI-Manager).**
> This fork changes behavior on purpose. Removed: the share integrations
> (ComfyWorkflows/Matrix/OpenArt/YouML/Copus/eSheep — the backend variants uploaded your
> workflow plus a full pip-freeze and the SHA-256 of every model used), the remote notice-board
> fetch, and unguarded ComfyRegistry calls. Changed: startup performs **zero network requests**
> in the shipped configuration (`db_mode=local`), the catalog database is served from this
> repository, and model downloads gain Hugging Face / Civitai **token support**, strict **URL
> validation**, and **streaming downloads with resume**. Node management itself works as
> upstream documents.
>
> [What changed](./docs/forgeguard/forgeguard-changes.md) ·
> [Upstream README](https://github.com/ltdrdata/ComfyUI-Manager#readme) ·
> Not affiliated with or endorsed by Comfy Org or the upstream author.

## Highlights of the delta

| Area | This fork |
|---|---|
| Share features | Fully removed (backend + UI). |
| Startup egress | None with the shipped config: `db_mode=local` serves the packaged catalog; the notice board renders locally; the api.comfy.org registry crawl is disabled unless `network_mode=public`. |
| Model downloads | `HF_TOKEN` / `CIVITAI_TOKEN` env tokens for gated models; catalog entries pin their URL; non-catalog URLs must be https on the `model_download_allowed_hosts` allowlist; chunked `.part` downloads with Range resume and a free-space check. |
| Config correctness | `get_bool()` honors documented defaults (a partial `config.ini` no longer silently disables `file_logging`); security install flags remain fail-closed. |
| Catalog channels | `channels.list` points at this fork, which carries the upstream node/model database and syncs it regularly. |

The full, file-level list lives in
[docs/forgeguard/forgeguard-changes.md](./docs/forgeguard/forgeguard-changes.md).
Upstream base: see [`FORK_UPSTREAM_BASE`](./FORK_UPSTREAM_BASE).

## Usage

Use it exactly like upstream ComfyUI-Manager — install into `custom_nodes/` or use the
prebuilt [ComfyUI-Foundry](https://github.com/forgeguard-ai/comfyui-foundry) image where it is
already baked in and preconfigured. Upstream's
[README](https://github.com/ltdrdata/ComfyUI-Manager#readme) documents the manager itself;
everything it says applies here except the removed share features and the network defaults
above.

## License

GPL-3.0, same as upstream. ForgeGuard modifications are documented in
[docs/forgeguard/](./docs/forgeguard/forgeguard-changes.md) and the commit history.
