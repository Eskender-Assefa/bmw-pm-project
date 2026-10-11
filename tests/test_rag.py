"""RAG contract checks use a migrated disposable backup and fake AI responses only."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import json
import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
from backend.config import ROOT, DATA_DIR
from backend.db import SessionLocal, engine, install_guards
from backend.models import Source, EvidenceRef, Feedback, RagChunk, RagRun
from backend.ingestion import evidence
from backend.documents import import_documents, extract_document
from backend.rag import (index_sources, search, split_text, classify, answer, validate_answer,
                         validate_assignments, review_chunk, live_completion, mapping_overview,
                         suggest_assignments, HINTS_METHOD)
from backend.rag_schemas import (DocumentMetadata, RagSearchRequest, RagClassifyRequest,
                                 RagAnswerRequest, RagReviewRequest, RagAnswerOutput)
from backend.audit import digest, verify_audit


@pytest.fixture(autouse=True)
def rag_schema(isolated_database):
    command.upgrade(Config(str(ROOT / 'alembic.ini')), 'head')
    # The seed may already contain the user's RAG index. Clear only its test copy.
    with engine.begin() as connection:
        connection.execute(text('DELETE FROM rag_fts'))
        connection.execute(text('DELETE FROM rag_chunks'))
        connection.execute(text('DROP TRIGGER IF EXISTS immutable_rag_runs_delete'))
        connection.execute(text('DELETE FROM rag_runs'))
        install_guards(connection)


def staged(name, content, metadata=None):
    folder = DATA_DIR / 'uploads'
    folder.mkdir(exist_ok=True)
    path = folder / (uuid4().hex + Path(name).suffix)
    path.write_bytes(content.encode() if isinstance(content, str) else content)
    return {'files': [{'filename': name, 'path': str(path)}], 'metadata': metadata or {}}


def add_source(session, model='G60', content='Touchscreen software controls need simpler menus.', origin='unknown'):
    key = uuid4().hex
    source = Source(id=key, checksum=digest(key), filename=key+'.txt', format='txt',
                    kind='document', origin=origin, path='test-only', extraction_version='test')
    session.add(source)
    session.flush()
    evidence(session, source, {'line': 1}, content, 'document', model)
    index_sources(session, [source.id])
    session.commit()
    chunk = session.scalar(select(RagChunk).where(RagChunk.source_id == source.id))
    return source, chunk


def proposal(chunk, category='C07', scope='variable'):
    return {'category': category, 'scope_layer': scope, 'quote': chunk.text[:50],
            'rationale': 'Supported by the exact passage in this isolated test.'}


def test_chunk_offsets_cover_original_without_altered_quotes():
    content = ('A heading\nA moderately long paragraph about vehicle charging. ' * 150)
    spans = list(split_text(content))
    assert len(spans) > 1
    assert spans[0][0] == 0 and spans[-1][1] == len(content)
    for index, (start, end, body) in enumerate(spans):
        assert body == content[start:end] and len(body) <= 1800
        if index:
            assert start <= spans[index-1][1]


def test_new_csv_models_metadata_idempotence_and_demand_isolation(session):
    before = session.scalar(select(func.count()).select_from(Feedback))
    payload = staged('mixed.csv', 'Model,Comment\nG61,The charging software needs clearer menus\nF70,Seat comfort is poor\n')
    result = import_documents(session, payload)
    session.commit()
    assert len(result['imported']) == 1 and result['index']['added'] == 2
    assert before > 0
    assert session.scalar(select(func.count()).select_from(Feedback)) == before
    assert len(search(session, RagSearchRequest(model='G61'))['items']) == 1
    assert not search(session, RagSearchRequest(model='G70', query='charging'))['items']
    again = import_documents(session, payload)
    assert again['skipped'] and again['index']['added'] == 0
    assert verify_audit(session)['valid']


def test_mixed_models_cannot_be_relabeled_as_single_model(session):
    payload = staged('conflict.csv', 'Model,Comment\nG61,Charging feature\n', {'model': 'G60'})
    result = import_documents(session, payload)
    assert not result['imported'] and 'disagrees' in result['failed'][0]['error']
    assert not session.scalar(select(Source).where(Source.filename == 'conflict.csv'))


def test_xlsx_headers_rows_and_formula_warning(session):
    import openpyxl
    from io import BytesIO
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = 'New models'
    sheet.append(['Title'])
    sheet.append(['Model', 'Feature', 'Value'])
    sheet.append(['G61', 'Battery range', 500])
    buf = BytesIO()
    book.save(buf)
    result = import_documents(session, staged('new.xlsx', buf.getvalue(), {'header_row': 2}))
    assert result['imported'][0]['records'] == 1
    assert 'cached formula' in result['imported'][0]['warnings'][0]
    row = session.scalar(select(EvidenceRef).where(EvidenceRef.source_id == result['imported'][0]['source_id']))
    assert row.locator['row'] == 3 and row.locator['range'] == 'A3:C3'
    assert row.model == 'G61' and 'Value: 500' in row.text


def test_pdf_extracts_page_citations_and_blank_requires_ocr(session):
    source = session.scalar(select(Source).where(Source.filename == 'G60_OptionList.PDF'))
    warnings = []
    first = next(extract_document(Path(source.path), DocumentMetadata(model='G60'), warnings))
    assert first[0].strip() and first[1]['page'] == 1 and first[2] == 'G60'
    from pypdf import PdfWriter
    from io import BytesIO
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    stream = BytesIO()
    writer.write(stream)
    result = import_documents(session, staged('scan.pdf', stream.getvalue()))
    assert 'OCR' in result['failed'][0]['error'] and not result['imported']


def test_failed_file_is_atomic_and_other_files_survive(session):
    payload = staged('good.txt', 'Battery charging takes too long.')
    payload['files'] += staged('bad.xlsx', 'not a workbook')['files']
    result = import_documents(session, payload)
    session.commit()
    assert len(result['imported']) == 1 and len(result['failed']) == 1
    assert not session.scalar(select(Source).where(Source.filename == 'bad.xlsx'))
    assert session.scalar(select(func.count()).select_from(RagChunk)) == 1


def test_fts_filters_quote_syntax_and_scope_pairs(session):
    _, chunk = add_source(session)
    add_source(session, 'G70', 'A touchscreen battery prototype', 'synthetic')
    assert search(session, RagSearchRequest(query='touchscreen', model='G60'))['total'] == 1
    assert search(session, RagSearchRequest(query='" OR *', model='G60'))['total'] == 0
    assert search(session, RagSearchRequest(query='touchscreen', origin='synthetic'))['total'] == 1
    chunk.assignments = [proposal(chunk, 'C07', 'variable'), proposal(chunk, 'C02', 'fixed')]
    session.commit()
    assert search(session, RagSearchRequest(category='C07', scope_layer='fixed', model='G60'))['total'] == 0
    assert search(session, RagSearchRequest(category='C02', scope_layer='fixed', model='G60'))['total'] == 1


@pytest.mark.parametrize('content,expected', [
    ('Leistung Gesamtfahrzeugbetrieb 130 kW (177 PS)\nGetriebe 9G-TRONIC Automatik', {'C01'}),
    ('Fahrzeuggrundpreis (brutto) 59.803,45 EUR inkl. MwSt.', {'C03'}),
    ('Pflichtangaben: 6,3 l/100 km kombiniert; CO2-Emissionen 143 g/km', {'C02'}),
    ('Ladeleistung an Wechselstrom und Gleichstrom', {'C02'}),
    ('SEAL Comfort / Design / Excellence; Fortgeltung des Comfort-Listenpreises', {'C03'}),
    ('Quelle: https://www.byd.com/de/presse/byd-seal-2026-mehr-platz-komfort', {'C10'}),
    ('G60, US, Comfort of front seat, Delightful: 0.302', {'C05'}),
    ('I wish there were a more comfort-oriented setting.', {'C05'}),
    ('KOMFORT UND FUNKTIONALITÄT', {'C05'}),
])
def test_lexical_hints_handle_german_specs_trims_and_links(content, expected):
    hints = suggest_assignments(content, 'document')
    assert {h['category'] for h in hints} == expected
    assert all(h['quote'] in content for h in hints)


def test_reindex_refreshes_only_pending_older_lexical_hints(session):
    source, chunk = add_source(session, content='Leistung 150 kW (204 PS), Grundpreis 56.300 EUR.')
    _, reviewed = add_source(session, content='Leistung 220 kW (299 PS).')
    for row, method in [(chunk, 'lexical-hints-v1'), (reviewed, 'lexical-hints-v1')]:
        row.assignments, row.method = [proposal(row, 'C10', 'fixed')], method
    reviewed.review_status = 'reviewed'
    session.commit()
    result = index_sources(session, [source.id, reviewed.source_id])
    session.commit()
    assert result['added'] == 0 and result['refreshed'] == 1
    assert {a['category'] for a in chunk.assignments} == {'C01', 'C03'}
    assert chunk.method == HINTS_METHOD and chunk.revision == 2
    assert reviewed.assignments[0]['category'] == 'C10' and reviewed.revision == 1
    assert index_sources(session, [source.id])['refreshed'] == 0
    assert verify_audit(session)['valid']


def test_index_dedup_inactive_sources_and_no_review_overwrite(session):
    source, chunk = add_source(session)
    evidence(session, source, {'line': 2}, chunk.text, 'document', chunk.model)
    session.commit()
    assert index_sources(session, [source.id])['added'] == 0
    chunk.review_status = 'reviewed'
    chunk.assignments = [proposal(chunk)]
    session.commit()
    index_sources(session, [source.id])
    assert chunk.review_status == 'reviewed' and chunk.assignments[0]['scope_layer'] == 'variable'
    source.active = False
    session.commit()
    assert search(session, RagSearchRequest(query='software'))['total'] == 0


def test_review_revision_audit_and_exact_quotes(session):
    _, chunk = add_source(session)
    request = RagReviewRequest(expected_revision=1, status='reviewed', assignments=[proposal(chunk)], rationale='Checked against the source record.')
    session.rollback()
    result = review_chunk(session, chunk.id, request)
    assert result['review_status'] == 'reviewed' and result['revision'] == 2
    session.rollback()
    with pytest.raises(HTTPException) as error:
        review_chunk(session, chunk.id, request)
    assert error.value.status_code == 409
    session.rollback()
    assert verify_audit(session)['valid']
    bad = proposal(chunk)
    bad['quote'] = 'fabricated specification'
    with pytest.raises(ValueError):
        validate_assignments(chunk.text, [bad])


def test_classification_requires_consent_and_preserves_human_review(session, monkeypatch):
    _, chunk = add_source(session)
    def fake(task, inputs, schema):
        return 'fake-model', {'chunks': [{'chunk_id': chunk.id, 'assignments': [proposal(chunk)]}]}
    monkeypatch.setattr('backend.rag.live_completion', fake)
    with pytest.raises(ValueError, match='Confirm'):
        classify(session, RagClassifyRequest(chunk_ids=[chunk.id]))
    result = classify(session, RagClassifyRequest(chunk_ids=[chunk.id], allow_live=True))
    session.commit()
    assert result['model'] == 'fake-model' and chunk.review_status == 'pending'
    chunk.review_status = 'reviewed'
    session.commit()
    with pytest.raises(ValueError, match='human decisions'):
        classify(session, RagClassifyRequest(chunk_ids=[chunk.id], allow_live=True))


@pytest.mark.parametrize('mutation', ['id', 'quote', 'omitted'])
def test_bad_classification_fails_closed(session, monkeypatch, mutation):
    _, chunk = add_source(session)
    output = {'chunks': [{'chunk_id': chunk.id, 'assignments': [proposal(chunk)]}]}
    if mutation == 'id': output['chunks'][0]['chunk_id'] = 'invented'
    if mutation == 'quote': output['chunks'][0]['assignments'][0]['quote'] = 'invented quote'
    if mutation == 'omitted': output['chunks'] *= 2
    monkeypatch.setattr('backend.rag.live_completion', lambda *args: ('fake', output))
    with pytest.raises(ValueError):
        classify(session, RagClassifyRequest(chunk_ids=[chunk.id], allow_live=True))
    session.rollback()
    assert session.get(RagChunk, chunk.id).revision == 1
    assert session.scalar(select(func.count()).select_from(RagRun)) == 0


def test_classification_uses_short_labels_and_keeps_only_supported_proposals(session, monkeypatch):
    _, chunk = add_source(session, content='C 300 e\nPlug-in-Hybrid Leistung 230 kW. Preis 59.803 EUR.')
    seen = {}
    good = dict(category='C01', scope_layer='fixed', quote=chunk.text, rationale='Explicit power specification.',
                feature='Power', value='230', unit='kW', variant='C 300 e Plug-in-Hybrid')
    bad = dict(good, category='C03', feature='Price', value='99.999', unit='EUR', variant=None)
    def fake(task, inputs, schema):
        seen['ids'] = [p['id'] for p in inputs['passages']]
        return 'fake', {'chunks': [{'chunk_id': 'P1', 'assignments': [good, bad]}]}
    monkeypatch.setattr('backend.rag.live_completion', fake)
    result = classify(session, RagClassifyRequest(chunk_ids=[chunk.id], allow_live=True))
    session.commit()
    assert seen['ids'] == ['P1'] and result['context'][0]['id'] == chunk.id
    assert result['output']['rejected_proposals'] == 1
    assert [a['category'] for a in chunk.assignments] == ['C01'] and chunk.assignments[0]['variant'] == 'C 300 e Plug-in-Hybrid'


def test_stale_ai_does_not_overwrite_concurrent_review(session, monkeypatch):
    _, chunk = add_source(session)
    def concurrent_review(*args):
        with SessionLocal() as other:
            current = other.get(RagChunk, chunk.id)
            current.review_status = 'reviewed'
            current.revision += 1
            other.commit()
        return 'fake', {'chunks': [{'chunk_id': chunk.id, 'assignments': [proposal(chunk)]}]}
    monkeypatch.setattr('backend.rag.live_completion', concurrent_review)
    with pytest.raises(ValueError, match='changed'):
        classify(session, RagClassifyRequest(chunk_ids=[chunk.id], allow_live=True))
    session.rollback()
    assert session.get(RagChunk, chunk.id).review_status == 'reviewed'


def test_grounded_answer_and_append_only_run(session, monkeypatch):
    _, chunk = add_source(session)
    raw = {'abstained': False, 'claims': [{'text': 'Simpler software controls are requested.',
           'citations': [{'chunk_id': chunk.id, 'quote': chunk.text}]}], 'limitations': ['No measured customer prevalence.']}
    monkeypatch.setattr('backend.rag.live_completion', lambda *args: ('fake', raw))
    result = answer(session, RagAnswerRequest(question='What software controls need change?', model='G60', allow_live=True))
    session.commit()
    assert result['output']['claims'] and result['context'][0]['checksum']
    with pytest.raises(IntegrityError):
        session.execute(text('DELETE FROM rag_runs WHERE id=:id'), {'id': result['run_id']})
    session.rollback()
    bad = deepcopy(raw)
    bad['claims'][0]['citations'][0]['quote'] = 'not present'
    with pytest.raises(ValueError): validate_answer(result['context'], bad)
    bad = deepcopy(raw)
    bad['abstained'] = True
    with pytest.raises(ValueError): validate_answer(result['context'], bad)


def test_absent_rejected_and_wrong_model_context_do_not_call_ai(session, monkeypatch):
    _, chunk = add_source(session, model='F70')
    monkeypatch.setattr('backend.rag.live_completion', lambda *args: pytest.fail('No AI call permitted'))
    for request in [RagAnswerRequest(question='software controls', model='G60', allow_live=True),
                    RagAnswerRequest(question='zyxwvunknown', allow_live=True)]:
        result = answer(session, request)
        session.commit()
        assert result['output']['abstained'] and result['model'] == 'no-provider-call'
    chunk.review_status = 'rejected'
    session.commit()
    result = answer(session, RagAnswerRequest(question='software controls', model='F70', allow_live=True))
    assert result['output']['abstained']


def test_api_upload_job_search_validation_and_replay(client, monkeypatch):
    import backend.jobs
    monkeypatch.setattr(backend.jobs.executor, 'submit', lambda fn, identifier: fn(identifier))
    response = client.post('/api/v1/rag/documents', data={'metadata': json.dumps({'model': 'G61'})},
                           files=[('files', ('feedback.txt', b'The charging software needs simpler menus.', 'text/plain'))])
    assert response.status_code == 200
    job = client.get('/api/v1/jobs/' + response.json()['id']).json()
    assert job['state'] == 'succeeded', job
    results = client.post('/api/v1/rag/search', json={'query': 'charging', 'model': 'G61'}).json()
    assert results['total'] == 1
    mappings = client.post('/api/v1/rag/mappings', json={'model': 'G61'}).json()
    assert len(mappings['categories']) == 10 and mappings['total_passages'] == 1
    assert mappings['items'][0]['assignment']['value'] is None and mappings['ai_calls'] == 0
    assert client.post('/api/v1/rag/answer', json={'question': 'Charging?'}).status_code == 422
    assert client.post('/api/v1/rag/documents', files={'files': ('bad.exe', b'bad')}).status_code == 422
    assert client.post('/api/v1/rag/search', json={'category': 'C99'}).status_code == 422
    assert client.post('/api/v1/rag/mappings', json={'category': 'C99'}).status_code == 422
    assert client.post('/api/v1/rag/index', json={}, headers={'origin': 'https://untrusted.example'}).status_code == 403


def test_live_provider_missing_key_and_structured_adapter(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(ValueError, match='not configured'):
        live_completion('test', {}, RagAnswerOutput)
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-test-value-never-transmitted')
    import openai
    seen = {}
    def parse(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(status='completed', output_parsed=RagAnswerOutput(abstained=True, claims=[], limitations=['Unknown.']))
    monkeypatch.setattr(openai, 'OpenAI', lambda **kwargs: SimpleNamespace(responses=SimpleNamespace(parse=parse)))
    model, result = live_completion('test', {'passages': []}, RagAnswerOutput)
    assert result['abstained'] and seen['store'] is False and seen['text_format'] is RagAnswerOutput


def test_mapping_overview_full_counts_paging_variants_and_source_isolation(session, monkeypatch):
    monkeypatch.setattr('backend.rag.live_completion', lambda *args: pytest.fail('Overview must be local'))
    source, first = add_source(session, content='520i power 153 kW. 520d power 145 kW.')
    first.assignments = [dict(category='C01', scope_layer='fixed', quote=first.text,
        rationale='Explicit test specification for this variant.', feature='Power',
        value=value, unit='kW', variant=variant) for value, variant in [('153', '520i'), ('145', '520d')]]
    validate_assignments(first.text, first.assignments)
    for number in range(25):
        evidence(session, source, {'line': number+2}, f'Touchscreen software statement {number}', 'document', 'G60')
    index_sources(session, [source.id])
    session.commit()
    add_source(session, 'AUDI 6', 'Transmission and torque specification.')
    request = RagSearchRequest(source_id=source.id, limit=3)
    overview = mapping_overview(session, request)
    counts = {c['id']: c for c in overview['categories']}
    assert list(counts) == [f'C{i:02d}' for i in range(1,11)]
    assert counts['C01']['mappings'] == 2 and counts['C01']['passages'] == 1
    assert counts['C01']['pending'] == 2 and counts['C04']['mappings'] == 0
    assert counts['C07']['mappings'] == 25
    assert overview['total'] == 27 and overview['total_passages'] == 26
    assert len(overview['items']) == 3
    following = mapping_overview(session, request.model_copy(update={'offset': 3}))
    assert following['categories'] == overview['categories']
    assert {(r['passage']['id'],r['assignment_index']) for r in overview['items']}.isdisjoint(
        {(r['passage']['id'],r['assignment_index']) for r in following['items']})
    detail = mapping_overview(session, request.model_copy(update={'category': 'C01'}))
    assert detail['total'] == 2 and detail['categories'] == overview['categories']
    assert {r['assignment']['variant'] for r in detail['items']} == {'520i','520d'}
    assert {r['passage']['source_id'] for r in detail['items']} == {source.id}
    assert not mapping_overview(session, request.model_copy(update={'model':'AUDI 6'}))['items']
    assert not mapping_overview(session, request.model_copy(update={'query':'" OR *'}))['items']
    source.active = False
    session.commit()
    assert mapping_overview(session, request)['total_mappings'] == 0


def test_mapping_counts_follow_same_aspect_scope_and_review_filters(session):
    source, chunk = add_source(session)
    chunk.assignments = [proposal(chunk, 'C01', 'fixed'), proposal(chunk, 'C07', 'variable')]
    chunk.review_status = 'reviewed'
    session.commit()
    request = RagSearchRequest(source_id=source.id, scope_layer='fixed', category='C07')
    result = mapping_overview(session, request)
    assert result['total'] == 0 and result['total_mappings'] == 1
    assert result['categories'][0]['reviewed'] == 1 and result['categories'][6]['mappings'] == 0
    assert mapping_overview(session, request.model_copy(update={'category':None,'review_status':'pending'}))['total'] == 0
    legacy = mapping_overview(session, RagSearchRequest(source_id=source.id))['items'][0]['assignment']
    assert legacy['feature'] is None and legacy['value'] is None and legacy['variant'] is None


@pytest.mark.parametrize('field,value', [('value','999'),('unit','mph'),('variant','550e'),('feature','  ')])
def test_extracted_details_must_be_supported_by_the_same_quote(field, value):
    assignment = dict(category='C01',scope_layer='fixed',quote='520i power 153 kW.',
        rationale='Explicit test specification.',feature='Power',value='153',unit='kW',variant='520i')
    assignment[field] = value
    with pytest.raises(ValueError):
        validate_assignments('520i power 153 kW. 550e power 999 kW.', [assignment])


def test_structured_extraction_review_and_reindex_preserve_details(session, monkeypatch):
    source, chunk = add_source(session, content='520i power 153 kW. 520d power 145 kW.')
    assignment = dict(category='C01',scope_layer='fixed',quote=chunk.text,
        rationale='Explicit test specification.',feature='Power',value='153',unit='kW',variant='520i')
    monkeypatch.setattr('backend.rag.live_completion', lambda *args: ('fake', {'chunks':[
        {'chunk_id':chunk.id,'assignments':[assignment]}]}))
    classify(session, RagClassifyRequest(chunk_ids=[chunk.id],allow_live=True))
    session.commit()
    row = mapping_overview(session, RagSearchRequest(source_id=source.id))['items'][0]
    assert row['assignment']['value'] == '153' and row['passage']['review_status'] == 'pending'
    request = RagReviewRequest(expected_revision=row['passage']['revision'],status='reviewed',
        assignments=[assignment],rationale='Checked the feature, value and variant in the source.')
    session.rollback()
    review_chunk(session, chunk.id, request)
    assert index_sources(session, [source.id])['added'] == 0
    row = mapping_overview(session, RagSearchRequest(source_id=source.id))['items'][0]
    assert row['assignment']['variant'] == '520i' and row['passage']['review_status'] == 'reviewed'
    assert verify_audit(session)['valid']
