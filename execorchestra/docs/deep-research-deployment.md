# Deep-research deployment on an allocated cluster node

The Docker distribution already includes the web research profile. Use the [QuickStart](QUICKSTART.md) for Docker. The instructions below describe the additional browser and search services and the alternative Apptainer deployment on an allocated cluster node.

## Resource profile

The supplied candidate list includes 10 models, 38 tools, 4 skills, and 5 agents. A fresh Docker checkout does not need to regenerate this list. Prepare the browser and search endpoints before checking the web tools. On an Apptainer cluster, select the Apptainer backend for preparation, build the index and run the release checks. Each index belongs to the pool and embedding configuration that created it.

The four new Skills cover query decomposition, webpage navigation, source
verification and evidence synthesis. Their referenced tool IDs belong to this
profile. They are instructions, not hidden network executors. The existing
research/search agents consume explicit supplied context; browser and search
access remains in separately bound tool operations. Optional suggestions in
the retained upstream Agent cards are not promises of autonomous browsing.

The browser resource is `tool.browser_read_page.v1`. Its client runs inside
the existing tool SIF; Playwright runs in a separate job-scoped environment.
The local HTTP endpoint binds to loopback and uses a generated token. It
receives no model-gateway credentials. Only public HTTP(S) pages are accepted.
Authentication walls, CAPTCHAs and page failures are reported, not bypassed.

Each result contains title, requested/final URL, access time, snapshot ID,
visible text and followable links. The tool emits less than 14,000 UTF-8 bytes
per call. Follow `next_text_offset` and `next_link_offset` to continue reading
the same cached snapshot. A 250,000-character source cap is explicitly marked;
this cap and the 40-page cache mean this is not unlimited browser storage.
Text extraction follows rendered DOM innerText, including navigation text;
the existing Trafilatura tool remains available for main-body extraction.

Free exchange-rate conversion is not advertised. The original paid
exchangerate conversion resource remains excluded. Existing Frankfurter rates
and deterministic calculation tools are available for task-relevant public
rate lookups; respect each source's date, units and availability.

## Runtime and data separation

Use `scripts.with_web_services` and `scripts.with_research_browser` around the
framework child command inside Slurm. Browser startup requires an allocation.
The wrappers stop child processes and services at exit. Keep model/proxy keys
in private deployment configuration, not this repository. A new commercial
search or browser key is not required.

`scripts.download_research_data --output PRIVATE_DIRECTORY` resolves and records
official dataset revisions. XBench plaintext stays private, consistent with
the dataset publisher's instructions. `scripts.research_benchmark prepare`
creates separate `solver/tasks.jsonl` and `evaluation/references.jsonl` files;
the solver projection excludes answers, reference steps and golden paths.

The `run` command accepts only the solver projection, starts one trial per
selected task, resets browser state between tasks, retains failures, and saves
predictions and framework cost summaries. Run identity binds input/config/pool
hashes, runtime image and limits. Resume keeps terminal attempts and refuses
unidentified partial attempts or changed identities. Use a new output folder
for another trial; never select the best retry silently.

`scripts.run_apptainer` also accepts `--query-file`, `--input NAME=PATH` and
`--input-root DIRECTORY` using the existing immutable public-input contract.
Input declarations are snapshotted before model calls. This does not make
arbitrary generated-code dependencies available: isolated dynamic dependency
installation remains a separate runtime capability to validate when needed.

## Evaluation scope

XBench DeepSearch-2510 uses open-web research. The current WebWalker runner
starts from `root_url` but also exposes the general research pool: its recorded
protocol is **open_web_research_v1**, not a technically enforced site-only
WebWalker reproduction. For a site-only experiment, separately constrain all
network-capable tools and the browser; a browser-only hostname restriction is
insufficient when shell/HTTP tools can still access other sites.

The `score` command requires an explicit `--judge-model`, reuses the existing
gateway, and never shares reference answers with the solver process. It uses
an adapted reference-answer grading prompt and records that protocol and model.
It does not claim parity with the original XBench Gemini-2.0 grader or the
WebWalker LangChain evaluator. Judge usage is stored separately; its cost is
null until a matching billing rate is supplied. Malformed/error judge results
are not silently converted to task failures; an incomplete grading run has no
overall accuracy. Framework completion is not itself benchmark correctness.

## Sources

- https://github.com/xbench-ai/xbench-evals
- https://github.com/Alibaba-NLP/DeepResearch/tree/main/WebAgent/WebWalker
- https://playwright.dev/python/docs/browsers
- https://playwright.dev/python/docs/api/class-browser

Component acceptance covers English/Chinese/search-type samples, rendered
page access, following an actual returned link, chunk continuation and rejected
private URLs. It is not a benchmark score or proof of complete search coverage.
