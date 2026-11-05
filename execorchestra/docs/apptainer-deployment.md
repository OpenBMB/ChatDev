# Apptainer deployment branch

Development branch: `codex/cluster-apptainer`.
Baseline: `main` at `8ea74254d03d10c556cc5608667e501805f16555`.

This branch adds an opt-in execution substrate. Existing Docker executors and
their default entrypoints remain unchanged. Changes are developed in a separate
checkout; neither the source archive nor the original working checkout is used
as the development directory. No merge or public push is implied.

## Execution boundary

`ApptainerExecutionSubstrate` implements the transport used by the existing
external execution boundary. Resource wrapper staging, declared dependency
checks, typed dispatch and artifact publication remain framework operations.
The container contains the original tool image, identified by its SIF SHA-256.

Each run must have a new state directory. Only its `app` and `task-tmp`
subdirectories are writable container mounts. File operations execute in the
container so task symlinks are never followed by host-side file reads/writes.
The source tree, model gateway credentials, and other users' directories are not
mounted. Output is bounded and timed-out process groups are stopped.

Offline calls use a separate network namespace. A network-enabled call requires
both the operator's `declared` policy and the resource's network requirement.
These calls use the compute node's network, not a Docker bridge. Tool proxy and
service variables are explicitly selected; ambient model keys and container
runtime overrides are not inherited. This is user-space containment, not a VM
or a promise of identical Docker isolation. Slurm supplies resource limits.

The configuration follows the official Apptainer documentation for
[bind mounts](https://apptainer.org/docs/user/1.4/bind_paths_and_mounts.html) and
[environment handling](https://apptainer.org/docs/user/1.4/environment_and_metadata.html).
The host helper PATH must include both the container-tools `bin` and `sbin`
directories, including `squashfuse_ll` and `fusermount3`.

## Contract check

Run inside an allocated Slurm job, from the framework directory:

```bash
python -m scripts.run_apptainer \
  --mode contract \
  --image /path/to/sgar-runtime-rc1.sif \
  --image-sha256 VERIFIED_SIF_SHA256 \
  --apptainer /path/to/apptainer \
  --tools-prefix /path/to/container-tools \
  --run-id unique-contract-id \
  --output-dir runs/unique-contract-id
```

This runs a real resource wrapper, publishes its artifact and verifies that a
dependent resource consumes it. It makes no model or embedding API calls and
does not claim task-solving success. Unit regressions can be run with
`python -m unittest discover -s tests -p 'test_apptainer_runtime.py'`.

## Pipeline integration

`--mode pipeline --query '...'` uses the same `run_pipeline` and existing
readiness, model-health, control-probe and retrieval-index gates. Nothing is
marked ready merely because the container starts. The default network policy
is `disabled`; use `--network-policy declared` only for the intended online task.
Explicit tool settings are passed by name, e.g. `--tool-env SEARXNG_BASE_URL`.
Load private credentials outside version control before starting the process.

Input-file staging is exposed through `--query-file`, `--input NAME=PATH` and
`--input-root PATH` using the same immutable public-input contract. Generated-code
dependency provisioning still needs parity verification with the Docker
runtime; this transport does not silently install missing task packages.

## Fresh tool and service evidence

`python -m scripts.smoke_tools_apptainer --help` runs the existing fixtures,
argument builders, source checks and success classifier in the pinned SIF.
Every row includes the SIF digest and implementation hash. Reports preserve
failures. Task-specific browser/compiler images remain a separate prerequisite.
An empty selection fails rather than producing a vacuous pass.

`python -m scripts.with_web_services --help` wraps a command with pinned
SearXNG and Zotero containers in the allocated job. Supply the preserved
SearXNG configuration as a private file. Search engine settings are retained;
the cluster proxy and dynamically allocated loopback ports replace the old
Docker network addresses. Zotero starts its installed server without updating
translators. Both services are stopped when the command exits or times out.
No gateway key is passed to either service. Startup alone is not a functional
check: run the search and DOI wrappers while the services are alive.

For readiness, write verified combined tool evidence to the existing local
`tool_smoke_latest.json` location and an ignored
`sgar_mvp/config/apptainer_runtime_lock.json` containing `runtime_backend`,
`runtime_image_sha256`, and `source_oci_digest`. Then run:

```bash
python -m scripts.prepare_release readiness --runtime-backend apptainer
```

Docker remains the default. Apptainer evidence cannot reuse Docker image IDs,
and mismatched per-resource SIF digests are rejected. The existing strict
preparation gate preserves the configured candidate pool when resources are
unavailable. Do not manufacture ready rows or use `--allow-unavailable` to
claim a full-pool reproduction. Index refresh and a complete task are later
stages, after the required configuration and availability decisions are made.

Three pre-existing wrappers (CORS headers, HTTP security headers, DNS latency)
actually perform network requests while their manifests declared offline use.
This branch corrects only their `network_required` flags, consistently in the
individual and combined catalogs. Their implementations and interfaces are
unchanged. All other resource definitions remain identical to the baseline.

## Verified checkpoint (2026-10-30)

On the target A800 compute cluster, job `267052` passed all seven formal
resource/artifact contract checks. Job `267063` passed eight unit boundary
checks and six real-container integration checks, including UTF-8/binary file
identity, hidden host files and ambient credentials, a read-only image,
symlink containment, offline/declared networking, and timed-out child cleanup.
Both allocations completed and released their GPUs. No model API requests were
made by these checks, and complete framework task execution is still pending.

The existing production-contract fixture needed the current
`authorized_materials` descriptors for its downstream artifact. The fixture
now supplies the recorded artifact identity; production validators are unchanged.

The next checks verified all five configured control roles (`267115`) and all
20 Agent wrappers (`267137`). Ten of the 12 selected model resources passed
every declared capability probe. The other two remain unavailable to strict
preparation; a failed probe is not replaced with a synthetic ready record.

Across the original fixtures, 127 of 133 tools passed actual execution. Three
require task-specific images; dictionary access, exchange-rate authentication,
and the Hypothesis service remain separate availability issues in snapshot
`267214`. That strict preparation check failed as expected and verified that
the configured 238-resource pool and effective catalogs were unchanged.

Job `267138` passed eight unit and seven real-container boundary checks,
including the new task-owned HOME/cache needed by Go. Job `267174` passed
six readiness regression tests, rechecked the three corrected network tools,
and verified all 102 declared Python package versions in the original image.
Job `267155` verified real SearXNG search and Zotero DOI translation, followed
by service shutdown and port release. These are component results; index
construction and complete task execution have not yet been verified.
