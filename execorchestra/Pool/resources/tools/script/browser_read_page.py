"""Read a rendered public page through the private job-scoped browser service."""
import argparse
import json
import os
import ipaddress
from urllib.parse import urlsplit
import httpx


def private_service_address(base):
    """Allow an explicitly configured local service on a Docker private bridge.

    This checks the trusted deployment endpoint, never the page URL requested by
    the solver. Public-page admission remains enforced by the browser service.
    """
    p=urlsplit(base)
    if p.scheme!='http' or not p.hostname or p.username or p.password:
        return False
    if p.hostname in {'127.0.0.1','localhost','::1'}:
        return True
    try:
        address=ipaddress.ip_address(p.hostname)
    except ValueError:
        return False
    return any(address in network for network in (
        ipaddress.ip_network('10.0.0.0/8'),
        ipaddress.ip_network('172.16.0.0/12'),
        ipaddress.ip_network('192.168.0.0/16')))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('--text-offset',type=int,default=0)
    parser.add_argument('--link-offset',type=int,default=0)
    args=parser.parse_args()
    base=os.environ.get('SGAR_BROWSER_BASE_URL','')
    token=os.environ.get('SGAR_BROWSER_TOKEN','')
    if not private_service_address(base) or not token:
        print(json.dumps({'status':'error','error':'private_browser_service_not_configured'})); return 2
    try:
        with httpx.Client(timeout=60,trust_env=False,follow_redirects=False) as client:
            response=client.post(base.rstrip('/')+'/read',headers={'Authorization':'Bearer '+token},
                json={'url':args.url,'text_offset':args.text_offset,'link_offset':args.link_offset})
            if response.status_code!=200:
                print(json.dumps({'status':'error','error':'browser_service_http_error','http_status':response.status_code})); return 1
            data=response.json()
        print(json.dumps(data,ensure_ascii=False))
        return 0 if data.get('status')=='success' else 1
    except Exception as exc:
        print(json.dumps({'status':'error','error':'browser_service_unavailable','error_class':type(exc).__name__})); return 1


if __name__=='__main__': raise SystemExit(main())
