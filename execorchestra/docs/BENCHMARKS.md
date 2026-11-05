# Benchmark invocation

Run these commands after completing the preparation sequence in README.md.
The distributed candidate list is the 57-resource research profile. For comparisons with published results, match the experimental pool, model configuration, and evaluator. Obtain benchmark datasets separately from their official distributions.

## Terminal-Bench 2.1

### Dataset and container preparation

The reference input is an 89-task export from
[Harbor Hub](https://hub.harborframework.com/datasets/terminal-bench/terminal-bench-2-1/latest),
obtained with Harbor 0.23.0. Install that downloader in a separate Python 3.12+
environment; the framework itself continues to use Python 3.11:

```bash
python3.12 -m venv .cache/harbor-env
.cache/harbor-env/bin/python -m pip install harbor==0.23.0
.cache/harbor-env/bin/harbor auth login
.cache/harbor-env/bin/harbor download terminal-bench/terminal-bench-2-1 --export -o benchmarks
export TB_TASK_ROOT="$PWD/benchmarks/terminal-bench-2-1"
```

`TB_TASK_ROOT` must directly contain the task directories, each with `task.toml`,
`instruction.md`, `environment/`, and `tests/test.sh`. The adapter enforces the
reference tree SHA-256:

```text
c31db162da898b59e8f5d827715a65378ca999e4df0dc052fe2a18f4241e0c0b
```

`configs/tb21_dataset_files.json` lists the reference file hashes. The recorded
export used `@latest`; use a matching snapshot if the current download fails
the adapter's tree-hash check.

Inspect the inventory and pre-pull the exact images declared by the tasks:

```bash
python -m sgar_mvp.benchmarks.terminalbench21.runner inventory --task-root "$TB_TASK_ROOT"
python - <<'PY'
import os, subprocess, tomllib
from pathlib import Path
root = Path(os.environ["TB_TASK_ROOT"])
images = {tomllib.loads(p.read_text())["environment"]["docker_image"]
          for p in root.glob("*/task.toml")}
for image in sorted(images):
    subprocess.run(["docker", "pull", image], check=True)
PY
```

Docker registry access is needed for this step. Pre-pulling avoids the optional
runtime downloader, which requires `skopeo` and `SGAR_MODEL_PROXY` for missing
registry-qualified images. Configure `SGAR_DOCKER_PROXY` as described in
[SERVICES.md](SERVICES.md) before running tasks with internet access. Images,
CPU/RAM limits, GPU requirements, and verifier timeouts come from `task.toml`.

### Run

For one task, set `TASK_ID` to a directory name in `TB_TASK_ROOT`:

```bash
python -m sgar_mvp.benchmarks.terminalbench21.runner \
  --task-root "$TB_TASK_ROOT" --task-id "$TASK_ID" \
  --config "$PWD/sgar_mvp/config.json" --output-root "$PWD/runs/tb21" --network
```

Run the complete 89-task benchmark with a new output directory:

```bash
python -m sgar_mvp.benchmarks.terminalbench21.runner \
  --task-root "$TB_TASK_ROOT" --task-id all \
  --config "$PWD/sgar_mvp/config.json" --output-root "$PWD/runs/tb21-full" --network
```

The adapter uses task-defined images and deadlines, then runs the executable
verifier. The commands above retain those defaults.

## GAIA

Obtain GAIA's 2023 validation split through its
[official distribution](https://huggingface.co/datasets/gaia-benchmark/GAIA).
Accept its access terms and use your own Hugging Face token.

The included GAIA harness separates public task inputs from evaluator answers.
The reference dataset revision is `682dd723ee1e1697e00360edccf2366dc8418dd9`.
Download only the validation material into private local storage:

```bash
export GAIA_REVISION=682dd723ee1e1697e00360edccf2366dc8418dd9
hf auth login
python - <<'PY'
import os
from huggingface_hub import snapshot_download
snapshot_download("gaia-benchmark/GAIA", repo_type="dataset",
    revision=os.environ["GAIA_REVISION"], local_dir="data/gaia-source",
    allow_patterns=["2023/validation/*"])
PY
export GAIA_SOURCE="$PWD/data/gaia-source/2023/validation"
```

The directory must contain `metadata.jsonl` or
`metadata.parquet` and the referenced attachments; Parquet input additionally
requires `pyarrow`.

```bash
python -m evaluation.gaia.freeze_dataset \
  --source "$GAIA_SOURCE" --output data/gaia-frozen --revision "$GAIA_REVISION"
python -m scripts.freeze_gaia_manifest --dataset-root data/gaia-frozen
python -m evaluation.gaia.run_validation \
  --dataset-root data/gaia-frozen --sgar-root "$PWD" \
  --experiment-manifest sgar_mvp/runtime_state/gaia_manifest.json \
  --config "$PWD/sgar_mvp/config.json" --output-root runs/gaia \
  --task-timeout-sec 3600 --network-policy declared
```

Freeze the manifest after preparation and source commit. It binds code, models,
resources, index, scorer, and dataset. The command runs all 165 validation tasks
with a 3,600-second agent-phase cap. For one task, add `--task-id ID --max-tasks 1`.
The included scorer uses GAIA/AOrchestra scoring rules.

## Outputs and accounting

The launchers process tasks sequentially within each benchmark. For parallel
execution, assign disjoint tasks to separate processes and output directories,
using the same prepared index. Size concurrency to provider and container limits.

| Output | Contents |
| --- | --- |
| GAIA `validation_results.json` | Per-task scores and aggregate accuracy, cost, calls, and timing. |
| GAIA task `benchmark_result.json`, `trial_record.json` | Official score, delivery status, timeout/failure class, and phase durations. |
| TB `batch_result.json` | Per-task native results and success/failure counts. |
| TB task `result.json` | Verifier reward, verified success, delivery status, timing, and native-run location. |
| Native `cost_summary.json`, `execution_summary.json` | Model usage/cost completeness and observed resource execution. |

SR uses the complete task count (165/89). Cost/Trial divides total trial cost by
that count; CPVS divides it by successful tasks and is undefined with no successes.
Include failed and timed-out trial costs. Costs and calls cover control,
execution, and recovery, with reported cache usage priced by the supplied policy.
Check usage completeness; keep agent-phase and end-to-end time separate.

Optional semantic review is in `sgar_mvp/benchmarks/answer_validation.py`.
It records assisted results and review cost separately from official scoring.
