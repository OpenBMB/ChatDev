"""Lossless semantic factoring of workspace metadata for model requests.

The sealed inputs remain unchanged. This view shares path collections and
per-file metadata; no files, constraints or content facts are discarded.
"""
from copy import deepcopy
import json
import posixpath
import re
from typing import Any, Mapping

from .pipeline_control import canonical_json_bytes, canonical_sha256


PATH_RULE = (
    "workspace_path_sets contains complete ordered path collections. Each paths row "
    "is [directory_index, basename]; join directories[directory_index] and basename "
    "with '/'. authorized_runtime_paths_ref names one such collection. A files object "
    "with encoding=workspace-file-metadata-v1 uses path_set_ref for its paths; "
    "metadata_indices[i] selects metadata for path i. All original per-file facts "
    "are retained. These are unread inventory facts, not file contents. Sealed "
    "hashes refer to the original inputs, before this model-view projection."
)

SHARED_PATH_RULE = (
    "When basenames is present, integer basename entries index that table. "
    "A directories entry [parent_index, name] joins an earlier directory entry "
    "and name with '/'; a string entry is already a directory path."
)

SEQUENCE_RULE = (
    "A path table may use path_sequences instead of paths. Read entries in order: "
    "a [directory_index, basename] entry is one path; a numeric entry expands count "
    "basenames as prefix + str(start+i).zfill(width) + suffix for i=0..count-1, "
    "under directories[directory_index]. This is the complete exact collection, "
    "including gaps represented by separate entries, not a sample or glob. "
    "metadata_indices with encoding=runs expands each [index,count] in order. "
    "A runtime_fixed_arguments value with workspace_path_set_ref is that complete "
    "list, already bound by the runtime; do not copy the reference into Tool arguments."
)


def _compact_path_table(directories, rows):
    """Encode only exact consecutive numeric names; preserve order and gaps."""
    sequences = []
    offset = 0
    while offset < len(rows):
        directory, name = rows[offset]
        best_count, best = 1, None
        for match in re.finditer(r"[0-9]+", name):
            prefix, digits, suffix = name[:match.start()], match.group(), name[match.end():]
            start, width = int(digits), len(digits)
            count = 1
            while offset + count < len(rows):
                expected = prefix + str(start + count).zfill(width) + suffix
                if rows[offset + count] != [directory, expected]:
                    break
                count += 1
            if count > best_count:
                best_count = count
                best = {"directory_index": directory, "prefix": prefix, "suffix": suffix,
                        "start": start, "width": width, "count": count}
        if best is not None and len(canonical_json_bytes(best)) < len(canonical_json_bytes(rows[offset:offset+best_count])):
            sequences.append(best)
            offset += best_count
        else:
            sequences.append([directory, name])
            offset += 1
    original = {"directories": directories, "paths": rows}
    compact = {"directories": directories, "path_sequences": sequences}
    basenames, indices, shared_rows = [], {}, []
    for directory, name in rows:
        if name not in indices:
            indices[name] = len(basenames)
            basenames.append(name)
        shared_rows.append([directory, indices[name]])
    shared = {"directories": directories, "basenames": basenames, "paths": shared_rows}
    options = [original, compact, shared]
    nodes, node_indices = [], {}
    def intern_directory(directory):
        if directory not in node_indices:
            parent, basename = posixpath.split(directory)
            value = [intern_directory(parent), basename] if parent and parent != directory and basename else directory
            node_indices[directory] = len(nodes)
            nodes.append(value)
        return node_indices[directory]
    mapped = [intern_directory(directory) for directory in directories]
    for value in (original, compact, shared):
        factored = deepcopy(value)
        factored['directories'] = nodes
        key = 'paths' if 'paths' in factored else 'path_sequences'
        for row in factored[key]:
            if isinstance(row, list):
                row[0] = mapped[row[0]]
            else:
                row['directory_index'] = mapped[row['directory_index']]
        options.append(factored)
    # Account for the extra representation rule before choosing a new encoding.
    def cost(value):
        extra = bool('basenames' in value or any(isinstance(item, list) for item in value['directories']))
        return len(canonical_json_bytes(value)) + (len(SHARED_PATH_RULE) if extra else 0)
    return min(options, key=cost)


def _expand_path_table(table):
    directories = []
    for item in table['directories']:
        directories.append(posixpath.join(directories[item[0]], item[1]) if isinstance(item, list) else item)
    rows = table.get("paths")
    if rows is None:
        rows = []
        for entry in table["path_sequences"]:
            if isinstance(entry, list):
                rows.append(entry)
            else:
                rows.extend([entry["directory_index"], entry["prefix"] +
                             str(entry["start"] + i).zfill(entry["width"]) + entry["suffix"]]
                            for i in range(entry["count"]))
    return [posixpath.join(directories[directory],
                          table["basenames"][name] if isinstance(name, int) else name)
            for directory, name in rows]


def project_runtime_fixed_arguments(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Represent fixed path lists exactly, whether or not also bound as context."""
    tables = payload.get("workspace_path_sets", {})
    if not payload.get("authorized_tool_functions"):
        return dict(payload)
    collections = {canonical_json_bytes(_expand_path_table(table)): identity
                   for identity, table in tables.items()}
    result = deepcopy(dict(payload))
    projected_tables = deepcopy(dict(tables))
    for tool in result["authorized_tool_functions"]:
        for name, value in tool.get("runtime_fixed_arguments", {}).items():
            if isinstance(value, list):
                identity = collections.get(canonical_json_bytes(value))
                if identity is None and value and all(
                    isinstance(path, str) and posixpath.isabs(path)
                    and posixpath.join(*posixpath.split(path)) == path for path in value
                ):
                    directories, indices, rows = [], {}, []
                    for path in value:
                        directory, basename = posixpath.split(path)
                        if directory not in indices:
                            indices[directory] = len(directories)
                            directories.append(directory)
                        rows.append([indices[directory], basename])
                    table = _compact_path_table(directories, rows)
                    candidate_id = canonical_sha256(value)
                    if len(canonical_json_bytes(table)) + len(candidate_id) + 128 < len(canonical_json_bytes(value)):
                        identity = candidate_id
                        projected_tables[identity] = table
                        collections[canonical_json_bytes(value)] = identity
                ref = {"workspace_path_set_ref": identity}
                if identity and len(canonical_json_bytes(ref)) < len(canonical_json_bytes(value)):
                    tool["runtime_fixed_arguments"][name] = ref
    if projected_tables:
        result["workspace_path_sets"] = projected_tables
    if len(canonical_json_bytes(result)) >= len(canonical_json_bytes(payload)):
        return dict(payload)
    if not result.get("workspace_inventory_view_rule"):
        result["workspace_inventory_view_rule"] = PATH_RULE
    if SEQUENCE_RULE not in result.get("workspace_inventory_view_rule", ""):
        result["workspace_inventory_view_rule"] = result.get("workspace_inventory_view_rule", "") + " " + SEQUENCE_RULE
    if any('basenames' in table or any(isinstance(item, list) for item in table['directories'])
           for table in projected_tables.values()) and SHARED_PATH_RULE not in result['workspace_inventory_view_rule']:
        result['workspace_inventory_view_rule'] += " " + SHARED_PATH_RULE
    return result if len(canonical_json_bytes(result)) < len(canonical_json_bytes(payload)) else dict(payload)


def project_workspace_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Factor only explicitly typed workspace inventories and their contracts."""
    if "workspace_path_sets" in payload:
        return dict(payload)
    path_sets: dict[str, Any] = {}

    def intern(paths):
        identity = canonical_sha256(paths)
        if identity not in path_sets:
            directories: list[str] = []
            index: dict[str, int] = {}
            rows = []
            for path in paths:
                directory, name = posixpath.split(path)
                if directory not in index:
                    index[directory] = len(directories)
                    directories.append(directory)
                rows.append([index[directory], name])
            path_sets[identity] = _compact_path_table(directories, rows)
        return identity

    def visit(value):
        if isinstance(value, str) and value.lstrip().startswith("{") and '"workspace_file_inventory"' in value:
            try:
                decoded = json.loads(value)
            except (ValueError, TypeError):
                return value
            contract = decoded.get("representation_contract") if isinstance(decoded, dict) else None
            if isinstance(contract, Mapping) and contract.get("contract_kind") == "workspace_file_inventory":
                return json.dumps(visit(decoded), ensure_ascii=False, separators=(",", ":"))
            return value
        if isinstance(value, (list, tuple)):
            return [visit(item) for item in value]
        if not isinstance(value, Mapping):
            return value
        result = {key: visit(item) for key, item in value.items()}
        if value.get("contract_kind") == "workspace_file_inventory":
            paths = value.get("authorized_runtime_paths")
            if isinstance(paths, (list, tuple)) and all(isinstance(path, str) for path in paths):
                result.pop("authorized_runtime_paths")
                result["authorized_runtime_paths_ref"] = intern(list(paths))
        contract = value.get("representation_contract")
        files = value.get("files")
        if (isinstance(contract, Mapping) and contract.get("contract_kind") == "workspace_file_inventory"
                and isinstance(files, list) and files
                and all(isinstance(item, Mapping) and isinstance(item.get("path"), str) for item in files)):
            metadata: list[dict[str, Any]] = []
            index: dict[bytes, int] = {}
            rows = []
            for item in files:
                facts = {key: deepcopy(child) for key, child in item.items() if key != "path"}
                encoded = canonical_json_bytes(facts)
                if encoded not in index:
                    index[encoded] = len(metadata)
                    metadata.append(facts)
                rows.append(index[encoded])
            runs = []
            for index_value in rows:
                if runs and runs[-1][0] == index_value:
                    runs[-1][1] += 1
                else:
                    runs.append([index_value, 1])
            encoded_indices = {"encoding": "runs", "values": runs}
            result["files"] = {
                "encoding": "workspace-file-metadata-v1",
                "path_set_ref": intern([item["path"] for item in files]),
                "metadata": metadata, "metadata_indices": (
                    encoded_indices if len(canonical_json_bytes(encoded_indices)) < len(canonical_json_bytes(rows)) else rows
                ),
            }
        return result

    result = visit(payload)
    if not path_sets:
        return dict(payload)
    result["workspace_path_sets"] = path_sets
    result["workspace_inventory_view_rule"] = PATH_RULE + " " + SEQUENCE_RULE
    if any('basenames' in table or any(isinstance(item, list) for item in table['directories'])
           for table in path_sets.values()):
        result["workspace_inventory_view_rule"] += " " + SHARED_PATH_RULE
    return result if len(canonical_json_bytes(result)) < len(canonical_json_bytes(payload)) else dict(payload)


def expand_workspace_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Expand the view for offline equivalence checks (JSON text is canonicalized)."""
    path_sets = payload.get("workspace_path_sets", {})

    def paths(identity):
        return _expand_path_table(path_sets[identity])

    def visit(value):
        if isinstance(value, str) and value.lstrip().startswith("{") and '"workspace_file_inventory"' in value:
            try:
                decoded = json.loads(value)
            except (ValueError, TypeError):
                return value
            contract = decoded.get("representation_contract") if isinstance(decoded, dict) else None
            if isinstance(contract, Mapping) and contract.get("contract_kind") == "workspace_file_inventory":
                return json.dumps(visit(decoded), ensure_ascii=False, separators=(",", ":"))
            return value
        if isinstance(value, list):
            return [visit(item) for item in value]
        if not isinstance(value, Mapping):
            return value
        result = {key: visit(item) for key, item in value.items()}
        if "authorized_runtime_paths_ref" in result and result.get("contract_kind") == "workspace_file_inventory":
            result["authorized_runtime_paths"] = paths(result.pop("authorized_runtime_paths_ref"))
        files = result.get("files")
        if isinstance(files, Mapping) and files.get("encoding") == "workspace-file-metadata-v1":
            indices = files["metadata_indices"]
            if isinstance(indices, Mapping) and indices.get("encoding") == "runs":
                indices = [index for index, count in indices["values"] for _ in range(count)]
            result["files"] = [{"path": path, **deepcopy(files["metadata"][metadata_index])}
                               for path, metadata_index in zip(paths(files["path_set_ref"]), indices)]
        for name, fixed in result.get("runtime_fixed_arguments", {}).items():
            if isinstance(fixed, Mapping) and set(fixed) == {"workspace_path_set_ref"}:
                result["runtime_fixed_arguments"][name] = paths(fixed["workspace_path_set_ref"])
        return result

    return visit({key: value for key, value in payload.items()
                  if key not in {"workspace_path_sets", "workspace_inventory_view_rule"}})
