"""Run the frozen framework-only probe cohort using the existing solver."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    path.chmod(0o600)


def verify(experiment, root=ROOT):
    protocol = read(experiment / 'experiment-protocol.json')
    if protocol['protocol'] != 'xbench-pilot-experiment-v2-framework-only':
        raise ValueError('unexpected_protocol')
    if list(protocol['arms']) != ['framework_native']:
        raise ValueError('framework_only_required')
    sample = read(experiment / 'sample-manifest.json')
    expected = {
        experiment / 'sample-manifest.json': protocol['sample_manifest_sha256'],
        experiment / 'solver/tasks.jsonl': sample['sample_solver_sha256'],
        experiment / 'framework-config.private.json': protocol['arms']['framework_native']['configuration_sha256'],
        root / 'sgar_mvp/config.json': protocol['identities']['original_config_sha256'],
        root / 'Pool/resources/json/effective_combine.json': protocol['identities']['effective_pool_sha256'],
    }
    expected.update({root / 'sgar_mvp/config' / name: digest
                     for name, digest in protocol['identities']['policy_sha256'].items()})
    for path, digest in expected.items():
        if sha(path) != digest:
            raise ValueError('frozen_identity_mismatch:' + path.name)
    tasks = [json.loads(x) for x in (experiment / 'solver/tasks.jsonl').read_text().splitlines() if x.strip()]
    if [x['id'] for x in tasks] != protocol['sample_ids'] or sample['sample_ids'] != protocol['sample_ids']:
        raise ValueError('sample_id_mismatch')
    fields = {'id', 'benchmark', 'query', 'root_url', 'query_sha256'}
    if any(set(x) != fields or hashlib.sha256(x['query'].encode()).hexdigest() != x['query_sha256'] for x in tasks):
        raise ValueError('solver_projection_or_query_mismatch')
    probes = protocol['execution']['initial_phase_ids']
    if probes != sample['probe_ids'] or probes != protocol['probe_ids'] or len(probes) != 3:
        raise ValueError('probe_selection_mismatch')
    return protocol


def hold_reason(row, limits):
    if row.get('prediction_extraction',{}).get('status')=='error':
        return 'prediction_extraction_error'
    if row['pipeline_status'] in {'complete_success','success_with_warnings'} and not row.get('prediction','').strip():
        return 'missing_delivered_prediction'
    cost = row.get('cost_summary')
    if not isinstance(cost, dict):
        return 'missing_cost_summary'
    if cost.get('max_generation_requests') != limits['max_generation_requests']:
        return 'request_limit_mismatch'
    if cost.get('resolved_cost_policy') != limits['model_cost_policy']:
        return 'cost_policy_mismatch'
    for key in ['accounting_persistence_failure_count', 'pending_call_count',
                'response_usage_invalid_count', 'response_usage_missing_count',
                'response_usage_unpriced_count', 'no_response_attempt_count']:
        if key not in cost or cost[key] != 0:
            return 'accounting_or_provider_issue:' + key
    budget_stop = cost.get('budget_status', {}).get('limit_reached', False)
    if row['return_code'] and not (row.get('timed_out') or budget_stop):
        return 'solver_nonzero_exit_requires_inspection'
    if row['pipeline_status'] not in {'complete_success', 'success_with_warnings'} and not (row.get('timed_out') or budget_stop):
        return 'incomplete_pipeline_requires_inspection'
    return None


def stop(proc):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def command(argv, logfile, timeout):
    with logfile.open('wb') as stream:
        logfile.chmod(0o600)
        proc = subprocess.Popen(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return proc.wait(timeout=timeout)
        except BaseException:
            stop(proc)
            raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--experiment', required=True)
    p.add_argument('--check-only', action='store_true')
    p.add_argument('--probe-id', help='Run one member of the frozen probe independently for diagnosis')
    for name in ['output', 'references', 'image', 'image-sha256', 'apptainer', 'tools-prefix']:
        p.add_argument('--' + name)
    a = p.parse_args()
    experiment = Path(a.experiment).resolve()
    protocol = verify(experiment)
    if a.probe_id is not None and a.probe_id not in protocol['probe_ids']:
        raise ValueError('diagnostic_id_outside_frozen_probe')
    selected_ids = [a.probe_id] if a.probe_id is not None else protocol['probe_ids']
    scope = 'independent_diagnostic' if a.probe_id is not None else 'frozen_probe'
    if a.check_only:
        print(json.dumps({'verified': True, 'probe_ids': protocol['probe_ids'], 'framework_only': True,
                          'selected_ids': selected_ids, 'scope': scope}))
        return 0
    if not os.environ.get('SLURM_JOB_ID'):
        raise ValueError('allocated_job_required')
    if not all(getattr(a, name) for name in ['output', 'references', 'image', 'image_sha256', 'apptainer', 'tools_prefix']):
        raise ValueError('runtime_arguments_required')
    out = Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    save(out / 'protocol-snapshot.json', protocol)
    limits = protocol['shared_limits']
    save(out / 'run-identity.json', {
        'job_id': os.environ['SLURM_JOB_ID'], 'protocol_sha256': sha(experiment / 'experiment-protocol.json'),
        'sample_manifest_sha256': sha(experiment / 'sample-manifest.json'),
        'selected_ids': selected_ids, 'scope': scope, 'deadline_seconds': limits['deadline_seconds'],
        'max_generation_requests': limits['max_generation_requests'],
        'source_sha256': {name: sha(ROOT / 'scripts' / name) for name in ['research_pilot.py', 'research_benchmark.py', 'run_apptainer.py']},
    })
    summary = {'job_id': os.environ['SLURM_JOB_ID'], 'selected_ids': selected_ids, 'scope': scope,
               'state': 'running', 'trials': [], 'hold_reason': None}
    save(out / 'summary.json', summary)
    container = ['--image', a.image, '--image-sha256', a.image_sha256,
                 '--apptainer', a.apptainer, '--tools-prefix', a.tools_prefix]
    try:
        for ident in selected_ids:
            print(json.dumps({'event': 'task_started', 'id': ident}), flush=True)
            dest = out / ('task-' + ident)
            argv = [sys.executable, '-m', 'scripts.research_benchmark', 'run',
                    '--tasks', str(experiment / 'solver/tasks.jsonl'), '--output', str(dest),
                    '--config', str(experiment / 'framework-config.private.json'),
                    '--limit', '1', '--id', ident, '--deadline-sec', str(limits['deadline_seconds']),
                    '--max-generation-requests', str(limits['max_generation_requests']), *container]
            started = time.monotonic()
            code = command(argv, out / (ident + '-solver.log'), limits['deadline_seconds'] + 120)
            predictions = dest / 'predictions.jsonl'
            if not predictions.exists():
                summary['hold_reason'] = 'missing_trial_record:' + ident
                summary['trials'].append({'id': ident, 'solver_exit_code': code, 'elapsed_seconds': round(time.monotonic() - started, 3)})
                break
            rows = [json.loads(x) for x in predictions.read_text().splitlines() if x.strip()]
            if len(rows) != 1 or rows[0]['id'] != ident:
                raise ValueError('prediction_identity_mismatch')
            row = rows[0]
            record = {key: row[key] for key in ['id', 'return_code', 'timed_out', 'elapsed_seconds', 'pipeline_status']}
            record.update(prediction_present=bool(row['prediction'].strip()), cost_summary=row['cost_summary'])
            gradefile = out / (ident + '-scores.jsonl')
            gradecode = command([sys.executable, '-m', 'scripts.research_benchmark', 'score',
                                 '--tasks', str(experiment / 'solver/tasks.jsonl'), '--references', a.references,
                                 '--predictions', str(predictions), '--output', str(gradefile),
                                 '--judge-model', protocol['evaluation']['judge_model']],
                                out / (ident + '-judge.log'), 210)
            if gradefile.exists():
                grades = [json.loads(x) for x in gradefile.read_text().splitlines() if x.strip()]
                if len(grades) == 1 and grades[0]['id'] == ident:
                    record['grade'] = {k: grades[0].get(k) for k in ['score', 'status', 'usage', 'judge_model']}
            record['judge_exit_code'] = gradecode
            summary['trials'].append(record)
            summary['hold_reason'] = hold_reason(row, limits)
            save(out / 'summary.json', summary)
            print(json.dumps({'event': 'task_finished', 'id': ident, 'pipeline_status': row['pipeline_status'],
                              'score': record.get('grade', {}).get('score'), 'hold_reason': summary['hold_reason']}), flush=True)
            if summary['hold_reason']:
                break
        summary['state'] = 'held' if summary['hold_reason'] else 'completed'
        scores = [x.get('grade', {}).get('score') for x in summary['trials']]
        summary['answer_accuracy'] = sum(scores) / len(scores) if len(scores) == len(protocol['probe_ids']) and all(x is not None for x in scores) else None
        save(out / 'summary.json', summary)
        return 4 if summary['hold_reason'] else 0
    except BaseException as exc:
        summary.update(state='interrupted_or_error', error_class=type(exc).__name__)
        save(out / 'summary.json', summary)
        raise


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, interrupted)
    raise SystemExit(main())
