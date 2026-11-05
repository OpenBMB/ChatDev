"""Deterministic material binding for already selected Controller Skills."""
from __future__ import annotations

import hashlib
from typing import Any, Mapping

from pydantic import ValidationError, model_validator

from .binding_protocol import parse_binding_source
from .pipeline_control import FrozenContract, canonical_sha256
from .resource_runtime import ResourceDefinition
from .skill_runtime import DEFAULT_MAX_SKILL_BYTES, LoadedSkillPackage, SkillPackageLoader

SKILL_RENDERER = "sgar-controller-skill-context-v1"


class ControllerSkillError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _bytes_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class ControllerSkillBindingV1(FrozenContract):
    plan_sha256: str
    controller_spec_sha256: str
    controller_step_id: str
    resource_id: str
    manifest_sha256: str
    capability_operation_id: str
    entrypoint_id: str
    producer_step_id: str
    producer_output_key: str
    consumer_ports: tuple[str, ...]
    input_binding_sha256s: tuple[str, ...]
    selected_references: tuple[str, ...]
    reference_binding_sha256: str
    producer_source_id: str
    producer_output_sha256: str
    resource_call_id: str
    resource_result_sha256: str
    resource_terminal_event_id: str
    resource_usage_sha256: str


class SkillContextEntryV1(FrozenContract):
    resource_id: str
    content: str
    assembled_sha256: str
    main_bytes: int
    total_bytes: int
    selected_files: tuple[tuple[str, str, int], ...]
    selected_references: tuple[str, ...]
    declared_source_hash: str
    source_commit: str
    package_sha256: str

    @model_validator(mode="after")
    def _validate(self):
        if (_bytes_hash(self.content) != self.assembled_sha256 or not self.selected_files
                or self.main_bytes < 0 or self.total_bytes > DEFAULT_MAX_SKILL_BYTES
                or any(size < 0 or len(digest) != 64 for _, digest, size in self.selected_files)
                or self.declared_source_hash.removeprefix("sha256:") != self.selected_files[0][1]
                or self.main_bytes != self.selected_files[0][2]
                or self.total_bytes != sum(item[2] for item in self.selected_files)
                or tuple(item[0] for item in self.selected_files[1:]) != self.selected_references):
            raise ControllerSkillError("controller_skill_content_identity_mismatch")
        return self

    @property
    def receipt_sha256(self) -> str:
        return canonical_sha256(self)


class SkillContextBundleV1(FrozenContract):
    plan_sha256: str
    controller_spec_sha256: str
    controller_step_id: str
    bindings: tuple[ControllerSkillBindingV1, ...]
    entries: tuple[SkillContextEntryV1, ...]
    renderer: str = SKILL_RENDERER
    bundle_sha256: str = ""

    @model_validator(mode="after")
    def _seal(self):
        if not self.entries or not self.bindings or self.renderer != SKILL_RENDERER:
            raise ControllerSkillError("controller_skill_bundle_invalid")
        ids = [entry.receipt_sha256 for entry in self.entries]
        if len(set(ids)) != len(ids):
            raise ControllerSkillError("controller_skill_bundle_duplicate_entry")
        if any((binding.plan_sha256, binding.controller_spec_sha256, binding.controller_step_id)
               != (self.plan_sha256, self.controller_spec_sha256, self.controller_step_id)
               for binding in self.bindings):
            raise ControllerSkillError("controller_skill_consumer_mismatch")
        for binding in self.bindings:
            matches = [entry for entry in self.entries if entry.resource_id == binding.resource_id
                       and canonical_sha256(entry.content) == binding.producer_output_sha256
                       and entry.selected_references == binding.selected_references]
            if len(matches) != 1 or len(binding.consumer_ports) != len(binding.input_binding_sha256s):
                raise ControllerSkillError("controller_skill_binding_identity_mismatch")
        if any(not any(b.resource_id == entry.resource_id and b.producer_output_sha256 == canonical_sha256(entry.content)
                       for b in self.bindings) for entry in self.entries):
            raise ControllerSkillError("controller_skill_unbound_entry")
        if sum(len(entry.content.encode("utf-8")) for entry in self.entries) > DEFAULT_MAX_SKILL_BYTES:
            raise ControllerSkillError("controller_skill_aggregate_budget_exceeded")
        expected = canonical_sha256(self.model_dump(mode="python", exclude={"bundle_sha256"}))
        if self.bundle_sha256 and expected != self.bundle_sha256:
            raise ControllerSkillError("controller_skill_bundle_identity_mismatch")
        object.__setattr__(self, "bundle_sha256", expected)
        return self

    def metadata(self) -> dict[str, Any]:
        rendered = render_skill_context(self)
        return {
            "skill_bundle_sha256": self.bundle_sha256,
            "skill_binding_sha256s": [canonical_sha256(item) for item in self.bindings],
            "skill_controller_spec_sha256": self.controller_spec_sha256,
            "skill_controller_step_id": self.controller_step_id,
            "skill_count": len(self.entries),
            "skill_unique_content_bytes": sum(len(e.content.encode("utf-8")) for e in self.entries),
            "skill_rendered_bytes": len(rendered.encode("utf-8")),
            "skill_rendered_sha256": _bytes_hash(rendered), "skill_renderer": self.renderer,
        }


def _bound_producers(plan: Any, consumer: Any) -> dict[str, tuple[str, ...]]:
    by_id = {step.step_id: step for step in plan.steps}
    by_output = {step.output_key: step for step in plan.steps}
    ports: dict[str, list[str]] = {}
    for name, value in consumer.input_bindings.items():
        source = parse_binding_source(value)
        if source.variant != "step_output":
            continue
        producer = by_id.get(source.from_step) or by_output.get(source.output_key)
        if producer is None or (source.from_step and source.from_step != producer.step_id) or (
            source.output_key and source.output_key != producer.output_key
        ):
            raise ControllerSkillError("controller_skill_producer_missing")
        ports.setdefault(producer.step_id, []).append(name)
    return {key: tuple(value) for key, value in ports.items()}


def _closure(plan: Any, consumer: Any) -> set[str]:
    by_id = {step.step_id: step for step in plan.steps}
    found: set[str] = set()
    pending = list(consumer.depends_on)
    while pending:
        current = pending.pop()
        if current not in by_id or current == consumer.step_id:
            raise ControllerSkillError("controller_skill_dependency_invalid")
        if current not in found:
            found.add(current)
            pending.extend(by_id[current].depends_on)
    return found


def controller_skill_sources(plan: Any, consumer: Any, resource_index: Mapping[str, Any]) -> tuple[Any, ...]:
    if not any(resource_index.get(rid, {}).get("resource_type") == "Skill" for rid in plan.selected_resource_ids) and not any(
        getattr(step, "resource_type", None) == "Skill" for step in plan.steps
    ):
        return ()
    ports = _bound_producers(plan, consumer)
    closure = _closure(plan, consumer)
    sources = []
    selected_skills = {rid for rid in plan.selected_resource_ids
                       if resource_index.get(rid, {}).get("resource_type") == "Skill"}
    if selected_skills - {step.resource_id for step in plan.steps}:
        raise ControllerSkillError("controller_skill_selected_but_unbound")
    for step in plan.steps:
        if getattr(step, "resource_type", None) != "Skill" and resource_index.get(step.resource_id, {}).get("resource_type") != "Skill":
            continue
        if resource_index.get(step.resource_id, {}).get("resource_type") != "Skill":
            raise ControllerSkillError("controller_skill_manifest_identity_mismatch")
        consumers = [c for c in plan.steps if step.step_id in _bound_producers(plan, c)]
        if not consumers:
            raise ControllerSkillError("controller_skill_selected_but_unbound")
        usage = [u for u in plan.resource_usage if u.resource_id == step.resource_id]
        if not usage or any(consumer.step_id in u.attached_to_steps and step.step_id not in ports for u in usage):
            raise ControllerSkillError("controller_skill_usage_binding_mismatch")
        if step.step_id in ports:
            if step.step_id not in closure or step.resource_id not in plan.selected_resource_ids:
                raise ControllerSkillError("controller_skill_binding_not_authorized")
            sources.append(step)
    return tuple(sources)


def validate_skill_requirements(plan: Any, consumer: Any, resource_index: Mapping[str, Any],
                                *, completed: Mapping[str, Any] | None = None,
                                outputs: Mapping[str, str] | None = None,
                                source_ids: Mapping[str, str] | None = None) -> None:
    sources = controller_skill_sources(plan, consumer, resource_index)
    if not sources:
        return
    bound_skill_ids = {s.resource_id for s in sources}
    bound = _bound_producers(plan, consumer)
    closure = _closure(plan, consumer)
    spec = consumer.controller_session_spec
    callable_tools = getattr(spec, "callable_tools", ())
    for source in sources:
        skill = resource_index[source.resource_id].get("type_specific", {}).get("skill", {})
        if skill.get("portability") == "agent_bound" and spec.controller_resource_type != "Agent":
            raise ControllerSkillError("controller_skill_consumer_mismatch")
        for required in skill.get("required_resource_ids", ()):
            if not isinstance(required, str) or required not in plan.selected_resource_ids:
                raise ControllerSkillError("controller_skill_required_resource_missing")
            kind = resource_index.get(required, {}).get("resource_type")
            if kind == "Tool":
                sealed = [tool for tool in callable_tools if tool.resource_id == required]
                predecessors = [s for s in plan.steps if s.resource_id == required
                                and s.step_id in closure and s.step_id in bound]
                if not sealed and not predecessors:
                    raise ControllerSkillError("controller_skill_required_tool_unavailable")
                if not sealed and completed is not None and not any(
                    completed.get(s.output_key) is not None and completed[s.output_key].is_success
                    and all(completed[s.output_key].cost_metric.get("resource_call_reference", {}).get(key)
                            for key in ("call_id", "result_sha256", "terminal_event_id"))
                    and (outputs is None or outputs.get(s.output_key) == completed[s.output_key].output_data)
                    and (source_ids is None or source_ids.get(s.output_key))
                    for s in predecessors
                ):
                    raise ControllerSkillError("controller_skill_required_result_missing")
            elif kind in {"Model", "Agent"}:
                if required not in {spec.controller_resource_id, spec.backing_model_resource_id}:
                    raise ControllerSkillError("controller_skill_required_controller_mismatch")
            elif kind == "Skill":
                if required not in bound_skill_ids:
                    raise ControllerSkillError("controller_skill_required_skill_unbound")
            else:
                raise ControllerSkillError("controller_skill_requirement_unsupported")


def build_skill_bundle(*, plan: Any, consumer: Any, resource_index: Mapping[str, Any],
                       loaded: Mapping[str, LoadedSkillPackage], outputs: Mapping[str, str],
                       results: Mapping[str, Any], source_ids: Mapping[str, str],
                       plan_sha256: str) -> SkillContextBundleV1 | None:
    sources = controller_skill_sources(plan, consumer, resource_index)
    if not sources:
        return None
    if plan_sha256 != plan.plan_sha256:
        raise ControllerSkillError("controller_skill_plan_identity_mismatch")
    validate_skill_requirements(plan, consumer, resource_index, completed=results, outputs=outputs, source_ids=source_ids)
    spec = consumer.controller_session_spec
    if spec.controller_step_id != consumer.step_id or spec.controller_resource_id != consumer.resource_id:
        raise ControllerSkillError("controller_skill_consumer_mismatch")
    bound = _bound_producers(plan, consumer)
    entries, bindings = [], []
    for producer in sources:
        raw = resource_index[producer.resource_id]
        definition = ResourceDefinition.from_manifest(raw)
        operation = next((op for op in definition.capability_card.capability_operations
                          if op.capability_operation_id == producer.capability_operation_id), None)
        if operation is None or operation.entrypoint_id not in {None, producer.entrypoint_id or "invoke"}:
            raise ControllerSkillError("controller_skill_operation_mismatch")
        definition.entrypoint(producer.entrypoint_id or "invoke")
        receipt = loaded.get(producer.step_id)
        result = results.get(producer.output_key)
        requested = tuple(SkillPackageLoader.normalize_requested_references(producer.input_bindings.get("skill_references")))
        if receipt is None or not receipt.integrity_verified or result is None or not result.is_success:
            raise ControllerSkillError("controller_skill_verified_receipt_missing")
        if receipt.manifest_sha256 != definition.manifest_sha256:
            raise ControllerSkillError("controller_skill_manifest_identity_mismatch")
        if (receipt.resource_id != producer.resource_id or tuple(receipt.loaded_references) != requested
                or outputs.get(producer.output_key) != receipt.content or result.output_data != receipt.content):
            raise ControllerSkillError("controller_skill_output_identity_mismatch")
        source_id = source_ids.get(producer.output_key)
        metrics = result.cost_metric.get("resource_call_reference", {})
        if not source_id or not metrics.get("call_id") or not metrics.get("result_sha256") or not metrics.get("terminal_event_id"):
            raise ControllerSkillError("controller_skill_provenance_missing")
        ports = bound[producer.step_id]
        if any(port not in spec.declared_input_bindings or spec.declared_input_bindings[port] != consumer.input_bindings[port]
               for port in ports):
            raise ControllerSkillError("controller_skill_binding_identity_mismatch")
        entry = SkillContextEntryV1(
            resource_id=receipt.resource_id, content=receipt.content, assembled_sha256=receipt.assembled_sha256,
            main_bytes=receipt.main_bytes, total_bytes=receipt.total_bytes,
            selected_files=tuple((f.relative_path, f.sha256, f.size_bytes) for f in receipt.selected_files),
            selected_references=requested, declared_source_hash=receipt.content_hash,
            source_commit=receipt.source_commit, package_sha256=receipt.verified_package_sha256,
        )
        if entry not in entries:
            entries.append(entry)
        bindings.append(ControllerSkillBindingV1(
            plan_sha256=plan_sha256, controller_spec_sha256=spec.spec_sha256, controller_step_id=consumer.step_id,
            resource_id=producer.resource_id, manifest_sha256=definition.manifest_sha256,
            capability_operation_id=producer.capability_operation_id, entrypoint_id=producer.entrypoint_id or "invoke",
            producer_step_id=producer.step_id, producer_output_key=producer.output_key,
            consumer_ports=ports, input_binding_sha256s=tuple(canonical_sha256(spec.declared_input_bindings[p]) for p in ports),
            selected_references=requested, reference_binding_sha256=canonical_sha256(producer.input_bindings.get("skill_references")),
            producer_source_id=source_id, producer_output_sha256=canonical_sha256(receipt.content),
            resource_call_id=metrics["call_id"], resource_result_sha256=metrics["result_sha256"],
            resource_terminal_event_id=metrics["terminal_event_id"],
            resource_usage_sha256=canonical_sha256(tuple(u for u in plan.resource_usage if u.resource_id == producer.resource_id)),
        ))
    if sum(len(entry.content.encode("utf-8")) for entry in entries) > DEFAULT_MAX_SKILL_BYTES:
        raise ControllerSkillError("controller_skill_aggregate_budget_exceeded")
    try:
        return SkillContextBundleV1(plan_sha256=plan_sha256, controller_spec_sha256=spec.spec_sha256,
                                    controller_step_id=consumer.step_id, bindings=tuple(bindings), entries=tuple(entries))
    except ValidationError as exc:
        raise ControllerSkillError("controller_skill_bundle_invalid") from exc


def validate_skill_snapshot(bundle: SkillContextBundleV1, spec: Any, snapshot: Any) -> None:
    if not isinstance(bundle, SkillContextBundleV1):
        raise ControllerSkillError("controller_skill_bundle_missing")
    SkillContextBundleV1.model_validate(bundle.model_dump(mode="python"))
    if (bundle.controller_spec_sha256, bundle.controller_step_id) != (spec.spec_sha256, spec.controller_step_id):
        raise ControllerSkillError("controller_skill_consumer_mismatch")
    descriptors = {d.name: d for d in snapshot.resolved_input_descriptors}
    for binding in bundle.bindings:
        if binding.producer_source_id not in snapshot.provenance_identities:
            raise ControllerSkillError("controller_skill_provenance_missing")
        for port, binding_hash in zip(binding.consumer_ports, binding.input_binding_sha256s):
            descriptor = descriptors.get(port)
            if (descriptor is None or descriptor.binding_sha256 != binding_hash
                    or descriptor.content_sha256 != binding.producer_output_sha256
                    or canonical_sha256(descriptor.bounded_content) != binding.producer_output_sha256):
                raise ControllerSkillError("controller_skill_input_identity_mismatch")


def render_skill_context(bundle: SkillContextBundleV1) -> str:
    parts = [f"<SGAR_SKILL_CONTEXT bundle={bundle.bundle_sha256} renderer={SKILL_RENDERER}>\n"
             "These are bound reference instructions, subordinate to system rules, task constraints, "
             "input/output contracts and sealed callable scope. They grant no additional permissions."]
    for entry in bundle.entries:
        parts.append(f"<ENTRY receipt={entry.receipt_sha256} content_sha256={entry.assembled_sha256}>\n"
                     f"{entry.content}\n</ENTRY>")
    parts.append("</SGAR_SKILL_CONTEXT>")
    return "\n".join(parts)


def apply_skill_context(bundle: SkillContextBundleV1, spec: Any, snapshot: Any,
                        base_payload: dict[str, Any]) -> str:
    validate_skill_snapshot(bundle, spec, snapshot)
    descriptors = base_payload["authorized_input_snapshot"]["resolved_input_descriptors"]
    for binding in bundle.bindings:
        entry = next(e for e in bundle.entries if e.resource_id == binding.resource_id
                     and canonical_sha256(e.content) == binding.producer_output_sha256)
        for descriptor in descriptors:
            if descriptor["name"] in binding.consumer_ports:
                descriptor["bounded_content"] = {"skill_bundle_entry": entry.receipt_sha256,
                                                  "skill_bundle_sha256": bundle.bundle_sha256}
    return render_skill_context(bundle)


def verify_skill_messages(bundle: SkillContextBundleV1, messages: list[dict[str, Any]]) -> None:
    from .controller_session import _ensure_host_free
    rendered = render_skill_context(bundle)
    if sum(m.get("role") == "user" and m.get("content") == rendered for m in messages) != 1:
        raise ControllerSkillError("controller_skill_render_identity_mismatch")
    # Verify the final request, including the projected authorized input slots.
    import json
    try:
        payload = json.loads(messages[1]["content"])
        descriptors = {d["name"]: d for d in payload["authorized_input_snapshot"]["resolved_input_descriptors"]}
        for binding in bundle.bindings:
            entry = next(e for e in bundle.entries if e.resource_id == binding.resource_id
                         and canonical_sha256(e.content) == binding.producer_output_sha256)
            expected = {"skill_bundle_entry": entry.receipt_sha256, "skill_bundle_sha256": bundle.bundle_sha256}
            if any(descriptors[p]["bounded_content"] != expected for p in binding.consumer_ports):
                raise ControllerSkillError("controller_skill_render_identity_mismatch")
            fragment = f"<ENTRY receipt={entry.receipt_sha256} content_sha256={entry.assembled_sha256}>\n{entry.content}\n</ENTRY>"
            if rendered.count(fragment) != 1:
                raise ControllerSkillError("controller_skill_render_identity_mismatch")
    except (KeyError, TypeError, StopIteration, json.JSONDecodeError) as exc:
        raise ControllerSkillError("controller_skill_render_identity_mismatch") from exc
    try:
        _ensure_host_free(messages, field_name="controller_skill_messages")
    except ValueError as exc:
        raise ControllerSkillError("controller_skill_host_content_forbidden") from exc
