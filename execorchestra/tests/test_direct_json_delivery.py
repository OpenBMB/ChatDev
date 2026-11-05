"""Direct writes use the compiled schema without discarding macro constraints."""
from types import SimpleNamespace

import pytest

from sgar_mvp.src.artifact_semantics import OutputContractViolation
from sgar_mvp.src.orchestrator import _validate_direct_final_write_source
from sgar_mvp.src.schema import OperationKind, ResourceOutputContract, SubtaskOutputContract


def fixture(schema=True):
    hint = {"type": "object", "properties": {"value": {"type": "integer"}},
            "required": ["value"], "additionalProperties": False} if schema else None
    producer = SimpleNamespace(step_id="calculate", output_key="result", resource_application=None,
        operation_kind=OperationKind.CALL_MODEL,
        expected_output_contract=ResourceOutputContract(artifact_type="json", schema_hint=hint))
    writer = SimpleNamespace(step_id="save", output_key="receipt", resource_application=None,
        operation_kind=OperationKind.WRITE_FILE,
        input_bindings={"content": {"from_step": "calculate", "output_key": "result"}},
        expected_output_contract=ResourceOutputContract(artifact_type="json"))
    plan = SimpleNamespace(steps=[producer, writer], final_output_from="receipt")
    macro = SubtaskOutputContract(artifact_type="json", output_extension=".json")
    return plan, producer, macro


def validate(content='{"value": 7}', *, schema=True, macro_schema=None, transform=False):
    plan, producer, macro = fixture(schema)
    if macro_schema is not None:
        macro = macro.model_copy(update={"json_schema": macro_schema})
    if transform:
        plan.steps[-1].input_bindings["content"] = {"literal": "different content"}
    return _validate_direct_final_write_source(plan=plan, producer_step=producer,
                                              task_output_contract=macro, content=content)


def test_deferred_macro_schema_uses_compiled_contract():
    assert validate()["status"] == "pass"


def test_missing_required_field_is_rejected():
    with pytest.raises(OutputContractViolation, match="artifact_execution_schema_mismatch"):
        validate("{}")


def test_invalid_json_is_rejected():
    with pytest.raises(OutputContractViolation, match="artifact_json_invalid"):
        validate("{")


def test_explicit_incompatible_macro_remains_enforced():
    with pytest.raises(OutputContractViolation, match="artifact_macro_requirement_conflict"):
        validate(macro_schema={"type": "array", "items": {"type": "integer"}})


def test_stricter_macro_value_constraint_remains_enforced():
    with pytest.raises(OutputContractViolation, match="artifact_macro_requirement_conflict"):
        validate(macro_schema={"type": "object", "properties": {"value": {"type": "integer", "minimum": 10}}})


def test_missing_schema_on_both_sides_fails_closed():
    with pytest.raises(OutputContractViolation, match="artifact_execution_schema_missing"):
        validate(schema=False)


def test_non_direct_bindings_keep_the_existing_validation_path():
    assert validate(transform=True) is None
