# Reproduce the minimal end-to-end example

This path prepares a fresh Linux x86-64 checkout and verifies a delivered JSON
file. The complete resource catalog remains in the repository. Preparation
records which resources are available at your endpoint and host.

You need Git, a usable Docker Engine, Python 3.11, a compatible model gateway,
and the configured 4B embedding endpoint. If you host the embedding model, use
a BF16-capable NVIDIA GPU. Model IDs and service contracts are described in
[SERVICES.md](SERVICES.md).

## 1. Create the framework environment

With Conda installed, run from `ChatDev/execorchestra`:

```bash
conda create -n execorchestra python=3.11 -y
conda activate execorchestra
python -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
python -m scripts.prepare_release init
test -f .env || cp .env.example .env
```

The CPU PyTorch wheel is sufficient for the host framework. GPU inference uses
the separate `execorchestra-embedding` environment. The branch-level
[README](../../README.md#quick-start) includes the complete installation and startup commands.

Fill `.env` with your gateway URL/key and a private, nonempty embedding API key.
Export it in each preparation or execution shell:

```bash
set -a
source .env
set +a
```

Configure host and tool proxies only where your network needs them. Values
containing shell characters must be quoted. Container network access is checked
separately from host access.

## 2. Prepare the Docker runtime

```bash
docker build -f sgar_mvp/docker/Dockerfile.runtime -t sgar-runtime:rc1 .
python -m sgar_mvp.scripts.seal_rc1_runtime
```

A cached runtime archive can instead be restored with `docker load --input
<archive.tar>`. It must provide the `sgar-runtime:rc1` tag. Always seal and verify
the image on the target host. On shared machines, use an independently configured
Docker instance and keep `DOCKER_HOST` set in every preparation and run shell.

The Dockerfile pins match the validated runtime, including `dateparser==1.4.3`,
`jsonschema==4.26.0`, `lxml==6.1.3`, `requests==2.34.2`, and `urllib3==2.8.0`.

## 3. Start the embedding endpoint

Follow [SERVICES.md](SERVICES.md#embedding-service) to download the exact model
and tokenizer revision and start the authenticated service from its separate
environment. Keep the service running while preparing the index and executing
the example. The defaults are:

- Model: `Qwen/Qwen3-Embedding-4B`.
- Revision: `5cf2132abc99cad020ac570b19d031efec650f2b`.
- Endpoint: `http://127.0.0.1:8001/v1/embeddings`.
- API model ID: `sgar-embedding-4b`; vector dimension: 2,560.
- BF16, SDPA, normalized last-token pooling, and a fixed microbatch of one.

The client template uses `.cache/embedding-tokenizer`. Update the ignored
`sgar_mvp/config/embedding_release.json` if the tokenizer or service is elsewhere.
Use a separate service terminal and stop the GPU process after use.

## 4. Generate fresh preparation evidence

```bash
(
  set -e
  python -m scripts.prepare_release health
  python -m scripts.prepare_release control
  python -m scripts.prepare_release tools
  python -m scripts.prepare_release agents
  python -m scripts.prepare_release readiness --allow-unavailable
  python -m scripts.prepare_release index
  python -m scripts.prepare_release check
)
```

These checks make real API and tool requests. `health` checks the declared model
capabilities and can take several minutes when optional models time out.
`readiness --allow-unavailable` explicitly prepares an available-resource
demonstration; inspect `sgar_mvp/runtime_state/preparation_report.json` for every
exclusion. For complete-catalog reproduction, omit `--allow-unavailable` and
resolve each missing resource first.

With explicit preparation completed, use its verified control receipts instead
of resending the same preflight requests on every launch:

```bash
python - <<'PY'
import json
from pathlib import Path
p = Path('sgar_mvp/config.json')
config = json.loads(p.read_text())
config.setdefault('runtime_settings', {})['auto_refresh_control_receipt'] = False
p.write_text(json.dumps(config, indent=2) + '\n')
PY
python -m scripts.prepare_release check
```

Runtime identity, receipt, and output-contract checks remain enabled. Repeat the
relevant preparation stages after changing the endpoint, model profile, runtime
image, or resource configuration. Preserve prior records and index directories
before rebuilding them; the index command refuses to overwrite an existing index.

## 5. Execute and inspect the delivered file

Use a new run directory for every attempt:

```bash
RUN_DIR="runs/quickstart-$(date -u +%Y%m%dT%H%M%SZ)"
bash scripts/run.sh --query-file examples/task.txt \
  --public-input-root examples --run-dir "$RUN_DIR"
python - "$RUN_DIR" <<'PY'
import hashlib, json, sys
from pathlib import Path
run = Path(sys.argv[1]).resolve()
manifest = json.loads((run / 'run_manifest.json').read_text())
assert manifest['pipeline_succeeded'] and manifest['manifest_valid']
delivery = json.loads((run / 'delivery_manifest.json').read_text())
answer = (run / delivery['delivery_locator']).resolve()
assert answer.is_relative_to(run)
raw = answer.read_bytes()
assert hashlib.sha256(raw).hexdigest() == delivery['content_sha256']
assert json.loads(raw) == {'sum': 42}
print('Verified delivered JSON:', answer)
PY
```

The task writes and verifies `answer.json` in its task workspace. The delivery
manifest names the final published copy. Inspect that copy and its hash;
intermediate files and tool success receipts are execution evidence.

This example validates the framework's artifact-generation and delivery path.
Web research additionally needs browser and search services; see [deep-research-deployment.md](deep-research-deployment.md).
