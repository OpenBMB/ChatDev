"""Private, metadata-only proxy checks for an allocated SearXNG service."""
import json
import os
from pathlib import Path
import signal
import subprocess


def proxy_state(env, expected):
    names = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
    return {'expected_proxy_present': bool(expected),
            'variables': {name: {'present': bool(env.get(name)),
                                 'matches_expected': bool(expected) and env.get(name) == expected}
                          for name in names},
            'loopback_bypass': all(host in env.get('NO_PROXY', '').split(',')
                                   for host in ['localhost', '127.0.0.1', '::1'])}


def process_states(pid, expected):
    pending, seen, rows = [pid], set(), []
    while pending and len(seen) < 24:
        current = pending.pop(0)
        if current in seen:
            continue
        seen.add(current)
        proc = Path('/proc') / str(current)
        try:
            raw = (proc / 'environ').read_bytes()
            env = {k.decode(errors='replace'): v.decode(errors='replace')
                   for entry in raw.split(b'\0') if b'=' in entry for k, v in [entry.split(b'=', 1)]}
            rows.append({'pid': current, 'executable': (proc / 'exe').resolve().name,
                         **proxy_state(env, expected)})
            for task in (proc / 'task').iterdir():
                try:
                    pending.extend(int(x) for x in (task / 'children').read_text().split())
                except (OSError, ValueError):
                    pass
        except OSError:
            rows.append({'pid': current, 'readable': False})
    return rows


CONTAINER_PROBE = r'''
import asyncio,json,os
from searx import settings
from searx.network.client import new_client
from curl_cffi import __version__ as curl_version
proxy=os.environ.get('HTTPS_PROXY')
outgoing=settings['outgoing']
result={'curl_cffi_version':curl_version,'proxy_env_present':bool(proxy),
        'settings_proxy_matches_env':bool(proxy) and outgoing.get('proxies')=={'all://':[proxy]},
        'configured_http2':outgoing['enable_http2'],'requests':[]}
async def probe(http2,route,label,url):
    client=new_client(False,outgoing['verify'],http2,False,2,{'all://':route},None,5)
    row={'transport':'searx_factory','http2_enabled':http2,'route':'invalid_control' if route=='http://127.0.0.1:9' else 'configured_proxy','endpoint':label}
    try:
        response=await client.get(url,timeout=12)
        row.update(http_status=response.status_code,response_bytes=len(response.content),http_version=int(response.http_version))
    except Exception as exc:
        row.update(error_class=type(exc).__name__,error_code=getattr(exc,'code',None))
    finally:
        await client.aclose()
    result['requests'].append(row)
async def main():
    if not proxy:return
    for http2 in [outgoing['enable_http2'],not outgoing['enable_http2']]:
        for label,url in [('documentation','https://docs.python.org/3/whatsnew/3.13.html'),('bing','https://www.bing.com/search?q=Python+3.13+release+date')]:
            await probe(http2,proxy,label,url)
    await probe(False,'http://127.0.0.1:9','documentation','https://docs.python.org/3/whatsnew/3.13.html')
asyncio.run(main())
print(json.dumps(result))
'''


def audit(state, expected, service_pid, service_cmd, service_env, image):
    import httpx
    result = {'host_environment': proxy_state(os.environ, expected),
              'service_processes': process_states(service_pid, expected), 'host_requests': []}
    def search_check():
        row = {}
        try:
            port = service_env['APPTAINERENV_GRANIAN_PORT']
            with httpx.Client(trust_env=False, timeout=35) as client:
                response = client.get('http://127.0.0.1:' + port + '/search',
                                      params={'q': 'Python 3.13 release date official', 'format': 'json', 'categories': 'general'})
                body = response.json()
                row.update(http_status=response.status_code, result_count=len(body.get('results', [])),
                           unresponsive_engines=body.get('unresponsive_engines', []))
        except Exception as exc:
            row['error_class'] = type(exc).__name__
        return row
    result['search_before_transport_checks'] = search_check()
    for route in ['inherited_environment', 'explicit_proxy', 'direct_control', 'invalid_proxy_control']:
        row = {'route': route, 'endpoint': 'documentation'}
        options = {'trust_env': route == 'inherited_environment', 'timeout': 8, 'follow_redirects': False}
        if route == 'explicit_proxy':
            options['proxy'] = expected
        elif route == 'invalid_proxy_control':
            options['proxy'] = 'http://127.0.0.1:9'
        try:
            with httpx.Client(**options) as client:
                response = client.get('https://docs.python.org/3/whatsnew/3.13.html')
                row.update(http_status=response.status_code, response_bytes=len(response.content))
        except Exception as exc:
            row['error_class'] = type(exc).__name__
        result['host_requests'].append(row)
    # Same image, user namespace, binds and environment as the live service.
    # The diagnostic uses SearXNG's own HTTP-client factory and loaded settings.
    argv = service_cmd[:service_cmd.index(image) + 1] + [
        '/usr/bin/env', 'HOME=/tmp/home', 'XDG_CACHE_HOME=/tmp/home/.cache',
        '/usr/local/searxng/.venv/bin/python', '-c', CONTAINER_PROBE]
    log = state / 'proxy-audit-container.log'
    try:
        with log.open('wb') as err:
            log.chmod(0o600)
            proc = subprocess.Popen(argv, env=service_env, cwd=state, stdout=subprocess.PIPE,
                                    stderr=err, start_new_session=True)
            try:
                stdout, _ = proc.communicate(timeout=90)
            except BaseException:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    proc.wait()
                raise
        result['container_exit_code'] = proc.returncode
        try:
            result['container_transport'] = json.loads(stdout)
        except ValueError:
            result['container_error'] = 'non_json_diagnostic_output'
    except subprocess.TimeoutExpired:
        result['container_error'] = 'diagnostic_timeout'
    result['search_after_transport_checks'] = search_check()
    target = state / 'proxy-audit.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    target.chmod(0o600)
    print(json.dumps({'proxy_audit_recorded': True, 'container_exit_code': result.get('container_exit_code')}), flush=True)
    return result
