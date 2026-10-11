"""Sequential Reddit collection and categorization, with per-run credentials and artifacts."""
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from sqlalchemy import select, text
from .audit import append_event
from .config import DATA_DIR, ROOT
from .db import SessionLocal
from .ingestion import evidence
from .jobs import executor, progress_messages
from .models import Job, Source, Feedback, Feature, Aspect, now
from .taxonomy import CATEGORIES, seed_taxonomy, serious_concern

RUNS = DATA_DIR / 'reddit-runs'
COLLECTOR = ROOT / 'reddit_collector' / 'collect_reddit.py'
CATEGORIZER = ROOT / 'Categorized-Scrapped-Data' / 'categorize_comments.py'
ARTIFACTS = {'input.jsonl', 'categorized.jsonl', 'manifest.json', 'import-bundle.zip'}
MAX_COUNT = 10000
submission_lock = threading.Lock()


class PipelineError(Exception):
    """Messages in this exception are fixed application text, never subprocess output."""


def run_folder(job_id):
    if not re.fullmatch(r'[0-9a-f]{32}', job_id):
        raise PipelineError('Invalid collection run.')
    return RUNS / job_id


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path):
    with path.open(encoding='utf-8-sig') as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise PipelineError('The pipeline returned invalid JSONL records.')
    return rows


def categorizer_module():
    spec = importlib.util.spec_from_file_location('bmw_comment_categorizer', CATEGORIZER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_input(path, requested):
    rows = jsonl(path)
    ids = set()
    for row in rows:
        row_id = row.get('row_id')
        if (not isinstance(row_id, str) or not row_id or row_id in ids
                or not isinstance(row.get('comment_text'), str) or 'date_displayed' not in row
                or row['date_displayed'] is not None and not isinstance(row['date_displayed'], str)
                or row.get('text_verification') != 'unverified_model_extraction'):
            raise PipelineError('Collector output has invalid IDs, text, dates, or provenance.')
        ids.add(row_id)
    if len(rows) > requested:
        raise PipelineError('Collector output exceeds the requested count.')
    return rows


def validate_output(folder, requested):
    original = validate_input(folder / 'input.jsonl', requested)
    module = categorizer_module()
    output = jsonl(folder / 'categorized.jsonl')
    # The script's validator verifies text, IDs, dates, ordering, and every discard hash.
    if module.processed_row_count(folder / 'input.jsonl', folder / 'categorized.jsonl') != len(original):
        raise PipelineError('Categorization did not account for every collected comment.')
    for row in output:
        score = row.get('sentiment_score')
        if row.get('categorie') not in CATEGORIES.values() or type(score) not in (int, float) or not math.isfinite(score) or not -100 <= score <= 100:
            raise PipelineError('Categorized output has invalid categories or sentiment scores.')
    return original, output


def stage(job_id, message):
    progress_messages[job_id] = message
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        job.progress = message
        job.updated_at = now()
        db.commit()


def command(args, secret, timeout):
    # Never modify the API server's environment or put credentials on a command line.
    env = os.environ.copy()
    env['OPENAI_API_KEY'] = secret.get_secret_value()
    env['OPENAI_BASE_URL'] = 'https://api.openai.com/v1'
    env['PYTHONIOENCODING'] = 'utf-8'
    for key in ('OPENAI_ORG_ID', 'OPENAI_PROJECT_ID', 'OPENAI_LOG'):
        env.pop(key, None)
    try:
        return subprocess.run(
            [sys.executable, *map(str, args)], cwd=ROOT, env=env, shell=False,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        ).returncode
    finally:
        env.pop('OPENAI_API_KEY', None)


def submit(db, model, count, secret):
    with submission_lock:
        # One pending collection avoids accidental repeated billable runs.
        active = db.scalar(select(Job.id).where(Job.kind == 'reddit_pipeline', Job.state.in_(['queued', 'running'])))
        if active:
            raise PipelineError('A Reddit collection is already running. Wait for it to finish.')
        payload = {'model': model, 'count': count,
                   'collector_model': os.getenv('BMWPM_REDDIT_MODEL', 'gpt-5.5'),
                   'categorizer_model': os.getenv('BMWPM_CATEGORIZER_MODEL', 'gpt-4.1-mini')}
        job = Job(kind='reddit_pipeline', input=payload)
        db.add(job)
        db.commit()
        try:
            executor.submit(execute_pipeline, job.id, secret)
        except Exception:
            job.state = 'failed'
            job.error = 'Could not start the collection worker. Submit a new run.'
            db.commit()
        return job


def execute_pipeline(job_id, secret):
    try:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            job.state = 'running'
            job.updated_at = now()
            payload = job.input
            db.commit()
        folder = run_folder(job_id)
        folder.mkdir(parents=True, exist_ok=False)
        stage(job_id, '1 / 3 · Collecting Reddit quotations with OpenAI web search')
        code = command([COLLECTOR, '--topic', 'BMW ' + payload['model'], '--count', payload['count'],
                        '--out', folder / 'collector', '--model', payload['collector_model']], secret, 7200)
        if code not in (0, 2):
            raise PipelineError('Collection failed. Check your API key, model access, quota, and connection; saved partial files remain in the run folder.')
        collected_path = folder / 'collector' / 'comments.jsonl'
        rows = validate_input(collected_path, payload['count'])
        if not rows:
            raise PipelineError('No comments were collected. Categorization was not started.')
        shutil.copyfile(collected_path, folder / 'input.jsonl')
        stage(job_id, f'2 / 3 · Categorizing {len(rows)} collected comments')
        code = command([CATEGORIZER, folder / 'input.jsonl', folder / 'categorized.jsonl',
                        '--model', payload['categorizer_model']], secret, 14400)
        if code:
            raise PipelineError('Categorization failed. Check API access or quota. Partial output was preserved but is not ready for import.')
        stage(job_id, '3 / 3 · Validating output and preparing the import bundle')
        original, output = validate_output(folder, payload['count'])
        counts = {'requested': payload['count'], 'collected': len(original), 'categorized': len(output),
                  'discarded': len(original) - len(output), 'shortfall': payload['count'] - len(original)}
        manifest = {
            'schema_version': 'reddit-import-v1', 'run_id': job_id, 'model': payload['model'],
            'created_at': now(), 'origin': 'unknown', 'text_verification': 'unverified_model_extraction',
            'market': 'unknown', 'powertrain': 'unknown', 'counts': counts,
            'collector_model': payload['collector_model'], 'categorizer_model': payload['categorizer_model'],
            'collector_script_sha256': sha256(COLLECTOR), 'categorizer_script_sha256': sha256(CATEGORIZER),
            'category_mapping': {name: code for code, name in CATEGORIES.items()},
            'files': {name: sha256(folder / name) for name in ('input.jsonl', 'categorized.jsonl', 'categorized.jsonl.discarded.jsonl')},
            'limitations': ['Model-extracted quotations require source review.',
                            'Source dates are displayed text, not verified timestamps.',
                            'Categories and sentiment are AI interpretations; exact feature mappings need review.',
                            'Market and powertrain are unknown; selected workspace filters are not assigned to collected rows.'],
        }
        (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        with ZipFile(folder / 'import-bundle.zip', 'w', ZIP_DEFLATED) as bundle:
            for name in (*manifest['files'], 'manifest.json'):
                bundle.write(folder / name, name)
            report = folder / 'collector' / 'run_report.json'
            if report.exists():
                bundle.write(report, 'collector/run_report.json')
            for response in sorted((folder / 'collector' / 'api_responses').glob('*.json')):
                bundle.write(response, 'collector/' + response.relative_to(folder / 'collector').as_posix())
        with SessionLocal() as db:
            try:
                job = db.get(Job, job_id)
                base_result = {**counts, 'model': payload['model'], 'ready_for_import': bool(output),
                               'artifacts': {name: f'/api/v1/reddit/runs/{job_id}/files/{name}' for name in sorted(ARTIFACTS)}}
                if output:
                    # Import validated output before marking the job complete, so a completed run is
                    # immediately visible in Reviews & Comments even if the browser is closed.
                    imported = import_result(db, job)
                    base_result['imported_source_id'] = imported['source_id']
                    base_result['imported'] = imported['imported']
                    job.progress = f"Imported {len(output)} categorized comments · visible in Reviews & Comments"
                else:
                    job.progress = 'Complete · all comments were filtered out'
                job.result = base_result
                job.state = 'succeeded'
                job.updated_at = now()
                db.commit()
            except Exception:
                db.rollback()
                raise
    except Exception as exc:
        # Do not persist exception text: SDK/subprocess exceptions may contain credentials.
        message = str(exc) if isinstance(exc, PipelineError) else (
            'The pipeline timed out. Partial files were preserved; start a new run with a smaller count.'
            if isinstance(exc, subprocess.TimeoutExpired) else
            'The pipeline could not validate or prepare its files. Partial files were preserved and are not importable.')
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job:
                job.state = 'failed'
                job.error = message
                job.progress = 'Needs attention'
                job.updated_at = now()
                db.commit()
    finally:
        secret = None
        progress_messages.pop(job_id, None)


def import_result(db, job):
    folder = run_folder(job.id)
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['schema_version'] != 'reddit-import-v1' or manifest['model'] != job.input['model']:
        raise PipelineError('The run metadata does not match this job.')
    for name in ('input.jsonl', 'categorized.jsonl', 'categorized.jsonl.discarded.jsonl'):
        if sha256(folder / name) != manifest['files'][name]:
            raise PipelineError('A pipeline file changed after validation. Import was stopped.')
    original, categorized = validate_output(folder, job.input['count'])
    if not categorized:
        raise PipelineError('No relevant comments remain to import.')
    bundle = folder / 'import-bundle.zip'
    checksum = sha256(bundle)
    prior = db.scalar(select(Source).where(Source.checksum == checksum))
    if prior:
        return {'source_id': prior.id, 'imported': 0, 'skipped': len(categorized), 'model': job.input['model']}
    seed_taxonomy(db)
    source = Source(id=checksum[:32], checksum=checksum, format='zip', kind='customer_statement',
                    filename=f"BMW-{job.input['model']}-Reddit-{job.id[:8]}.zip",
                    path=str(bundle), origin='unknown', market=None, language='unknown',
                    extraction_version='reddit-import-v1', record_count=len(categorized), row_count=len(categorized))
    db.add(source)
    db.flush()
    raw_by_id = {r['row_id']: r for r in original}
    category_codes = {name: code for code, name in CATEGORIES.items()}
    for line, row in enumerate(categorized, 1):
        raw = raw_by_id[row['row_id']]
        category = category_codes[row['categorie']]
        feature_id = 'reddit-category-' + category.lower()
        if not db.get(Feature, feature_id):
            db.add(Feature(id=feature_id, name=row['categorie'] + ' (category only)', category=category,
                           secondary_tags=[], mapping_reason='AI category only; exact vehicle feature needs human review.'))
            db.flush()
        locator = {'sheet': 'categorized.jsonl', 'row': line, 'range': f'Line {line}',
                   'external_id': row['row_id'], 'source_url': raw.get('source_url'),
                   'raw_record': raw, 'manifest': 'manifest.json', 'category': row['categorie'],
                   'sentiment_score': row['sentiment_score']}
        ref = evidence(db, source, locator, row['comment'], 'customer_statement', job.input['model'])
        text_hash = hashlib.sha256(row['comment'].encode('utf-8')).hexdigest()
        record = Feedback(id=source.id + ':' + row['row_id'], source_id=source.id, external_id=row['row_id'],
                          model=job.input['model'], country='unknown', powertrain='unknown', raw_powertrain='unknown',
                          text=row['comment'], text_hash=text_hash, origin='unknown', source_label='Reddit · unverified model extraction',
                          source_date=None, duplicate_text=bool(db.scalar(select(Feedback.id).where(Feedback.text_hash == text_hash).limit(1))),
                          tags=[{'row': line, 'type': 'Unclassified', 'level2': row['categorie'], 'level3': None,
                                 'evidence_id': ref.id, 'raw_source': raw, 'sentiment_score': row['sentiment_score']}])
        db.add(record)
        db.flush()
        db.add(Aspect(feedback_id=record.id, evidence_id=ref.id, feature_id=feature_id,
                      feedback_type='Unclassified', quote=row['comment'], mapping_status='pending',
                      mapping_reason='AI category and sentiment; exact feature and need type require review.',
                      mapping_version='reddit-import-v1', sentiment=row['sentiment_score'],
                      critical=serious_concern(row['comment'], 'Unclassified')))
    append_event(db, 'Demo PM', 'reddit.imported', source.id, {
        'run_id': job.id, 'model': job.input['model'], 'records': len(categorized),
        'origin': 'unknown', 'checksum': checksum, 'counts': manifest['counts']})
    return {'source_id': source.id, 'imported': len(categorized), 'skipped': 0, 'model': job.input['model']}
