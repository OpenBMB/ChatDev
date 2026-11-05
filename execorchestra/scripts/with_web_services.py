"""Run a command with pinned, loopback-only SearXNG and Zotero services.

Requires an allocated Linux job. No daemon, root privilege, translator update,
or public listener is used. The caller supplies its preserved SearXNG settings.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time

import yaml

from sgar_mvp.src.apptainer_runtime import file_sha256, ApptainerExecutionSubstrate


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("apptainer", "tools-prefix", "state-dir", "searxng-image",
                 "searxng-sha256", "searxng-settings", "zotero-image", "zotero-sha256"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--timeout-sec", type=int, default=600)
    parser.add_argument("--audit-proxy", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("allocated_job_required")
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise ValueError("child_command_required")
    state = Path(args.state_dir).resolve()
    state.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name in ("searxng", "zotero"):
        image = Path(getattr(args, name + "_image")).resolve(strict=True)
        digest = getattr(args, name + "_sha256")
        if not re.fullmatch("[a-f0-9]{64}", digest) or file_sha256(image) != digest:
            raise RuntimeError(name + "_image_identity_mismatch")
    ports = {name: free_port() for name in ("searxng", "zotero")}
    while ports["zotero"] == ports["searxng"]:
        ports["zotero"] = free_port()
    settings = yaml.safe_load(Path(args.searxng_settings).read_text())
    settings.setdefault("server", {}).update(bind_address="127.0.0.1", port=ports["searxng"])
    # Service operation and search engines remain those of the supplied config;
    # only the network route and loopback endpoint change for the cluster.
    proxy = os.environ.get("SGAR_TOOL_HTTPS_PROXY") or os.environ.get("SGAR_TOOL_HTTP_PROXY")
    if proxy:
        settings.setdefault("outgoing", {})["proxies"] = {"all://": [proxy]}
    config_dir = state / "searxng-config"
    config_dir.mkdir(mode=0o700)
    config_file = config_dir / "settings.yml"
    config_file.write_text(yaml.safe_dump(settings, sort_keys=False))
    config_file.chmod(0o600)
    processes = []
    handles = []
    launch_context = {}
    summary = {"job_id": os.environ["SLURM_JOB_ID"], "services": {}, "child_exit_code": None}

    def launch(name, workdir, argv, extra_env, binds=()):
        private = state / name
        private.mkdir(mode=0o700)
        tmp = private / "tmp"; tmp.mkdir(mode=0o700)
        (tmp / "home").mkdir(mode=0o700)
        tools = Path(args.tools_prefix).resolve()
        env = {"PATH": f"{tools}/bin:{tools}/sbin:/usr/bin:/bin", "HOME": str(private),
               "APPTAINER_TMPDIR": str(private), "APPTAINER_CACHEDIR": str(private / "cache")}
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            if proxy:
                extra_env[key] = proxy
        extra_env.update(NO_PROXY="localhost,127.0.0.1,::1", no_proxy="localhost,127.0.0.1,::1")
        env.update({"APPTAINERENV_" + k: v for k, v in extra_env.items()})
        cmd = [args.apptainer, "exec", "--userns", "--containall", "--cleanenv", "--no-eval",
               "--no-mount", "home,cwd,hostfs,bind-paths", "--drop-caps", "all",
               "--security", "no-new-privs", "--pwd", workdir]
        for src, dst, mode in [(tmp, "/tmp", "rw"), *binds]:
            if any(char in str(src) for char in (":", ",", "\n")):
                raise ValueError("unrepresentable_bind_path")
            cmd += ["--bind", f"{src}:{dst}:{mode}"]
        cmd += [str(Path(getattr(args, name + "_image")).resolve()), "/usr/bin/env",
                "HOME=/tmp/home", "XDG_CACHE_HOME=/tmp/home/.cache", *argv]
        handle = (private / "service.log").open("w")
        handles.append(handle)
        (private / "service.log").chmod(0o600)
        proc = subprocess.Popen(cmd, env=env, cwd=private, stdout=handle,
                                stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(proc)
        launch_context[name] = (cmd, env)
        return proc

    def stop_signal(signum, frame):
        raise SystemExit(128 + signum)

    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, stop_signal)
    try:
        cache = state / "searxng-cache"; cache.mkdir(mode=0o700)
        launched = {
            "searxng": launch("searxng", "/usr/local/searxng",
                ["/usr/local/searxng/entrypoint.sh"],
                {"GRANIAN_HOST": "127.0.0.1", "GRANIAN_PORT": str(ports["searxng"]),
                 "FORCE_OWNERSHIP": "false"},
                [(config_dir, "/etc/searxng", "ro"), (cache, "/var/cache/searxng", "rw")]),
            "zotero": launch("zotero", "/app", ["node", "src/server.js"],
                {"NODE_CONFIG": json.dumps({"host": "127.0.0.1", "port": ports["zotero"]})}),
        }
        for name, proc in launched.items():
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError(name + "_service_exited")
                try:
                    with socket.create_connection(("127.0.0.1", ports[name]), timeout=0.3):
                        break
                except OSError:
                    time.sleep(0.5)
            else:
                raise TimeoutError(name + "_startup_timeout")
            summary["services"][name] = {"ready": True, "port": ports[name],
                "image_sha256": getattr(args, name + "_sha256")}
        if args.audit_proxy:
            from scripts.search_proxy_audit import audit
            audit(state, proxy, launched['searxng'].pid,
                  *launch_context['searxng'], str(Path(args.searxng_image).resolve()))
        child_env = dict(os.environ)
        child_env.update(SEARXNG_BASE_URL=f"http://127.0.0.1:{ports['searxng']}",
                         ZOTERO_TRANSLATION_SERVER_URL=f"http://127.0.0.1:{ports['zotero']}")
        child = subprocess.Popen(command, env=child_env, start_new_session=True)
        processes.append(child)
        summary["child_exit_code"] = child.wait(timeout=args.timeout_sec)
    finally:
        for proc in reversed(processes):
            ApptainerExecutionSubstrate._stop_group(proc)
        for handle in handles:
            handle.close()
        for name, port in ports.items():
            with socket.socket() as sock:
                summary["services"].setdefault(name, {})["endpoint_released"] = sock.connect_ex(("127.0.0.1", port)) != 0
        (state / "receipt.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary), flush=True)
    return summary["child_exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
