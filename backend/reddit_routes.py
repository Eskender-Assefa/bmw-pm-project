"""Local UI endpoints. Request secrets are validated without echoing request bodies."""
import json
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from .db import session_dependency
from .models import Job, now
from .schemas import JobView
from .jobs import progress_messages
from .reddit_pipeline import ARTIFACTS, MAX_COUNT, PipelineError, import_result, run_folder, submit

router = APIRouter(prefix='/api/v1/reddit', tags=['Reddit pipeline'])
DB = Annotated[Session, Depends(session_dependency)]


class CollectionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    api_key: SecretStr
    model: Literal['G60', 'G70', 'F70']
    count: int = Field(ge=1, le=MAX_COUNT, strict=True)

    @field_validator('api_key')
    @classmethod
    def key_is_valid(cls, value):
        key = value.get_secret_value()
        if not 10 <= len(key) <= 512 or any(c.isspace() or ord(c) < 32 for c in key):
            raise ValueError('Invalid API key.')
        return value


@router.post('/runs', response_model=JobView, status_code=202)
async def start_collection(request: Request, db: DB):
    # FastAPI's default validation response can echo raw inputs; use a fixed response instead.
    try:
        body = await request.body()
        if len(body) > 4096:
            raise ValueError('Oversized request.')
        payload = CollectionRequest.model_validate(json.loads(body))
    except (ValueError, TypeError, ValidationError):
        raise HTTPException(422, 'Enter an API key, select G60, G70 or F70, and choose a whole number from 1 to 10,000.')
    try:
        return submit(db, payload.model, payload.count, payload.api_key)
    except PipelineError as exc:
        raise HTTPException(409, str(exc))


@router.get('/runs', response_model=list[JobView])
def collection_runs(db: DB):
    rows = db.scalars(select(Job).where(Job.kind == 'reddit_pipeline').order_by(Job.created_at.desc()).limit(10)).all()
    results = []
    for job in rows:
        view = JobView.model_validate(job)
        view.progress = progress_messages.get(job.id, view.progress)
        results.append(view)
    return results


def completed_job(db, job_id):
    job = db.get(Job, job_id)
    if not job or job.kind != 'reddit_pipeline':
        raise HTTPException(404, 'Reddit collection not found.')
    if job.state != 'succeeded':
        raise HTTPException(409, 'This run has not produced validated output.')
    return job


@router.get('/runs/{job_id}/files/{filename}')
def download_artifact(job_id: str, filename: str, db: DB):
    completed_job(db, job_id)
    if filename not in ARTIFACTS:
        raise HTTPException(404, 'Artifact not found.')
    try:
        path = run_folder(job_id) / filename
    except PipelineError:
        raise HTTPException(404, 'Artifact not found.')
    if not path.is_file():
        raise HTTPException(404, 'Artifact not found.')
    media = 'application/zip' if filename.endswith('.zip') else 'application/json' if filename.endswith('.json') else 'application/x-ndjson'
    return FileResponse(path, filename=filename, media_type=media, headers={'Cache-Control': 'no-store'})


@router.post('/runs/{job_id}/import')
def import_collection(job_id: str, db: DB):
    try:
        db.execute(text('BEGIN IMMEDIATE'))
        job = completed_job(db, job_id)
        if not job.result or not job.result.get('ready_for_import'):
            raise HTTPException(409, 'This run has no categorized comments to import.')
        result = import_result(db, job)
        job.result = {**job.result, 'imported_source_id': result['source_id']}
        job.updated_at = now()
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except PipelineError as exc:
        db.rollback()
        raise HTTPException(409, str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(409, 'Could not validate and import this run. No partial import was saved.')
