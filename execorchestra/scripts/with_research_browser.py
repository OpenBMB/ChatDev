"""Run a child command with a private browser and clean up its process group."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
import httpx


def stop(proc):
    if proc is None: return
    try: os.killpg(proc.pid,signal.SIGTERM)
    except ProcessLookupError: return
    try: proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try: os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        proc.wait()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--python',required=True)
    p.add_argument('--browsers-path',required=True)
    p.add_argument('--state-dir',required=True)
    p.add_argument('--timeout-sec',type=int,default=1800)
    p.add_argument('--allowed-host',action='append',default=[])
    p.add_argument('--inline-links',action='store_true')
    p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'): raise RuntimeError('allocated_job_required')
    command=a.command[1:] if a.command[:1]==['--'] else a.command
    if not command: raise ValueError('child_command_required')
    state=Path(a.state_dir).resolve(); state.mkdir(parents=True,exist_ok=False,mode=0o700)
    with socket.socket() as s: s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
    token=secrets.token_urlsafe(32); base=f'http://127.0.0.1:{port}'
    service_env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','LANG','SLURM_JOB_ID','SGAR_TOOL_HTTPS_PROXY'}}
    temp=state/'tmp'; temp.mkdir(mode=0o700)
    service_env.update(SGAR_BROWSER_TOKEN=token,PLAYWRIGHT_BROWSERS_PATH=a.browsers_path,
                       PYTHONUNBUFFERED='1',TMPDIR=str(temp))
    argv=[a.python,str(Path(__file__).with_name('research_browser.py')),'--port',str(port),'--state-dir',str(state/'snapshots')]
    for host in a.allowed_host: argv+=['--allowed-host',host]
    if a.inline_links: argv.append('--inline-links')
    service=child=None
    receipt={'job_id':os.environ['SLURM_JOB_ID'],'ready':False,'child_exit_code':None,
             'service_sha256':hashlib.sha256(Path(argv[1]).read_bytes()).hexdigest(),
             'python':str(Path(a.python).absolute()),'browsers_path':str(Path(a.browsers_path).absolute())}
    if a.inline_links: receipt['inline_links']=True
    def interrupted(signum,frame): raise SystemExit(128+signum)
    for sig in [signal.SIGTERM,signal.SIGINT]: signal.signal(sig,interrupted)
    try:
        log=state/'service.log'
        with log.open('wb') as f:
            log.chmod(0o600)
            service=subprocess.Popen(argv,env=service_env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        with httpx.Client(timeout=2,trust_env=False) as client:
            for _ in range(60):
                if service.poll() is not None: raise RuntimeError('browser_service_exited')
                try:
                    r=client.get(base+'/health',headers={'Authorization':'Bearer '+token})
                    if r.status_code==200 and r.json().get('ready'): receipt['ready']=True; break
                except httpx.HTTPError: pass
                time.sleep(1)
            else: raise TimeoutError('browser_startup_timeout')
        env=dict(os.environ,SGAR_BROWSER_BASE_URL=base,SGAR_BROWSER_TOKEN=token)
        child=subprocess.Popen(command,env=env,start_new_session=True)
        receipt['child_exit_code']=child.wait(timeout=a.timeout_sec)
    finally:
        stop(child); stop(service)
        with socket.socket() as s: receipt['endpoint_released']=s.connect_ex(('127.0.0.1',port))!=0
        (state/'receipt.json').write_text(json.dumps(receipt,indent=2))
        print(json.dumps(receipt),flush=True)
    return receipt['child_exit_code']


if __name__=='__main__': raise SystemExit(main())
