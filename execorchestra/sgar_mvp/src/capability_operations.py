"""Canonical capability-operation registry for Tool routing.

Execution ``OperationKind`` answers *how* a selected resource runs.  This
module answers *what* a Tool does.  Tool manifests register their operations
through ``capability.core_primitives`` so the registry remains data-driven.
"""

from __future__ import annotations

import re
from typing import Any, Dict, FrozenSet

EXACT_CAPABILITY_OPERATIONS = frozenset(
    {
        "convert_json_to_yaml",
        "convert_yaml_to_json",
        "convert_json_to_toml",
        "convert_xml_to_json",
        "project_csv_columns",
        "infer_json_schema",
        "parse_sql_ddl",
        "solve_symbolic",
        "detect_language",
        "transpile_sql_dialect",
        "audit_bandit",
        "scan_secrets",
        "audit_dependencies",
        "compile_coq_source",
        "compile_latex_document",
        "browser_capture",
        "search_web",
        "fetch_web_resource",
        "execute_shell_commands",
        "extract_zip_archive",
        "extract_complete_pdf_text_range",
    }
)

CAPABILITY_TO_EXECUTION_OPERATION = {
    "read_text_file": "read_file",
    "load_file_contents": "read_file",
    "inspect_known_file": "read_file",
    "write_complete_text_file": "write_file",
    "create_text_artifact": "write_file",
    "overwrite_file_contents": "write_file",
    "convert_json_to_yaml": "convert_format",
    "convert_yaml_to_json": "convert_format",
    "convert_json_to_toml": "convert_format",
    "convert_xml_to_json": "convert_format",
    "project_csv_columns": "transform_data",
    "infer_json_schema": "parse_data",
    "parse_sql_ddl": "parse_data",
    "solve_symbolic": "compute_math",
    "detect_language": "analyze_text",
    "transpile_sql_dialect": "convert_format",
    "audit_bandit": "audit_security",
    "scan_secrets": "audit_security",
    "audit_dependencies": "audit_security",
    "compile_coq_source": "run_tool",
    "compile_latex_document": "run_tool",
    "browser_capture": "run_tool",
    "search_web": "run_tool",
    "fetch_web_resource": "run_tool",
    "execute_shell_commands": "run_tool",
    "extract_zip_archive": "run_tool",
    "extract_complete_pdf_text_range": "run_tool",
}

# The only canonical source for exact Tool capabilities.  A Tool manifest may
# advertise one of these semantic operations; the orchestrator executes it
# through the mapped OperationKind enum below.
CAPABILITY_OPERATION_REGISTRY = {
    operation: {"execution_operation_kind": execution_kind, "resource_fragments": ()}
    for operation, execution_kind in CAPABILITY_TO_EXECUTION_OPERATION.items()
}
for _fragment, _operation in {
    "tool_json_to_yaml": "convert_json_to_yaml",
    "tool_yaml_to_json": "convert_yaml_to_json",
    "tool_json_to_toml": "convert_json_to_toml",
    "tool_xml_to_json": "convert_xml_to_json",
    "tool_csv_column_filter": "project_csv_columns",
    "tool_lib_genson_schema": "infer_json_schema",
    "tool_sql_ddl_to_json_schema": "parse_sql_ddl",
    "tool_lib_sympy_solve": "solve_symbolic",
    "tool_lib_langdetect_detect": "detect_language",
    "tool_lib_sqlglot_transpile": "transpile_sql_dialect",
}.items():
    CAPABILITY_OPERATION_REGISTRY[_operation]["resource_fragments"] = (_fragment,)


def validate_tool_manifest_operations(manifest: Dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """Validate explicit manifest capability declarations.

    Legacy manifests use ``core_primitives`` as descriptive metadata and are
    compiled by ``tool_allowed_operation_kinds``.  New manifests should use
    ``capability.operation_kinds``; those declarations are strict and must be
    present in the canonical registry.
    """
    capability = manifest.get("capability", {}) if isinstance(manifest, dict) else {}
    if not isinstance(capability, dict):
        return False, ("capability must be an object",)
    declared = capability.get("operation_kinds")
    if declared is None:
        return True, ()
    if isinstance(declared, str):
        declared = [declared]
    if not isinstance(declared, (list, tuple, set)):
        return False, ("capability.operation_kinds must be a list",)
    normalized = tuple(normalize_capability_operation(item) for item in declared)
    unknown = tuple(sorted(item for item in normalized if item not in CAPABILITY_OPERATION_REGISTRY))
    return not unknown, unknown


def execution_operation_kind_for_tool(manifest: Dict[str, Any]) -> str:
    """Return the executable OperationKind for a Tool's exact capability."""
    allowed = tool_allowed_operation_kinds(manifest)
    mapped = {
        CAPABILITY_TO_EXECUTION_OPERATION.get(operation, operation)
        for operation in allowed
    }
    return sorted(mapped)[0] if len(mapped) == 1 else "run_tool"


def normalize_capability_operation(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower())
    normalized = normalized.strip("_")
    # Runtime manifests historically called these transport-level operations
    # ``network_search``/``network_read``. Keep that vocabulary compatible
    # with the semantic registry so routing can match the declared ability
    # independently of the wrapper runtime.
    return {
        "network_search": "search_web",
        "web_search": "search_web",
        "network_read": "fetch_web_resource",
        "web_fetch": "fetch_web_resource",
    }.get(normalized, normalized)


def manifest_capability_operations(manifest: Dict[str, Any]) -> FrozenSet[str]:
    capability = manifest.get("capability", {}) if isinstance(manifest, dict) else {}
    if not isinstance(capability, dict):
        return frozenset()
    constraint = manifest.get("constraint", {}) if isinstance(manifest, dict) else {}
    constraint = constraint if isinstance(constraint, dict) else {}
    explicit = (
        capability.get("operation_kinds")
        or constraint.get("operation_kinds")
        or capability.get("core_primitives")
        or []
    )
    if isinstance(explicit, str):
        explicit = [explicit]
    return frozenset(
        operation
        for item in explicit
        if (operation := normalize_capability_operation(item))
    )


def _semantic_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        values: list[str] = []
        for key in sorted(value):
            values.extend(_semantic_values(value[key]))
        return values
    if isinstance(value, (list, tuple)):
        values = []
        for item in value:
            values.extend(_semantic_values(item))
        return values
    if isinstance(value, (set, frozenset)):
        values = []
        for item in sorted(value, key=str):
            values.extend(_semantic_values(item))
        return values
    if value is None:
        return []
    return [str(value)]


def _tool_semantic_text(manifest: Dict[str, Any]) -> str:
    """Collect positive manifest evidence without treating exclusions as capabilities."""
    capability = manifest.get("capability", {})
    routing = manifest.get("routing", {})
    constraint = manifest.get("constraint", {})
    execution = manifest.get("execution", {})
    io_contract = manifest.get("io", {})

    evidence: list[Any] = [manifest.get("resource_id", "")]
    if isinstance(routing, dict):
        evidence.extend((routing.get("family", ""), routing.get("intent_tags", [])))
    if isinstance(capability, dict):
        evidence.extend(
            capability.get(field, "")
            for field in (
                "core_primitives",
                "summary",
                "description",
                "problem_space",
                "domain_tags",
            )
        )
    if isinstance(constraint, dict):
        evidence.extend(
            constraint.get(field, "")
            for field in (
                "io_signature",
                "accepted_inputs",
                "output_shape",
                "artifact_input",
                "artifact_output",
                "env_requirements",
            )
        )
    if isinstance(execution, dict):
        evidence.append(execution.get("runtime", ""))
    evidence.extend(
        (
            io_contract,
            manifest.get("input_contract", []),
            manifest.get("output_contract", {}),
        )
    )

    normalized = " ".join(_semantic_values(evidence)).lower()
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def _tool_identity_text(manifest: Dict[str, Any]) -> str:
    """Collect high-signal identity fields that do not describe exclusions."""
    capability = manifest.get("capability", {})
    routing = manifest.get("routing", {})
    evidence: list[Any] = [manifest.get("resource_id", "")]
    if isinstance(routing, dict):
        evidence.extend((routing.get("family", ""), routing.get("intent_tags", [])))
    if isinstance(capability, dict):
        evidence.extend(
            capability.get(field, "")
            for field in ("core_primitives", "summary", "domain_tags")
        )
    normalized = " ".join(_semantic_values(evidence)).lower()
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def _has_any(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def tool_allowed_operation_kinds(manifest: Dict[str, Any]) -> FrozenSet[str]:
    """Classify an active Tool manifest by its general semantic operation.

    Rules are intentionally ordered from narrow semantic families to broad
    fallbacks.  Runtime and file-shaped inputs are supporting evidence only;
    they never make a document extractor a filesystem reader.
    """
    text = _tool_semantic_text(manifest if isinstance(manifest, dict) else {})
    identity = _tool_identity_text(manifest if isinstance(manifest, dict) else {})
    resource_id = normalize_capability_operation(
        manifest.get("resource_id", "") if isinstance(manifest, dict) else ""
    )

    # Preserve the concrete operation identity before broad families such as
    # ``convert_format`` and ``parse_data`` are considered.  These IDs are
    # deliberately source/target-specific so adjacent Tools cannot compete
    # for the same task merely because they share a transport format.
    for exact_operation, spec in CAPABILITY_OPERATION_REGISTRY.items():
        if any(fragment in resource_id for fragment in spec["resource_fragments"]):
            return frozenset({exact_operation})

    if _has_any(identity, "bandit security", "bandit scan", "bandit audit"):
        return frozenset({"audit_bandit"})
    if _has_any(identity, "detect secrets", "secret scan", "secret detection"):
        return frozenset({"scan_secrets"})
    if _has_any(identity, "dependency cve", "dependency vulnerability", "dependency audit"):
        return frozenset({"audit_dependencies"})

    # New manifests may declare a source/target-specific capability directly.
    # Keep those values authoritative; broad execution OperationKinds such as
    # ``convert_format`` are retained only for legacy manifests below.
    declared_operations = manifest_capability_operations(manifest)
    exact_declared = frozenset(
        operation
        for operation in declared_operations
        if operation in CAPABILITY_OPERATION_REGISTRY
    )
    if exact_declared:
        return exact_declared

    # Security scanners and auditors are more specific than generic code checks.
    if _has_any(
        identity,
        "bandit security",
        "security audit",
        "security header",
        "dependency cve",
        "known vulnerability",
        "pip audit",
        "npm audit",
        "detect secrets",
        "secret scan",
        "cors header presence probe",
    ):
        return frozenset({"audit_security"})

    # Test execution must win over generic script/process execution.
    if _has_any(
        identity,
        "test runner",
        "test execution",
        "execute pytest",
        "run pytest",
        "run cargo test",
        "run recursive go tests",
        "run default jest suite",
        "execute npm test",
        "execute vitest",
    ):
        return frozenset({"run_tests"})

    # Format checkers are format semantics even when they run in check-only mode.
    if _has_any(
        identity,
        "black format",
        "clang format",
        "gofmt",
        "go fmt",
        "rustfmt",
        "format compliance",
        "format check only",
    ):
        return frozenset({"format_code"})

    if _has_any(
        identity,
        "flake8",
        "eslint",
        "ruff lint",
        "ruff check",
        "shellcheck",
        "stylelint",
        "pyflakes",
        "gitlint",
        "lint code",
        "lint python",
        "lint javascript",
    ):
        return frozenset({"lint_code"})

    if _has_any(
        identity,
        "cyclomatic complexity",
        "dead code candidate",
        "static analyzer",
        "static analysis",
        "source line analysis",
        "source line reporting",
        "typescript compiler diagnostics",
        "tsc no emit",
    ):
        return frozenset({"analyze_code"})

    # Document metadata inspection is narrower than document text extraction.
    if _has_any(identity, "pdf page and metadata inspection", "metadata preview"):
        return frozenset({"inspect_metadata"})

    # Document semantics precede generic conversion and file handling.
    if _has_any(
        identity,
        "pdf text preview extraction",
        "extract page text",
        "docx basic paragraph",
        "extract docx",
        "pptx slide text",
        "extract slide",
        "xlsx all sheets",
        "extract every worksheet",
        "local html css text extraction",
        "extract text from local html",
    ):
        return frozenset({"extract_document"})

    # Query languages and structural parsers win over format-looking outputs.
    if _has_any(
        identity,
        "jq filter",
        "jq query",
        "xpath query",
        "evaluate single lxml xpath",
    ):
        return frozenset({"query_data"})

    if _has_any(
        identity,
        "date expression parsing",
        "parse one natural language date",
        "phone number parsing",
        "parse regional phone",
        "junit xml report summary",
        "parse junit xml",
        "sql ddl create table structural summary",
        "parse sql ddl",
        "parse local yaml",
    ):
        return frozenset({"parse_data"})

    if _has_any(
        identity,
        "format conversion",
        "text conversion",
        "to yaml",
        "to toml",
        "to json",
        "to markdown",
        "to html",
        "sql dialect transpilation",
        "transpile sql",
        "tablib export preview",
        "markdown rendering",
        "syntax highlight html",
    ):
        return frozenset({"convert_format"})

    if _has_any(
        identity,
        "schema validation",
        "validate instance against schema",
        "validator by name",
        "graphql sdl schema build",
        "structurally report success",
    ):
        return frozenset({"validate_artifact"})

    if _has_any(
        identity,
        "genson schema",
        "infer json schema",
        "schema from one json",
        "single sample json schema",
        "infer schema from one json",
    ):
        return frozenset({"parse_data"})

    if _has_any(
        identity,
        "csv column projection",
        "project named csv columns",
        "csv mean aggregation",
        "serialize pivot csv",
        "html security sanitization",
        "sanitize html",
        "template rendering",
        "render template variables",
        "compute sha256 digest",
        "schema inference",
        "infer schema from sample",
        "data transformation",
        "normalize record fields",
        "normalize structured records",
    ):
        return frozenset({"transform_data"})

    if _has_any(
        identity,
        "descriptive statistics",
        "pandas describe",
        "process rss measurement",
        "memory metric",
        "system memory point in time snapshot",
        "virtual memory snapshot",
    ):
        return frozenset({"analyze_data"})

    if _has_any(
        identity,
        "language detection",
        "detect language candidates",
        "encoding inference",
        "infer character encoding",
        "semantic word association",
    ):
        return frozenset({"analyze_text"})

    if _has_any(
        identity,
        "symbolic solving",
        "sympy",
        "matrix linalg",
        "numpy linalg",
        "physical unit conversion",
        "pint units",
        "planar geometry calculation",
        "wkt geometry",
        "graph centrality analysis",
        "networkx",
    ):
        return frozenset({"compute_math"})

    if _has_any(
        identity,
        "qr generation",
        "generate qr",
        "image generation",
        "generate image",
        "generate media",
    ):
        return frozenset({"generate_media"})

    # Git-family operations classify by semantic action, independent of runtime.
    git_semantics = resource_id.startswith("tool_mcp_git_") or _has_any(
        identity, " git ", "git read only", "git history", "git branch", "git index"
    )
    if git_semantics:
        if _has_any(
            identity,
            "stage selected paths",
            "commit staged changes",
            "create named branch",
            "git history mutation",
            "git branch mutation",
            "git index management",
        ):
            return frozenset({"mutate_version_control"})
        return frozenset({"inspect_version_control"})

    # MCP filesystem tools classify by action, not by their mcp_server runtime.
    filesystem_semantics = resource_id.startswith("tool_mcp_fs_") or _has_any(
        identity, "filesystem content", "filesystem discovery", "filesystem metadata", "filesystem mutation"
    )
    if filesystem_semantics:
        if _has_any(identity, "create directory", "create parent folder"):
            return frozenset({"create_directory"})
        if _has_any(identity, "move file", "rename file", "relocate path"):
            return frozenset({"move_path"})
        if _has_any(identity, "edit existing file", "replace text fragment"):
            return frozenset({"edit_file"})
        if _has_any(identity, "write complete text file", "overwrite file contents"):
            return frozenset({"write_file"})
        if _has_any(identity, "search files by pattern", "find matching paths", "find matching content"):
            return frozenset({"search_files"})
        if _has_any(identity, "inspect path metadata", "filesystem attributes"):
            return frozenset({"inspect_metadata"})
        if _has_any(
            identity,
            "list immediate directory entries",
            "recursive directory traversal",
            "directory tree generation",
        ):
            return frozenset({"list_directory"})
        if _has_any(identity, "read text file", "read multiple text files", "load file contents"):
            return frozenset({"read_file"})

    if _has_any(
        identity,
        "academic preprint search",
        "clinical trial registry search",
        "crossref bibliographic work search",
        "pubmed biomedical search",
        "search arxiv",
        "search clinicaltrials",
        "search crossref",
        "search pubmed",
    ):
        return frozenset({"search_knowledge"})

    if _has_any(
        identity,
        "searxng",
        "self hosted web search",
        "public web search",
        "ranked web sources",
        "metasearch",
    ):
        return frozenset({"search_web"})

    if _has_any(
        identity,
        "bounded http request",
        "known public url",
        "public http url",
        "httpx",
    ):
        return frozenset({"fetch_web_resource"})

    if _has_any(identity, "browsertrix", "browser web evidence capture", "web archive"):
        return frozenset({"browser_capture"})

    if _has_any(
        identity,
        "dns record resolution",
        "resolve dns",
        "dns single query resolution",
        "ip address geolocation",
        "geolocate ip",
    ):
        return frozenset({"resolve_network"})

    if _has_any(
        identity,
        "current weather",
        "latest ecb fx rate",
        "spot currency",
        "spot price",
        "live iss",
        "current iss",
        "live aircraft",
        "recent usgs earthquakes",
        "recent earthquake",
    ):
        return frozenset({"fetch_live_data"})

    if _has_any(
        identity,
        "definition lookup",
        "reference lookup",
        "reference profile lookup",
        "public holiday calendar",
        "nutrition lookup",
        "product barcode lookup",
        "pokemon resource",
        "wikipedia summary",
        "poetry author lookup",
        "entity lookup",
        "university directory",
        "sports team directory",
        "recipe name search",
        "museum artwork search",
    ):
        return frozenset({"lookup_reference"})

    if _has_any(identity, "python script execution", "execute one workspace local python script"):
        return frozenset({"execute_script"})

    # REST-backed Tools without a narrower semantic family remain API queries.
    execution = manifest.get("execution", {}) if isinstance(manifest, dict) else {}
    runtime = execution.get("runtime", "") if isinstance(execution, dict) else ""
    if normalize_capability_operation(runtime) == "rest_api" and _has_any(
        text, "rest api", "api query", "query api", "api envelope", "http response"
    ):
        return frozenset({"query_api"})

    if _has_any(identity, "image header metadata", "inspect image format", "path metadata"):
        return frozenset({"inspect_metadata"})

    return frozenset({"run_tool"})


def normalize_task_capability_operations(text: str) -> FrozenSet[str]:
    """Normalize explicit node-local intent into registered primitive IDs."""
    value = str(text or "").lower()
    operations: set[str] = set()

    if "pdflatex" in value or (
        "latex" in value
        and _has_any(value, "compile", "compilation", "build", "typeset")
    ):
        return frozenset({"compile_latex_document"})
    if "flake8" in value or re.search(r"\b(?:ruff|pylint|eslint)\s+(?:lint|linting|check)", value):
        return frozenset({"lint_code"})
    if (
        "bandit" in value
        and "dependency" not in value
        and _has_any(value, "security", "scan", "audit")
    ):
        return frozenset({"audit_bandit"})
    if _has_any(value, "detect secrets", "secret scan", "secret detection"):
        return frozenset({"scan_secrets"})
    if _has_any(value, "dependency cve", "dependency vulnerability", "dependency audit"):
        return frozenset({"audit_dependencies"})
    if "bandit" in value and _has_any(value, "security", "scan", "audit"):
        return frozenset({"audit_security"})
    if "pdf" in value:
        if any(term in value for term in ("extract", "text preview", "preview text", "read", '\u8bfb\u53d6', '\u63d0\u53d6', '\u6587\u672c\u9884\u89c8')):
            operations.add("extract_page_text")
        elif any(term in value for term in ("page count", "metadata", '\u9875\u6570', '\u5143\u6570\u636e')):
            operations.add("count_pdf_pages")
    if any(term in value for term in ("immediate child", "immediate entr", "without recursion", "non-recursive", '\u76f4\u63a5\u5185\u5bb9', '\u5217\u51fa')):
        operations.add("list_immediate_directory_entries")
    if any(term in value for term in ("directory tree", "recursive tree", "recursively list", '\u76ee\u5f55\u6811', '\u9012\u5f52')):
        operations.add("recursive_directory_traversal")
    if any(term in value for term in ("search files", "search file", "grep", "find files", "file pattern", '\u641c\u7d22\u6587\u4ef6', '\u5339\u914d\u6587\u4ef6')):
        operations.add("search_files_by_pattern")
    if any(term in value for term in ("file metadata", "file info", "timestamps", '\u6587\u4ef6\u4fe1\u606f', '\u5143\u6570\u636e')) and "pdf" not in value:
        operations.add("inspect_path_metadata")
    if any(term in value for term in ("read file", "file contents", "read the complete", '\u8bfb\u53d6\u6587\u4ef6', '\u6587\u4ef6\u5185\u5bb9')) and "pdf" not in value:
        operations.add("read_text_file")
    if any(term in value for term in ("edit file", "replace text", "write file", '\u4fee\u6539\u6587\u4ef6', '\u5199\u5165\u6587\u4ef6')):
        operations.add("edit_file_content")
    if any(term in value for term in ("create directory", "make directory", '\u521b\u5efa\u76ee\u5f55')):
        operations.add("create_directory")
    if any(term in value for term in ("detect language", "language detection", '\u8bc6\u522b\u8bed\u8a00', '\u8bed\u8a00\u68c0\u6d4b')):
        operations.add("detect_language_candidates")
    return frozenset(operations)


def normalize_task_general_operation_kinds(text: str) -> FrozenSet[str]:
    """Normalize explicit task action/object phrases into general Tool kinds.

    This deliberately does not infer an operation from a bare noun such as
    ``PDF`` or ``weather``.  It is used for pre-ranking compatibility, where
    absent evidence must remain UNKNOWN rather than excluding a Tool.
    """
    value = str(text or "").lower()
    operations: set[str] = set()

    if "pdflatex" in value or (
        "latex" in value
        and _has_any(value, "compile", "compilation", "build", "typeset")
    ):
        return frozenset({"compile_latex_document"})
    if "flake8" in value or re.search(r"\b(?:ruff|pylint|eslint)\s+(?:lint|linting|check)", value):
        return frozenset({"lint_code"})
    if (
        "bandit" in value
        and "dependency" not in value
        and _has_any(value, "security", "scan", "audit")
    ):
        return frozenset({"audit_bandit"})

    exact_patterns = (
        (r"json\s*(?:file|document|data)?\s*(?:to|into|as)\s*toml", "convert_json_to_toml"),
        (r"xml\s*(?:file|document|data)?\s*(?:to|into|as)\s*json", "convert_xml_to_json"),
        (r"yaml\s*(?:file|document|data)?\s*(?:to|into|as)\s*json", "convert_yaml_to_json"),
        (r"json\s*(?:file|document|data)?\s*(?:to|into|as)\s*yaml", "convert_json_to_yaml"),
    )
    if _has_any(value, "convert", "transform", "serialize"):
        for pattern, operation in exact_patterns:
            if re.search(pattern, value):
                return frozenset({operation})
        # Natural language often inserts an object phrase between the source
        # and target formats ("JSON file ... convert its contents into TOML").
        # Preserve direction without requiring an exact adjacent "JSON to
        # TOML" phrase.
        format_positions = {
            fmt: value.find(fmt) for fmt in ("json", "yaml", "xml", "toml")
        }
        directional = {
            ("json", "yaml"): "convert_json_to_yaml",
            ("yaml", "json"): "convert_yaml_to_json",
            ("json", "toml"): "convert_json_to_toml",
            ("xml", "json"): "convert_xml_to_json",
        }
        for (source, target), operation in directional.items():
            if format_positions[source] >= 0 and format_positions[target] > format_positions[source]:
                return frozenset({operation})
    if "csv" in value and _has_any(value, "column", "columns", "project", "projection", "select"):
        return frozenset({"project_csv_columns"})
    if "sql" in value and _has_any(value, "ddl", "create table", "table names", "column definitions"):
        return frozenset({"parse_sql_ddl"})
    if "json schema" in value and _has_any(value, "infer", "generate", "sample", "structure"):
        return frozenset({"infer_json_schema"})
    if _has_any(value, "sympy", "symbolic solving", "symbolic solve") and _has_any(value, "solve", "equation"):
        return frozenset({"solve_symbolic"})
    if (
        _has_any(value, "detect language", "language detection", "language-detection")
        or re.search(r"detect\s+(?:the\s+)?language", value)
    ):
        return frozenset({"detect_language"})

    if (
        "pdf" in value
        and _has_any(value, "extract", '\u63d0\u53d6')
        and _has_any(value, "text", '\u6587\u672c', "preview")
    ) or _has_any(value, "pdf text extraction", '\u63d0\u53d6pdf\u6587\u672c', '\u4ecepdf\u63d0\u53d6\u6587\u672c', '\u63d0\u53d6 pdf \u6587\u672c'):
        operations.add("extract_document")
    if _has_any(
        value,
        "list directory", "list the directory", "list immediate directory",
        "list immediate child", "directory entries", '\u5217\u51fa\u76ee\u5f55', '\u5217\u51fa\u8be5\u76ee\u5f55',
    ):
        operations.add("list_directory")
    if _has_any(
        value,
        "convert json", "convert yaml", "json to yaml", "yaml to json",
        "convert format", "format conversion", 'json \u8f6c yaml', 'yaml \u8f6c json',
        '\u8f6c\u6362json', '\u8f6c\u6362yaml', '\u683c\u5f0f\u8f6c\u6362',
    ) or (
        "json" in value
        and "yaml" in value
        and re.search(r"\b(?:convert|transform|serialize)\b", value) is not None
    ):
        operations.add("convert_format")
    if _has_any(
        value,
        "jsonpath", "jq", "sql query", "query sql", '\u67e5\u8be2jsonpath',
        '\u6267\u884csql\u67e5\u8be2', 'sql \u67e5\u8be2',
    ):
        operations.add("query_data")
    if "json schema" in value and _has_any(
        value,
        "validate", "validation", "check against", "conform to", "verify against",
    ):
        operations.add("validate_artifact")
    if _has_any(
        value,
        "generate json schema", "generate schema", "generate a schema",
        "infer schema", "schema from sample", '\u63a8\u65adschema', '\u751f\u6210schema',
    ):
        operations.add("parse_data")
    if _has_any(value, "lint code", "lint the", "run lint", '\u4ee3\u7801\u68c0\u67e5', '\u4ee3\u7801\u9759\u6001\u68c0\u67e5'):
        operations.add("lint_code")
    if _has_any(
        value,
        "security audit", "dependency audit", "bandit audit", "run bandit",
        '\u4f9d\u8d56\u5b89\u5168\u5ba1\u8ba1', '\u5b89\u5168\u5ba1\u8ba1', 'bandit \u5b89\u5168',
    ):
        operations.add("audit_security")
    if _has_any(value, "run pytest", "execute pytest", "pytest tests", '\u8fd0\u884cpytest', '\u8fd0\u884c pytest'):
        operations.add("run_tests")
    if _has_any(
        value,
        "search arxiv", "search pubmed", "arxiv search", "pubmed search",
        "search for papers", '\u68c0\u7d22arxiv', '\u68c0\u7d22pubmed', '\u641c\u7d22arxiv', '\u641c\u7d22pubmed',
    ):
        operations.add("search_knowledge")
    local_material_markers = (
        "supplied", "provided", "attached", "local file", "local material",
        "input file", "provided file", "artifact handle", "handle",
        '\u5df2\u63d0\u4f9b', '\u9644\u4ef6', '\u672c\u5730\u6587\u4ef6', '\u672c\u5730\u6750\u6599', '\u8f93\u5165\u6587\u4ef6', '\u6587\u4ef6\u53e5\u67c4',
    )
    external_evidence_requested = (
        _has_any(value, "external evidence", "external source", "external information", '\u5916\u90e8\u8bc1\u636e', '\u5916\u90e8\u4fe1\u606f')
        and _has_any(value, "acquire", "acquisition", "search", "retrieve", "look up", "verify", '\u83b7\u53d6', '\u68c0\u7d22', '\u67e5\u627e', '\u9a8c\u8bc1')
    )
    if (
        _has_any(value, "public web search", "search the public web", "ranked web sources", "search the web", '\u516c\u5171\u7f51\u9875', '\u7f51\u7edc\u68c0\u7d22', '\u8054\u7f51\u68c0\u7d22')
        or (external_evidence_requested and not _has_any(value, *local_material_markers))
    ):
        operations.add("search_web")
    if _has_any(
        value,
        "known url", "specified url", "public url", "http url",
        "fetch the page", "fetch a page", "retrieve the page",
        '\u5df2\u77e5url', '\u6307\u5b9aurl', '\u83b7\u53d6\u7f51\u9875', '\u6293\u53d6\u7f51\u9875',
    ):
        operations.add("fetch_web_resource")
    if _has_any(
        value,
        "capture a specified public webpage",
        "capture a specified public web page",
        "capture a public webpage",
        "capture a webpage",
        "web archive", "warc", "wacz", '\u7f51\u9875\u6355\u83b7', '\u7f51\u9875\u5f52\u6863',
    ):
        operations.add("browser_capture")
    if (
        _has_any(value, "dns", "ip address", 'ip\u5730\u5740')
        and _has_any(value, "resolve", "resolution", '\u89e3\u6790')
    ) or _has_any(value, 'dns\u89e3\u6790', '\u89e3\u6790dns', '\u89e3\u6790ip', 'ip\u89e3\u6790'):
        operations.add("resolve_network")
    if _has_any(
        value,
        "live weather", "current weather", "weather lookup", "live exchange",
        "exchange price", "spot price", '\u5b9e\u65f6\u5929\u6c14', '\u5f53\u524d\u5929\u6c14', '\u5b9e\u65f6\u6c47\u7387', '\u6700\u65b0\u6c47\u7387',
    ):
        operations.add("fetch_live_data")
    if _has_any(
        value,
        "symbolic math", "symbolic sympy", "sympy math", "solve with sympy",
        '\u7b26\u53f7\u6570\u5b66', '\u7b26\u53f7\u8ba1\u7b97', '\u4f7f\u7528sympy', '\u4f7f\u7528 sympy',
    ):
        operations.add("compute_math")

    return frozenset(operations)


def requests_external_content(text: str) -> bool:
    """Recognize an explicit action on remote content, including links from files.

    Merely mentioning a URL inside a local document does not imply fetching it.
    Supplied material does not suppress a separately requested remote action.
    """
    value = str(text or "").casefold()
    verbs = list(re.finditer(r"\b(?:fetch|retrieve|visit|inspect|read|open|access|query|download)\b", value))
    remote_object = re.compile(
        r"https?://|\b(?:urls?|websites?|webpages?)\b|"
        r"\b(?:public|online|web)\b(?:[ \t]+[\w-]+)*?[ \t]+(?:pages?|sites?|sources?|records?|apis?)\b"
    )
    for index, verb in enumerate(verbs):
        if re.search(r"(?:do not|don't|never)\s*$", value[:verb.start()]):
            continue
        end = verbs[index + 1].start() if index + 1 < len(verbs) else len(value)
        clause = re.split(r"[.;\n]", value[verb.end():end], maxsplit=1)[0]
        target = remote_object.search(clause)
        if target is not None and not re.search(
            r"\b(?:file|attachment|spreadsheet|image|document|dataset)\b", clause[:target.start()]
        ):
            return True
    # A source relation is an acquisition requirement even without an imperative
    # "fetch": e.g. determine a value from a public record. This does not turn
    # links merely listed inside an attachment into instructions to visit them.
    for relation in re.finditer(r"\b(?:from|on|according to|based on|using)\b", value):
        clause = re.split(r"[.;\n]", value[relation.end():], maxsplit=1)[0]
        target = remote_object.search(clause)
        if target is None:
            continue
        prefix = clause[:target.start()]
        if (len(prefix.split()) > 6 or re.search(
            r"\b(?:file|attachment|spreadsheet|image|document|dataset|local|offline|cached|copies|copy)\b",
            prefix,
        )):
            continue
        sentence_prefix = re.split(r"[.;\n]", value[:relation.start()])[-1]
        if re.search(r"\b(?:do not|don't|never)\b", sentence_prefix):
            continue
        return True
    return False


def requires_external_grounding(
    text: str,
    *,
    has_authorized_materials: bool = False,
    declared_grounding: bool = False,
    evidence_source_scope: str | None = None,
) -> bool:
    """Recognize factual-acquisition needs without naming a provider.

    Free-form task text remains conservative and must identify an external
    source. A non-empty Planner grounding declaration is already the formal
    statement that facts outside supplied materials must be acquired and
    verified, so it does not depend on a provider-keyword lexicon. Explicitly
    local source language still prevents an external route.
    """
    value = str(text or "").casefold()
    if evidence_source_scope == "supplied_materials":
        return False
    if evidence_source_scope in {"external_sources", "mixed"}:
        return bool(value.strip())
    if requests_external_content(value):
        return True
    source_requested = _has_any(
        value,
        "external evidence", "external source", "external information",
        "authoritative source", "authoritative reference",
        "primary source", "technical specification",
        "published paper", "research paper",
        "public source", "public record", "historical record", "official source",
        "changelog", "release notes", "according to official",
        "public web", "web search", "search the web", "internet", "online",
        '\u6839\u636e\u516c\u5f00', '\u6839\u636e\u5b98\u7f51', '\u516c\u5f00\u8d44\u6599', '\u5916\u90e8\u8bc1\u636e', '\u5916\u90e8\u4fe1\u606f',
        '\u66f4\u65b0\u65e5\u5fd7', '\u53d1\u884c\u8bf4\u660e', '\u4e92\u8054\u7f51', '\u7f51\u9875\u641c\u7d22',
    )
    acquisition_requested = _has_any(
        value,
        "search", "look up", "find out", "identify", "retrieve", "acquire",
        "obtain", "verify", "check", "according to", '\u67e5\u8be2', '\u67e5\u627e', '\u68c0\u7d22',
        '\u83b7\u53d6', '\u6838\u5b9e', '\u9a8c\u8bc1', '\u786e\u8ba4',
    )
    question_requested = "?" in value or re.search(
        r"\b(?:what|which|when|where|who|whom|whose|how many|how much)\b",
        value,
    ) is not None or _has_any(value, '\u4ec0\u4e48', '\u54ea\u4e00', '\u4f55\u65f6', '\u591a\u5c11')
    local_only = _has_any(
        value,
        "supplied local", "provided local", "attached local", "provided file",
        "supplied file", "attached file", "from the input file", "in the supplied",
        "repository changelog", "repo changelog", "workspace changelog",
        "local changelog", "in the repository", "in this repository",
        '\u5df2\u63d0\u4f9b\u7684\u672c\u5730', '\u7ed9\u5b9a\u6587\u4ef6', '\u63d0\u4f9b\u7684\u6587\u4ef6', '\u9644\u4ef6\u4e2d\u7684', '\u57fa\u4e8e\u672c\u5730\u6750\u6599',
    )
    if declared_grounding:
        # Supplied inputs and external acquisition can both be required. A
        # formal declaration must not be vetoed by local-material keywords.
        return bool(value.strip())
    if has_authorized_materials:
        return False
    return source_requested and (acquisition_requested or question_requested) and not local_only
