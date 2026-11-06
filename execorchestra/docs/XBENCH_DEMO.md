# XBench web research example

XBench DeepSearch-2510 case 157 exercises search, page reading, and answer
delivery. Run this command from `ExecOrchestra/execorchestra` once the framework
environment, Docker runtime image, model gateway, and embedding service are
ready. The command handles the resource preparation needed for this example.
[Quick Start](../../README.md#quick-start)

```bash
bash scripts/run_xbench_demo.sh
```

The command loads the project's `.env`, prepares the case locally from the
pinned dataset, and starts temporary SearXNG and Chromium services on the local
Docker bridge. It checks for search results and browser readiness before
starting the framework. The model gateway and embedding endpoint come from
the Quick Start setup. The example supplies its own search and browser
addresses and browser token. [Pinned dataset](https://github.com/xbench-ai/xbench-evals/blob/17c562192cc7e62215bfb98b65e9f8806fb95504/data/DeepSearch-2510.csv)

If the prepared index already includes both web tools, the example reuses it.
Otherwise, it prepares a separate checkout of the current commit and builds
the index there. This step makes live API calls and may incur charges. The
first run downloads or builds the service images. Sites and search engines
must be reachable from the Docker host. On networks that require a tool proxy,
use the same optional proxy settings as in the framework. [Network settings](SERVICES.md#network-configuration)

The command prints a new directory under `runs/xbench-157-*/`. It contains
the service logs and, when applicable, the preparation report. Open
`run/progress.log` for the trace, `run/run_manifest.json` for completion, and
`run/delivery_manifest.json` for the delivered file location. The temporary
service containers stop when the command exits. Keep the decoded question
and its run outputs local. Benchmark grading is a separate step.
