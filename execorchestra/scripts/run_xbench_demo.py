"""Start demo-only web services, prepare resources if needed, and run XBench."""

from contextlib import ExitStack
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory, mkdtemp
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from scripts.prepare_xbench_demo import CASE_ID, ROOT, TASK_PATH


SEARXNG_IMAGE = "searxng/searxng@sha256:394bc18556af80cd1cd448daf5b69ead7f65d990912851a47ba1ec79c85fec44"
BROWSER_IMAGE = "execorchestra-xbench-browser:1.64.1"
RUNTIME_IMAGE = "sgar-runtime:rc1"
WEB_TOOLS = {"tool.searxng_search.v1", "tool.browser_read_page.v1"}
READINESS = Path("sgar_mvp/config/resource_readiness_rc1.json")
RUNTIME_LOCK = Path("sgar_mvp/config/rc1_runtime_lock.json")


def run(*command, cwd=ROOT, env=None):
    subprocess.run(command, cwd=cwd, env=env, check=True)


def docker_output(*args):
    return subprocess.check_output(("docker", *args), text=True).strip()


def remove_service(name, log_path):
    with log_path.open("wb") as log:
        subprocess.run(("docker", "logs", name), stdout=log, stderr=subprocess.STDOUT)
    result = subprocess.run(("docker", "rm", "-fv", name), capture_output=True)
    if result.returncode and b"No such container" not in result.stderr:
        print(f"Could not remove demo container {name}. See {log_path}.", file=sys.stderr)


def start_service(stack, session, label, gateway, port, options, image, *, env=None):
    name = f"execorchestra-xbench-{label}-{uuid4().hex[:12]}"
    stack.callback(remove_service, name, session / f"{label}.log")
    run("docker", "run", "-d", "--name", name, "--network", "bridge",
        "-p", f"{gateway}::{port}", *options, image, env=env)
    address = docker_output("port", name, f"{port}/tcp")
    return f"http://{address}"


def wait_for_service(label, url, ready, *, token=None):
    opener = build_opener(ProxyHandler({}))
    request = Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            with opener.open(request, timeout=8) as response:
                if ready(json.load(response)):
                    return
        except (URLError, TimeoutError, ValueError):
            pass
        time.sleep(2)
    raise RuntimeError(f"{label} did not become ready. See the service log in the demo directory.")


def start_web_services(stack, session, temp_dir):
    print("Starting temporary search and browser services...", flush=True)
    gateway = docker_output("network", "inspect", "bridge", "-f", "{{(index .IPAM.Config 0).Gateway}}")
    if not gateway:
        raise RuntimeError("The demo requires a local Docker Engine with its default bridge network.")

    search_settings = temp_dir / "searxng"
    search_settings.mkdir(mode=0o755)
    settings = {
        "use_default_settings": True,
        "search": {"formats": ["html", "json"]},
        "server": {"limiter": False, "secret_key": secrets.token_hex(32)},
    }
    proxy = os.environ.get("SGAR_TOOL_HTTPS_PROXY") or os.environ.get("SGAR_TOOL_HTTP_PROXY")
    if proxy:
        settings["outgoing"] = {"proxies": {"all://": [proxy]}}
    # JSON is valid YAML and quotes any proxy credentials safely.
    settings_file = search_settings / "settings.yml"
    settings_file.write_text(json.dumps(settings), encoding="utf-8")
    settings_file.chmod(0o644)
    search = start_service(
        stack, session, "search", gateway, 8080,
        ("-e", "FORCE_OWNERSHIP=false", "--mount",
         f"type=bind,source={search_settings},target=/etc/searxng,readonly"),
        SEARXNG_IMAGE,
    )

    browser_context = temp_dir / "browser-image"
    (browser_context / "scripts").mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts/research_browser.py", browser_context / "scripts/research_browser.py")
    shutil.copyfile(ROOT / "sgar_mvp/docker/Dockerfile.xbench-browser", browser_context / "Dockerfile")
    image_id_file = temp_dir / "browser-image-id"
    run("docker", "build", "--iidfile", str(image_id_file), "-t", BROWSER_IMAGE, str(browser_context))
    token = secrets.token_urlsafe(32)
    env = dict(os.environ, SGAR_BROWSER_TOKEN=token)
    if proxy:
        env["SGAR_TOOL_HTTPS_PROXY"] = proxy
    browser = start_service(
        stack, session, "browser", gateway, 8002,
        ("--init", "--shm-size", "256m", "--cap-drop", "ALL",
         "--security-opt", "no-new-privileges", "-e", "SGAR_BROWSER_TOKEN",
         "-e", "SGAR_TOOL_HTTPS_PROXY"),
        image_id_file.read_text(encoding="ascii").strip(), env=env,
    )
    query = urlencode({"q": "Python documentation", "format": "json"})
    wait_for_service("Search", f"{search}/search?{query}", lambda data: bool(data.get("results")))
    wait_for_service("Browser", f"{browser}/health", lambda data: data.get("ready"), token=token)

    env.update(SEARXNG_BASE_URL=search, SGAR_BROWSER_BASE_URL=browser, SGAR_PYTHON=sys.executable)
    host_bypass = env.get("no_proxy", env.get("NO_PROXY"))
    env["NO_PROXY"] = env["no_proxy"] = ",".join(filter(None, (host_bypass, gateway)))
    env["SGAR_TOOL_NO_PROXY"] = ",".join(filter(None, (env.get("SGAR_TOOL_NO_PROXY"), gateway)))
    return env


def has_web_index(project):
    if not (project / "Pool/index_meta/index_build_manifest.json").is_file():
        return False
    try:
        report = json.loads((project / READINESS).read_text(encoding="utf-8-sig"))
        return WEB_TOOLS.issubset(report["effective_resource_ids"])
    except (FileNotFoundError, ValueError, KeyError, TypeError):
        return False


def prepare_project(temp_dir, session, env):
    if has_web_index(ROOT):
        return ROOT
    print("Preparing an isolated resource index with both web tools. This may make billable API calls.",
          flush=True)
    top = Path(subprocess.check_output(("git", "rev-parse", "--show-toplevel"), cwd=ROOT, text=True).strip())
    checkout = temp_dir / "checkout"
    run("git", "clone", "--quiet", "--shared", "--no-tags", "--", str(top), str(checkout))
    project = checkout / ROOT.relative_to(top)
    config = Path("sgar_mvp/config.json")
    if (ROOT / config).is_file():
        shutil.copyfile(ROOT / config, project / config)
    run(sys.executable, "-m", "scripts.prepare_release", "init", cwd=project, env=env)

    embedding = Path("sgar_mvp/config/embedding_release.json")
    source = ROOT / embedding
    settings = json.loads((source if source.exists() else project / embedding).read_text(encoding="utf-8-sig"))
    tokenizer = Path(settings["runtime"]["tokenizer_path"]).expanduser()
    settings["runtime"]["tokenizer_path"] = str((ROOT / tokenizer).resolve())
    (project / embedding).write_text(json.dumps(settings), encoding="utf-8")
    if (ROOT / RUNTIME_LOCK).is_file():
        shutil.copyfile(ROOT / RUNTIME_LOCK, project / RUNTIME_LOCK)
    else:
        run(sys.executable, "-m", "sgar_mvp.scripts.seal_rc1_runtime", cwd=project, env=env)
    try:
        run(sys.executable, "-m", "scripts.prepare_release", "all", "--allow-unavailable", cwd=project, env=env)
    finally:
        report = project / "sgar_mvp/runtime_state/preparation_report.json"
        if report.is_file():
            shutil.copyfile(report, session / report.name)
    if not has_web_index(project):
        raise RuntimeError("Both web tools must pass preparation. See preparation_report.json in the demo directory.")
    return project


def main():
    if not sys.platform.startswith("linux"):
        raise SystemExit("Run this example on the Linux Docker host used for Quick Start.")
    if not os.environ.get("LLM_API_KEY") or not os.environ.get("SGAR_EMBEDDING_API_KEY"):
        raise SystemExit("Complete the Quick Start model and embedding configuration in .env first.")
    run("docker", "image", "inspect", "--format", "{{.Id}}", RUNTIME_IMAGE)
    run(sys.executable, "-m", "scripts.prepare_xbench_demo")
    runs = ROOT / "runs"
    runs.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    session = Path(mkdtemp(prefix=f"xbench-{CASE_ID}-{stamp}-", dir=runs))
    print(f"Demo directory: {session}", flush=True)
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    with (
        TemporaryDirectory(prefix="xbench-demo-", dir=cache, ignore_cleanup_errors=True) as temporary,
        ExitStack() as services,
    ):
        temp_dir = Path(temporary)
        env = start_web_services(services, session, temp_dir)
        project = prepare_project(temp_dir, session, env)
        task = ROOT / TASK_PATH
        run("bash", "scripts/run.sh", "--query-file", str(task),
            "--public-input-root", str(task.parent), "--network-policy", "declared",
            "--max-generation-requests", "48", "--deadline-sec", "1800",
            "--run-dir", str(session / "run"), cwd=project, env=env)


if __name__ == "__main__":
    def terminate(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"XBench demo stopped: {exc}") from None
