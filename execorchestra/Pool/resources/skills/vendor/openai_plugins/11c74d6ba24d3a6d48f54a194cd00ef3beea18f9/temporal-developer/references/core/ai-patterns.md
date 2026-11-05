# AI/LLM Integration Patterns with Temporal

## Overview

Temporal provides durable execution for AI/LLM applications, handling retries, rate limits, and long-running operations automatically. These patterns apply across languages, with Python being the most mature for AI integration.

For Python-specific implementation details and code examples, see `references/python/ai-patterns.md`. Temporal's Python SDK also provides pre-built integrations with several LLM and agent SDKs, which can be leveraged to create agentic workflows with minimal effort (when working in Python).

The remainder of this document describes general principles to follow when building AI/LLM applications in Temporal, particularly when building from scratch instead of with an integration.

## Why Temporal for AI?

| Challenge | Temporal Solution |
|-----------|-------------------|
| LLM API timeouts | Automatic retries with backoff |
| Rate limiting | Activity retry policies handle 429s |
| Long-running agents | Durable state survives crashes |
| Multi-step pipelines | Workflow orchestration |
| Cost tracking | Activity-level visibility |
| Debugging | Full execution history |

## Core Patterns

### Pattern 1: Activities should Wrap LLM Calls

- activity: call_llm
  - inputs:
    - model_id -> internally activity can route to different models, so we don't need 1 activity per unique model.
    - prompt / chat history
    - tools
    - etc.
  - returns model response, as a typed structured output

**Benefits**:
- Single activity handles multiple use cases
- Consistent retry handling
- Centralized configuration

### Pattern 2: Non-deterministic / heavy tools in Activities

Tools which are non-deterministic and/or heavy actions (file system, hitting APIs, etc.) should be placed in activities:

```
Workflow:
  ├── Activity: call_llm (get tool selection)
  ├── Activity: execute_tool (run selected tool)
  └── Activity: call_llm (interpret results)
```

**Benefits**:
- Independent retry for each step
- Clear audit trail in history
- Easier testing and mocking
- Failure isolation

### Pattern 3: Tools that Mutate Agent State can be in the Workflow directly

Generally, agent state is in bijection with workflow state. Thus, tools which mutate agent state and are deterministic (like TODO tools, just updating a hash map) typically belong in the workflow code rather than an activity.

```
Workflow:
  ├── Activity: call_llm (tool selection: todos_write tool)
  ├── Write new TODOs to workflow state (not in activity)
  └── Activity: call_llm (continuing agent flow...)
```

### Pattern 4: Centralized Retry Management

Disable retries in LLM client libraries, let Temporal handle retries.

- LLM Client Config:
  - max_retries = 0  ← Disable client retries at the LLM client level

Use either the default activity retry policy, or customize it as needed for the situation.

**Why**:
- Temporal retries are durable (survive crashes)
- Single retry configuration point
- Better visibility into retry attempts
- Consistent backoff behavior


### Pattern 5: Multi-Agent Orchestration

Complex pipelines with multiple specialized agents:

```
Deep Research Example:
  │
  ├── Planning Agent (Activity)
  │   └── Output: subtopics to research
  │
  ├── Query Generation Agent (Activity)
  │   └── Output: search queries per subtopic
  │
  ├── Parallel Web Search (Multiple Activities)
  │   └── Output: search results (resilient to partial failures)
  │
  └── Synthesis Agent (Activity)
      └── Output: final report
```

**Key Pattern**: Use parallel execution with `return_exceptions=True` to continue with partial results when some searches fail.

## Approximate Timeout Recommendations

| Operation Type | Recommended Timeout |
|----------------|---------------------|
| Simple LLM calls (GPT-4, GPT-5) | 30 seconds |
| Reasoning models (o1, o3, extended thinking) | 300 seconds (5 min) |
| Web searches | 300 seconds (5 min) |
| Simple tool execution | 30-60 seconds |
| Image generation | 120 seconds |
| Document processing | 60-120 seconds |

**Rationale**:
- Reasoning models need time for complex computation
- Web searches may hit rate limits requiring backoff
- Fast timeouts catch stuck operations
- Longer timeouts prevent premature failures for expensive operations

## Rate Limit Handling

### From HTTP Headers

Parse rate limit info from API responses:

- Response Headers:
  - Retry-After: 30
  - X-RateLimit-Remaining: 0

- Activity:
  - If rate limited:
    - Raise retryable error with a next retry delay
    - Temporal handles the delay

## Error Handling

### Retryable Errors
- Rate limits (429)
- Timeouts
- Temporary server errors (500, 502, 503)
- Network errors

### Non-Retryable Errors
- Invalid API key (401)
- Invalid input/prompt
- Content policy violations
- Model not found

## Best Practices

1. **Disable client retries** - Let Temporal handle all retries
2. **Set appropriate timeouts** - Based on operation type
3. **Separate activities** - One per logical operation
4. **Use structured outputs** - For type safety and validation
5. **Handle partial failures** - Continue with available results
6. **Monitor costs** - Track LLM calls at activity level
7. **Test with mocks** - Mock LLM responses in tests

## Observability

See `references/{your_language}/observability.md` for the language you are working in for documentation on implementing observability in Temporal. It is generally recommended to add observability for:
- Token usage, via activity logging
- any else to help track LLM usage and debug agentic flows, within moderation.
