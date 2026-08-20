import os
from urllib.parse import urlparse
import sys
import shutil
import logging
import requests
from huggingface_hub import HfApi
from tqdm.auto import tqdm

aria2 = os.getenv('COMFYUI_MANAGER_ARIA2_SERVER')
HF_ENDPOINT = os.getenv('HF_ENDPOINT')


if aria2 is not None:
    secret = os.getenv('COMFYUI_MANAGER_ARIA2_SECRET')
    url = urlparse(aria2)
    port = url.port
    host = url.scheme + '://' + url.hostname
    import aria2p

    aria2 = aria2p.API(aria2p.Client(host=host, port=port, secret=secret))


BROWSER_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
FREE_SPACE_MARGIN = 256 * 1024 * 1024


def _auth_headers(url: str) -> dict:
    """ForgeGuard: attach operator-provided tokens for gated model sources.

    HF_TOKEN covers huggingface.co (and an HF_ENDPOINT mirror); CIVITAI_TOKEN
    covers civitai.com. Values are read from the environment and never logged.
    """
    headers = {}
    try:
        host = (urlparse(url).hostname or '').lower()
    except ValueError:
        return headers
    hf_hosts = {'huggingface.co'}
    if HF_ENDPOINT:
        mirror = urlparse(HF_ENDPOINT).hostname
        if mirror:
            hf_hosts.add(mirror.lower())
    token = None
    if host in hf_hosts or host.endswith('.huggingface.co'):
        token = os.getenv('HF_TOKEN')
    elif host == 'civitai.com' or host.endswith('.civitai.com'):
        token = os.getenv('CIVITAI_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


def stream_download(url: str, dest_path: str, user_agent: str | None = None):
    """Chunked download to <dest>.part with rename-on-complete and resume.

    ForgeGuard replacement for the upstream paths that either buffered whole
    checkpoints in memory (urllib agent path) or went through torchvision.
    Raises on HTTP errors and on insufficient free disk space.
    """
    dest_dir = os.path.dirname(dest_path)
    os.makedirs(dest_dir, exist_ok=True)
    part_path = dest_path + '.part'

    headers = dict(_auth_headers(url))
    if user_agent:
        headers['User-Agent'] = user_agent

    resume_from = os.path.getsize(part_path) if os.path.exists(part_path) else 0
    if resume_from:
        headers['Range'] = f'bytes={resume_from}-'

    with requests.get(url, stream=True, headers=headers, timeout=(30, 120), allow_redirects=True) as r:
        if resume_from and r.status_code == 200:
            resume_from = 0  # server ignored Range: restart from scratch
        elif resume_from and r.status_code == 206:
            logging.info(f"[ComfyUI-Manager] resuming download at {resume_from} bytes: {dest_path}")
        r.raise_for_status()

        total = r.headers.get('Content-Length')
        total = int(total) + resume_from if total is not None else None
        if total is not None:
            free = shutil.disk_usage(dest_dir).free
            if free < (total - resume_from) + FREE_SPACE_MARGIN:
                raise OSError(
                    f"insufficient free space for {os.path.basename(dest_path)}: "
                    f"need {total - resume_from} bytes, {free} available in {dest_dir}")

        mode = 'ab' if resume_from else 'wb'
        with open(part_path, mode) as f, tqdm(
            total=total, initial=resume_from, unit='B', unit_scale=True,
            desc=os.path.basename(dest_path),
        ) as pbar:
            for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

    os.replace(part_path, dest_path)


def basic_download_url(url, dest_folder: str, filename: str):
    '''
    Download file from url to dest_folder with filename
    using requests library.
    '''
    import requests

    # Ensure the destination folder exists
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)

    # Full path to save the file
    dest_path = os.path.join(dest_folder, filename)

    # Download the file
    response = requests.get(url, stream=True, headers=_auth_headers(url))
    if response.status_code == 200:
        with open(dest_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    file.write(chunk)
    else:
        raise Exception(f"Failed to download file from {url}")


def download_url(model_url: str, model_dir: str, filename: str):
    if HF_ENDPOINT:
        model_url = model_url.replace('https://huggingface.co', HF_ENDPOINT)
        logging.info(f"model_url replaced by HF_ENDPOINT, new = {model_url}")
    if aria2:
        return aria2_download_url(model_url, model_dir, filename)
    else:
        try:
            return stream_download(model_url, os.path.join(model_dir, filename))
        except Exception as e:
            logging.error(f"[ComfyUI-Manager] Failed to download: {model_url} / {repr(e)}")
            raise


def aria2_find_task(dir: str, filename: str):
    target = os.path.join(dir, filename)

    downloads = aria2.get_downloads()

    for download in downloads:
        for file in download.files:
            if file.is_metadata:
                continue
            if str(file.path) == target:
                return download


def aria2_download_url(model_url: str, model_dir: str, filename: str):
    import manager_core as core
    import tqdm
    import time

    if model_dir.startswith(core.comfy_path):
        model_dir = model_dir[len(core.comfy_path) :]

    download_dir = model_dir if model_dir.startswith('/') else os.path.join('/models', model_dir)

    download = aria2_find_task(download_dir, filename)
    if download is None:
        options = {'dir': download_dir, 'out': filename}
        auth = _auth_headers(model_url)
        if auth:
            options['header'] = [f'{k}: {v}' for k, v in auth.items()]
        download = aria2.add(model_url, options)[0]

    if download.is_active:
        with tqdm.tqdm(
            total=download.total_length,
            bar_format='{l_bar}{bar}{r_bar}',
            desc=filename,
            unit='B',
            unit_scale=True,
        ) as progress_bar:
            while download.is_active:
                if progress_bar.total == 0 and download.total_length != 0:
                    progress_bar.reset(download.total_length)
                progress_bar.update(download.completed_length - progress_bar.n)
                time.sleep(1)
                download.update()


def download_url_with_agent(url, save_path):
    # ForgeGuard: upstream buffered the whole file in memory via urllib;
    # stream to disk instead (with resume + token support).
    try:
        stream_download(url, save_path, user_agent=BROWSER_USER_AGENT)
    except Exception as e:
        print(f"Download error: {url} / {e}", file=sys.stderr)
        return False

    print("Installation was successful.")
    return True

# NOTE: snapshot_download doesn't provide file size tqdm.
def download_repo_in_bytes(repo_id, local_dir):
    api = HfApi(token=os.getenv('HF_TOKEN'))
    repo_info = api.repo_info(repo_id=repo_id, files_metadata=True)

    os.makedirs(local_dir, exist_ok=True)

    total_size = 0
    for file_info in repo_info.siblings:
        if file_info.size is not None:
            total_size += file_info.size

    pbar = tqdm(total=total_size, unit="B", unit_scale=True, desc="Downloading")

    for file_info in repo_info.siblings:
        out_path = os.path.join(local_dir, file_info.rfilename)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        if file_info.size is None:
            continue

        download_url = f"https://huggingface.co/{repo_id}/resolve/main/{file_info.rfilename}"

        with requests.get(download_url, stream=True, headers=_auth_headers(download_url)) as r, open(out_path, "wb") as f:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

    pbar.close()


