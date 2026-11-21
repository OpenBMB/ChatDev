"""Invalid node numbers must surface as validation errors, not crashes.

``POST /api/config/schema/validate`` catches ``ConfigError`` only, so a node
field parsed with a bare ``int()`` escapes as an unhandled error and the
endpoint answers with HTTP 500 instead of reporting the document as invalid.
"""

import pytest

from runtime.bootstrap.schema import ensure_schema_registry_populated
from entity.config_loader import load_design_from_mapping
from entity.configs import ConfigError
from server.config_schema_router import SchemaValidateRequest, validate_document


DESIGN_YAML = """
graph:
  id: demo
  start: ["A"]
  nodes:
    - id: A
      type: literal
      context_window: "3 rows"
      config:
        content: hello
  edges: []
"""


@pytest.fixture(scope="module", autouse=True)
def _registered_schemas():
    ensure_schema_registry_populated()


def test_node_context_window_reports_config_error():
    with pytest.raises(ConfigError) as excinfo:
        load_design_from_mapping(
            {
                "graph": {
                    "id": "demo",
                    "start": ["A"],
                    "nodes": [
                        {
                            "id": "A",
                            "type": "literal",
                            "context_window": "3 rows",
                            "config": {"content": "hello"},
                        }
                    ],
                    "edges": [],
                }
            }
        )

    assert excinfo.value.path == "root.graph.nodes[0].context_window"


def test_schema_validate_reports_invalid_document():
    response = validate_document(SchemaValidateRequest(document=DESIGN_YAML))

    assert response["valid"] is False
    assert response["path"] == "root.graph.nodes[0].context_window"


def test_node_context_window_accepts_integers():
    design = load_design_from_mapping(
        {
            "graph": {
                "id": "demo",
                "start": ["A"],
                "nodes": [
                    {
                        "id": "A",
                        "type": "literal",
                        "context_window": 3,
                        "config": {"content": "hello"},
                    }
                ],
                "edges": [],
            }
        }
    )

    assert design.graph.nodes[0].context_window == 3
