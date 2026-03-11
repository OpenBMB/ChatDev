---
name: chatdev
description: Invoke ChatDev ability units (workflows) via local API (port 6400). Use when the user needs specialized agent workflows like paper reviews (arXiv), data visualization (from CSV), or when they mention "ChatDev", "ability units", or "workflows" at http://127.0.0.1:6400.
---

# ChatDev Ability Units

Ability units represent capability units. You can browse what's available, inspect
required args, run them, or upload new ones. Use these endpoints when you need to
invoke a predefined ability unit (e.g., paper review, data visualization) via the
local API.

Run ability units via the local API and return `final_message` from the JSON response.

## API endpoints
1) Browse ability units
- Method: GET
- URL: http://127.0.0.1:6400/api/workflows
- Example:
  ```
  curl --noproxy 127.0.0.1 -v http://127.0.0.1:6400/api/workflows
  ```

2) Get ability unit raw content
- Method: GET
- URL: http://127.0.0.1:6400/api/workflows/<filename>/get
- Purpose: fetch the raw YAML content for an ability unit file.
- Example:
  ```
  curl --noproxy 127.0.0.1 -v \
    http://127.0.0.1:6400/api/workflows/test.yaml/get
  ```

3) Get ability unit args
- Method: GET
- URL: http://127.0.0.1:6400/api/workflows/<ability_unit>.yaml/args
- Purpose: fetch input parameter schema for an ability unit.
- Example:
  ```
  curl --noproxy 127.0.0.1 -v -X GET \
    http://127.0.0.1:6400/api/workflows/test.yaml/args
  ```

4) Run ability unit
- Method: POST
- URL: http://127.0.0.1:6400/api/workflow/run
- Content-Type: application/json
- SSE support: set `Accept: text/event-stream` to stream events (`started`, `log`,
  `completed`, `error`). Omit the header to get the normal JSON response.
- Output: parse JSON and return `final_message`. If missing, report failure and
  include any error fields. After you get `output_dir`, move it to your working
  directory.
- Available ability units:
  1) Paper Review
  - yaml_file: `yaml_instance/paper_review.yaml`
  - task_prompt: arXiv URL/ID or paper title.
  - Purpose: fetch content and deliver technical + writing reviews.
  - Example:
    ```
    curl --noproxy 127.0.0.1 -v -X POST http://127.0.0.1:6400/api/workflow/run \
      -H "Content-Type: application/json" \
      -H "Accept: text/event-stream" \
      -d '{
        "yaml_file": "yaml_instance/paper_review.yaml",
        "task_prompt": "https://arxiv.org/abs/1706.03762"
      }'
    ```

  2) Data Visualization
  - yaml_file: `yaml_instance/data_visualization_basic.yaml`
  - task_prompt: dataset description + analysis goals.
  - attachments: absolute paths to CSV files.
  - Purpose: profile, clean, plan 4-6 charts, iterate visualizations.
  - Example:
    ```
    curl --noproxy 127.0.0.1 -v -X POST http://127.0.0.1:6400/api/workflow/run \
      -H "Content-Type: application/json" \
      -d '{
        "yaml_file": "yaml_instance/data_visualization_basic.yaml",
        "task_prompt": "please analyze and visualize the data",
         "attachments": ["/Users/yufan/Projects/bugfix/ChatDev/sample_sales.csv"]
      }'
    ```

5) Upload ability unit
- Method: POST
- URL: http://127.0.0.1:6400/api/workflows/upload/content
- Content-Type: application/json
- Format notes: `filename` should end with `.yaml`; `content` must be a valid YAML
  string that includes `version`, `vars`, and a `graph` with `id`, `start`,
  `nodes`, and `edges` (as in the example).
- Tip: if uploads keep failing with format errors, call the "get ability unit raw content" endpoint to inspect
  an existing ability unit's structure and copy its format.
- Example:
  ```
  curl --noproxy 127.0.0.1 -v -X POST \
    http://127.0.0.1:6400/api/workflows/upload/content \
    -H "Content-Type: application/json" \
    -d @- <<'EOF'
  {
    "filename": "test.yaml",
    "content": "version: 0.4.0\nvars: {}\ngraph:\n  id: paper_review\n  description: Three agents collaboratively review academic papers from different perspectives. Input can be an arxiv URL or paper title.\n  is_majority_voting: false\n  start:\n    - Paper Fetcher\n  nodes:\n    - id: Paper Fetcher\n      type: agent\n      config:\n        name: gpt-4o\n        provider: openai\n        role: |\n          You are a paper content fetcher.\n        base_url: ${BASE_URL}\n        api_key: ${API_KEY}\n      description: Fetches paper content from arxiv\n      context_window: 0\n  edges: []"
  }
  EOF
  ```

6) Update ability unit
- Method: PUT
- URL: http://127.0.0.1:6400/api/workflows/<filename>/update
- Content-Type: application/json
- Format notes: same payload as upload (`filename` + YAML `content` string).
- Example:
  ```
  curl --noproxy 127.0.0.1 -v -X PUT \
    http://127.0.0.1:6400/api/workflows/test.yaml/update \
    -H "Content-Type: application/json" \
    -d @- <<'EOF'
  {
    "filename": "test.yaml",
    "content": "version: 0.4.0\nvars: {}\ngraph:\n  id: paper_review\n  description: Update example.\n  is_majority_voting: false\n  start:\n    - Paper Fetcher\n  nodes:\n    - id: Paper Fetcher\n      type: agent\n      config:\n        name: gpt-4o\n        provider: openai\n        role: |\n          You are a paper content fetcher.\n        base_url: ${BASE_URL}\n        api_key: ${API_KEY}\n      description: Fetches paper content from arxiv\n      context_window: 0\n  edges: []"
  }
  EOF
  ```

7) Rename ability unit
- Method: POST
- URL: http://127.0.0.1:6400/api/workflows/<filename>/rename
- Content-Type: application/json
- Body: `{ "new_filename": "new_name.yaml" }`
- Example:
  ```
  curl --noproxy 127.0.0.1 -v -X POST \
    http://127.0.0.1:6400/api/workflows/test.yaml/rename \
    -H "Content-Type: application/json" \
    -d '{"new_filename":"renamed.yaml"}'
  ```

8) Copy ability unit
- Method: POST
- URL: http://127.0.0.1:6400/api/workflows/<filename>/copy
- Content-Type: application/json
- Body: `{ "new_filename": "copy.yaml" }`
- Example:
  ```
  curl --noproxy 127.0.0.1 -v -X POST \
    http://127.0.0.1:6400/api/workflows/test.yaml/copy \
    -H "Content-Type: application/json" \
    -d '{"new_filename":"test-copy.yaml"}'
  ```

9) Delete ability unit
- Method: DELETE
- URL: http://127.0.0.1:6400/api/workflows/<filename>/delete
- Example:
  ```
  curl --noproxy 127.0.0.1 -v -X DELETE \
    http://127.0.0.1:6400/api/workflows/test.yaml/delete
  ```

## Tools hot updates
Run the MCP server separately from the main backend. Use `cache_ttl: 0` in the
MCP tooling config to disable tool list caching.

Endpoints:
- List tools: `GET http://127.0.0.1:8010/admin/tools/list` (returns `source` and `call_methods`)
- Upload tool: `POST http://127.0.0.1:8010/admin/tools/upload`
- Reload tools: `POST http://127.0.0.1:8010/admin/tools/reload`

Wiring rules (from `source`):
- `local_tools`: can wire via `tooling.type: function` or `tooling.type: mcp_remote`.
- `mcp_tools`: wire via `tooling.type: mcp_remote` only.

Upload example:
```
curl --noproxy 127.0.0.1 -v -X POST http://127.0.0.1:8010/admin/tools/upload \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "test.py",
    "content": "def add(a: int, b: int) -> dict:\n    return {\"result\": a + b}\n",
    "functions": ["add"],
    "replace": true
  }'
```

YAML example (MCP):
```
tooling:
  - type: mcp_remote
    config:
      server: "http://127.0.0.1:8010/mcp"
      cache_ttl: 0
```

YAML example (local function_calling):
```
tooling:
  - type: function
    config:
      tools:
        - name: add
```

## Advanced Workflow Templates

Below are advanced YAML templates you can copy and adapt. They cover debate loops,
subgraph reuse, conditional edges, and selective payload routing.

### 1) Two-Agent Debate Loop with Judge Stop Criteria
```yaml
version: 0.4.0
vars: {}
graph:
  id: debate_loop
  description: Two agents debate until the judge outputs "Verdict: STOP".
  is_majority_voting: false
  start:
    - Topic
  nodes:
    - id: Topic
      type: passthrough
      config: {}
    - id: Pro
      type: agent
      config:
        provider: openai
        base_url: ${BASE_URL}
        api_key: ${API_KEY}
        name: gpt-4o
        role: |
          You are the PRO debater. Respond with arguments and counterpoints.
    - id: Con
      type: agent
      config:
        provider: openai
        base_url: ${BASE_URL}
        api_key: ${API_KEY}
        name: gpt-4o
        role: |
          You are the CON debater. Respond with arguments and counterpoints.
    - id: Judge
      type: agent
      config:
        provider: openai
        base_url: ${BASE_URL}
        api_key: ${API_KEY}
        name: gpt-4o
        role: |
          Evaluate the debate. Output:
          Score: <0-1>
          Notes: <brief>
          Verdict: CONTINUE|STOP
    - id: Final
      type: agent
      config:
        provider: openai
        base_url: ${BASE_URL}
        api_key: ${API_KEY}
        name: gpt-4o
        role: |
          Produce the final summary of the debate and recommendation.
  edges:
    - from: Topic
      to: Pro
      keep_message: true
    - from: Topic
      to: Con
      keep_message: true
    - from: Pro
      to: Judge
    - from: Con
      to: Judge
    - from: Judge
      to: Pro
      condition: need_reflection_loop
    - from: Judge
      to: Con
      condition: need_reflection_loop
    - from: Judge
      to: Final
      condition: should_stop_loop
```

### 2) Subgraph Reuse + Selective Payload Passing
```yaml
version: 0.4.0
vars: {}
graph:
  id: parent_with_subgraph
  description: Uses a subgraph and only forwards the "Summary" section.
  start:
    - Request
  nodes:
    - id: Request
      type: passthrough
      config: {}
    - id: ResearchSubgraph
      type: subgraph
      config:
        type: file
        config:
          path: "subgraphs/deep_research_executor_sub.yaml"
    - id: Writer
      type: agent
      config:
        provider: openai
        base_url: ${BASE_URL}
        api_key: ${API_KEY}
        name: gpt-4o
        role: |
          Write the final report using only the provided Summary.
  edges:
    - from: Request
      to: ResearchSubgraph
      keep_message: true
    - from: ResearchSubgraph
      to: Writer
      process:
        type: regex_extract
        config:
          pattern: "Summary:\\s*(.*)"
          group: 1
          multiline: true
          dotall: true
          on_no_match: pass
```

### 3) Conditional Routing + Minimal Payload
```yaml
version: 0.4.0
vars: {}
graph:
  id: router_with_conditions
  description: Route to different nodes based on tags; forward only CONTENT block.
  start:
    - Router
  nodes:
    - id: Router
      type: agent
      config:
        provider: openai
        base_url: ${BASE_URL}
        api_key: ${API_KEY}
        name: gpt-4o
        role: |
          Decide the route. Output exactly:
          ROUTE: QA|REPORT
          CONTENT: <payload to forward>
    - id: QA
      type: agent
      config:
        provider: openai
        base_url: ${BASE_URL}
        api_key: ${API_KEY}
        name: gpt-4o
        role: |
          Answer the question concisely.
    - id: REPORT
      type: agent
      config:
        provider: openai
        base_url: ${BASE_URL}
        api_key: ${API_KEY}
        name: gpt-4o
        role: |
          Write a structured report.
  edges:
    - from: Router
      to: QA
      condition:
        type: keyword
        config:
          any: ["ROUTE: QA"]
      process:
        type: regex_extract
        config:
          pattern: "CONTENT:\\s*(.*)"
          group: 1
          dotall: true
          on_no_match: drop
    - from: Router
      to: REPORT
      condition:
        type: keyword
        config:
          any: ["ROUTE: REPORT"]
      process:
        type: regex_extract
        config:
          pattern: "CONTENT:\\s*(.*)"
          group: 1
          dotall: true
          on_no_match: drop
```

## Tips
- Any workflow YAML can be used as a subgraph to compose more complex tasks, including existing ability units/workflows. Example:
  ```
  - id: Research Subgraph
    type: subgraph
    config:
      type: file
      config:
        path: "yaml_instance/deep_research_v1.yaml"
  ```
- Ensure that all generated artifacts are output to your workspace file paths whenever possible
- Ensure that all agents’ roles are concise, sophisticated, and equipped with sufficient tools