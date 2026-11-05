"""Project-scoped registry download through an explicit proxy, then local load.

Never reconfigure/restart dockerd or refresh an existing image. Skopeo's archive
transport also works with old Skopeo and a new Docker daemon API.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .direct_network import direct_environment, load_model_proxy


class ImagePreparationError(RuntimeError):
    pass


def prepare_image(image: str, *, project_root: Path | None = None,
                  timeout: float = 900, runner=None) -> dict:
    """Use a cached image or download the exact requested registry reference.

    New images use an SGAR-owned tag. The official reference and immutable image
    ID are returned separately; no shared tag is overwritten.
    """
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    run = runner or subprocess.run

    def inspect(ref):
        result = run(['docker', 'image', 'inspect', ref, '--format', '{{.Id}}'],
                     capture_output=True, text=True, timeout=30, check=False)
        return result.stdout.strip() if result.returncode == 0 else ''

    image_id = inspect(image)
    if image_id:
        return {'source_image': image, 'image_id': image_id, 'status': 'cached', 'downloaded': False}
    # Unqualified local builds have no authoritative registry source to fetch.
    first = image.split('/', 1)[0]
    if '/' not in image or not ('.' in first or ':' in first or first == 'localhost'):
        raise ImagePreparationError('image_missing_no_explicit_registry_source')
    proxy = load_model_proxy(root)
    if not proxy:
        raise ImagePreparationError('image_preparation_proxy_not_configured')
    if shutil.which('skopeo') is None:
        raise ImagePreparationError('image_preparation_skopeo_unavailable')

    cache = root / 'sgar_mvp/execution_outputs/image_preparation'
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(image.encode()).hexdigest()
    tag = 'sgar-prepared:' + key[:24]
    receipt_path = cache / (key + '.json')
    # Serialize only SGAR cold downloads, not task execution or shared Docker.
    import fcntl
    with (cache / 'download.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        image_id = inspect(image)
        if image_id:
            return {'source_image': image, 'image_id': image_id, 'status': 'cached', 'downloaded': False}
        if receipt_path.exists():
            prior = json.loads(receipt_path.read_text())
            if prior.get('source_image') == image and inspect(tag) == prior.get('image_id'):
                return {**prior, 'status': 'cached_project_image', 'downloaded': False}
        env = direct_environment(os.environ)
        env.update({name: proxy for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy')})
        env.update(NO_PROXY='localhost,127.0.0.1,::1', no_proxy='localhost,127.0.0.1,::1')
        with tempfile.TemporaryDirectory(prefix='download-', dir=cache) as tmp:
            archive = Path(tmp) / 'image.tar'
            digest_file = Path(tmp) / 'manifest.digest'
            command = ['skopeo', '--override-os', 'linux', '--override-arch', 'amd64',
                       'copy', '--digestfile', str(digest_file), 'docker://' + image,
                       'docker-archive:' + str(archive) + ':' + tag]
            try:
                result = run(command, env=env, capture_output=True, text=True, timeout=timeout, check=False)
                if result.returncode:
                    # Proxy/registry credentials must not appear in diagnostics.
                    raise ImagePreparationError('image_proxy_download_failed')
                digest = digest_file.read_text().strip()
                result = run(['docker', 'load', '--input', str(archive)],
                             capture_output=True, text=True, timeout=timeout, check=False)
                if result.returncode:
                    raise ImagePreparationError('image_local_load_failed')
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ImagePreparationError('image_preparation_transport_failed') from exc
        image_id = inspect(tag)
        if not image_id:
            raise ImagePreparationError('prepared_image_not_loaded')
        record = {'source_image': image, 'image_id': image_id, 'local_tag': tag,
                  'copied_manifest_digest': digest, 'status': 'downloaded_via_proxy',
                  'downloaded': True, 'proxy_config_fingerprint': hashlib.sha256(proxy.encode()).hexdigest()}
        receipt_path.write_text(json.dumps(record, indent=2) + '\n')
        return record
