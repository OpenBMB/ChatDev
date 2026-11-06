# Migration verification

Use the `execorchestra` branch layout for a new server. Run project commands
from `ChatDev/execorchestra`; this document adds migration checks to the
[README installation path](../../README.md#quick-start).

## What this revision contains

- The Apptainer branch and its Docker-compatible default entrypoint.
- JSON pre-write validation using the accepted compiled schema while still
  enforcing explicit Planner constraints.
- Browser continuation, public-page challenge detection, external-discovery
  context forwarding, committed-delivery extraction and bounded proxy diagnostics.
- Planner `gpt-6.1-sol`, Profiler `gemini-3.8-flash`, Composer/adaptation
  `gpt-6-luna`, high reasoning and no model failover. Evaluation remains off.
- Qwen3-Embedding-4B revision `5cf2132abc99cad020ac570b19d031efec650f2b`,
  BF16, SDPA, 2,560 dimensions, last-token pooling and normalized output. The
  cluster Transformers service and its separate dependency list are included.

The experimental Planner handoff prompt, external evidence-repair/replan loop,
workstation model relay and experimental search relay are not default dependencies.

## Before moving

Clone the branch and record its commit identity:

```bash
git clone -b execorchestra --single-branch https://github.com/OpenBMB/ChatDev.git
cd ChatDev/execorchestra
git status --short
git rev-parse HEAD
python3.11 scripts/verify_contents.py
python3.11 -m scripts.migration_check --stage source
```

Record the exact commit and, if transferring an archive, its checksum.
The source check is offline. It does not use API keys or start containers,
embedding, browser or search services.

Transfer private configuration separately: gateway credentials/base URL,
embedding key, any required service credentials, and proxy configuration if
the new host needs it. Do not copy the old `.env` into Git. Environment paths
and service URLs must be reviewed for the target network. Python environments
are recreated on the new host; do not copy old virtual environments.

Weights, the matching tokenizer and container images can be copied separately
to avoid downloading them again. The source bundle contains neither weights
nor images. Preserve the model revision and verify image identity. Rebuild
readiness records and the resource index on the target host instead of treating
the old machine's preparation receipts as proof for the new host.

## Standard Linux server with Docker

Run from a clean checkout with Python 3.11. Docker must be usable by the current
user. A dedicated BF16-capable NVIDIA GPU is needed only if this host serves the
embedding model; the framework may use a separately hosted 4B endpoint.

```bash
conda create -n execorchestra python=3.11 -y
conda activate execorchestra
python -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
python -m scripts.prepare_release init
test -f .env || cp .env.example .env
```

Fill `.env` privately. Keep values shell-compatible, quoting them when needed.
Configure `sgar_mvp/config/embedding_release.json` with the target embedding
endpoint and matching tokenizer directory. Then export the settings:

```bash
set -a
source .env
set +a
```

[SERVICES.md](SERVICES.md) contains the weight/tokenizer download and explicit
Transformers service startup. Use `requirements-embedding.txt` in the separate
`execorchestra-embedding` environment when restoring that service. Start it only for
validation/task execution and stop it after use. On Slurm, do not set the
dedicated-server override; request a GPU allocation instead.

Complete the existing preparation stages while the needed services are alive:

```bash
docker build -f sgar_mvp/docker/Dockerfile.runtime -t sgar-runtime:rc1 .
python -m sgar_mvp.scripts.seal_rc1_runtime
python -m scripts.prepare_release health
python -m scripts.prepare_release control
python -m scripts.prepare_release tools
python -m scripts.prepare_release agents
python -m scripts.prepare_release readiness
python -m scripts.prepare_release index
python -m scripts.prepare_release check
python -m scripts.migration_check --stage configured --backend docker
```

The health/control/tool/agent stages make real external requests. The source
and configured migration checks do not. A configured check only checks local
preparation files and environment presence; it does not replace the integrity
and runtime identity checks in `prepare_release check`.

Full-pool readiness correctly stops for unavailable resources. For a separately
declared reduced demonstration, `readiness --allow-unavailable` records and
excludes unavailable candidates. Choose that scope explicitly and then build
its index; do not claim it is the complete 238-resource reproduction.

## First end-to-end smoke task

After preparation, run the existing task without a network requirement:

```bash
bash scripts/run.sh --query-file examples/task.txt \
  --public-input-root examples --run-dir runs/migration-smoke-001
```

Use a new run directory for every attempt. Inspect the terminal outcome,
`run_manifest.json`, `delivery_manifest.json` and committed answer. The task
must actually write and verify `answer.json` containing `{"sum":42}`. An API
probe, a generated plan, or an uncommitted file is not an end-to-end pass.
Record the exact failure stage if it does not deliver; keep the attempt before
retrying. The source bundle does not contain a pre-recorded successful answer.

## Slurm/Apptainer and deep research

[apptainer-deployment.md](apptainer-deployment.md) retains the alternative
runtime path. It requires the verified SIF, container-tools, an allocation and
fresh runtime lock/readiness evidence; it cannot use Docker image IDs as SIF
identity. [deep-research-deployment.md](deep-research-deployment.md) documents
the optional browser/search profile and input/scoring separation.

For research-profile preparation, use a fresh clone with `.research-workspace`,
apply `python -m scripts.prepare_research_profile --apply` before index creation,
and commit the generated resource/configuration changes before live preparation.
The profile is provisional until real resource checks pass. Keep browser and
search services alive for both online resource checks and actual research tasks.
The current automatic service wrappers require Slurm. A dedicated Docker host
needs separately configured browser/search endpoints reachable by its tool
containers; host `127.0.0.1` is not a container-reachable service address.

## Validation boundary

This revision can be checked and transferred independently of the old working
tree. Successful installation, container execution, live model/embedding probes,
and a committed correct smoke result are all required on the new server before
calling migration complete. Short research tasks and answer/source inspection
come after that. README presentation and progress-output redesign are deferred.
