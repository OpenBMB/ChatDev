# Template Node

The Template node formats the latest input message with a [Jinja2](https://jinja.palletsprojects.com/) template and emits the rendered text. Use it to build reports, banners, or structured prompts without spending an LLM call.

## Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `template` | text | Yes | - | Jinja2 template string; must not be empty |

## Template Context

| Variable | Value |
|----------|-------|
| `input` | Text content of the latest input message |

Custom filters, in addition to the Jinja2 built-ins:

| Filter | Description |
|--------|-------------|
| `fromjson` | Parses a JSON string into an object, e.g. `{% set data = input \| fromjson %}` |
| `tojson` | Serializes a value to JSON (non-ASCII characters kept as-is) |

## Behavior

- Only the **latest** input message is rendered; earlier inputs are ignored (same as `passthrough` with `only_last_message: true`).
- Rendering runs in Jinja2's `SandboxedEnvironment`, so templates cannot reach Python internals.
- Undefined variables fail the node (`StrictUndefined`); the error lists the available context keys.
- Invalid template syntax or invalid JSON passed to `fromjson` also fails the node.
- If the node is triggered without inputs, it emits an empty message and logs a warning.
- The output is a new `user` message whose source is the template node.

## When to Use

- **Formatting agent output**: turn JSON produced by an agent into a readable report
- **Deterministic glue**: add headers, footers, or fixed wording between agents without an LLM call
- **Prompt assembly**: wrap upstream text in a fixed instruction before it reaches the next agent

## Examples

### Basic Usage

```yaml
nodes:
  - id: Banner
    type: template
    config:
      template: |
        ==== STATUS ====
        {{ input | upper }}
```

### Formatting JSON from an Agent

```yaml
nodes:
  - id: Report
    type: template
    config:
      template: |
        {% set data = input | fromjson %}
        Patient: {{ data.name }}
        Findings:
        {% for item in data.findings %}
        - {{ item }}
        {% endfor %}
```

A complete runnable workflow is in `yaml_instance/demo_simple_template.yaml`.

## Template Edge Processor

The same rendering is available on edges as the `template` processor, which rewrites the payload in transit instead of adding a node:

```yaml
edges:
  - from: Analyst
    to: Writer
    process:
      type: template
      config:
        template: "Summarize for a clinician:\n{{ input }}"
```

The processor context has `input` and `extracted` (an alias of `input`), and the same `fromjson`/`tojson` filters.
