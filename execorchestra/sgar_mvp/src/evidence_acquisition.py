"""Select actual execution routes for inferred evidence duties, without asserting truth."""
from .capability_operations import normalize_capability_operation


def equivalent_acquisition_operations(resources):
    """Index alternate declarations of the same native Tool execution contract.

    Both frozen compiler cards and runtime definitions expose this contract.
    Equality is local to one resource and includes the entrypoint, ports,
    artifacts, effects, modalities and evidence semantics. Names and their
    derived identity hashes alone may differ. This grants no execution credit.
    """
    equivalent = {}
    for resource in resources:
        if (resource.resource_type != "Tool"
                or getattr(resource, "compatibility_status", None) == "incompatible"):
            continue
        operations = getattr(resource, "capability_operations", None)
        if operations is None:
            operations = getattr(getattr(resource, "capability_card", None), "capability_operations", ())
        entrypoint_ids = {entry.entrypoint_id for entry in getattr(resource, "entrypoints", ())}
        groups = []
        for operation in operations:
            if (getattr(operation, "entrypoint_id", None) not in entrypoint_ids
                    or not callable(getattr(operation, "model_dump", None))):
                continue
            contract = operation.model_dump(mode="json")
            for field in ("capability_operation_id", "declared_operation", "operation_sha256"):
                contract.pop(field, None)
            for signature, members in groups:
                if contract == signature:
                    members.append(operation.capability_operation_id)
                    break
            else:
                groups.append((contract, [operation.capability_operation_id]))
        for _, members in groups:
            if len(members) > 1:
                for operation_id in members:
                    equivalent[operation_id] = tuple(sorted(other for other in members if other != operation_id))
    return equivalent


def execution_acquisition_operations(contract):
    """Keep source discovery optional only when the task contract declares it so.

    Retrieval still sees all inferred acquisition capabilities. An explicitly
    required search operation is never removed, and fetching/source validation
    remain separate duties. Legacy contracts keep their original operations.
    """
    operations = tuple(getattr(contract, "evidence_acquisition_operations", ()))
    required = {normalize_capability_operation(v) for v in contract.required_operation_kinds}
    if getattr(contract, "external_discovery_mode", None) != "if_needed" or "search_web" in required:
        return operations
    return tuple(v for v in operations if normalize_capability_operation(v) != "search_web")


def evidence_route_operations(*, required, acquisition, selected_operation_ids,
                              network_execution_operation_ids=(), acquisition_execution_required=True,
                              equivalent_operation_ids=None):
    selected_operation_ids = tuple(selected_operation_ids)
    network_execution_operation_ids = frozenset(network_execution_operation_ids)
    selected = {normalize_capability_operation(str(v).rsplit("::", 1)[-1])
                for v in selected_operation_ids if v}
    # These are capability operation families, never resource or task IDs.
    # A generic processor counts only when the selected invocation declares
    # network use. Compatibility and network authorization are checked by the
    # caller/readiness; execution and evidence validation remain mandatory.
    network_selected = {
        normalize_capability_operation(str(v).rsplit("::", 1)[-1])
        for v in set(network_execution_operation_ids) & set(selected_operation_ids)
    }
    composite = next((kind for kind in (
        "execute_shell_commands", "generated_code_execution", "python_execution",
        "browser_capture",
    ) if kind in selected and (kind == "execute_shell_commands" or kind in network_selected)), None)
    result = {normalize_capability_operation(v) for v in required}
    missing = []
    for operation in acquisition:
        kind = normalize_capability_operation(operation)
        # Credit the operation that must actually run, never its unexecuted
        # alternate name. Web acquisition still needs a declared network route.
        equivalent_selected = next((normalize_capability_operation(str(selected_id).rsplit("::", 1)[-1])
            for selected_id in sorted(selected_operation_ids)
            # Search has an operation-specific nonempty-result check. Retain
            # its exact route rather than bypassing that check with an alias.
            if kind != "search_web" and (kind != "fetch_web_resource"
                or selected_id in network_execution_operation_ids)
            and any(normalize_capability_operation(str(other).rsplit("::", 1)[-1]) == kind
                    for other in (equivalent_operation_ids or {}).get(selected_id, ()))), None)
        if kind in selected:
            result.add(kind)
        elif equivalent_selected:
            result.add(equivalent_selected)
        elif composite and kind in {"fetch_web_resource", "search_web"}:
            # A source-acquisition program is an executable route. Its result
            # and source coverage still need inspection; a shell declaration
            # never establishes that any website was fetched or any fact true.
            result.add(composite)
        else:
            missing.append(kind)
    if not acquisition_execution_required:
        # The conditional route remains required at compilation. Only its actual
        # invocation is deferred until material inspection identifies a gap.
        # Explicitly required operations are never made optional by this mode.
        result = {normalize_capability_operation(v) for v in required}
    return tuple(sorted(result)), tuple(sorted(missing))
