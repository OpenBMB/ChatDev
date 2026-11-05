"""Share identical model-visible inputs without changing the sealed snapshot."""
from collections import defaultdict
from copy import deepcopy
from typing import Any, Mapping

from .pipeline_control import canonical_json_bytes, canonical_sha256
from .workspace_inventory_projection import project_workspace_metadata


def project_controller_input_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    original = {"authorized_input_snapshot": dict(snapshot)}
    occurrences: dict[bytes, list[int]] = defaultdict(list)
    descriptors = snapshot.get("resolved_input_descriptors", ())
    for index, descriptor in enumerate(descriptors):
        if "bounded_content" in descriptor:
            occurrences[canonical_json_bytes(descriptor["bounded_content"])].append(index)
    duplicates = [indices for indices in occurrences.values() if len(indices) > 1]
    if not duplicates:
        return project_workspace_metadata(original)
    projected = deepcopy(dict(snapshot))
    shared = {}
    for indices in duplicates:
        content = descriptors[indices[0]]["bounded_content"]
        identity = canonical_sha256(content)
        shared[identity] = deepcopy(content)
        for index in indices:
            descriptor = projected["resolved_input_descriptors"][index]
            descriptor.pop("bounded_content")
            descriptor["bounded_content_ref"] = identity
    result = {
        "authorized_input_snapshot": projected,
        "shared_input_materials": shared,
        "input_material_reference_rule": (
            "Each descriptor's bounded_content_ref names its complete content in "
            "shared_input_materials. Port bindings and hashes retain the original "
            "snapshot authority; sharing does not remove or change any input."
        ),
    }
    shared_view = result if len(canonical_json_bytes(result)) < len(canonical_json_bytes(original)) else original
    return project_workspace_metadata(shared_view)
