"""Template node executor."""

import json
from typing import List, Any

from jinja2 import TemplateSyntaxError, UndefinedError, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from entity.configs import Node
from entity.configs.node.template import TemplateNodeConfig
from entity.messages import Message, MessageRole
from runtime.node.executor.base import NodeExecutor


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


class TemplateNodeExecutor(NodeExecutor):
    """Format input messages using Jinja2 templates and emit the result."""

    def execute(self, node: Node, inputs: List[Message]) -> List[Message]:
        if node.node_type != "template":
            raise ValueError(f"Node {node.id} is not a template node")

        config = node.as_config(TemplateNodeConfig)
        if config is None:
            raise ValueError(f"Node {node.id} missing template configuration")

        self._ensure_not_cancelled()

        # Handle empty inputs - return empty message
        if not inputs:
            warning_msg = f"Template node '{node.id}' triggered without inputs"
            self.log_manager.warning(
                warning_msg, node_id=node.id, details={"input_count": 0}
            )
            return [Message(content="", role=MessageRole.USER)]

        # Get latest input message (consistent with passthrough node behavior)
        latest_input = inputs[-1]
        input_text = latest_input.text_content()

        if len(inputs) > 1:
            self.log_manager.debug(
                f"Template node '{node.id}' received {len(inputs)} inputs; processing the latest entry",
                node_id=node.id,
                details={"input_count": len(inputs)},
            )

        # Create sandboxed Jinja2 environment
        env = SandboxedEnvironment(
            autoescape=False,
            undefined=StrictUndefined,  # Strict mode - fail on undefined variables
        )

        # Register custom filters
        env.filters["fromjson"] = _fromjson_filter
        env.filters["tojson"] = _tojson_filter

        # Compile template
        try:
            template = env.from_string(config.template)
        except TemplateSyntaxError as exc:
            error_msg = f"Invalid template syntax in node '{node.id}': {exc}"
            self.log_manager.error(
                error_msg, node_id=node.id, details={"error": str(exc)}
            )
            raise TemplateRenderError(error_msg) from exc

        # Build template context
        template_context = {
            "input": input_text,
            "environment": getattr(self.context, "environment", {}),
        }

        # Render template
        try:
            output = template.render(template_context)
        except UndefinedError as exc:
            available_keys = ", ".join(sorted(template_context.keys()))
            error_msg = f"Undefined variable in template for node '{node.id}': {exc}. Available context keys: {available_keys}"
            self.log_manager.error(
                error_msg,
                node_id=node.id,
                details={"error": str(exc), "available_keys": available_keys},
            )
            raise TemplateRenderError(error_msg) from exc
        except TemplateRenderError:
            raise
        except Exception as exc:
            error_msg = f"Template rendering failed for node '{node.id}': {exc}"
            self.log_manager.error(
                error_msg, node_id=node.id, details={"error": str(exc)}
            )
            raise TemplateRenderError(error_msg) from exc

        # Return new message with rendered output
        return [
            self._build_message(
                role=MessageRole.USER,
                content=output,
                source=node.id,
                preserve_role=False,
            )
        ]
