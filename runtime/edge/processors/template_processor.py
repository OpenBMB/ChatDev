"""Jinja2 template-based edge payload processor."""

import json
from typing import Any

from jinja2 import Environment, TemplateSyntaxError, UndefinedError, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from entity.configs.edge.edge_processor import TemplateEdgeProcessorConfig
from entity.messages import Message
from runtime.node.executor import ExecutionContext
from utils.log_manager import LogManager

from .base import EdgePayloadProcessor, ProcessorFactoryContext


class TemplateRenderError(Exception):
    """Raised when template rendering fails."""

    pass


def _fromjson_filter(value: str) -> Any:
    """Parse JSON string into Python object."""
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise TemplateRenderError(f"JSON decode error: {exc}") from exc


def _tojson_filter(value: Any) -> str:
    """Serialize Python object to JSON string."""
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise TemplateRenderError(f"JSON encode error: {exc}") from exc


class TemplateEdgePayloadProcessor(EdgePayloadProcessor[TemplateEdgeProcessorConfig]):
    """Transform edge payloads using Jinja2 templates."""

    def __init__(
        self, config: TemplateEdgeProcessorConfig, ctx: ProcessorFactoryContext
    ) -> None:
        super().__init__(config, ctx)

        # Create sandboxed Jinja2 environment
        self.env = SandboxedEnvironment(
            autoescape=False,
            undefined=StrictUndefined,  # Strict mode - fail on undefined variables
        )

        # Register custom filters
        self.env.filters["fromjson"] = _fromjson_filter
        self.env.filters["tojson"] = _tojson_filter

        # Compile template during initialization to catch syntax errors early
        try:
            self.template = self.env.from_string(config.template)
        except TemplateSyntaxError as exc:
            raise TemplateRenderError(f"Invalid template syntax: {exc}") from exc

    def transform(
        self,
        payload: Message,
        *,
        source_result: Message,
        from_node: Any,
        edge_link: Any,
        log_manager: LogManager,
        context: ExecutionContext,
    ) -> Message | None:
        """Render template with payload and context variables."""
        input_text = self._text(payload)

        # Build template context
        template_context = {
            "input": input_text,
            "environment": getattr(context, "environment", {}),
            "extracted": input_text,  # Default to input if no prior extraction
        }

        # Render template
        try:
            output = self.template.render(template_context)
        except UndefinedError as exc:
            available_keys = ", ".join(sorted(template_context.keys()))
            raise TemplateRenderError(
                f"Undefined variable in template: {exc}. Available context keys: {available_keys}"
            ) from exc
        except TemplateRenderError:
            raise
        except Exception as exc:
            raise TemplateRenderError(f"Template rendering failed: {exc}") from exc

        # Return new message with rendered output
        cloned = payload.clone()
        cloned.content = output
        return cloned
