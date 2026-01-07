# Thinking Module Guide

The Thinking module provides reasoning enhancement capabilities for Agent nodes, enabling the model to perform additional inference before or after generating results. This document covers the Thinking module architecture, built-in modes, and configuration methods.

## 1. Architecture

1. **ThinkingConfig**: Declared in YAML under `nodes[].config.thinking`, containing `type` and `config` fields.
2. **ThinkingManagerBase**: Abstract base class defining thinking logic for two timing hooks: `_before_gen_think` and `_after_gen_think`.
3. **Registry**: New thinking modes are registered via `register_thinking_mode()`, and Schema API automatically displays available options.

## 2. Configuration Example

```yaml
nodes:
  - id: Thoughtful Agent
    type: agent
    config:
      provider: openai
      name: gpt-4o
      api_key: ${API_KEY}
      thinking:
        type: reflection
        config:
          reflection_prompt: |
            Please carefully review your response, considering:
            1. Is the logic sound?
            2. Are there any factual errors?
            3. Is the expression clear?
            Then provide an improved response.
```

## 3. Built-in Thinking Modes

| Type | Description | Trigger Timing | Config Fields |
|------|-------------|----------------|---------------|
| `reflection` | Model reflects on and refines its output after generation | After generation (`after_gen`) | `reflection_prompt` |

### 3.1 Reflection Mode

Self-Reflection mode allows the model to reflect on and improve its initial output. The execution flow:

1. Agent node calls the model to generate initial response
2. ThinkingManager concatenates conversation history (system role, user input, model output) as reflection context
3. Calls the model again with `reflection_prompt` to generate reflection result
4. Reflection result replaces the original output as the final node output

#### Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `reflection_prompt` | string | Yes | Prompt guiding model reflection, specifying reflection dimensions and expected improvements |

#### Use Cases

- **Writing refinement**: Self-review and correct grammar, logic issues
- **Code review**: Automatic security and quality checks after code generation
- **Complex reasoning**: Verify and correct multi-step reasoning results

## 4. Execution Timing

ThinkingManager supports two execution timings:

| Timing | Property | Description |
|--------|----------|-------------|
| Before generation (`before_gen`) | `before_gen_think_enabled` | Execute thinking before model call for input preprocessing |
| After generation (`after_gen`) | `after_gen_think_enabled` | Execute thinking after model output for post-processing or refinement |

The built-in `reflection` mode only enables after-generation thinking. Extension developers can implement before-generation thinking as needed.

## 5. Interaction with Memory

The Thinking module can access Memory context:

- `ThinkingPayload.text`: Text content at current stage
- `ThinkingPayload.blocks`: Multimodal content blocks (images, attachments, etc.)
- `ThinkingPayload.metadata`: Additional metadata

Memory retrieval results are passed to thinking functions via the `memory` parameter, allowing reflection to reference historical memories.

## 6. Custom Thinking Mode Extension

1. **Create config class**: Inherit from `BaseConfig`, define required configuration fields
2. **Implement ThinkingManager**: Inherit from `ThinkingManagerBase`, implement `_before_gen_think` or `_after_gen_think`
3. **Register mode**:
   ```python
   from runtime.node.agent.thinking.registry import register_thinking_mode
   
   register_thinking_mode(
       "my_thinking",
       config_cls=MyThinkingConfig,
       manager_cls=MyThinkingManager,
       summary="Custom thinking mode description",
   )
   ```
4. **Export template**: Run `python -m tools.export_design_template` to update frontend options

## 7. Best Practices

- **Control reflection rounds**: Current reflection is single-round; specify iteration requirements in `reflection_prompt` for multi-round
- **Concise prompts**: Lengthy `reflection_prompt` increases token consumption; focus on key improvement points
- **Combine with Memory**: Store important reflection results in Memory for downstream nodes
- **Monitor costs**: Reflection makes additional model calls; track token usage

## 8. Related Documentation

- [Agent Node Configuration](../nodes/agent.md)
- [Memory Module](memory.md)
- [Workflow Authoring Guide](../workflow_authoring.md)
