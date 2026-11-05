"""HyDE-enhanced, typed dual-path retrieval for S-GAR."""

from __future__ import annotations

import json
import hashlib
import logging
import os
import pickle
import re
import threading
import time
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple

import certifi
import faiss
import numpy as np
from retrieval_profiles import PROFILE_VERSION
from sgar_mvp.src.embedding_runtime import (
    EmbeddingRuntimeConfigV1,
    IndexMetaV2,
    LocalEmbeddingEncoder,
    embedding_config_from_metadata,
    prepare_query_texts,
)
from sgar_mvp.src.internal_language import prompt_file_text
from sgar_mvp.src.retrieval_policy import (
    RETRIEVAL_STRATEGIES,
    load_retrieval_policy,
)
from sgar_mvp.src.model_accounting import (
    BudgetControlError,
    ModelAccountingError,
    RunCostLedger,
)
from sgar_mvp.src.proxy_retry import wait_for_proxy_retry
from sgar_mvp.src.model_transport import (
    ModelTransportError,
    ProviderEndpointIdentity,
    SyncModelTransportPort,
    classify_transport_exception,
    legacy_sync_transport_from_client,
    model_request_sha256,
    require_sync_model_transport,
)
from sgar_mvp.src.model_response_contracts import (
    StructuredResponseModeInput,
    normalize_portable_wire_instance,
    normalize_structured_response_mode,
    strict_json_loads,
    structured_response_format,
    system_role_requirement,
    validate_json_schema_instance,
)
from sgar_mvp.src.retrieval_lifecycle import (
    LocalEmbeddingIdentity,
    RetrievalLifecycleError,
)
from sgar_mvp.src.profiler_protocol import (
    PROFILER_NORMAL_OUTPUT_CAP,
    PROFILER_TRUNCATION_RETRY_OUTPUT_CAP,
    ProfilerInputEnvelopeV1,
    ProfilerOutputV2,
)
from sgar_mvp.src.runtime_policy_context import active_retrieval_policy_path
from sgar_mvp.src.provider_reasoning import observe_provider_reasoning
from sgar_mvp.src.release_source_seal import (
    load_and_verify_source_seal,
    source_seal_reference,
)


PROJECT_ROOT = Path(__file__).resolve().parent
INDEX_DIR = Path(
    os.environ.get("SGAR_INDEX_DIR", str(PROJECT_ROOT / "Pool" / "index_meta"))
).resolve()
CAP_INDEX_FILE = INDEX_DIR / "faiss_cap.index"
CON_INDEX_FILE = INDEX_DIR / "faiss_con.index"
METADATA_FILE = INDEX_DIR / "resource_meta.pkl"
MODEL_HEALTH_FILE = PROJECT_ROOT / "sgar_mvp" / "config" / "model_health.json"
_BOUND_POLICY_PATH = active_retrieval_policy_path()
_POLICY_OVERRIDE = str(_BOUND_POLICY_PATH) if _BOUND_POLICY_PATH else os.environ.get("SGAR_RETRIEVAL_POLICY_PATH")
if (
    _POLICY_OVERRIDE
    and _BOUND_POLICY_PATH is None
    and os.environ.get("SGAR_SEALED_LOCAL_VALIDATION") != "1"
):
    raise RuntimeError("retrieval_policy_environment_override_requires_sealed_validation")
RETRIEVAL_POLICY = (
    load_retrieval_policy(Path(_POLICY_OVERRIDE).resolve())
    if _POLICY_OVERRIDE
    else load_retrieval_policy()
)
EMBED_MODEL = RETRIEVAL_POLICY.embedding_model
BGE_PREFIX = RETRIEVAL_POLICY.bge_prefix
HYDE_MODEL = os.environ.get("SGAR_HYDE_MODEL", RETRIEVAL_POLICY.hyde.api_model_id)
HYDE_BASE_URL = "https://api.example.invalid/v1"
HYDE_PROFILE_VERSION = RETRIEVAL_POLICY.hyde.prompt_version
TOP_N = 10
TOP_K = 3

TYPE_WEIGHTS: Dict[str, Tuple[float, float]] = RETRIEVAL_POLICY.weights()
# Explicit mode for retrieval quality audits. Production remains capability-only
# until a local policy is deliberately promoted after the quality gate.
SHADOW_RETRIEVAL_STRATEGY = "capability_constraint_weighted"

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)


PROFILER_SYSTEM_PROMPT = prompt_file_text("profiler_system.txt")
ENGLISH_PROFILER_PROMPT_VERSION = "ideal-resource-profiler-en-v3"


def _profiler_prompt_for_version(
    prompt_version: str,
) -> str:
    if prompt_version == ENGLISH_PROFILER_PROMPT_VERSION:
        return PROFILER_SYSTEM_PROMPT
    raise HyDEGenerationError(
        "profiler_prompt_version_unknown",
        responsibility="framework",
        response_received=False,
    )


@dataclass(frozen=True)
class QueryProfile:
    capability_text: str
    constraint_text: str
    capability_vector: List[float]
    constraint_vector: List[float]
    raw_query_text: str = ""
    raw_query_vector: List[float] | None = None
    hard_requirements: Dict[str, Any] = field(default_factory=dict)
    concatenated_vector: List[float] | None = None
    profile_version: str = "typed-query-v1"
    generation_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_text": self.capability_text,
            "constraint_text": self.constraint_text,
            "capability_vector": self.capability_vector,
            "constraint_vector": self.constraint_vector,
            "raw_query_text": self.raw_query_text,
            "raw_query_vector": self.raw_query_vector,
            "hard_requirements": self.hard_requirements,
            "concatenated_vector": self.concatenated_vector,
            "profile_version": self.profile_version,
            "generation_metadata": self.generation_metadata,
        }


class HyDEGenerationError(RuntimeError):
    """Structured terminal failure from one semantic HyDE generation."""

    def __init__(
        self,
        failure_code: str,
        *,
        responsibility: str,
        response_received: bool,
        transport_attempts: int = 0,
        request_sha256: str | None = None,
    ) -> None:
        super().__init__(failure_code)
        self.failure_code = str(failure_code)
        self.failure_responsibility = str(responsibility)
        self.response_received = bool(response_received)
        self.transport_attempts = int(transport_attempts)
        self.request_sha256 = request_sha256
        self.retryable = False


HYDE_PROMPT = _profiler_prompt_for_version(HYDE_PROFILE_VERSION)


def _profiler_output_is_english(
    output: ProfilerOutputV2,
    source_text: str,
) -> bool:
    """Require English prose while permitting literal CJK identifiers from input."""

    combined = f"{output.capability_text}\n{output.constraint_text}"
    combined += f"\n{output.think}"
    cjk_sequences = re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+", combined)
    if any(sequence not in source_text for sequence in cjk_sequences):
        return False
    latin_count = sum(character.isascii() and character.isalpha() for character in combined)
    cjk_count = sum(len(sequence) for sequence in cjk_sequences)
    return latin_count >= 20 and latin_count >= cjk_count * 4


def _profiler_think_is_valid(output: ProfilerOutputV2) -> bool:
    """Require a useful rationale; leakage is checked across every field below."""

    return bool(output.think.strip())


def _profiler_output_is_safe(
    output: ProfilerOutputV2, source_text: str = ""
) -> bool:
    """Apply the no-runtime/no-pool leakage rule to every generated field."""

    resource_id_pattern = re.compile(
        r"(?i)\b(?:model|tool|skill|agent|resource|device)\.[a-z0-9][a-z0-9_.:-]*"
    )
    fields = (output.capability_text, output.constraint_text, output.think)
    forbidden = (
        "resource_id",
        "retrieval score",
    )
    source = source_text.casefold()
    # Task-declared file names can share a resource-type prefix (model.weights,
    # tool.py). They describe authoritative deliverables, not pool selections.
    declared_file_names = {
        token.replace("\\", "/").rsplit("/", 1)[-1].rstrip(".,;:!?)]}{").casefold()
        for token in re.findall(r"[^\s<>\"'`]*[\\/][^\s<>\"'`]+", source_text)
    }
    for value in fields:
        text = str(value or "").strip()
        lowered = text.casefold()
        if (
            not text
            or any(term in lowered for term in forbidden)
            or any(
                match.group(0).rstrip(".,;:!?)").casefold() not in declared_file_names
                for match in resource_id_pattern.finditer(text)
            )
        ):
            return False
        # Source URLs and paths can be part of the task's authoritative input.
        # Reject invented locations without suppressing declared constraints.
        locations = re.findall(r"(?i)https?://[^\s<>\"']+|(?:^|\s)[a-z]:[\\/][^\s<>\"']+", text)
        if any(location.strip().rstrip(".,;:!?)").casefold() not in source for location in locations):
            return False
    return True


def get_profiler_transport() -> SyncModelTransportPort:
    """Return the shared exact Chat Completions transport for Profiler calls."""

    _engine.ensure_transport_loaded()
    legacy_client = _engine.llm_client
    if legacy_client is None:
        raise HyDEGenerationError(
            "hyde_client_unavailable",
            responsibility="framework",
            response_received=False,
        )
    base_url = (
        _load_env_value("LLM_BASE_URL", "OPENAI_BASE_URL") or HYDE_BASE_URL
    ).rstrip("/")
    endpoint = ProviderEndpointIdentity.create(
        provider="openai_compatible",
        base_url=base_url,
        credential_environment_variable="LLM_API_KEY",
        timeout_seconds=60.0,
    )
    return legacy_sync_transport_from_client(
        client=legacy_client,
        endpoint_identity=endpoint,
    )


def _load_env_value(*names: str) -> str:
    dotenv_values: Dict[str, str] = {}
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            dotenv_values[name.strip()] = value.strip()
    for name in names:
        value = os.environ.get(name, "").strip() or dotenv_values.get(name, "")
        if value:
            return value
    return ""


def _resource_type(raw: Mapping[str, Any]) -> str:
    legacy = raw.get("type")
    nested = legacy.get("resource_type") if isinstance(legacy, Mapping) else None
    return str(raw.get("resource_type") or nested or "Unknown")


def _load_unavailable_model_ids() -> set[str]:
    if not MODEL_HEALTH_FILE.exists():
        return set()
    try:
        payload = json.loads(MODEL_HEALTH_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return set()
    unavailable = {str(item) for item in payload.get("unavailable_model_ids", [])}
    for item in payload.get("models", []):
        if isinstance(item, Mapping) and item.get("status") == "unavailable":
            unavailable.add(str(item.get("model_id") or ""))
    return {item for item in unavailable if item}


class IndexMetadataRuntime:
    """Thread-safe frozen index lifecycle with no encoder or network client."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._loaded = False
        self.cap_index: faiss.Index | None = None
        self.con_index: faiss.Index | None = None
        self.metadata: Dict[str, Any] | None = None
        self.cap_matrix: np.ndarray | None = None
        self.con_matrix: np.ndarray | None = None
        self.unavailable_model_ids: set[str] = set()

    def ensure_loaded(self) -> None:
        with self._lock:
            if self._loaded:
                return
            cap_index = faiss.read_index(str(CAP_INDEX_FILE))
            con_index = faiss.read_index(str(CON_INDEX_FILE))
            with METADATA_FILE.open("rb") as handle:
                metadata = pickle.load(handle)
            from sgar_mvp.src.model_selection import require_registered_models
            require_registered_models(metadata["id_to_resource"].values())
            indexed_profile = metadata.get("profile_version")
            if indexed_profile != PROFILE_VERSION:
                raise RuntimeError(
                    "Retrieval index is stale: "
                    f"profile={indexed_profile!r}, expected={PROFILE_VERSION!r}. "
                    "Run build_index.py in the sgar environment."
                )
            dimension = int(metadata["dim"])
            for index in (cap_index, con_index):
                index_dimension = getattr(index, "d", dimension)
                if int(index_dimension) != dimension:
                    raise RetrievalLifecycleError("retrieval_index_dimension_mismatch")
            cap_matrix = np.asarray(metadata["cap_vectors"], dtype="float32")
            con_matrix = np.asarray(metadata["con_vectors"], dtype="float32")
            if (
                cap_matrix.ndim != 2
                or con_matrix.ndim != 2
                or cap_matrix.shape[1] != dimension
                or con_matrix.shape[1] != dimension
            ):
                raise RetrievalLifecycleError("retrieval_vector_dimension_mismatch")
            index_meta_raw = metadata.get("index_meta_v2")
            if index_meta_raw:
                try:
                    index_meta = IndexMetaV2.model_validate(index_meta_raw)
                except ValueError as exc:
                    raise RetrievalLifecycleError("retrieval_index_meta_v2_invalid") from exc
                resource_order = tuple(
                    str(metadata["idx_to_id"][index])
                    for index in range(len(metadata["idx_to_id"]))
                )
                if resource_order != index_meta.resource_id_order:
                    raise RetrievalLifecycleError("retrieval_index_resource_order_mismatch")
                if hashlib.sha256(
                    np.ascontiguousarray(cap_matrix, dtype="float32").tobytes()
                ).hexdigest() != index_meta.capability_vectors_sha256:
                    raise RetrievalLifecycleError("retrieval_capability_vector_hash_mismatch")
                if hashlib.sha256(
                    np.ascontiguousarray(con_matrix, dtype="float32").tobytes()
                ).hexdigest() != index_meta.constraint_vectors_sha256:
                    raise RetrievalLifecycleError("retrieval_constraint_vector_hash_mismatch")
            self.cap_index = cap_index
            self.con_index = con_index
            self.metadata = metadata
            self.cap_matrix = cap_matrix
            self.con_matrix = con_matrix
            self.unavailable_model_ids = _load_unavailable_model_ids()
            self._loaded = True

    def close(self) -> None:
        with self._lock:
            self.cap_index = None
            self.con_index = None
            self.metadata = None
            self.cap_matrix = None
            self.con_matrix = None
            self.unavailable_model_ids = set()
            self._loaded = False


class LocalEmbeddingRuntime:
    """Offline local encoder lifecycle independent from index and transport."""

    def __init__(
        self,
        index_runtime: IndexMetadataRuntime,
        *,
        encoder_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._index_runtime = index_runtime
        self._encoder_factory = encoder_factory
        self._lock = threading.RLock()
        self.encoder: Any | None = None
        self.identity: LocalEmbeddingIdentity | None = None
        self._snapshot_path: Path | None = None
        self.config: EmbeddingRuntimeConfigV1 | None = None
        self._runtime: LocalEmbeddingEncoder | None = None

    def ensure_config(self) -> EmbeddingRuntimeConfigV1:
        with self._lock:
            if self.config is not None:
                return self.config
            self._index_runtime.ensure_loaded()
            assert self._index_runtime.metadata is not None
            self.config = embedding_config_from_metadata(
                self._index_runtime.metadata,
                fallback_model_id=EMBED_MODEL,
                fallback_query_prefix=BGE_PREFIX,
            )
            return self.config

    def ensure_identity(self) -> LocalEmbeddingIdentity:
        with self._lock:
            if self.identity is not None:
                return self.identity
            config = self.ensure_config()
            runtime = LocalEmbeddingEncoder(
                config,
                encoder_factory=self._encoder_factory,
            )
            identity = runtime.identity()
            self._runtime = runtime
            self.identity = identity
            return identity

    def ensure_loaded(self) -> Any:
        with self._lock:
            if self.encoder is not None:
                return self.encoder
            identity = self.ensure_identity()
            assert self._runtime is not None
            encoder = self._runtime.load()
            if self.config is None or self.config.output_dimension != identity.index_dimension:
                raise RetrievalLifecycleError("embedding_index_dimension_mismatch")
            self.encoder = encoder
            return encoder

    def encode_queries(self, texts: Sequence[str], *, role: str) -> np.ndarray:
        self.ensure_loaded()
        assert self._runtime is not None
        return self._runtime.encode_queries(
            texts,
            role=role,  # type: ignore[arg-type]
            batch_size=32,
        )

    def assert_profile_texts_embeddable(
        self, capability_text: str, constraint_text: str
    ) -> None:
        self.ensure_loaded()
        assert self._runtime is not None
        assert self.config is not None
        prepared = (
            prepare_query_texts([capability_text], self.config, role="capability")
            + prepare_query_texts([constraint_text], self.config, role="constraint")
        )
        self._runtime.assert_token_lengths(prepared)

    def close(self) -> None:
        with self._lock:
            self.encoder = None
            self.identity = None
            self._snapshot_path = None
            self.config = None
            if self._runtime is not None:
                self._runtime.close()
            self._runtime = None


class HyDETransportRuntime:
    """Paid HyDE transport lifecycle independent from local retrieval state."""

    def __init__(self, *, client_factory: Callable[..., Any] | None = None) -> None:
        self._client_factory = client_factory
        self._lock = threading.RLock()
        self._initialized = False
        self.llm_client: Any | None = None

    def ensure_loaded(self) -> Any | None:
        with self._lock:
            if self.llm_client is not None:
                return self.llm_client
            if self._initialized:
                return None
            key = _load_env_value("LLM_API_KEY")
            if key:
                base_url = (
                    _load_env_value("LLM_BASE_URL", "OPENAI_BASE_URL") or HYDE_BASE_URL
                ).rstrip("/")
                factory = self._client_factory
                if factory is None:
                    from openai import OpenAI

                    from sgar_mvp.src.direct_network import direct_sync_http_client
                    from functools import partial
                    factory = partial(OpenAI, http_client=direct_sync_http_client())
                self.llm_client = factory(
                    api_key=key,
                    base_url=base_url,
                    max_retries=0,
                )
            self._initialized = True
            return self.llm_client

    def close(self) -> None:
        with self._lock:
            client = self.llm_client
            self.llm_client = None
            self._initialized = False
            close = getattr(client, "close", None)
            if callable(close):
                close()


class _RetrievalEngine:
    """Compatibility facade over three explicit, re-entrant runtimes."""

    def __init__(
        self,
        *,
        encoder_factory: Callable[..., Any] | None = None,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.index_runtime = IndexMetadataRuntime()
        self.embedding_runtime = LocalEmbeddingRuntime(
            self.index_runtime,
            encoder_factory=encoder_factory,
        )
        self.hyde_runtime = HyDETransportRuntime(client_factory=client_factory)

    def ensure_loaded(self) -> None:
        """Legacy name now means index-only loading."""

        self.index_runtime.ensure_loaded()

    def ensure_encoder_loaded(self) -> Any:
        return self.embedding_runtime.ensure_loaded()

    def ensure_transport_loaded(self) -> Any | None:
        return self.hyde_runtime.ensure_loaded()

    def local_embedding_identity(self) -> LocalEmbeddingIdentity:
        return self.embedding_runtime.ensure_identity()

    def close_index(self) -> None:
        self.index_runtime.close()

    def close_encoder(self) -> None:
        self.embedding_runtime.close()

    def close_transport(self) -> None:
        self.hyde_runtime.close()

    def close(self) -> None:
        self.close_transport()
        self.close_encoder()
        self.close_index()

    @property
    def cap_index(self) -> faiss.Index | None:
        return self.index_runtime.cap_index

    @property
    def con_index(self) -> faiss.Index | None:
        return self.index_runtime.con_index

    @property
    def metadata(self) -> Dict[str, Any] | None:
        return self.index_runtime.metadata

    @property
    def cap_matrix(self) -> np.ndarray | None:
        return self.index_runtime.cap_matrix

    @property
    def con_matrix(self) -> np.ndarray | None:
        return self.index_runtime.con_matrix

    @property
    def unavailable_model_ids(self) -> set[str]:
        return self.index_runtime.unavailable_model_ids

    @property
    def encoder(self) -> Any | None:
        return self.embedding_runtime.encoder

    @encoder.setter
    def encoder(self, value: Any | None) -> None:
        self.embedding_runtime.encoder = value

    @property
    def llm_client(self) -> Any | None:
        return self.hyde_runtime.llm_client

    @llm_client.setter
    def llm_client(self, value: Any | None) -> None:
        self.hyde_runtime.llm_client = value
        self.hyde_runtime._initialized = value is not None


_engine = _RetrievalEngine()


def _encode(text: str, *, role: str = "capability") -> np.ndarray:
    _engine.ensure_loaded()
    return _engine.embedding_runtime.encode_queries([text], role=role)


def _encode_many(
    texts: Sequence[str],
    *,
    role: str = "capability",
) -> np.ndarray:
    _engine.ensure_loaded()
    if not texts:
        return np.empty((0, get_embedding_dim()), dtype="float32")
    return _engine.embedding_runtime.encode_queries(texts, role=role)


def encode_query(text: str, *, role: str = "capability") -> List[float]:
    return _encode(text, role=role)[0].tolist()


def infer_hard_requirements(query: str) -> Dict[str, Any]:
    """Extract only explicit, deterministic task gates from the original query."""

    lowered = query.lower()
    required_features: List[str] = []
    input_modalities: List[str] = ["text"]
    output_artifacts: List[str] = []

    if any(term in lowered for term in ("image", "screenshot", "photo", '\u56fe\u7247', '\u56fe\u50cf', '\u622a\u56fe')):
        input_modalities.append("image")
        required_features.append("vision")
    if any(term in lowered for term in ("tool calling", "function calling", '\u5de5\u5177\u8c03\u7528', '\u51fd\u6570\u8c03\u7528')):
        required_features.append("tool_calling")
    if any(term in lowered for term in ("json mode", "strict json", "json schema", '\u7ed3\u6784\u5316 json')):
        required_features.append("json_mode")

    artifact_terms = {
        "json": ("json",),
        "csv": ("csv",),
        "markdown": ("markdown", ".md"),
        "code": ("code", '\u4ee3\u7801', '\u6e90\u7801'),
        "pdf": ("pdf",),
        "image": ("image", '\u56fe\u7247', '\u56fe\u50cf'),
    }
    for artifact, terms in artifact_terms.items():
        if any(term in lowered for term in terms):
            output_artifacts.append(artifact)

    min_context_tokens: int | None = None
    context_match = re.search(
        '(\\d+(?:\\.\\d+)?)\\s*([km]?)\\s*(?:tokens?|\u4e0a\u4e0b\u6587|context)',
        lowered,
    )
    if context_match:
        value = float(context_match.group(1))
        if context_match.group(2) == "k":
            value *= 1_000
        elif context_match.group(2) == "m":
            value *= 1_000_000
        min_context_tokens = int(value)

    return {
        "required_model_features": sorted(set(required_features)),
        "input_modalities": sorted(set(input_modalities)),
        "output_artifacts": sorted(set(output_artifacts)),
        "min_context_tokens": min_context_tokens,
        "original_query": query,
    }


def _parse_profiler_input(
    query: str,
    *,
    require_typed_input: bool,
) -> Mapping[str, Any]:
    try:
        profiler_input = strict_json_loads(query)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        if require_typed_input:
            raise HyDEGenerationError(
                "profiler_input_envelope_invalid",
                responsibility="framework",
                response_received=False,
            ) from exc
        return {
            "protocol": "sgar-profiler-input-compat-v1",
            "subtask_contract_text": query,
            "source_content_policy": "preserve_original",
            "internal_output_language": "en",
        }
    if not isinstance(profiler_input, Mapping):
        if require_typed_input:
            raise HyDEGenerationError(
                "profiler_input_envelope_invalid",
                responsibility="framework",
                response_received=False,
            )
        return {
            "protocol": "sgar-profiler-input-compat-v1",
            "subtask_contract": profiler_input,
            "source_content_policy": "preserve_original",
            "internal_output_language": "en",
        }
    if require_typed_input:
        if profiler_input.get("protocol") != "sgar-profiler-input-v1":
            raise HyDEGenerationError(
                "profiler_input_envelope_protocol_invalid",
                responsibility="framework",
                response_received=False,
            )
        try:
            return ProfilerInputEnvelopeV1.model_validate(profiler_input).model_dump(
                mode="json"
            )
        except ValueError as exc:
            raise HyDEGenerationError(
                "profiler_input_envelope_invalid",
                responsibility="framework",
                response_received=False,
            ) from exc
    return profiler_input


def _generate_hyde_result(
    query: str,
    *,
    allow_direct_fallback: bool | None = None,
    cost_ledger: RunCostLedger | None = None,
    subtask_id: str | None = None,
    subtask_revision: int | None = None,
    transport: SyncModelTransportPort | None = None,
    response_mode: StructuredResponseModeInput = "native_strict_schema",
    model_id: str | None = None,
    reasoning_effort: str | None = None,
    require_typed_input: bool = False,
    prompt_version: str | None = None,
    system_prompt: str | None = None,
    max_output_tokens: int | None = None,
    correction_diagnostics: Mapping[str, Any] | None = None,
    model_attempt_limit: int | None = None,
    source_seal_path: Path | None = None,
) -> Dict[str, Any]:
    """Generate one strict, pool-blind Profiler profile with bounded correction."""

    selected_seal_path = source_seal_path
    if selected_seal_path is None and os.environ.get("SGAR_SOURCE_SEAL_PATH"):
        selected_seal_path = Path(os.environ["SGAR_SOURCE_SEAL_PATH"])
    source_seal = (
        load_and_verify_source_seal(
            selected_seal_path,
            project_root=PROJECT_ROOT,
            allowed_stages=("release", "activated"),
        )
        if selected_seal_path is not None
        else None
    )
    profiler_input = _parse_profiler_input(
        query,
        require_typed_input=require_typed_input,
    )
    if transport is None:
        _engine.ensure_transport_loaded()
    fallback_allowed = (
        RETRIEVAL_POLICY.hyde.allow_direct_fallback
        if allow_direct_fallback is None
        else allow_direct_fallback
    )
    if transport is None and _engine.llm_client is None:
        if fallback_allowed:
            return {
                "capability_text": query,
                "constraint_text": query,
                "think": "Direct fallback used because no Profiler client was available.",
                "metadata": {"status": "direct_fallback", "reason": "missing_api_key"},
            }
        raise HyDEGenerationError(
            "hyde_client_unavailable",
            responsibility="framework",
            response_received=False,
        )
    if transport is None:
        transport = get_profiler_transport()
    transport = require_sync_model_transport(transport)
    started = time.perf_counter()
    profiler_requirement = system_role_requirement("hyde")
    selected_mode = normalize_structured_response_mode(response_mode)
    selected_model = str(model_id or HYDE_MODEL).strip()
    if not selected_model:
        raise HyDEGenerationError(
            "profiler_model_id_missing",
            responsibility="framework",
            response_received=False,
        )
    selected_reasoning_effort = str(
        reasoning_effort or RETRIEVAL_POLICY.hyde.reasoning_effort
    ).strip()
    selected_prompt_version = str(prompt_version or HYDE_PROFILE_VERSION).strip()
    expected_system_prompt = _profiler_prompt_for_version(selected_prompt_version)
    selected_system_prompt = str(system_prompt or expected_system_prompt)
    if selected_system_prompt != expected_system_prompt:
        raise HyDEGenerationError(
            "profiler_prompt_version_content_mismatch",
            responsibility="framework",
            response_received=False,
        )
    if selected_model != RETRIEVAL_POLICY.hyde.api_model_id:
        raise HyDEGenerationError(
            "profiler_model_policy_violation",
            responsibility="framework",
            response_received=False,
        )
    if selected_reasoning_effort != RETRIEVAL_POLICY.hyde.reasoning_effort:
        raise HyDEGenerationError(
            "profiler_reasoning_effort_policy_violation",
            responsibility="framework",
            response_received=False,
        )
    accounting_context = (
        cost_ledger.new_operation(
            stage="retrieval_hyde",
            subtask_id=subtask_id,
            subtask_revision=subtask_revision,
            request_policy_sha256=RETRIEVAL_POLICY.sha256(),
            reasoning_effort=selected_reasoning_effort,
        )
        if cost_ledger is not None
        else None
    )
    selected_max_output_tokens = int(
        max_output_tokens or RETRIEVAL_POLICY.hyde.max_tokens
    )
    if selected_max_output_tokens <= 0:
        raise HyDEGenerationError(
            "profiler_max_output_tokens_invalid",
            responsibility="framework",
            response_received=False,
        )
    selected_model_attempt_limit = int(
        model_attempt_limit or RETRIEVAL_POLICY.hyde.max_model_attempts
    )
    if selected_model_attempt_limit not in {1, 2}:
        raise HyDEGenerationError(
            "profiler_model_attempt_limit_invalid",
            responsibility="framework",
            response_received=False,
        )
    request_hashes: List[str] = []
    model_request_hashes: List[str] = []
    model_attempt_output_caps: List[int] = []
    response: Any | None = None
    last_failure_code = "profiler_response_invalid"
    last_request_sha256: str | None = None

    def build_messages(
        *,
        correction_code: str | None,
    ) -> list[dict[str, str]]:
        user_payload: Dict[str, Any]
        if selected_mode == "json_object_local_validator":
            user_payload = {
                "profiler_input": profiler_input,
                "authoritative_output_schema": profiler_requirement.json_schema,
            }
        else:
            user_payload = dict(profiler_input)
        messages = [
            {"role": "system", "content": selected_system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    user_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        ]
        if correction_code is not None:
            diagnostic_payload = dict(correction_diagnostics or {})
            messages.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "protocol": "sgar-profiler-correction-v1",
                            "failure_code": correction_code,
                            "diagnostics": diagnostic_payload,
                            "instruction": (
                                "Return a complete replacement object matching the same "
                                "Profiler schema. Preserve the subtask semantics and correct "
                                "only the reported output-contract failure."
                            ),
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            )
        return messages

    try:
        for model_attempt in range(1, selected_model_attempt_limit + 1):
            attempt_output_cap = (
                int(RETRIEVAL_POLICY.hyde.truncation_retry_max_output_tokens)
                if model_attempt == 2
                and last_failure_code == "profiler_output_truncated"
                and selected_max_output_tokens < int(
                    RETRIEVAL_POLICY.hyde.truncation_retry_max_output_tokens
                )
                else selected_max_output_tokens
            )
            model_attempt_output_caps.append(attempt_output_cap)
            request_payload = {
                "model": selected_model,
                "messages": build_messages(
                    correction_code=(
                        "profiler_profile_revision_required"
                        if correction_diagnostics is not None and model_attempt == 1
                        else last_failure_code if model_attempt == 2 else None
                    )
                ),
                "max_tokens": attempt_output_cap,
                "response_format": structured_response_format(
                    profiler_requirement,
                    mode=selected_mode,
                ),
            }
            if RETRIEVAL_POLICY.hyde.temperature is not None:
                request_payload["temperature"] = RETRIEVAL_POLICY.hyde.temperature
            if selected_reasoning_effort:
                request_payload["reasoning_effort"] = selected_reasoning_effort
            expected_request_sha256 = model_request_sha256(request_payload)
            last_request_sha256 = expected_request_sha256
            model_request_hashes.append(expected_request_sha256)
            response = None
            for transport_attempt in range(
                1,
                RETRIEVAL_POLICY.hyde.max_transport_attempts_per_model_attempt + 1,
            ):
                attempt_payload = deepcopy(request_payload)
                attempt_hash = model_request_sha256(attempt_payload)
                if attempt_hash != expected_request_sha256:
                    raise HyDEGenerationError(
                        "profiler_transport_request_changed",
                        responsibility="framework",
                        response_received=False,
                        transport_attempts=len(request_hashes),
                        request_sha256=expected_request_sha256,
                    )
                request_hashes.append(attempt_hash)
                try:
                    response = transport.send(
                        ledger=cost_ledger,
                        context=accounting_context,
                        **attempt_payload,
                    )
                    break
                except BudgetControlError as exc:
                    raise HyDEGenerationError(
                        str(exc.error_code),
                        responsibility="budget",
                        response_received=False,
                        transport_attempts=len(request_hashes),
                        request_sha256=expected_request_sha256,
                    ) from exc
                except (ModelAccountingError, ModelTransportError) as exc:
                    raise HyDEGenerationError(
                        type(exc).__name__,
                        responsibility="framework",
                        response_received=False,
                        transport_attempts=len(request_hashes),
                        request_sha256=expected_request_sha256,
                    ) from exc
                except Exception as exc:
                    retryable, failure_code = classify_transport_exception(exc)
                    if (
                        retryable
                        and transport_attempt
                        < RETRIEVAL_POLICY.hyde.max_transport_attempts_per_model_attempt
                        and not (cost_ledger is not None and cost_ledger.is_exhausted)
                        and wait_for_proxy_retry(exc, transport_attempt)
                    ):
                        continue
                    raise HyDEGenerationError(
                        failure_code,
                        responsibility="infrastructure" if retryable else "framework",
                        response_received=False,
                        transport_attempts=len(request_hashes),
                        request_sha256=expected_request_sha256,
                    ) from exc
            if response is None:
                raise HyDEGenerationError(
                    "profiler_transport_no_terminal_response",
                    responsibility="framework",
                    response_received=False,
                    transport_attempts=len(request_hashes),
                    request_sha256=expected_request_sha256,
                )

            choice = response.choices[0]
            finish_reason = str(getattr(choice, "finish_reason", "") or "")
            full_text = str(choice.message.content or "").strip()
            failure_code: str | None = None
            if finish_reason == "length":
                failure_code = "profiler_output_truncated"
            else:
                try:
                    parsed = strict_json_loads(full_text)
                except (TypeError, ValueError, json.JSONDecodeError):
                    parsed = None
                    failure_code = "profiler_response_json_invalid"
                if failure_code is None and not isinstance(parsed, Mapping):
                    failure_code = "profiler_response_schema_invalid"
                if failure_code is None and selected_mode == "native_strict_schema":
                    parsed = normalize_portable_wire_instance(
                        parsed,
                        profiler_requirement.json_schema or {},
                    )
                if failure_code is None:
                    valid, _reason = validate_json_schema_instance(
                        parsed,
                        profiler_requirement.json_schema or {},
                    )
                    if not valid:
                        failure_code = "profiler_response_schema_invalid"
                if failure_code is None:
                    try:
                        output = ProfilerOutputV2.model_validate(parsed)
                    except ValueError:
                        failure_code = "profiler_response_fields_empty"
                if (
                    failure_code is None
                    and not _profiler_output_is_english(output, query)
                ):
                    failure_code = "profiler_output_language_invalid"
                if (
                    failure_code is None
                    and isinstance(output, ProfilerOutputV2)
                    and not _profiler_think_is_valid(output)
                ):
                    failure_code = "profiler_think_invalid"
                if (
                    failure_code is None
                    and isinstance(output, ProfilerOutputV2)
                    and not _profiler_output_is_safe(output, query)
                ):
                    failure_code = "profiler_output_leakage_invalid"
            if failure_code is not None:
                last_failure_code = failure_code
                if model_attempt < selected_model_attempt_limit:
                    continue
                raise HyDEGenerationError(
                    failure_code,
                    responsibility="research",
                    response_received=True,
                    transport_attempts=len(request_hashes),
                    request_sha256=expected_request_sha256,
                )

            usage = getattr(response, "usage", None)
            completion_details = getattr(usage, "completion_tokens_details", None)
            if isinstance(completion_details, Mapping):
                reasoning_tokens = int(completion_details.get("reasoning_tokens") or 0)
            else:
                reasoning_tokens = int(
                    getattr(completion_details, "reasoning_tokens", 0) or 0
                )
            usage_payload = {
                "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                "reasoning_tokens": reasoning_tokens,
                "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
            }
            reasoning_observation = observe_provider_reasoning(response)
            result = {
                "capability_text": output.capability_text.strip(),
                "constraint_text": output.constraint_text.strip(),
                "metadata": {
                    "status": "generated",
                    "model_id": selected_model,
                    "reasoning_effort": selected_reasoning_effort,
                    "effective_max_output_tokens": attempt_output_cap,
                    "normal_max_output_tokens": selected_max_output_tokens,
                    "truncation_retry_max_output_tokens": int(
                        RETRIEVAL_POLICY.hyde.truncation_retry_max_output_tokens
                    ),
                    "model_attempt_output_caps": list(model_attempt_output_caps),
                    "truncation_retry_used": model_attempt_output_caps == [
                        selected_max_output_tokens,
                        int(RETRIEVAL_POLICY.hyde.truncation_retry_max_output_tokens),
                    ],
                    "prompt_version": selected_prompt_version,
                    "prompt_sha256": hashlib.sha256(
                        selected_system_prompt.encode("utf-8")
                    ).hexdigest(),
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    "usage": usage_payload,
                    "model_attempt_count": model_attempt,
                    "model_attempt_limit": selected_model_attempt_limit,
                    "transport_attempt_count": len(request_hashes),
                    "transport_request_sha256": expected_request_sha256,
                    "transport_request_hashes": list(request_hashes),
                    "model_request_hashes": list(model_request_hashes),
                    "response_sha256": hashlib.sha256(
                        full_text.encode("utf-8")
                    ).hexdigest(),
                    "finish_reason": finish_reason,
                    "response_mode": selected_mode,
                    "endpoint_identity_sha256": transport.endpoint_identity.identity_sha256,
                    "wire_schema_sha256": profiler_requirement.wire_schema_sha256,
                    "provider_reasoning_observation": reasoning_observation.model_dump(
                        mode="json"
                    ),
                    "model_accounting_reference": getattr(
                        response,
                        "accounting_reference",
                        None,
                    ),
                    "source_seal": (
                        source_seal_reference(source_seal)
                        if source_seal is not None
                        else None
                    ),
                },
            }
            result["think"] = output.think.strip()
            return result
        raise HyDEGenerationError(
            last_failure_code,
            responsibility="research",
            response_received=True,
            transport_attempts=len(request_hashes),
            request_sha256=last_request_sha256,
        )
    except HyDEGenerationError as exc:
        if fallback_allowed:
            logging.getLogger(__name__).warning(
                "HyDE failed; explicit direct fallback: %s",
                exc.failure_code,
            )
            return {
                "capability_text": query,
                "constraint_text": query,
                "think": "Direct fallback used after the Profiler request failed.",
                "metadata": {
                    "status": "direct_fallback",
                    "reason": exc.failure_code,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    "transport_attempt_count": exc.transport_attempts,
                    "transport_request_sha256": exc.request_sha256,
                },
            }
        raise
    except Exception as exc:
        if fallback_allowed:
            logging.getLogger(__name__).warning(
                "HyDE failed; explicit direct fallback: %s",
                type(exc).__name__,
            )
            return {
                "capability_text": query,
                "constraint_text": query,
                "think": "Direct fallback used after Profiler response processing failed.",
                "metadata": {
                    "status": "direct_fallback",
                    "reason": type(exc).__name__,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                },
            }
        raise HyDEGenerationError(
            "profiler_response_processing_failed",
            responsibility="research" if response is not None else "framework",
            response_received=response is not None,
            transport_attempts=len(request_hashes),
            request_sha256=last_request_sha256,
        ) from exc


def generate_hyde_profile_text(
    query: str,
    *,
    cost_ledger: RunCostLedger | None = None,
    subtask_id: str | None = None,
    subtask_revision: int | None = None,
    transport: SyncModelTransportPort | None = None,
    response_mode: StructuredResponseModeInput = "native_strict_schema",
    model_id: str | None = None,
    reasoning_effort: str | None = None,
    require_typed_input: bool = False,
    prompt_version: str | None = None,
    system_prompt: str | None = None,
    max_output_tokens: int | None = None,
    correction_diagnostics: Mapping[str, Any] | None = None,
    model_attempt_limit: int | None = None,
    source_seal_path: Path | None = None,
) -> Dict[str, Any]:
    """Generate exactly one semantic ideal-profile response.

    Provider transport retries are internal to that one semantic operation.
    Local embedding/index retries must call ``encode_stored_query_profiles``
    with the returned texts and must never call this function again.
    """

    return _generate_hyde_result(
        query,
        allow_direct_fallback=False,
        cost_ledger=cost_ledger,
        subtask_id=subtask_id,
        subtask_revision=subtask_revision,
        transport=transport,
        response_mode=response_mode,
        model_id=model_id,
        reasoning_effort=reasoning_effort,
        require_typed_input=require_typed_input,
        prompt_version=prompt_version,
        system_prompt=system_prompt,
        max_output_tokens=max_output_tokens,
        correction_diagnostics=correction_diagnostics,
        model_attempt_limit=model_attempt_limit,
        source_seal_path=source_seal_path,
    )


def profiler_output_is_embeddable(
    output: ProfilerOutputV2,
) -> bool:
    """Return false only for an explicit tokenizer-limit violation."""

    try:
        _engine.embedding_runtime.assert_profile_texts_embeddable(
            output.capability_text, output.constraint_text
        )
    except RetrievalLifecycleError as exc:
        if str(exc.failure_code).startswith("embedding_input_token_limit_exceeded"):
            return False
        raise
    return True


def generate_hyde(
    query: str,
    *,
    cost_ledger: RunCostLedger | None = None,
    transport: SyncModelTransportPort | None = None,
) -> Tuple[str, str]:
    result = _generate_hyde_result(
        query,
        cost_ledger=cost_ledger,
        transport=transport,
    )
    return str(result["capability_text"]), str(result["constraint_text"])


def encode_query_profile(
    query: str,
    use_hyde: bool = True,
    *,
    cost_ledger: RunCostLedger | None = None,
    subtask_id: str | None = None,
    subtask_revision: int | None = None,
) -> QueryProfile:
    if use_hyde:
        result = _generate_hyde_result(
            query,
            cost_ledger=cost_ledger,
            subtask_id=subtask_id,
            subtask_revision=subtask_revision,
        )
        capability_text = str(result["capability_text"])
        constraint_text = str(result["constraint_text"])
        generation_metadata = dict(result["metadata"])
    else:
        capability_text = query
        constraint_text = query
        generation_metadata = {"status": "no_hyde"}
    return QueryProfile(
        capability_text=capability_text,
        constraint_text=constraint_text,
        capability_vector=encode_query(capability_text, role="capability"),
        constraint_vector=encode_query(constraint_text, role="constraint"),
        raw_query_text=query,
        raw_query_vector=encode_query(query, role="raw"),
        hard_requirements=infer_hard_requirements(query),
        profile_version=HYDE_PROFILE_VERSION if use_hyde else "direct-query-v1",
        generation_metadata=generation_metadata,
    )


def encode_query_profiles(
    queries: Sequence[str],
    use_hyde: bool = True,
    hyde_workers: int | None = None,
    *,
    cost_ledger: RunCostLedger | None = None,
) -> List[QueryProfile]:
    """Batch-encode profiles; HyDE generation remains one request per query."""

    if use_hyde:
        _engine.ensure_loaded()
        worker_count = hyde_workers or int(os.environ.get("SGAR_HYDE_WORKERS", "6"))
        with ThreadPoolExecutor(max_workers=max(1, min(worker_count, 12))) as executor:
            generated = list(
                executor.map(
                    lambda item: _generate_hyde_result(
                        item,
                        cost_ledger=cost_ledger,
                    ),
                    queries,
                )
            )
    else:
        generated = [
            {
                "capability_text": query,
                "constraint_text": query,
                "metadata": {"status": "no_hyde"},
            }
            for query in queries
        ]
    text_pairs = [
        (str(item["capability_text"]), str(item["constraint_text"]))
        for item in generated
    ]
    capability_texts = [pair[0] for pair in text_pairs]
    constraint_texts = [pair[1] for pair in text_pairs]
    raw_query_vectors = _encode_many(list(queries), role="raw")
    if use_hyde:
        cap_vectors = _encode_many(capability_texts, role="capability")
        con_vectors = _encode_many(constraint_texts, role="constraint")
    else:
        # Direct mode has identical texts; encode once for deterministic CI.
        cap_vectors = _encode_many(capability_texts, role="capability")
        con_vectors = cap_vectors
    return [
        QueryProfile(
            capability_text=capability_text,
            constraint_text=constraint_text,
            capability_vector=cap_vectors[index].tolist(),
            constraint_vector=con_vectors[index].tolist(),
            raw_query_text=queries[index],
            raw_query_vector=raw_query_vectors[index].tolist(),
            hard_requirements=infer_hard_requirements(queries[index]),
            profile_version=HYDE_PROFILE_VERSION if use_hyde else "direct-query-v1",
            generation_metadata=dict(generated[index]["metadata"]),
        )
        for index, (capability_text, constraint_text) in enumerate(text_pairs)
    ]


def encode_stored_query_profiles(
    stored_profiles: Sequence[Mapping[str, Any]],
) -> List[QueryProfile]:
    """Re-encode cached HyDE texts without making provider/API calls."""

    capability_texts = [str(item.get("capability_text") or "") for item in stored_profiles]
    constraint_texts = [str(item.get("constraint_text") or "") for item in stored_profiles]
    if any(not text for text in capability_texts + constraint_texts):
        raise ValueError("Stored query profile is missing capability/constraint text")
    cap_vectors = _encode_many(capability_texts, role="capability")
    con_vectors = _encode_many(constraint_texts, role="constraint")
    raw_query_texts = [
        str(
            (item.get("hard_requirements") or {}).get("original_query")
            or item.get("query")
            or ""
        )
        for item in stored_profiles
    ]
    if any(not text for text in raw_query_texts):
        raise ValueError("Stored query profile is missing its original query")
    raw_vectors = _encode_many(raw_query_texts, role="raw")
    return [
        QueryProfile(
            capability_text=capability_texts[index],
            constraint_text=constraint_texts[index],
            capability_vector=cap_vectors[index].tolist(),
            constraint_vector=con_vectors[index].tolist(),
            raw_query_text=raw_query_texts[index],
            raw_query_vector=raw_vectors[index].tolist(),
            hard_requirements=dict(item.get("hard_requirements") or {}),
            profile_version=str(item.get("profile_version") or "typed-query-v1"),
            generation_metadata=dict(item.get("generation_metadata") or {"status": "cache"}),
        )
        for index, item in enumerate(stored_profiles)
    ]


def attach_concatenated_vectors(
    profiles: Sequence[QueryProfile],
) -> List[QueryProfile]:
    """Batch-compute the legacy concatenated-HyDE vector for ablation only."""

    missing = [profile for profile in profiles if profile.concatenated_vector is None]
    if not missing:
        return list(profiles)
    combined = _encode_many(
        [
            profile.capability_text + "\n---\n" + profile.constraint_text
            for profile in missing
        ]
    )
    iterator = iter(combined)
    output: List[QueryProfile] = []
    for profile in profiles:
        if profile.concatenated_vector is None:
            output.append(replace(profile, concatenated_vector=next(iterator).tolist()))
        else:
            output.append(profile)
    return output


def _model_api_id(raw: Mapping[str, Any]) -> str:
    type_specific = raw.get("type_specific")
    model = type_specific.get("model") if isinstance(type_specific, Mapping) else {}
    execution = raw.get("execution")
    execution = execution if isinstance(execution, Mapping) else {}
    return str(
        (model.get("model_id") if isinstance(model, Mapping) else None)
        or execution.get("model_id")
        or ""
    )


def resource_passes_hard_requirements(
    resource_id: str,
    task_requirements: Mapping[str, Any] | None = None,
) -> Tuple[bool, str | None]:
    """Apply deterministic base and explicit task gates."""

    _engine.ensure_loaded()
    assert _engine.metadata is not None
    raw = _engine.metadata["id_to_resource"].get(resource_id)
    if not isinstance(raw, Mapping):
        return False, "resource_not_indexed"
    from sgar_mvp.src.model_selection import is_candidate_resource
    if not is_candidate_resource(raw):
        return False, "model_not_candidate"
    hard = _engine.metadata.get("hard_requirements", {}).get(resource_id, {})
    status = str(hard.get("status") or "active").lower()
    execution_status = str(hard.get("execution_status") or "active").lower()
    if status not in {"active", "available", "ok", "ready", ""}:
        return False, "inactive_resource"
    if execution_status not in {"active", "available", "ok", "ready", ""}:
        return False, "inactive_execution"
    rtype = _resource_type(raw)
    if rtype == "Model":
        model_id = _model_api_id(raw)
        if resource_id in _engine.unavailable_model_ids or model_id in _engine.unavailable_model_ids:
            return False, "model_health_gate"
        requirements = task_requirements or {}
        supports = hard.get("supports") if isinstance(hard.get("supports"), Mapping) else {}
        for feature in requirements.get("required_model_features", []):
            if supports.get(feature) is not True:
                return False, f"missing_model_feature:{feature}"
        minimum = requirements.get("min_context_tokens")
        available = hard.get("context_tokens")
        if minimum and (not available or int(available) < int(minimum)):
            return False, "insufficient_context_window"
    if rtype == "Skill":
        requirements = task_requirements or {}
        query = str(requirements.get("original_query") or "").lower()
        for cue in hard.get("avoid_when", []):
            normalized = str(cue).strip().lower()
            if len(normalized) >= 5 and normalized in query:
                return False, "skill_avoid_when"
        ids = set(_engine.metadata["id_to_resource"])
        missing = set(hard.get("required_resource_ids", [])) - ids
        if missing:
            return False, "missing_skill_dependency"
    return True, None


def _semantic_scores(
    profile: QueryProfile,
    strategy: str,
    resource_type: str | None,
    type_weights: Mapping[str, Tuple[float, float]] | None = None,
) -> List[Dict[str, Any]]:
    _engine.ensure_loaded()
    assert _engine.metadata is not None
    assert _engine.cap_matrix is not None and _engine.con_matrix is not None

    if strategy == "concatenated_hyde":
        combined = profile.concatenated_vector or encode_query(
            profile.capability_text + "\n---\n" + profile.constraint_text
        )
        cap_query = np.asarray(combined, dtype="float32")
        con_query = cap_query
    else:
        cap_query = np.asarray(profile.capability_vector, dtype="float32")
        con_query = np.asarray(profile.constraint_vector, dtype="float32")

    cap_scores = _engine.cap_matrix @ cap_query
    con_scores = _engine.con_matrix @ con_query
    raw_scores: np.ndarray | None = None
    if strategy == "raw_capability_rrf":
        if profile.raw_query_vector is None:
            raise ValueError("raw_capability_rrf requires an encoded raw query")
        raw_query = np.asarray(profile.raw_query_vector, dtype="float32")
        raw_scores = _engine.cap_matrix @ raw_query

    # RRF is computed independently inside each resource type. This prevents
    # the score distribution of a large Tool pool from displacing Model,
    # Agent, or Skill candidates and preserves the typed retrieval contract.
    rrf_scores: Dict[int, float] = {}
    if raw_scores is not None:
        grouped: Dict[str, List[int]] = {}
        for index in range(len(cap_scores)):
            resource_id = _engine.metadata["idx_to_id"][index]
            raw = _engine.metadata["id_to_resource"][resource_id]
            rtype = _resource_type(raw)
            from sgar_mvp.src.model_selection import is_candidate_resource
            if not is_candidate_resource(raw):
                continue
            if resource_type and rtype != resource_type:
                continue
            grouped.setdefault(rtype, []).append(index)
        rrf_k = 60.0
        normalizer = 2.0 / (rrf_k + 1.0)
        for indices in grouped.values():
            cap_order = sorted(
                indices,
                key=lambda item: (float(cap_scores[item]), _engine.metadata["idx_to_id"][item]),
                reverse=True,
            )
            raw_order = sorted(
                indices,
                key=lambda item: (float(raw_scores[item]), _engine.metadata["idx_to_id"][item]),
                reverse=True,
            )
            cap_rank = {item: rank for rank, item in enumerate(cap_order, start=1)}
            raw_rank = {item: rank for rank, item in enumerate(raw_order, start=1)}
            for item in indices:
                rrf_scores[item] = (
                    1.0 / (rrf_k + cap_rank[item])
                    + 1.0 / (rrf_k + raw_rank[item])
                ) / normalizer
    output: List[Dict[str, Any]] = []
    for index in range(len(cap_scores)):
        resource_id = _engine.metadata["idx_to_id"][index]
        raw = _engine.metadata["id_to_resource"][resource_id]
        rtype = _resource_type(raw)
        from sgar_mvp.src.model_selection import is_candidate_resource
        if not is_candidate_resource(raw):
            continue
        if resource_type and rtype != resource_type:
            continue
        cap_score = float(cap_scores[index])
        con_score = float(con_scores[index])
        if strategy == "capability_only":
            semantic_score = cap_score
        elif strategy == "raw_capability_rrf":
            semantic_score = rrf_scores[index]
        else:
            w_cap, w_con = (type_weights or TYPE_WEIGHTS).get(rtype, (0.70, 0.30))
            semantic_score = w_cap * cap_score + w_con * con_score
        output.append(
            {
                "resource_id": resource_id,
                "resource_type": rtype,
                "score": semantic_score,
                "capability_score": cap_score,
                "constraint_score": con_score,
                "raw_query_score": (
                    float(raw_scores[index]) if raw_scores is not None else None
                ),
                "utility_adjustment": 0.0,
                "hard_gate": "not_applied",
            }
        )
    return output


def _apply_utility_rerank(items: List[Dict[str, Any]]) -> None:
    assert _engine.metadata is not None
    empirical = [
        item
        for item in items
        if _engine.metadata.get("utility_profiles", {})
        .get(item["resource_id"], {})
        .get("ranking_enabled")
    ]
    if not empirical:
        return
    for item in empirical:
        utility = _engine.metadata["utility_profiles"][item["resource_id"]]
        success = max(0.0, min(1.0, float(utility.get("expected_success_rate") or 0.5)))
        # Bounded to ±0.025 so semantic fit remains dominant.
        adjustment = 0.05 * (success - 0.5)
        item["utility_adjustment"] = adjustment
        item["score"] += adjustment


def rank_resources(
    profile: QueryProfile,
    *,
    strategy: str | None = None,
    resource_type: str | None = None,
    top_k: int = TOP_K,
    type_weights: Mapping[str, Tuple[float, float]] | None = None,
) -> List[Dict[str, Any]]:
    selected_strategy = str(strategy or RETRIEVAL_POLICY.active_strategy)
    return rank_resources_with_trace(
        profile,
        strategy=selected_strategy,
        resource_type=resource_type,
        top_k=top_k,
        type_weights=type_weights,
    )["ranked"]


def rank_resources_with_trace(
    profile: QueryProfile,
    *,
    strategy: str | None = None,
    resource_type: str | None = None,
    top_k: int = TOP_K,
    type_weights: Mapping[str, Tuple[float, float]] | None = None,
) -> Dict[str, List[Dict[str, Any]]]:
    strategy = str(strategy or RETRIEVAL_POLICY.active_strategy)
    if strategy not in RETRIEVAL_STRATEGIES and strategy != SHADOW_RETRIEVAL_STRATEGY:
        raise ValueError(f"Unknown retrieval strategy: {strategy}")
    items = _semantic_scores(profile, strategy, resource_type, type_weights)
    pre_gate = sorted(
        (dict(item) for item in items),
        key=lambda item: (item["score"], item["capability_score"]),
        reverse=True,
    )
    rejected: List[Dict[str, Any]] = []
    if strategy in {"dual_hard", "dual_hard_utility"}:
        gated: List[Dict[str, Any]] = []
        for item in items:
            passed, reason = resource_passes_hard_requirements(
                item["resource_id"], profile.hard_requirements
            )
            item["hard_gate"] = "passed" if passed else str(reason)
            if passed:
                gated.append(item)
            else:
                rejected.append(dict(item))
        items = gated
    if strategy == "dual_hard_utility":
        _apply_utility_rerank(items)
    items.sort(key=lambda item: (item["score"], item["capability_score"]), reverse=True)
    return {
        "ranked": items[: max(0, top_k)],
        "pre_gate": pre_gate,
        "rejected": rejected,
    }


def rank_resources_shadow(
    profile: QueryProfile,
    *,
    resource_type: str | None = None,
    top_k: int = TOP_K,
    type_weights: Mapping[str, Tuple[float, float]] | None = None,
) -> List[Dict[str, Any]]:
    """Rank with capability/constraint weights without changing active policy.

    This is intentionally an explicit audit-only entry point.  It shares the
    same index, candidate filtering, and per-type weights as formal retrieval,
    but cannot be selected through ``retrieval_policy.json``.
    """

    return rank_resources_with_trace(
        profile,
        strategy=SHADOW_RETRIEVAL_STRATEGY,
        resource_type=resource_type,
        top_k=top_k,
        type_weights=type_weights,
    )["ranked"]


def utility_ranking_active_count() -> int:
    _engine.ensure_loaded()
    assert _engine.metadata is not None
    return sum(
        1
        for item in _engine.metadata.get("utility_profiles", {}).values()
        if item.get("ranking_enabled")
    )


def direct_retrieve(query: str, top_k: int = TOP_K, verbose: bool = True) -> List[Dict[str, Any]]:
    profile = encode_query_profile(query, use_hyde=False)
    ranked = rank_resources(
        profile,
        strategy=RETRIEVAL_POLICY.active_strategy,
        top_k=top_k,
    )
    if verbose:
        for item in ranked:
            print(
                f"{item['resource_id']} ({item['resource_type']}) "
                f"score={item['score']:.4f} "
                f"cap={item['capability_score']:.4f} "
                f"con={item['constraint_score']:.4f}"
            )
    assert _engine.metadata is not None
    return [_engine.metadata["id_to_resource"][item["resource_id"]] for item in ranked]


def hyde_retrieve(query: str, top_k: int = TOP_K, verbose: bool = True) -> List[Dict[str, Any]]:
    profile = encode_query_profile(query, use_hyde=True)
    ranked = rank_resources(
        profile,
        strategy=RETRIEVAL_POLICY.active_strategy,
        top_k=top_k,
    )
    if verbose:
        print(f"Capability HyDE: {profile.capability_text[:160]}")
        print(f"Constraint HyDE: {profile.constraint_text[:160]}")
        for item in ranked:
            print(
                f"{item['resource_id']} ({item['resource_type']}) "
                f"score={item['score']:.4f} "
                f"cap={item['capability_score']:.4f} "
                f"con={item['constraint_score']:.4f}"
            )
    assert _engine.metadata is not None
    return [_engine.metadata["id_to_resource"][item["resource_id"]] for item in ranked]


def get_resource_vectors(resource_id: str) -> Tuple[List[float], List[float]]:
    _engine.ensure_loaded()
    assert _engine.metadata is not None
    alias = _engine.metadata.get("duplicate_resource_aliases", {}).get(resource_id, resource_id)
    index = _engine.metadata["id_to_idx"][alias]
    return (
        _engine.metadata["cap_vectors"][index],
        _engine.metadata["con_vectors"][index],
    )


def get_all_resources() -> List[Dict[str, Any]]:
    _engine.ensure_loaded()
    assert _engine.metadata is not None
    return list(_engine.metadata["id_to_resource"].values())


def get_embedding_dim() -> int:
    _engine.ensure_loaded()
    assert _engine.metadata is not None
    return int(_engine.metadata["dim"])


def get_index_metadata() -> Dict[str, Any]:
    _engine.ensure_loaded()
    assert _engine.metadata is not None
    return _engine.metadata


def get_local_embedding_identity() -> LocalEmbeddingIdentity:
    """Validate and return the host-free offline embedding identity."""

    _engine.ensure_loaded()
    return _engine.local_embedding_identity()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--top-k", type=int, default=TOP_K)
    arguments = parser.parse_args()
    if arguments.direct:
        direct_retrieve(arguments.query, top_k=arguments.top_k)
    else:
        hyde_retrieve(arguments.query, top_k=arguments.top_k)
