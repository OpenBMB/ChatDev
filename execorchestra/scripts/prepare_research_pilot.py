"""Freeze a reproducible task sample using IDs only, without reading answers."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['tasks', 'source-manifest', 'output']:
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--seed', default='20261030')
    parser.add_argument('--count', type=int, default=15)
    parser.add_argument('--probe-count', type=int, default=3)
    args = parser.parse_args()
    source = json.loads(Path(args.source_manifest).read_text(encoding='utf-8'))
    raw = Path(args.tasks).read_bytes()
    if sha(raw) != source['solver_inputs_sha256']:
        raise ValueError('source_task_file_identity_mismatch')
    tasks = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    if len(tasks) != source['count'] or len({x['id'] for x in tasks}) != len(tasks):
        raise ValueError('source_count_or_duplicate_id')
    if not 0 < args.probe_count <= args.count <= len(tasks):
        raise ValueError('invalid_sample_sizes')
    for task in tasks:
        if set(task) != {'id', 'benchmark', 'query', 'root_url', 'query_sha256'}:
            raise ValueError('unexpected_solver_fields')
        if sha(task['query'].encode()) != task['query_sha256']:
            raise ValueError('query_identity_mismatch')
    def rank(task):
        key = '\n'.join(['research-pilot-v1', args.seed, source['source_sha256'], task['id']])
        return sha(key.encode('utf-8')), task['id']
    selected = sorted(tasks, key=rank)[:args.count]
    encoded = ''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in selected).encode('utf-8')
    manifest = {
        'protocol': 'research-pilot-sample-v1',
        'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'seed': args.seed,
        'selection': 'ascending SHA256(research-pilot-v1 + newline + seed + newline + source_sha256 + newline + task_id); task_id breaks ties',
        'selection_uses_question_text': False,
        'selection_uses_answers_or_outcomes': False,
        'source_revision': source['source_revision'],
        'source_sha256': source['source_sha256'],
        'source_solver_sha256': sha(raw),
        'source_count': len(tasks),
        'sample_count': len(selected),
        'probe_ids': [x['id'] for x in selected[:args.probe_count]],
        'sample_ids': [x['id'] for x in selected],
        'sample_solver_sha256': sha(encoded),
        'selected_queries': [{'id': x['id'], 'query_sha256': x['query_sha256'], 'rank_sha256': rank(x)[0]}
                             for x in selected],
        'public_distribution': 'manifest only; solver task plaintext stays private',
        'analysis_scope': 'development pilot; not a held-out final performance estimate',
        'replace_failed_tasks': False,
    }
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    solver = output/'solver'
    solver.mkdir(mode=0o700)
    taskfile = solver/'tasks.jsonl'
    taskfile.write_bytes(encoded)
    taskfile.chmod(0o600)
    (output/'sample-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'sample_count':len(selected), 'sample_ids':manifest['sample_ids'],
                      'probe_ids':manifest['probe_ids'], 'sample_solver_sha256':sha(encoded)}))


if __name__ == '__main__':
    main()
