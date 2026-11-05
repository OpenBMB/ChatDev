# Models and services

Run these commands from the project directory (`ExecOrchestra/execorchestra`) after installing the host environment
and running `python -m scripts.prepare_release init`. Keep all service credentials
in `.env`, and export them with `set -a; source .env; set +a` in each shell.
Use shell-compatible values; quote values containing spaces or shell characters.

## Model endpoint

Set `LLM_BASE_URL` to the OpenAI-compatible API base URL and `LLM_API_KEY` to
its credential. The endpoint must support strict JSON-schema responses,
configured reasoning settings, tool continuation, and usage metadata.

| Control role | API model ID | Reasoning |
| --- | --- | --- |
| Planner | `gpt-6.1-sol` | `high` |
| Profiler | `gemini-3.8-flash` | `high` |
| Composer and plan adaptation | `gpt-6-luna` | `high` |
| Optional evaluator | `gpt-5.6-sol` | `high` |

The optional evaluator is disabled in the supplied execution configuration.
`gpt-6.1-sol` and `gpt-6-luna` are registered for control roles; adding them
does not add them to the task candidate pool. The distributed research pool contains 10 models, 38 tools, 4 skills, and 5 agents. The candidate model API IDs are:

```text
deepseek-v4.1-flash
deepseek-v4-pro-0813
gemini-3.8-flash
glm-5.3
gpt-5.6-luna
gpt-5.6-sol
gpt-6-astra
qwen3.5-35b-a3b
qwen3.8-flash
qwen3-coder-next
```

Health probes cover the model registry in `model_selection.json`; readiness
requires the configured candidate pool. Map API identifiers to the corresponding
model versions.

## Embedding service

The reference deployment uses `Qwen/Qwen3-Embedding-4B`, revision
`5cf2132abc99cad020ac570b19d031efec650f2b`, bfloat16 inference, and 2,560-dimensional
vectors.

### Download the model and tokenizer

For a local deployment, prepare its separate GPU environment and download the
weights and matching tokenizer. These commands do not start the service:

```bash
conda create -n execorchestra-embedding python=3.11 -y
conda run -n execorchestra-embedding python -m pip install -r requirements-embedding.txt
python -m scripts.download_embedding
```

For an existing remote service, download only the matching tokenizer. No GPU
environment or weights are needed on the framework host:

```bash
python -m scripts.download_embedding --tokenizer-only
```

### Start the local service

After configuration, open a separate terminal at the project directory (`ExecOrchestra/execorchestra`). Set a
private, nonempty `SGAR_EMBEDDING_API_KEY` in `.env` and use an NVIDIA GPU
supporting BF16. On a dedicated GPU server, start the prepared service with:

```bash
conda activate execorchestra-embedding
set -a
source .env
set +a
export SGAR_EMBEDDING_MODEL_PATH="$PWD/.cache/embedding-model"
# On a dedicated GPU server only; Slurm users instead run inside an allocation.
export SGAR_EMBEDDING_DEDICATED_GPU=1
python -m scripts.embedding_server
```

The service binds to `127.0.0.1:8001`. It uses BF16, SDPA, last-token pooling,
L2 normalization, and a fixed microbatch of one. It does not silently truncate
inputs or add a second retrieval instruction. Stop the foreground process after
the task; the module does not start automatically during installation or checks.
The model directory must contain the weights and tokenizer for the pinned revision.

An NVIDIA driver and NVIDIA Container Toolkit are required for the alternative
vLLM container deployment:

```bash
export EMBEDDING_GPU=0
VLLM_API_KEY="$SGAR_EMBEDDING_API_KEY" docker run -d \
  --name execorchestra-embedding --gpus "device=${EMBEDDING_GPU}" \
  --network host --ipc host -e VLLM_API_KEY \
  -v "$PWD/.cache/embedding-model:/models/embedding-4b:ro" \
  vllm/vllm-openai:v0.27.1-cu129-ubuntu2404 \
  /models/embedding-4b --served-model-name sgar-embedding-4b \
  --host 127.0.0.1 --port 8001 --dtype bfloat16 \
  --gpu-memory-utilization 0.80 --max-model-len 32768
```

The client template points to
`http://127.0.0.1:8001/v1/embeddings` with API model ID `sgar-embedding-4b`.
For a remote service, update `runtime.api_endpoint_url` and, if necessary,
`runtime.api_model_id` in `sgar_mvp/config/embedding_release.json`. Keep the
model revision, dimension, instructions, and normalization settings unchanged.
The host client adds retrieval instructions. Size GPU memory for the configured
sequence length and service concurrency.

The framework sends `{"model": "sgar-embedding-4b", "input": ["..."]}` and expects
`data` entries with unique zero-based `index` values and 2,560-element `embedding`
arrays. Export the API key even for a local service.

## Tool services

The complete candidate list includes the three services below. These endpoints
must be reachable from tool containers; `127.0.0.1` inside a container does not
refer to the host.

| Environment variable | Required interface |
| --- | --- |
| `SEARXNG_BASE_URL` | SearXNG root URL, with JSON search enabled at `/search`. |
| `ZOTERO_TRANSLATION_SERVER_URL` | Translation Server root URL, accepting text identifiers at `/search`. |
| `HYPOTHESIS_API_URL` | Hypothesis API root, including `/api`, accepting annotation creation at `/annotations`. |
| `HYPOTHESIS_API_TOKEN` | Write-capable token for an isolated Hypothesis instance. |

For SearXNG and Zotero, the following starts separate services on the default
Docker bridge gateway. Use an administrator-approved bind address if your host
uses different networking:

```bash
export DOCKER_GATEWAY="$(docker network inspect bridge -f '{{(index .IPAM.Config 0).Gateway}}')"
mkdir -p .cache/services/searxng
python - <<'PY'
from pathlib import Path
import secrets
p = Path(".cache/services/searxng/settings.yml")
if not p.exists():
    p.write_text("use_default_settings: true\nsearch:\n  formats: [html, json]\n"
                 "server:\n  limiter: false\n  secret_key: " + secrets.token_hex(32) + "\n")
PY
docker run -d --name execorchestra-search \
  -p "${DOCKER_GATEWAY}:8888:8080" \
  -v "$PWD/.cache/services/searxng:/etc/searxng" \
  searxng/searxng@sha256:394bc18556af80cd1cd448daf5b69ead7f65d990912851a47ba1ec79c85fec44
docker run -d --name execorchestra-translation \
  -p "${DOCKER_GATEWAY}:1969:1969" zotero/translation-server:2.0.3
```

Set `SEARXNG_BASE_URL=http://<bridge-gateway>:8888` and
`ZOTERO_TRANSLATION_SERVER_URL=http://<bridge-gateway>:1969` in `.env`, replacing
`<bridge-gateway>` with the value above. Include that address in proxy bypass
lists. SearXNG also needs outbound access to its configured search engines.
See the [SearXNG deployment documentation](https://docs.searxng.org/admin/installation-docker.html)
and [Zotero Translation Server](https://github.com/zotero/translation-server)
for service administration.

Use an isolated [Hypothesis server](https://github.com/hypothesis/h/tree/v0.39.0)
and its token for annotation tools. The retained environment used server version
`v0.39.0`. Its upstream deployment includes a database, search backend, and worker;
those services and their state are not part of the framework repository.
The tool check creates an annotation; use a private test instance. This service
is required by the complete candidate pool.

## Network configuration

Framework requests use explicit routes:

| Setting | Applies to |
| --- | --- |
| `SGAR_MODEL_PROXY` | Model API traffic and the optional cold-image downloader. Leave empty only when these routes work directly or images are pre-pulled. |
| `SGAR_TOOL_HTTP_PROXY`, `SGAR_TOOL_HTTPS_PROXY` | Network-enabled tool containers. |
| `SGAR_TOOL_NO_PROXY` | Local/internal tool-service addresses bypassing those proxies. |
| `SGAR_DOCKER_PROXY` | TB task containers; use an HTTP CONNECT proxy reachable from the Docker bridge. |
| `SGAR_NO_PROXY` | TB container proxy exclusions. |
| `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` | Host downloads, image builds, and preparation tool subprocesses. |

Use container-reachable proxy addresses for tools and TB. Configure
`SGAR_DOCKER_PROXY` explicitly: the adapter's default is a bridge-gateway relay
on port 7894. Model clients use `SGAR_MODEL_PROXY`; embedding requests to loopback
or private IP literals bypass it.

Export `.env` before preparation and execution. Public-network tools require
`--network-policy declared` in the framework/GAIA launcher or `--network` in the
TB launcher; these flags do not override a task's own network restrictions.
