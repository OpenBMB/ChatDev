"""Stage prebuilt pure-Python Tool dependencies without installing into a task.

Only frozen assets declared by the framework are eligible. A task's existing
working dependencies win; no network resolution or repair-time pip is used.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name


CONFIG = Path(__file__).resolve().parents[1] / 'config/external_python_bundles.json'


def stage_dependency_bundle(runtime, *, requirements, missing_packages, python_version):
    if not missing_packages or not CONFIG.is_file():
        return None
    settings = json.loads(CONFIG.read_text(encoding='utf-8'))
    requested = {canonicalize_name(p.get('name') or p.get('package') or ''):
                 str(p.get('version') or '') for p in requirements.get('python_packages', [])
                 if isinstance(p, dict) and p.get('required', True)}
    missing = {canonicalize_name(p) for p in missing_packages}
    for item in settings.get('bundles', []):
        packages = item['packages']
        if not missing.issubset(packages):
            continue
        # Loading a zip can shadow transitive packages. Validate every declared
        # package it supplies, and all Python requirements of its sealed closure.
        if any(name in packages and packages[name]['version'] not in SpecifierSet(spec)
               for name, spec in requested.items()):
            continue
        if python_version not in SpecifierSet(item['python_compatibility']):
            continue
        if any(python_version not in SpecifierSet(p.get('requires_python') or '')
               for p in packages.values()):
            continue
        source = (CONFIG.parent / item['archive']).resolve()
        source.relative_to(CONFIG.parent.parent.resolve())
        content = source.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != item['sha256']:
            raise ValueError('external_python_bundle_hash_mismatch')
        target = f'/tmp/sgar-resource-runtime/dependencies/{digest}.zip'
        if digest in runtime._python_bundle_cache:
            return runtime._python_bundle_cache[digest]
        result = runtime.call('write_text', path=target+'.b64',
                              text=base64.b64encode(content).decode('ascii'), timeout_sec=30)
        if not result.get('ok'):
            return None
        script = """import base64, hashlib, pathlib, sys
p = pathlib.Path(sys.argv[1]); expected = sys.argv[2]
data = base64.b64decode(p.with_suffix('.zip.b64').read_bytes(), validate=True)
assert hashlib.sha256(data).hexdigest() == expected
p.write_bytes(data)
p.with_suffix('.zip.b64').unlink()
"""
        result = runtime.call('exec_argv', argv=['python3','-c',script,target,digest], timeout_sec=30)
        if not result.get('ok'):
            return None
        runtime._python_bundle_cache[digest] = target
        return target
