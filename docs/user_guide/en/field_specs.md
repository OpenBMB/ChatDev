# FIELD_SPECS Authoring Guide

This guide explains how to write `FIELD_SPECS` for new configs so the Web UI forms and `python -m tools.export_design_template` stay in sync. It applies to any `BaseConfig` subclass (nodes, Memory, Thinking, Tooling, etc.).

## 1. Why FIELD_SPECS matter
- UI forms rely on `FIELD_SPECS` to render inputs, defaults, and helper text.
- The design template exporter reads `FIELD_SPECS` to populate `yaml_template/design*.yaml` and the mirrored files under `frontend/public/`.
- Fields missing from `FIELD_SPECS` will not appear in the UI or generated templates.

## 2. Basic structure
`FIELD_SPECS` is a dict mapping field name → `ConfigFieldSpec`, usually declared inside the config class:

```python
FIELD_SPECS = {
    "interpreter": ConfigFieldSpec(
        name="interpreter",
        display_name="Interpreter",
        type_hint="str",
        required=False,
        default="python3",
        description="Path to the Python executable",
    ),
    ...
}
```

Key attributes:
- `name`: same as the YAML field.
- `display_name`: optional human label shown in the UI; falls back to `name` when omitted.
- `type_hint`: string describing the shape (`str`, `list[str]`, `dict[str, Any]`, etc.).
- `required`: whether the UI treats the field as mandatory; usually `False` if a default exists.
- `default`: scalar or JSON-serializable default value.
- `description`: helper text/tooltips in forms and docs.
- `enum`: array of allowed values (strings).
- `enumOptions`: richer metadata per enum entry (label, description). Use it alongside `enum` for user-friendly dropdowns.
- `child`: reference to another `BaseConfig` subclass for nested structures.

## 3. Authoring flow
1. **Validate in `from_dict`** – ensure YAML parsing enforces types and emits clear `ConfigError`s (see `entity/configs/python_runner.py`).
2. **Define `FIELD_SPECS`** – cover all public fields with type, description, default, etc.
3. **Handle dynamic fields** – when options depend on registries or filesystem scans, override `field_specs()` and use `replace()` to inject real-time `enum`/`description` (e.g., `FunctionToolEntryConfig.field_specs()` lists functions on disk).
4. **Export templates** – after edits run:
   ```bash
   python -m tools.export_design_template --output yaml_template/design.yaml --mirror frontend/public/design.yaml
   ```
   The command uses the latest `FIELD_SPECS` to regenerate YAML templates and the frontend mirror—no manual edits needed.

## 4. Common patterns
- **Scalar fields**: see `entity/configs/python_runner.py` for `timeout_seconds` (integer default + validation).
- **Nested lists**: `entity/configs/memory.py` uses `child=FileSourceConfig` for `file_sources`, enabling repeatable subforms.
- **Dynamic enums**: `Node.field_specs()` (around `entity/configs/node.py:304`) pulls node types from the registry and supplies `enumOptions`; `FunctionToolEntryConfig.field_specs()` builds enumerations from the function catalog.
- **Registry-driven descriptions**: when calling `register_node_type` / `register_memory_store` / `register_thinking_mode` / `register_tooling_type`, always provide `summary`/`description`. Those strings populate `enumOptions` and keep dropdowns self-explanatory.
- **Optional blocks**: combine `required=False` with sensible `default` values and make sure `from_dict` honors the same defaults.

## 5. Best practices
- Keep descriptions user-friendly and clarify units (e.g., “Timeout (seconds)”).
- Align defaults with parsing logic so UI expectations match backend behavior.
- For nested configs, provide concise examples or cross-links so UI users understand the structure.
- After changing `FIELD_SPECS`, re-run the export command and commit the updated templates/mirror files.

For more examples inspect `entity/configs/model.py`, `entity/configs/tooling.py`, or other existing node/Memory/Thinking configs.
