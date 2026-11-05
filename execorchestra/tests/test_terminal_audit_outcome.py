"""Final audits govern CLI success; catalog prose is not authentication data."""
import base64
import json

import pytest

from sgar_mvp.main import _finalized_terminal_state, _terminal_exit_code
from sgar_mvp.src.portability_audit import audit_run_portability
from sgar_mvp.src.run_workspace import RunManifestStore


def write_trace(root, value):
    (root/'trace.json').write_text(json.dumps(value),encoding='utf-8')


def store(root):
    return RunManifestStore(run_dir=root,run_id='unit-run',request_id='unit-request',invocation_sha256='1'*64)


def finalize(manifest_store, status='succeeded'):
    return manifest_store.terminal(status,ledger_hashes={},unmatched_calls={},framework_source_clean=True)


def test_catalog_basic_coverage_prose_is_portable(tmp_path):
    write_trace(tmp_path,{'description':'Run all Go packages with basic coverage reporting. Basic node-centrality scoring is supported.'})
    assert audit_run_portability(tmp_path)['valid']


@pytest.mark.parametrize('authorization',[
    'Bearer test-authorization-token',
    'Basic '+base64.b64encode(b'test-user:test-password').decode(),
    'Basic '+base64.b64encode(b'u:p').decode(),
    'bAsIc '+base64.b64encode(b'test-user:test-password').decode().rstrip('='),
])
def test_real_authorization_values_remain_rejected(tmp_path,authorization):
    write_trace(tmp_path,{'header':authorization})
    assert audit_run_portability(tmp_path)['secret_occurrences']==['trace.json']


def test_natural_basic_phrase_does_not_hide_later_credentials(tmp_path):
    value='basic coverage; Authorization: Basic '+base64.b64encode(b'user:password').decode()
    write_trace(tmp_path,{'description':value})
    assert not audit_run_portability(tmp_path)['valid']


def test_exact_secret_and_hidden_value_checks_are_unchanged(tmp_path):
    write_trace(tmp_path,{'value':'test-private-secret and hidden-reference'})
    audit=audit_run_portability(tmp_path,secret_values=['test-private-secret'],hidden_values=['hidden-reference'])
    assert audit['secret_occurrences']==['trace.json']
    assert audit['hidden_value_occurrences']==['trace.json']


def test_final_audit_failure_overrides_earlier_pipeline_success(tmp_path):
    manifest_store=store(tmp_path)
    write_trace(tmp_path,{'header':'Bearer test-authorization-token'})
    manifest=finalize(manifest_store)
    assert manifest.status=='framework_failure' and not manifest.pipeline_succeeded
    pipeline,status=_finalized_terminal_state('success','succeeded',manifest)
    assert pipeline=='structured_failure' and _terminal_exit_code(status)==1


def test_clean_final_manifest_preserves_success_exit(tmp_path):
    manifest=finalize(store(tmp_path))
    assert manifest.pipeline_succeeded
    pipeline,status=_finalized_terminal_state('success','succeeded',manifest)
    assert pipeline=='success' and _terminal_exit_code(status)==0


def test_interruption_exit_is_preserved(tmp_path):
    manifest=finalize(store(tmp_path),'interrupted')
    pipeline,status=_finalized_terminal_state('interrupted','interrupted',manifest)
    assert pipeline=='interrupted' and _terminal_exit_code(status)==130
