# Deep Research: YAML Scenario File Format for ChatDev 2.0 (DevAll)

This document details the YAML format used for defining multi-agent workflows in ChatDev 2.0. It is based on an analysis of the codebase, specifically the configuration schemas in `entity/configs/` and validation logic in `check/`.

## 1. File Structure Overview

A valid workflow file consists of three main top-level keys:

```yaml
version: "0.0.0"      # Optional, defaults to "0.0.0"
vars:                 # Optional global variables
  API_KEY: ${API_KEY}
  BASE_URL: ${BASE_URL}
graph:                # REQUIRED: The core workflow definition
  id: "MyWorkflow"
  description: "Description of what this workflow does"
  nodes: []           # List of Node objects
  edges: []           # List of Edge objects
```

## 2. Graph Definition (`graph`)

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `id` | `str` | Yes | Unique identifier (alphanumeric, underscores, hyphens). |
| `nodes` | `List[Node]` | Yes | List of nodes. Must contain at least one node. |
| `edges` | `List[Edge]` | Yes | List of directed edges connecting nodes. |
| `description` | `str` | No | Human-readable description. |
| `log_level` | `enum` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Default: `DEBUG`. |
| `is_majority_voting` | `bool` | No | Default: `false`. |
| `memory` | `List` | No | List of `MemoryStoreConfig` definitions. |
| `start` | `List[str]` | No* | List of start node IDs. *Inferred if graph has unique source.* |
| `end` | `List[str]` | No* | List of end node IDs. *Inferred if graph has unique sink.* |
| `initial_instruction` | `str` | No | Initial instruction text for the user. |
| `organization` | `str` | No | Organization name. |

## 3. Node Configuration (`nodes`)

Each item in the `nodes` list represents a processing unit.

```yaml
- id: "NodeID"        # Required: Unique ID
  type: "agent"       # Required: Node type (agent, human, loop_counter, etc.)
  description: "..."  # Optional
  context_window: 0   # Optional: 0 (clear), -1 (unlimited), N (keep last N)
  config:             # Required: Configuration specific to the 'type'
    ...
```

### Common Node Types & Configurations

#### **`agent`**
Represents an LLM-based agent.
```yaml
type: agent
config:
  name: "gpt-4o"           # Required: Model name
  provider: "openai"       # Required: Provider (openai, etc.)
  role: "System prompt..." # Optional: System message
  base_url: ${BASE_URL}    # Optional: Override URL
  api_key: ${API_KEY}      # Optional: API Key
  params:                  # Optional: Model parameters
    temperature: 0.7
  tooling:                 # Optional: List of tools
    - type: function
      config:
        tools:
          - name: "read_file"
  memories: []             # Optional: Memory attachments
  retry:                   # Optional: Retry configuration
    enabled: true
    max_attempts: 5
```

#### **`human`**
Represents a human interaction point.
```yaml
type: human
config:
  description: "Instruction for the human user"
  memories:                # Optional: Memory attachments for context retrieval and writing
    - name: "memory_name"  # Reference to a memory store defined in graph.memory
      read: true           # Enable memory retrieval
      write: true          # Enable memory writing (human feedback stored)
      top_k: 10            # Number of relevant items to retrieve
      similarity_threshold: 0.5  # Minimum similarity score (0.0-1.0)
      retrieve_stage:      # When to retrieve memory
        - gen              # During generation stage (default if not specified)
        - pre_gen_thinking # Before thinking step
```

**Note**: 
- Memory context retrieved from attached memory stores will be displayed to the human user alongside the description and input data.
- When `write: true`, human feedback will be automatically stored in the memory for future retrieval.
- `retrieve_stage` controls when memory is retrieved. If not specified, defaults to `gen` stage.

**Best Practice - Memory Flow Patterns**:

When designing workflows with shared memory between agent and human nodes, consider who should write to which memory:

1. **State Memory Pattern** (Agent writes, Human reads):
   ```yaml
   # Environment/state generator agent
   - id: environment
     type: agent
     config:
       memories:
         - name: environment_memory
           read: true
           write: true              # Agent owns this memory
           top_k: 10
           similarity_threshold: 0.0  # IMPORTANT: Use 0.0 to always retrieve recent items
           retrieve_stage:
             - gen                  # Retrieve during generation (before model call)
   
   # Human controller
   - id: HumanControl
     type: human
     config:
       memories:
         - name: environment_memory
           read: true               # Human only reads to see history
           write: false             # Human does NOT write to state memory
           top_k: 10
           similarity_threshold: 0.0  # Always show recent history
   ```
   **Use when**: Agent generates state/context that human needs to review but not modify directly. The human provides commands via edges, and the agent interprets them to update state.
   
   **Why `similarity_threshold: 0.0`?** When the agent receives user input like "continue", the query text has low semantic similarity to past state descriptions (e.g., "COVID-19 outbreak" vs "continue"). Setting threshold to 0.0 ensures the agent ALWAYS retrieves its most recent states regardless of query similarity, maintaining continuity.
   
   **Why `retrieve_stage: gen`?** The `reflection` thinking type only processes memory during the generation stage. Using `pre_gen_thinking` would cause memory to be retrieved but ignored. With `gen` stage, memory is injected into the conversation BEFORE the model generates output, ensuring continuity.

2. **Feedback Memory Pattern** (Human writes, Agent reads):
   ```yaml
   # Agent processes feedback
   - id: processor
     type: agent
     config:
       memories:
         - name: feedback_memory
           read: true
           write: false
   
   # Human provides feedback
   - id: reviewer
     type: human
     config:
       memories:
         - name: feedback_memory
           read: true
           write: true    # Human owns feedback memory
   ```
   **Use when**: Human provides annotations, corrections, or judgments that agents need to incorporate.

3. **Separate Memory Pattern** (Isolated stores):
   ```yaml
   # Each node has its own memory store
   - id: agent_a
     memories:
       - name: agent_a_memory
   
   - id: human_b
     memories:
       - name: human_b_memory
   ```
   **Use when**: No memory sharing needed; each node maintains independent history.

#### **`loop_counter`**
Controls loops by counting iterations.
```yaml
type: loop_counter
config:
  max_iterations: 5     # Max allowed loops
  reset_on_emit: true   # Reset count when condition is met
  message: ""           # Optional message
```

#### **`loop_timer`**
Controls loops by tracking elapsed time.
```yaml
type: loop_timer
config:
  max_duration: 5       # Max allowed time
  duration_unit: seconds # Unit: 'seconds', 'minutes', or 'hours'
  reset_on_emit: true   # Reset timer when condition is met
  message: ""           # Optional message
  passthrough: false    # Passthrough mode (same as loop_counter)
```

#### **`passthrough`**
A simple node that passes data through without modification.
```yaml
type: passthrough
config: {}
```

#### **`literal`**
Injects static content into the workflow.
```yaml
type: literal
config:
  content: "Static content text"
  role: "user"          # Role of the message (user, assistant, system)
```

#### **`python_runner`** (implied from imports)
Executes Python code.
```yaml
type: python_runner
config:
  timeout_seconds: 60
```

## 4. Edge Configuration (`edges`)

Defines the flow between nodes.

```yaml
- from: "SourceNodeID"    # Required
  to: "TargetNodeID"      # Required
  trigger: true           # Default: true. Can trigger target execution?
  condition: "true"       # Condition to traverse (default "true")
  carry_data: true        # Pass output of source to target?
  keep_message: false     # Mark message as 'keep' in target context?
  clear_context: false    # Clear target's context before adding new data?
  clear_kept_context: false # Clear 'kept' messages in target?
  processor:              # Optional: Transform data before passing to target
    type: template
    config:
      template: "..."
  dynamic:                # Optional: Dynamic execution (map/tree patterns)
    type: map
    config:
      split_type: regex
```

### 4.1 Context Management

Context management controls how messages accumulate in a node's execution context across workflow execution.

#### **Context vs Memory**
- **Context**: Message queue visible to a node during execution (temporary, workflow-scoped)
- **Memory**: Persistent storage across workflow runs (permanent, stored in vector database)

#### **Message Lifecycle**
1. Source node produces output
2. Edge delivers message to target node's context
3. Target node processes messages in its context
4. Context can be cleared or preserved based on edge configuration

#### **Edge Parameters for Context Control**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `keep_message` | `bool` | `false` | Mark message as "kept" (survives soft reset) |
| `clear_context` | `bool` | `false` | Clear non-kept messages before adding new data |
| `clear_kept_context` | `bool` | `false` | Clear kept messages (requires `clear_context: true`) |

#### **Soft Reset vs Hard Reset**

**Soft Reset** (`clear_context: true`):
- Clears only messages with `keep=false`
- Preserves messages marked with `keep_message: true`
- Use case: Clear temporary data but keep system instructions

```yaml
- from: UserInput
  to: Agent
  clear_context: true      # Soft reset
  keep_message: false
```

**Hard Reset** (`clear_context: true` + `clear_kept_context: true`):
- Clears ALL messages (including `keep=true`)
- Complete context isolation
- Use case: Start fresh between workflow rounds

```yaml
- from: LoopControl
  to: StartNode
  clear_context: true      # Hard reset
  clear_kept_context: true
```

#### **Context Reset Demo Example**

See `yaml_instance/demo_context_reset.yaml` for a working demonstration:

**Workflow Structure**:
1. `entry_normal` → `collector` (`keep_message: false`) - Normal message
2. `entry_keep` → `collector` (`keep_message: true`) - Kept message
3. `soft_reset` → `collector` (`clear_context: true`) - Soft reset
4. `hard_reset` → `collector` (`clear_context: true`, `clear_kept_context: true`) - Hard reset

**Execution Flow**:
- After `entry_normal` + `entry_keep`: collector has 2 messages
- After `soft_reset`: collector has `entry_keep` + `soft_reset` (normal cleared)
- After `hard_reset`: collector has only `hard_reset` (all previous cleared)

#### **Common Use Cases**

**Preserve System Instructions**:
```yaml
- from: SystemSetup
  to: Agent
  keep_message: true       # This survives soft resets

- from: UserInput
  to: Agent
  clear_context: true      # Clears user messages but keeps system
```

**Recursive Workflows with Isolation**:
```yaml
- from: HumanControl
  to: StartNode
  clear_context: true      # Fresh start each round
  clear_kept_context: true # Complete isolation
  condition:
    type: keyword
    config:
      none: ["EXIT"]       # Loop until user says "EXIT"
```

**Accumulate Important Context**:
```yaml
- from: CriticalNode
  to: Aggregator
  keep_message: true       # Don't lose this data
  
- from: TemporaryNode
  to: Aggregator
  keep_message: false      # Can be cleared later
```

### 4.2 Condition Configuration

Edges can have conditions that determine when they are traversed.

#### **Keyword Condition**
Match specific keywords in the source node output.

```yaml
condition:
  type: keyword
  config:
    any: ["APPROVED", "SUCCESS"]    # Match if ANY keyword present
    none: ["ERROR", "FAILED"]        # Match if NONE present
    all: ["READY", "VERIFIED"]       # Match if ALL present
```

#### **Regex Condition**
Match output against a regular expression.

```yaml
condition:
  type: regex
  config:
    pattern: "^RESULT: .*"
    flags: ["IGNORECASE"]
```

## 5. Memory Configuration

Memory stores enable persistent data across workflow runs using vector similarity search.

### 5.1 Graph-Level Memory Stores

Define memory stores in the `graph.memory` section:

```yaml
graph:
  memory:
    - name: patient_memory
      type: simple
      config:
        embedding:
          provider: openai
          base_url: ${BASE_URL}
          api_key: ${API_KEY}
          model: text-embedding-bge-reranker-v2-m3
```

### 5.2 Node-Level Memory Attachments

Attach memory to nodes for read/write operations:

```yaml
nodes:
  - id: PatientGenerator
    type: agent
    config:
      memories:
        - name: patient_memory        # Must match graph.memory name
          top_k: 50                    # Retrieve top 50 similar items
          similarity_threshold: 0.3    # Minimum similarity score (0-1)
          retrieve_stage:              # When to retrieve memory
            - pre_gen_thinking         # Before thinking step
          read: true                   # Enable reading from memory
          write: true                  # Enable writing to memory
```

#### **Memory Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Memory store name (must exist in `graph.memory`) |
| `top_k` | `int` | Number of similar items to retrieve (default: 10) |
| `similarity_threshold` | `float` | Minimum similarity score 0-1 (default: 0.5) |
| `retrieve_stage` | `List[str]` | When to retrieve: `pre_gen_thinking`, `post_gen`, etc. |
| `read` | `bool` | Enable reading from memory (default: false) |
| `write` | `bool` | Enable writing to memory (default: false) |

#### **Use Cases**

**Cross-Round Uniqueness** (High top_k, Low threshold):
```yaml
memories:
  - name: patient_memory
    top_k: 50                    # Cast wide net
    similarity_threshold: 0.3    # Catch similar items
    retrieve_stage: [pre_gen_thinking]
    read: true
    write: true
```

**Recent Context Preservation** (Low top_k, Medium threshold):
```yaml
memories:
  - name: environment_memory
    top_k: 10                    # Only recent context
    similarity_threshold: 0.5    # Moderately similar
    retrieve_stage: [pre_gen_thinking]
    read: true
    write: true
```

**Human Node Memory Support**:

Human nodes support full memory functionality including read, write, and retrieve_stage configuration:

```yaml
nodes:
  - id: HumanFeedback
    type: human
    config:
      description: "Review the article and provide feedback..."
      memories:
        - name: feedback_memory
          read: true           # Retrieve and display previous feedback
          write: true          # Store human feedback for future reference
          top_k: 10
          similarity_threshold: 0.5
          retrieve_stage:      # Control when memory is retrieved
            - gen              # Default stage for human nodes
```

**Features**:
- **Read**: Retrieved memory is displayed alongside the description to help users make informed decisions
- **Write**: Human feedback is automatically stored in memory after user input
- **retrieve_stage**: Controls when memory retrieval occurs. Available stages: `gen`, `pre_gen_thinking`, `post_gen_thinking`, `finished`
- If `retrieve_stage` is not specified, defaults to `gen` stage

**Use Cases**:
- **Feedback Consistency**: Store and retrieve past user feedback to maintain consistent review standards
- **Context Awareness**: Display historical decisions to inform current choices
- **Learning from History**: Build up knowledge base from human inputs over multiple workflow runs

## 6. Thinking Module

The thinking module adds reflection and planning capabilities to agent nodes.

### 6.1 Reflection Thinking

Enables post-generation reflection and refinement:

```yaml
nodes:
  - id: environment
    type: agent
    config:
      thinking:
        type: reflection
        config:
          reflection_prompt: |
            You have just generated output. Now reflect and refine:
            
            QUALITY CHECK:
            1. Does the output meet all requirements?
            2. Is it consistent with retrieved memory?
            3. Are there any contradictions or gaps?
            
            Output ONLY the final refined result with no commentary.
```

### 6.2 Thinking with Memory Integration

Combine thinking with memory retrieval for intelligent context-aware processing:

```yaml
nodes:
  - id: PatientGenerator
    type: agent
    config:
      memories:
        - name: patient_memory
          retrieve_stage: [pre_gen_thinking]  # Retrieve BEFORE thinking
          read: true
          write: true
      thinking:
        type: reflection
        config:
          reflection_prompt: |
            Review retrieved patient memory and verify uniqueness:
            - Are there duplicate names or symptom patterns?
            - Generate fresh alternatives if conflicts exist.
            
            Output the final unique patient list.
```

**Execution Flow**:
1. Node generates initial output
2. Memory is retrieved (if `retrieve_stage: [pre_gen_thinking]`)
3. Retrieved memory + initial output passed to thinking module
4. Thinking module refines and returns final output

## 7. Dynamic Execution

Dynamic execution enables parallel processing patterns like map-reduce.

### 7.1 Map Pattern (Parallel Fan-Out)

Split input into multiple parallel branches:

```yaml
edges:
  - from: PatientGenerator
    to: NurseIntake
    dynamic:
      type: map
      config:
        split_type: json_array    # Split JSON array into items
        item_name: patient        # Variable name for each item
```

**How it works**:
1. `PatientGenerator` outputs JSON array: `[{patient1}, {patient2}, {patient3}]`
2. Edge splits into 3 parallel executions of `NurseIntake`
3. Each execution receives one patient object

### 7.2 Supported Split Types

| Split Type | Description | Example |
|------------|-------------|---------|
| `json_array` | Split JSON array | `[{...}, {...}]` → multiple items |
| `regex` | Split by regex pattern | Split by delimiter |
| `lines` | Split by newlines | Multi-line text → separate lines |

### 7.3 Real-World Example (Hospital Simulation)

```yaml
# Patient generator creates array of patients
- id: PatientGenerator
  type: agent
  config:
    role: "Generate array of patients in JSON format"

# Parallel fan-out to process each patient
edges:
  - from: PatientGenerator
    to: NurseIntake
    dynamic:
      type: map
      config:
        split_type: json_array
        item_name: patient

# Each nurse intake processes one patient in parallel
- id: NurseIntake
  type: agent
  config:
    role: "Process patient: {{patient}}"
```

**Result**: 5 patients → 5 parallel NurseIntake executions

## 8. Edge Processors

Edge processors transform data before passing to target nodes.

### 8.1 Template Processor

Use template strings to format data:

```yaml
edges:
  - from: HumanControl
    to: environment
    processor:
      type: template
      config:
        template: |
          USER INPUT: {{content}}
          
          INSTRUCTION: Update the environment based on user input.
          - If input is minimal ("continue"), maintain scenario with time progression
          - If input adds elements, integrate them while preserving context
```

**Variables available**:
- `{{content}}`: Message content from source node
- Custom variables from node outputs

### 8.2 Regex Extract Processor

Extract specific data using regex:

```yaml
edges:
  - from: Analyzer
    to: Processor
    processor:
      type: regex_extract
      config:
        pattern: "RESULT: (.*)"
        group: 1
```

## 9. Common Errors & Best Practices

1.  **Unique IDs**: Ensure every `id` in `nodes` is unique. Duplicate IDs cause validation failure.
2.  **Valid References**: `from` and `to` in `edges` must match exactly with a defined `id` in `nodes`.
3.  **Root Structure**: The file **must** have the `graph:` key. `vars:` defines placeholders like `${API_KEY}`.
4.  **Type Consistency**:
    *   `context_window` is an **integer**, not a string.
    *   `condition` is a string expression (e.g., `"true"`, `"false"`) or a config object.
5.  **Agent Config**:
    *   `name` and `provider` are mandatory for `agent` nodes.
    *   `tooling` must be a list of tool configurations.
6.  **Environment Variables**: Use `${VAR_NAME}` in YAML and define them in `.env` or the `vars` section. The validation logic checks schema but resolves variables at runtime.

## 9. Common Errors & Best Practices

1.  **Unique IDs**: Ensure every `id` in `nodes` is unique. Duplicate IDs cause validation failure.
2.  **Valid References**: `from` and `to` in `edges` must match exactly with a defined `id` in `nodes`.
3.  **Root Structure**: The file **must** have the `graph:` key. `vars:` defines placeholders like `${API_KEY}`.
4.  **Type Consistency**:
    *   `context_window` is an **integer**, not a string.
    *   `condition` is a string expression (e.g., `"true"`, `"false"`) or a config object.
5.  **Agent Config**:
    *   `name` and `provider` are mandatory for `agent` nodes.
    *   `tooling` must be a list of tool configurations.
6.  **Environment Variables**: Use `${VAR_NAME}` in YAML and define them in `.env` or the `vars` section. The validation logic checks schema but resolves variables at runtime.
7.  **Memory Configuration**:
    *   Memory store names in `nodes.config.memories` must exist in `graph.memory`.
    *   `retrieve_stage` determines when memory is retrieved (before/after thinking).
    *   Balance `top_k` and `similarity_threshold` based on use case.
8.  **Context Management**:
    *   Use `keep_message: true` for system instructions and critical context.
    *   Use soft reset (`clear_context: true`) to clear temporary data.
    *   Use hard reset (`clear_context + clear_kept_context`) for complete isolation.
9.  **Dynamic Execution**:
    *   Ensure source node output format matches `split_type` (e.g., JSON array for `json_array`).
    *   Use descriptive `item_name` for clarity in target node templates.
10. **Thinking Module**:
    *   Keep reflection prompts focused and concise.
    *   Clearly specify expected output format.
    *   Use thinking with memory retrieval for context-aware refinement.

## 10. Complete Example: Recursive Hospital Simulation

This example demonstrates advanced features: recursive loops, memory, thinking, dynamic execution, and context management.

See `yaml_instance/simulation_hospital.yaml` for the full implementation.

**Key Features**:

1. **Environment Continuity** (`environment` node):
   - Memory retrieval at `pre_gen_thinking` stage
   - Reflection thinking detects "continue" vs "evolve" modes
   - Maintains scenario context across rounds

2. **Unique Patient Generation** (`PatientGenerator` node):
   - Memory tracks all previously generated patients
   - Reflection thinking verifies uniqueness
   - Dynamic execution fans out to parallel patient processing

3. **Recursive Loop** (edges):
   - `HumanControl` → `environment` with hard reset
   - Condition: `none: ["SIMULATION ENDED."]` (continues)
   - Complete context isolation between rounds

4. **Parallel Processing** (dynamic execution):
   - Patient array splits into parallel nurse/doctor workflows
   - Each patient processed independently
   - Results aggregate before next round

**Simplified Structure**:

```yaml
graph:
  memory:
    - name: patient_memory
      type: simple
    - name: environment_memory
      type: simple
  
  nodes:
    - id: environment
      type: agent
      config:
        memories:
          - name: environment_memory
            top_k: 10
            similarity_threshold: 0.5
            retrieve_stage: [pre_gen_thinking]
            read: true
            write: true
        thinking:
          type: reflection
          config:
            reflection_prompt: "Detect mode and maintain continuity..."
    
    - id: PatientGenerator
      type: agent
      config:
        memories:
          - name: patient_memory
            top_k: 50
            similarity_threshold: 0.3
            retrieve_stage: [pre_gen_thinking]
            read: true
            write: true
        thinking:
          type: reflection
          config:
            reflection_prompt: "Verify uniqueness against memory..."
    
    - id: HumanControl
      type: human
      config:
        description: "Enter next scenario or 'SIMULATION ENDED.'"
    
    - id: SimulationEnd
      type: literal
      config:
        content: "Simulation complete."
  
  edges:
    # Dynamic parallel processing
    - from: PatientGenerator
      to: NurseIntake
      dynamic:
        type: map
        config:
          split_type: json_array
          item_name: patient
    
    # Recursive loop with hard reset
    - from: HumanControl
      to: environment
      clear_context: true          # Hard reset
      clear_kept_context: true     # Complete isolation
      condition:
        type: keyword
        config:
          none: ["SIMULATION ENDED."]
    
    # Exit condition
    - from: HumanControl
      to: SimulationEnd
      condition:
        type: keyword
        config:
          any: ["SIMULATION ENDED."]
```

## 11. Validation

Use the project's validation tool to check your YAML:
```bash
uv run python -m check.check --path yaml_instance/your_workflow.yaml
```

This tool performs:
*   **Schema Validation**: Checks if fields match the defined dataclasses (`entity/configs`).
*   **Structure Validation**: Checks for orphan nodes, invalid edges, and logical consistency.
*   **Memory Validation**: Verifies memory store references are valid.
*   **Condition Validation**: Ensures condition syntax is correct.

## 12. Quick Reference

### Context Management

| Goal | Configuration |
|------|---------------|
| Keep system instructions | `keep_message: true` on edge |
| Clear temporary messages | `clear_context: true` |
| Complete context reset | `clear_context: true` + `clear_kept_context: true` |
| Preserve between rounds | Use `keep_message: true` on critical edges |

### Memory Patterns

| Use Case | top_k | similarity_threshold |
|----------|-------|---------------------|
| Broad historical search | 50+ | 0.3 (low) |
| Recent context | 10 | 0.5 (medium) |
| Exact matches | 5 | 0.7+ (high) |

### Thinking Integration

| Retrieve Stage | Purpose |
|----------------|---------|
| `pre_gen_thinking` | Provide memory context before thinking |
| `post_gen` | Retrieve after generation (rare) |

### Dynamic Execution

| Split Type | Input Format |
|------------|--------------|
| `json_array` | `[{...}, {...}]` |
| `regex` | Text with delimiter |
| `lines` | Multi-line text |

### Condition Types

| Type | Use Case |
|------|----------|
| `keyword` | Match specific words (any/none/all) |
| `regex` | Pattern matching |
| `"true"` | Always traverse (default) |

## 13. Implementation Patterns

### Pattern 1: Recursive Workflow with Isolation

```yaml
edges:
  - from: HumanControl
    to: StartNode
    clear_context: true
    clear_kept_context: true
    condition:
      type: keyword
      config:
        none: ["EXIT"]
```

### Pattern 2: Memory-Based Uniqueness Check

```yaml
nodes:
  - id: Generator
    type: agent
    config:
      memories:
        - name: tracking_memory
          top_k: 50
          similarity_threshold: 0.3
          retrieve_stage: [pre_gen_thinking]
          read: true
          write: true
      thinking:
        type: reflection
        config:
          reflection_prompt: "Verify uniqueness against retrieved memory..."
```

### Pattern 3: Parallel Processing with Aggregation

```yaml
edges:
  # Fan out
  - from: Generator
    to: Processor
    dynamic:
      type: map
      config:
        split_type: json_array
  
  # Aggregate
  - from: Processor
    to: Aggregator
```

### Pattern 4: Conditional Branching

```yaml
edges:
  - from: Decision
    to: PathA
    condition:
      type: keyword
      config:
        any: ["APPROVE"]
  
  - from: Decision
    to: PathB
    condition:
      type: keyword
      config:
        any: ["REJECT"]
```

## 14. Reference Files

- **Demo Workflows**: `yaml_instance/demo_context_reset.yaml` - Context management demo
- **Complex Example**: `yaml_instance/simulation_hospital.yaml` - Full-featured recursive simulation
- **Configuration Schemas**: `entity/configs/` - Dataclass definitions
- **Validation Logic**: `check/check.py` - Schema and structure validation
- **User Guide**: `docs/user_guide/en/` - Official documentation

---

**Last Updated**: Based on codebase analysis and `demo_context_reset.yaml` demonstration workflow.
