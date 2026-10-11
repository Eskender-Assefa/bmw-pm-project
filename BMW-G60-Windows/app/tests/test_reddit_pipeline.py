import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import select, func
from backend import reddit_pipeline as pipeline
from backend.models import Job, Feedback, Source, AuditEvent
from backend.audit import verify_audit

SECRET = 'sk-test-only-never-a-real-key'
RAW = [
    {'row_id': 'web_test_1', 'comment_text': 'The seats are comfortable on long trips. Café!',
     'date_displayed': 'two days ago', 'source_url': 'https://www.reddit.com/r/BMW/comments/abc123/test/',
     'text_verification': 'unverified_model_extraction', 'extraction_method': 'openai_web_search',
     'extraction_model': 'collector-test', 'source_response_file': 'api_responses/000001_extract.json'},
    {'row_id': 'web_test_2', 'comment_text': 'Generic unrelated reaction.', 'date_displayed': None,
     'source_url': 'https://www.reddit.com/r/BMW/comments/abc123/test/',
     'text_verification': 'unverified_model_extraction'},
]


def write_jsonl(path, rows):
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')


@pytest.fixture
def harness(monkeypatch):
    queued, calls = [], []
    options = {'collector_code': 0, 'categorizer_code': 0, 'empty': False, 'all_discarded': False, 'bad_output': False, 'duplicate': False}
    monkeypatch.setattr(pipeline, 'executor', SimpleNamespace(submit=lambda fn, *args: queued.append((fn, args))))
    def fake_run(args, **kwargs):
        calls.append(args)
        assert kwargs['shell'] is False
        assert kwargs['env']['OPENAI_API_KEY'] == SECRET
        assert kwargs['env']['OPENAI_BASE_URL'] == 'https://api.openai.com/v1'
        assert SECRET not in ' '.join(args)
        assert kwargs['stdout'] == subprocess.DEVNULL and kwargs['stderr'] == subprocess.DEVNULL
        if args[1] == str(pipeline.COLLECTOR):
            out = Path(args[args.index('--out') + 1])
            out.mkdir(parents=True)
            rows = [] if options['empty'] else RAW + ([RAW[0]] if options['duplicate'] else [])
            write_jsonl(out / 'comments.jsonl', rows)
            (out / 'run_report.json').write_text('{}', encoding='utf-8')
            return SimpleNamespace(returncode=options['collector_code'])
        assert args[1] == str(pipeline.CATEGORIZER)
        input_path, output_path = Path(args[2]), Path(args[3])
        assert input_path.name == 'input.jsonl' and output_path.name == 'categorized.jsonl'
        assert input_path.read_bytes() == (input_path.parent / 'collector/comments.jsonl').read_bytes()
        module = pipeline.categorizer_module()
        rows = [] if options['all_discarded'] else [module.output_row(RAW[0], 'Comfort', 50)]
        if options['bad_output']:
            rows[0]['sentiment_score'] = 101
        write_jsonl(output_path, rows)
        discards = [module.discard_record(i, row) for i, row in enumerate(RAW, 1) if options['all_discarded'] or i == 2]
        write_jsonl(module.discard_log_path(output_path), discards)
        return SimpleNamespace(returncode=options['categorizer_code'])
    monkeypatch.setattr(pipeline.subprocess, 'run', fake_run)
    return queued, calls, options


def start(client, harness, model='G60', count=2):
    response = client.post('/api/v1/reddit/runs', json={'api_key': SECRET, 'model': model, 'count': count})
    assert response.status_code == 202, response.text
    assert SECRET not in response.text
    return response.json()['id']


def finish(client, harness, job_id):
    fn, args = harness[0].pop(0)
    fn(*args)
    return client.get('/api/v1/jobs/' + job_id).json()


@pytest.mark.parametrize('model', ['G60', 'G70', 'F70'])
def test_complete_pipeline_and_import(client, session, harness, model):
    old_key = os.environ.get('OPENAI_API_KEY')
    job_id = start(client, harness, model)
    job = finish(client, harness, job_id)
    assert job['state'] == 'succeeded', job
    assert os.environ.get('OPENAI_API_KEY') == old_key
    assert job['result']['collected'] == 2 and job['result']['categorized'] == 1 and job['result']['discarded'] == 1
    assert job['result']['imported'] == 1
    assert job['result']['imported_source_id']
    assert 'visible in Reviews & Comments' in job['progress']
    collector, categorizer = harness[1]
    assert collector[collector.index('--topic') + 1] == 'BMW ' + model
    assert collector[collector.index('--count') + 1] == '2'
    assert '--model' in collector and '--model' in categorizer
    for artifact in pipeline.ARTIFACTS:
        response = client.get(f'/api/v1/reddit/runs/{job_id}/files/{artifact}')
        assert response.status_code == 200
        assert SECRET.encode() not in response.content
    output = client.get(f'/api/v1/reddit/runs/{job_id}/files/categorized.jsonl').text
    assert set(json.loads(output)) == {'row_id', 'categorie', 'comment', 'date_displayed', 'sentiment_score'}
    source_id = job['result']['imported_source_id']
    again = client.post(f'/api/v1/reddit/runs/{job_id}/import').json()
    assert again['imported'] == 0 and again['skipped'] == 1
    records = client.get('/api/v1/feedback', params={'model': model, 'country': 'all', 'origin': 'unknown', 'source_id': source_id}).json()
    assert records['total'] == 1
    row = records['items'][0]
    assert row['country'] == 'unknown' and row['powertrain'] == 'unknown' and row['source_date'] is None
    assert row['origin'] == 'unknown' and row['aspects'][0]['category'] == 'C05'
    assert row['aspects'][0]['status'] == 'pending'
    evidence = client.get('/api/v1/evidence/' + row['evidence_id']).json()
    assert evidence['locator']['raw_record'] == RAW[0]
    assert evidence['aspects'][0]['sentiment'] == 50
    assert session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == 'reddit.imported', AuditEvent.entity_id == source_id)) == 1
    assert verify_audit(session)['valid']
    assert SECRET not in client.get('/api/v1/jobs').text
    assert SECRET not in client.get('/api/v1/reddit/runs').text
    assert client.get(f'/api/v1/reddit/runs/{job_id}/files/checkpoint.sqlite3').status_code == 404


def test_partial_collection_and_all_filtered_output(client, harness):
    harness[2]['collector_code'] = 2
    harness[2]['all_discarded'] = True
    job_id = start(client, harness, count=5)
    job = finish(client, harness, job_id)
    assert job['state'] == 'succeeded'
    assert job['result']['shortfall'] == 3 and job['result']['categorized'] == 0
    assert job['result']['ready_for_import'] is False
    assert client.post(f'/api/v1/reddit/runs/{job_id}/import').status_code == 409


@pytest.mark.parametrize('option,value,commands', [
    ('collector_code', 1, 1), ('categorizer_code', 1, 2), ('bad_output', True, 2),
    ('empty', True, 1), ('duplicate', True, 1),
])
def test_failures_do_not_expose_unvalidated_artifacts(client, harness, option, value, commands):
    harness[2][option] = value
    job_id = start(client, harness)
    job = finish(client, harness, job_id)
    assert job['state'] == 'failed'
    assert len(harness[1]) == commands
    assert SECRET not in json.dumps(job)
    assert client.get(f'/api/v1/reddit/runs/{job_id}/files/categorized.jsonl').status_code == 409
    assert client.post(f'/api/v1/reddit/runs/{job_id}/import').status_code == 409
    assert client.post(f'/api/v1/jobs/{job_id}/retry').status_code == 409


def test_key_not_echoed_on_invalid_requests_and_concurrent_run_blocked(client, harness):
    for fields in ({'model': 'G60;anything'}, {'count': 0}, {'count': 1.5}, {'count': '2'}, {'count': True}, {'count': 10001}, {'extra': SECRET}):
        response = client.post('/api/v1/reddit/runs', json={'api_key': SECRET, 'model': 'G60', 'count': 2, **fields})
        assert response.status_code == 422
        assert SECRET not in response.text
    start(client, harness)
    assert client.post('/api/v1/reddit/runs', json={'api_key': SECRET, 'model': 'G60', 'count': 2}).status_code == 409


def test_subprocess_exception_never_leaks_key(client, harness, monkeypatch):
    def failing_run(*args, **kwargs):
        raise RuntimeError('Deliberate mocked exception containing ' + SECRET)
    monkeypatch.setattr(pipeline.subprocess, 'run', failing_run)
    job_id = start(client, harness)
    job = finish(client, harness, job_id)
    assert job['state'] == 'failed' and SECRET not in json.dumps(job)


def test_automatic_import_failure_rolls_back_and_fails_the_job(client, session, harness, monkeypatch):
    job_id = start(client, harness)
    before = session.scalar(select(func.count()).select_from(Feedback))
    existing_sources = set(session.scalars(select(Source.id).where(Source.extraction_version == 'reddit-import-v1')))
    def fail_evidence(*args, **kwargs):
        raise RuntimeError('failed import')
    monkeypatch.setattr(pipeline, 'evidence', fail_evidence)
    job = finish(client, harness, job_id)
    assert job['state'] == 'failed'
    assert session.scalar(select(func.count()).select_from(Feedback)) == before
    assert set(session.scalars(select(Source.id).where(Source.extraction_version == 'reddit-import-v1'))) == existing_sources


def test_changed_artifact_blocks_repeat_import(client, harness):
    job_id = start(client, harness)
    finish(client, harness, job_id)
    output = pipeline.run_folder(job_id) / 'categorized.jsonl'
    output.write_text('{}\n', encoding='utf-8')
    response = client.post(f'/api/v1/reddit/runs/{job_id}/import')
    assert response.status_code == 409 and 'changed' in response.text
