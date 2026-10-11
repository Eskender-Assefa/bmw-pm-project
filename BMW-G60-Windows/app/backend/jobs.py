import threading
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select
from .db import SessionLocal
from .models import Job, now
from .schemas import AnalysisRequest, ExportRequest, WebConnectorRequest

executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='bmw-worker')
progress_messages={}

def recover_jobs():
    with SessionLocal() as s:
        for job in s.scalars(select(Job).where(Job.state.in_(['running','queued']))):
            job.state='interrupted'; job.error='The server stopped before this job completed. Retry explicitly; existing decisions are preserved.';job.updated_at=now()
        s.commit()

def enqueue(session,kind,payload):
    job=Job(kind=kind,input=payload)
    session.add(job); session.commit()
    executor.submit(execute,job.id)
    return job

def execute(job_id):
    with SessionLocal() as s:
        job=s.get(Job,job_id);job.state='running';job.progress='Working';job.updated_at=now();s.commit()
        kind=job.kind; payload=job.input
    try:
        with SessionLocal() as s:
            if kind=='import':
                from .ingestion import import_archive
                from .services import seed_requirements
                result=import_archive(s,payload['path'],lambda message:progress_messages.update({job_id:message}))
                seed_requirements(s)
            elif kind=='analysis':
                from .analysis import analyze
                progress_messages[job_id]='Validating saved evidence and contacting the model' if payload['mode']=='live' else 'Checking replay provenance'
                result=analyze(s,AnalysisRequest.model_validate(payload))
            elif kind=='export':
                from .exporter import export_deck
                progress_messages[job_id]='Freezing decisions and generating the deck'
                result=export_deck(s,ExportRequest.model_validate(payload))
            elif kind=='web_connector':
                from .connectors import import_web
                from .services import seed_requirements
                progress_messages[job_id]='Fetching seeded web evidence'
                result=import_web(s,WebConnectorRequest.model_validate(payload),lambda message:progress_messages.update({job_id:message}))
                seed_requirements(s)
            elif kind=='rag_import':
                from .documents import import_documents
                result=import_documents(s,payload,lambda message:progress_messages.update({job_id:message}))
            elif kind=='rag_index':
                from .rag import index_sources
                result=index_sources(s,payload['source_ids'],lambda message:progress_messages.update({job_id:message}))
            elif kind=='rag_classify':
                from .rag import classify
                from .rag_schemas import RagClassifyRequest
                progress_messages[job_id]='Classifying selected passages; existing human reviews stay unchanged'
                result=classify(s,RagClassifyRequest.model_validate(payload))
            elif kind=='rag_answer':
                from .rag import answer
                from .rag_schemas import RagAnswerRequest
                progress_messages[job_id]='Retrieving passages and validating a grounded answer'
                result=answer(s,RagAnswerRequest.model_validate(payload))
            else: raise ValueError('Unknown job type.')
            job=s.get(Job,job_id);job.result=result;job.state='succeeded';job.progress='Complete';job.updated_at=now();s.commit()
    except Exception as exc:
        if type(exc).__module__.startswith('openai'):
            message=f'Live AI request failed ({type(exc).__name__}, HTTP {getattr(exc,"status_code","unknown")}). Check the configured API account and model. No result was substituted.'
        else: message=str(exc)[:1500]
        with SessionLocal() as s:
            job=s.get(Job,job_id);job.state='failed';job.error=message;job.progress='Needs attention';job.updated_at=now();s.commit()
    finally:
        progress_messages.pop(job_id,None)
