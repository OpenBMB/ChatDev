# Python AI/LLM Integration Patterns

## Overview

This document provides Python-specific implementation details for integrating LLMs with Temporal. For conceptual patterns, see `references/core/ai-patterns.md`.

## Pydantic Data Converter Setup

**Required** for handling complex types like OpenAI response objects:

```python
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

client = await Client.connect(
    "localhost:7233",
    namespace="default",
    data_converter=pydantic_data_converter,
)
```

## OpenAI Client Configuration

**Critical**: Disable client retries, let Temporal handle them:

```python
from openai import AsyncOpenAI

openai_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    max_retries=0,  # CRITICAL: Disable client retries
    timeout=30.0,
)
```

## LiteLLM Configuration

For multi-model support:

```python
import litellm

litellm.num_retries = 0  # Disable LiteLLM retries
```

## Generic LLM Activity

Flexible, reusable activity for LLM calls:

```python
import openai
from temporalio import activity
from temporalio.exceptions import ApplicationError
from pydantic import BaseModel
from typing import Optional, Any

class LLMRequest(BaseModel):
    model: str
    system_prompt: str
    user_input: str
    tools: Optional[list] = None
    response_format: Optional[type] = None
    temperature: float = 0.7

class LLMResponse(BaseModel):
    content: str
    tool_calls: Optional[list] = None
    usage: dict

@activity.defn
async def call_llm(request: LLMRequest) -> LLMResponse:
    """Generic LLM activity supporting multiple use cases."""
    try:
        # As an example, calling OpenAI. This could be any chat API you wish though...
        response = await openai_client.chat.completions.create(
            model=request.model,
            messages=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_input},
            ],
            tools=request.tools,
            temperature=request.temperature,
        )
        return LLMResponse(
            content=response.choices[0].message.content or "",
            tool_calls=response.choices[0].message.tool_calls,
            usage=response.usage.model_dump(),
        )

    # Some example error cases to handle. These are not necessarily exhaustive, and depend on the API you are actually calling!
    except openai.AuthenticationError as e:
        # Invalid API key - permanent failure, don't retry
        raise ApplicationError(
            f"Invalid API key: {e}",
            type="AuthenticationError",
            non_retryable=True,
        )

    except openai.RateLimitError as e:
        # Rate limited - transient, let Temporal retry with backoff
        raise ApplicationError(
            f"Rate limited: {e}",
            type="RateLimitError",
            next_retry_delay=... # parse this from headers
        )

    except openai.APIStatusError as e:
        if e.status_code >= 500:
            # Server error - transient, retry
            raise ApplicationError(
                f"OpenAI server error ({e.status_code}): {e}",
                type="ServerError",
            )
        else:
            # Other client errors (400, etc.) - likely permanent
            raise ApplicationError(
                f"OpenAI client error ({e.status_code}): {e}",
                type="ClientError",
                non_retryable=True,
            )

    except openai.APIConnectionError as e:
        # Network error - transient, retry
        raise ApplicationError(
            f"Connection error: {e}",
            type="ConnectionError",
        )
```

## Activity Retry Policy

Configure retries at the workflow level:

```python
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities.llm import call_llm, LLMRequest

@workflow.defn
class LLMWorkflow:
    @workflow.run
    async def run(self, prompt: str) -> str:
        # Note that because call_llm classfies different types of exceptions as retryable / non-retryable,
        # we automatically get correct retry behavior just by calling it.
        response = await workflow.execute_activity(
            call_llm,
            LLMRequest(
                model="gpt-4",
                system_prompt="You are a helpful assistant.",
                user_input=prompt,
            ),
            start_to_close_timeout=timedelta(seconds=30),
        )
        return response.content
```

## Tool-Calling Agent Workflow

```python
from temporalio import workflow
from datetime import timedelta
from pydantic import BaseModel

with workflow.unsafe.imports_passed_through():
    from activities.llm import call_llm, LLMRequest, LLMResponse
    from activities.tools import execute_tool
    from models.tools import ToolDefinition

class AgentWorkflowInput(BaseModel):
    user_request: str
    tools: list[ToolDefinition]

@workflow.defn
class AgentWorkflow:
    @workflow.run
    async def run(self, input: AgentWorkflowInput) -> str:
        messages = []
        current_input = input.user_request

        while True:
            # Phase 1: Get LLM response with tools
            response = await workflow.execute_activity(
                call_llm,
                LLMRequest(
                    model="gpt-4",
                    system_prompt="You are a helpful agent with tools.",
                    user_input=current_input,
                    tools=[t.to_openai_format() for t in input.tools],
                ),
                start_to_close_timeout=timedelta(seconds=30),
            )

            # Check if LLM wants to use a tool
            if not response.tool_calls:
                return response.content

            # Phase 2: Execute tools
            for tool_call in response.tool_calls:
                tool_result = await workflow.execute_activity(
                    execute_tool,
                    tool_call,
                    start_to_close_timeout=timedelta(seconds=60),
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                })

            # Phase 3: Continue conversation with tool results
            current_input = f"Tool results: {messages}"
```

## Structured Outputs

Using Pydantic for validated responses:

```python
from pydantic import BaseModel
from temporalio import activity

class AnalysisResult(BaseModel):
    sentiment: str
    confidence: float
    key_topics: list[str]
    summary: str

@activity.defn
async def analyze_text(text: str) -> AnalysisResult:
    response = await openai_client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Analyze the following text."},
            {"role": "user", "content": text},
        ],
        response_format=AnalysisResult,
    )
    return response.choices[0].message.parsed
```

## Multi-Agent Pipeline (Deep Research)

```python
from temporalio import workflow
from datetime import timedelta
import asyncio

with workflow.unsafe.imports_passed_through():
    from activities.research import (
        generate_subtopics,
        generate_search_queries,
        search_web,
        synthesize_report,
    )

@workflow.defn
class DeepResearchWorkflow:
    @workflow.run
    async def run(self, topic: str) -> str:
        # Phase 1: Planning
        subtopics = await workflow.execute_activity(
            generate_subtopics,
            topic,
            start_to_close_timeout=timedelta(seconds=60),
        )

        # Phase 2: Query Generation
        queries = await workflow.execute_activity(
            generate_search_queries,
            subtopics,
            start_to_close_timeout=timedelta(seconds=60),
        )

        # Phase 3: Parallel Web Search (resilient to partial failures)
        search_tasks = [
            workflow.execute_activity(
                search_web,
                query,
                start_to_close_timeout=timedelta(seconds=300),
                schedule_to_close_timeout=timedelta(seconds=900), # We set a schedule to close timeout, so that if one search task repeatadly fails, then it won't hang up all the rest, in the below gather step.
            )
            for query in queries
        ]

        # Continue with partial results on failure
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        successful_results = [r for r in results if not isinstance(r, Exception)]

        # Phase 4: Synthesis
        report = await workflow.execute_activity(
            synthesize_report,
            {"topic": topic, "research": successful_results},
            start_to_close_timeout=timedelta(seconds=300),
        )

        return report
```

## OpenAI Agents SDK Integration

If using the OpenAI Agent SDK to create an agent, use Temporal's OpenAI contrib module to create a Temporal-aware durable agent:

```python
from temporalio import workflow
from temporalio.contrib.openai import create_workflow_agent
from agents import Agent, Runner

@workflow.defn
class DurableAgentWorkflow:
    @workflow.run
    async def run(self, task: str) -> str:
        # Create a Temporal-aware agent
        agent = create_workflow_agent(
            model="gpt-4",
            tools=[search_tool, calculator_tool],
        )
        # Run it. Under the hood, the automatically dispatches to activities for LLM calls, etc.
        result = await agent.run(task)
        return result.output
```

## Best Practices

1. **Always use Pydantic data converter** for complex types
2. **Disable retries in LLM clients** (max_retries=0)
3. **Set appropriate timeouts** per operation type
4. **Use structured outputs** for type safety
5. **Handle partial failures** in parallel operations
6. **Mock activities in tests** for fast, deterministic testing
7. **Log token usage** for cost tracking
8. **Version prompts** in code for reproducibility
