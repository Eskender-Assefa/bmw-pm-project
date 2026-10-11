import json
from pathlib import Path
from typing import Annotated
from uuid import uuid4
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import DATA_DIR
from .db import session_dependency
from .documents import FORMATS, MAX_BYTES
from .jobs import enqueue
from .models import RagRun
from .rag import search, status, review_chunk, mapping_overview
from .rag_schemas import (DocumentMetadata, RagSearchRequest, RagIndexRequest,
                          RagClassifyRequest, RagAnswerRequest, RagReviewRequest)
from .schemas import JobView

router = APIRouter(prefix='/api/v1/rag', tags=['Document RAG'])
DB = Annotated[Session, Depends(session_dependency)]


@router.get('/status')
def rag_status(db: DB):
    return status(db)


@router.post('/documents', response_model=JobView)
async def upload_documents(db: DB, files: list[UploadFile] = File(...), metadata: str = Form('{}')):
    try:
        meta = DocumentMetadata.model_validate(json.loads(metadata))
    except (ValueError, ValidationError) as exc:
        raise HTTPException(422, 'Invalid document metadata.') from exc
    if not 1 <= len(files) <= 10:
        raise HTTPException(422, 'Upload one to ten documents per batch.')
    folder = DATA_DIR / 'uploads'
    folder.mkdir(parents=True, exist_ok=True)
    staged, created, total = [], [], 0
    try:
        for upload in files:
            filename = Path((upload.filename or 'document').replace('\\', '/')).name
            suffix = Path(filename).suffix.lower()
            if suffix not in FORMATS:
                raise HTTPException(422, 'Supported formats: PDF, XLSX, CSV, TXT, MD. Convert legacy XLS first.')
            path = folder / (uuid4().hex + suffix)
            created.append(path)
            size = 0
            with path.open('xb') as handle:
                while block := await upload.read(1024 * 1024):
                    size += len(block)
                    total += len(block)
                    if size > MAX_BYTES or total > 40 * 1024 * 1024:
                        raise HTTPException(413, 'Limit: 20 MB per file and 40 MB per batch.')
                    handle.write(block)
            if not size:
                raise HTTPException(422, 'Empty files cannot be imported.')
            staged.append({'filename': filename[:200], 'path': str(path)})
        return enqueue(db, 'rag_import', {'files': staged, 'metadata': meta.model_dump()})
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    finally:
        for upload in files:
            await upload.close()


@router.post('/index', response_model=JobView)
def index_documents(request: RagIndexRequest, db: DB):
    return enqueue(db, 'rag_index', request.model_dump())


@router.post('/search')
def search_documents(request: RagSearchRequest, db: DB):
    return search(db, request)


@router.post('/classify', response_model=JobView)
def classify_documents(request: RagClassifyRequest, db: DB):
    if not request.allow_live:
        raise HTTPException(422, 'Explicit approval for a paid AI request is required.')
    return enqueue(db, 'rag_classify', request.model_dump())


@router.post('/mappings')
def document_mappings(request: RagSearchRequest, db: DB):
    return mapping_overview(db, request)


@router.post('/answer', response_model=JobView)
def answer_documents(request: RagAnswerRequest, db: DB):
    if not request.allow_live:
        raise HTTPException(422, 'Explicit approval for a paid AI request is required.')
    return enqueue(db, 'rag_answer', request.model_dump())


@router.post('/chunks/{chunk_id}/review')
def review_document(chunk_id: str, request: RagReviewRequest, db: DB):
    return review_chunk(db, chunk_id, request)


@router.get('/runs')
def list_runs(db: DB):
    return [{'id': r.id, 'kind': r.kind, 'model': r.model_version, 'created_at': r.created_at,
             'question': r.inputs.get('question')} for r in db.scalars(select(RagRun).order_by(RagRun.created_at.desc()).limit(30))]


@router.get('/runs/{run_id}')
def get_run(run_id: str, db: DB):
    run = db.get(RagRun, run_id)
    if not run:
        raise HTTPException(404, 'RAG run not found.')
    return {'run_id': run.id, 'kind': run.kind, 'model': run.model_version, 'output': run.output,
            'context': run.inputs['passages'], 'inputs': run.inputs, 'created_at': run.created_at}
