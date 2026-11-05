"""Download official public data at resolved revisions; keep plaintext private."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import httpx


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output',required=True); a=p.parse_args()
    root=Path(a.output).resolve(); root.mkdir(parents=True,exist_ok=False,mode=0o700)
    manifest={}
    with httpx.Client(proxy=os.environ.get('SGAR_TOOL_HTTPS_PROXY') or None,trust_env=False,timeout=60,follow_redirects=True) as c:
        r=c.get('https://api.github.com/repos/xbench-ai/xbench-evals/commits/main'); r.raise_for_status(); rev=r.json()['sha']
        r=c.get(f'https://raw.githubusercontent.com/xbench-ai/xbench-evals/{rev}/data/DeepSearch-2510.csv'); r.raise_for_status()
        path=root/'xbench-encrypted.csv'; path.write_bytes(r.content); path.chmod(0o600)
        manifest['xbench']={'repository':'xbench-ai/xbench-evals','revision':rev,'sha256':hashlib.sha256(r.content).hexdigest()}
        r=c.get('https://huggingface.co/api/datasets/callanwu/WebWalkerQA'); r.raise_for_status(); webrev=r.json()['sha']
    from datasets import load_dataset
    rows=load_dataset('callanwu/WebWalkerQA',split='main',revision=webrev,cache_dir=str(root/'cache'))
    path=root/'webwalker.jsonl'
    path.write_text(''.join(json.dumps(dict(x),ensure_ascii=False)+'\n' for x in rows),encoding='utf-8'); path.chmod(0o600)
    manifest['webwalker']={'repository':'callanwu/WebWalkerQA','revision':webrev,'split':'main','count':len(rows),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    for bench,file in [('xbench','xbench-encrypted.csv'),('webwalker','webwalker.jsonl')]:
        subprocess.run([sys.executable,'-m','scripts.research_benchmark','prepare','--benchmark',bench,
            '--source',str(root/file),'--revision',manifest[bench]['revision'],'--output',str(root/bench)],check=True)
    (root/'download-manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest),flush=True)


if __name__=='__main__': main()
