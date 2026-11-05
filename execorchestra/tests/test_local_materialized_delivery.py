"""Local file effects, native receipts, and strict delivery remain separate."""
import hashlib
from types import SimpleNamespace

import pytest

from sgar_mvp.src.artifact_semantics import OutputContractViolation, validate_delivery_content
from sgar_mvp.src.orchestrator import (
    DAGOrchestrator, RuntimeArtifactRecord, RuntimeArtifactRegistry,
    _realize_materialized_delivery_result,
)


def fixture(tmp_path, *, content=b'{"count":7}', logical='nested/result.json'):
    path=tmp_path/'observed';path.write_bytes(content)
    receipt_path=tmp_path/'receipt';receipt_path.write_text('{"status":"success"}')
    receipt=RuntimeArtifactRecord(str(receipt_path),'json','realized_step_output')
    record=RuntimeArtifactRecord(str(path),'file','tool_output',metadata={
        'source_task':'task','source_step':'writer','source_output':'receipt',
        'logical_path':logical,'tool_path':'/app/'+logical,
        'content_sha256':hashlib.sha256(content).hexdigest(),
    })
    orchestrator=DAGOrchestrator.__new__(DAGOrchestrator)
    orchestrator.execution_substrate=None
    orchestrator.artifact_registry=RuntimeArtifactRegistry(by_step={
        'task:writer:receipt':receipt,'task:writer:receipt:file:observed':record})
    step=SimpleNamespace(output_key='receipt',expected_output_contract=SimpleNamespace(artifact_type='json'),
        resource_application=SimpleNamespace(output_realization_contract=SimpleNamespace(realization_kind='materialized_file_side_effect')))
    contract={'artifact_type':'json','produced_files':[{'path_hint':'nested/result.json','artifact_type':'json','required':True}]}
    return orchestrator,step,record,receipt,contract


def select(orchestrator,step,contract):
    return orchestrator._formal_records_for_output(task_id='task',step_id='writer',output_key='receipt',output_contract=contract,step=step)


def test_exact_file_content_is_selected_instead_of_native_receipt(tmp_path):
    orchestrator,step,record,receipt,contract=fixture(tmp_path)
    records=select(orchestrator,step,contract)
    assert records[0].path==record.path and records[0].artifact_type=='json'
    result=SimpleNamespace(output_data=receipt_path_text(receipt),cost_metric={'application_step_outputs':{'receipt':receipt_path_text(receipt)}})
    _realize_materialized_delivery_result(result,step,records[0])
    assert result.output_data=='{"count":7}'
    assert result.cost_metric['application_step_outputs']['receipt']=='{"count":7}'
    assert result.cost_metric['materialized_delivery']['native_receipt_sha256']==hashlib.sha256(receipt_path_text(receipt).encode()).hexdigest()


def receipt_path_text(record):
    from pathlib import Path
    return Path(record.path).read_text()


def test_file_selection_does_not_relax_json_validation(tmp_path):
    orchestrator,step,_,_,contract=fixture(tmp_path,content=b'{"unexpected":7}')
    record=select(orchestrator,step,contract)[0]
    target={'artifact_type':'json','json_schema':{'type':'object','properties':{'count':{'type':'integer'}},'required':['count'],'additionalProperties':False}}
    from pathlib import Path
    with pytest.raises(OutputContractViolation):validate_delivery_content(Path(record.path).read_bytes(),target,target)


def test_tampered_file_is_rejected_before_selection(tmp_path):
    orchestrator,step,record,_,contract=fixture(tmp_path)
    from pathlib import Path
    Path(record.path).write_bytes(b'{"count":8}')
    with pytest.raises(RuntimeError,match='content_hash_mismatch'):select(orchestrator,step,contract)


def test_different_producer_is_not_promoted(tmp_path):
    orchestrator,step,record,receipt,contract=fixture(tmp_path)
    record.metadata['source_step']='other-step'
    assert select(orchestrator,step,contract)[0] is receipt


def test_matching_basename_in_a_different_directory_is_not_promoted(tmp_path):
    orchestrator,step,_,receipt,contract=fixture(tmp_path,logical='unrelated/result.json')
    assert select(orchestrator,step,contract)[0] is receipt


def test_inline_and_non_materialized_outputs_keep_the_existing_order(tmp_path):
    orchestrator,step,_,receipt,contract=fixture(tmp_path)
    assert select(orchestrator,step,{'artifact_type':'json'})[0] is receipt
    step.resource_application.output_realization_contract.realization_kind='identity'
    assert select(orchestrator,step,contract)[0] is receipt


def test_readback_checks_identity_again_if_the_file_changes(tmp_path):
    orchestrator,step,record,_,contract=fixture(tmp_path)
    selected=select(orchestrator,step,contract)[0]
    from pathlib import Path
    Path(record.path).write_bytes(b'{"count":9}')
    with pytest.raises(RuntimeError,match='content_hash_mismatch'):
        _realize_materialized_delivery_result(SimpleNamespace(output_data='receipt',cost_metric={}),step,selected)
