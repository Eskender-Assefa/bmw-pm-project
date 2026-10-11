import os
import re
from pathlib import Path
from contextlib import asynccontextmanager
from threading import Lock
from typing import Annotated, Literal
from fastapi import FastAPI, Depends, Query, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from .db import session_dependency
from .models import (Source,EvidenceRef,Feedback,Aspect,Feature,Fact,Vehicle,Requirement,RequirementRevision,Decision,AuditEvent,Job,Export,EvaluationLabel,AnalysisRun,now)
from .schemas import (Cohort,RankingResponse,DecisionRequest,ImportRequest,JobView,AnalysisRequest,AnalysisProposal,ExportRequest,MappingReviewRequest,FactReviewRequest,EvaluationRequest,WebConnectorRequest,UspResponse)
from .services import ranking,detail,decide,evidence_detail,evaluation_metrics
from .vehicle_target import TargetRequest, TargetResult, resolve_target
from .taxonomy import CATEGORIES
from .audit import append_event,verify_audit
from .config import DATA_DIR,DEFAULT_MODEL,PIPELINE_VERSION
from .jobs import enqueue,recover_jobs,progress_messages
from .comparisons import comparison
from .usp import usp_evaluation,DEFAULT_COST_RATIO_LOW,DEFAULT_COST_RATIO_HIGH
from .trends import trend_evaluation,TrendResponse,Horizon,Market
from .successor import successor_brief,review_proposal,SuccessorResponse,SuccessorReviewRequest

@asynccontextmanager
async def lifespan(app):
    recover_jobs()
    yield

from .rag_routes import router as rag_router
from .reddit_routes import router as reddit_router

app=FastAPI(title='BMW Product Manager Cockpit',version='1.0.0',lifespan=lifespan)
app.include_router(rag_router)
app.include_router(reddit_router)
ORIGINS=['http://127.0.0.1:3001','http://localhost:3001','http://127.0.0.1:8001','http://localhost:8001','http://127.0.0.1:3000','http://localhost:3000','http://127.0.0.1:8000','http://localhost:8000']
web_port=int(os.getenv('BMWPM_WEB_PORT','3001'))
if not 1<=web_port<=65535:raise ValueError('BMWPM_WEB_PORT must be a valid local port.')
ORIGINS.extend([f'http://127.0.0.1:{web_port}',f'http://localhost:{web_port}'])
app.add_middleware(CORSMiddleware,allow_origins=ORIGINS,allow_methods=['GET','POST'],allow_headers=['Content-Type'])
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])

@app.middleware('http')
async def local_mutations(request:Request,call_next):
    if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('origin') and request.headers['origin'] not in ORIGINS:
        return JSONResponse({'detail':'This local application does not accept cross-origin changes.'},status_code=403)
    return await call_next(request)

DB=Annotated[Session,Depends(session_dependency)]

def cohort_parameters(model:Literal['F70','G60','G68','G70','G60_G68']='G60',country:str='US',powertrain:Literal['all','ICE','BEV','PHEV']='all',origin:Literal['unknown','observed','synthetic','all']='unknown'):
    return Cohort(model=model,country=country,powertrain=powertrain,origin=origin)

COHORT=Annotated[Cohort,Depends(cohort_parameters)]
pdf_render_lock=Lock()

def row_dict(record):
    return {c.name:getattr(record,c.name) for c in record.__table__.columns}

@app.get('/api/v1/health')
def health():
    return {'status':'ok','pipeline':PIPELINE_VERSION,'mode':'replay','live_configured':bool(os.getenv('OPENAI_API_KEY')),'model':os.getenv('OPENAI_MODEL',DEFAULT_MODEL),'reviewer':'Demo PM (local demonstration identity)','rehearsal':os.getenv('BMWPM_REHEARSAL')=='1'}

@app.get('/api/v1/meta')
def metadata(db:DB):
    countries=[r[0] for r in db.execute(select(Feedback.country).distinct().order_by(Feedback.country))]
    return {'categories':CATEGORIES,'countries':countries,'models':[row_dict(v) for v in db.scalars(select(Vehicle).where(Vehicle.variant==None))],
            'facts_pending':db.scalar(select(func.count()).select_from(Fact).where(Fact.review_status=='pending')),
            'feedback_counts':dict(db.execute(select(Feedback.model,func.count()).group_by(Feedback.model)).all())}

@app.get('/api/v1/overview')
def overview(db:DB,cohort:COHORT):
    result=ranking(db,cohort)
    sources=db.scalars(select(Source).where(Source.active==True)).all()
    return {'cohort':cohort.model_dump(),'denominator':result.denominator,'mapped_records':result.mapped_records,'reviewed_mapping_records':result.reviewed_mapping_records,
            'mapping_coverage':result.mapping_coverage,'requirements':len(result.requirements),'critical':sum(r.critical for r in result.requirements),
            'approved':sum(r.status=='approved' for r in result.requirements),'sources':len(sources),'tagged_rows':sum(s.row_count for s in sources if s.kind=='customer_statement'),
            'total_feedback':sum(s.record_count for s in sources if s.kind=='customer_statement'),
            'category_counts':[{ 'category':c,'name':name,'requirements':sum(r.category==c for r in result.requirements),'mentions':sum(r.numerator for r in result.requirements if r.category==c)} for c,name in CATEGORIES.items()],
            'top_requirements':[r.model_dump() for r in result.requirements[:5]],'evaluation':evaluation_metrics(db)}

@app.get('/api/v1/requirements',response_model=RankingResponse)
def requirements(db:DB,cohort:COHORT,category:str|None=None):
    return ranking(db,cohort,category)

@app.get('/api/v1/requirements/{requirement_id}')
def requirement_detail(requirement_id:str,db:DB,cohort:COHORT):
    item,snapshot=detail(db,requirement_id,cohort)
    revisions=db.scalars(select(RequirementRevision).where(RequirementRevision.requirement_id==requirement_id).order_by(RequirementRevision.revision.desc())).all()
    decisions=db.scalars(select(Decision).where(Decision.requirement_id==requirement_id).order_by(Decision.created_at.desc())).all()
    analyses=db.scalars(select(AnalysisRun).order_by(AnalysisRun.created_at.desc())).all()
    return {'requirement':item.model_dump(),'revisions':[row_dict(r) for r in revisions],
            'decisions':[{k:v for k,v in row_dict(d).items() if k!='snapshot'}|{'cohort':d.snapshot['cohort']} for d in decisions],
            'replays':[{'id':a.id,'generated_at':a.created_at,'model':a.model_version,'revision':a.inputs['revision']} for a in analyses if a.inputs.get('requirement_id')==requirement_id]}

@app.post('/api/v1/requirements/{requirement_id}/decisions')
def requirement_decision(requirement_id:str,request:DecisionRequest,db:DB):
    return decide(db,requirement_id,request)

@app.post('/api/v1/vehicle-target',response_model=TargetResult)
def vehicle_target(request:TargetRequest,db:DB):
    item,_=detail(db,request.requirement_id,request.cohort)
    return resolve_target(item,request.cohort,request.allow_live)

@app.get('/api/v1/sources')
def sources(db:DB):
    return [{k:v for k,v in row_dict(s).items() if k!='path'} for s in db.scalars(select(Source).where(Source.active==True).order_by(Source.filename))]

@app.get('/api/v1/sources/{source_id}/file')
def source_file(source_id:str,db:DB):
    source=db.get(Source,source_id)
    if not source: raise HTTPException(404,'Source not found.')
    media={'pdf':'application/pdf','html':'text/html','csv':'text/csv','txt':'text/plain','md':'text/plain','zip':'application/zip','jsonl':'application/x-ndjson','pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation'}.get(source.format,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    return FileResponse(source.path,media_type=media,filename=source.filename,content_disposition_type='inline' if source.format=='pdf' else 'attachment')

@app.get('/api/v1/sources/{source_id}/pages/{page_number}')
def source_page(source_id:str,page_number:int,db:DB):
    source=db.get(Source,source_id)
    if not source or source.format!='pdf':raise HTTPException(404,'PDF source not found.')
    if page_number<1:raise HTTPException(422,'PDF pages start at one.')
    cache=DATA_DIR/'previews'/f'{source.checksum}-p{page_number}-v1.png'
    # PDFium calls must be serialized; the local API can use multiple request threads.
    with pdf_render_lock:
        if not cache.exists():
            import pypdfium2 as pdfium
            from uuid import uuid4
            with pdfium.PdfDocument(source.path) as document:
                if page_number>len(document):raise HTTPException(404,'PDF page not found.')
                page=document[page_number-1]
                bitmap=page.render(scale=1.6)
                temp=cache.with_suffix('.'+uuid4().hex+'.tmp')
                bitmap.to_pil().save(temp,format='PNG')
                bitmap.close();page.close()
                temp.replace(cache)
    return FileResponse(cache,media_type='image/png',headers={'Cache-Control':'private, max-age=86400'})

@app.get('/api/v1/feedback')
def feedback_register(db:DB,cohort:COHORT,q:str='',category:str='',source_id:str='',offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100)):
    from .feedback import list_feedback
    return list_feedback(db,cohort,q,category,source_id,offset,limit)

@app.get('/api/v1/evidence')
def evidence_search(db:DB,q:str='',model:str|None=None,source_id:str|None=None,kind:str|None=None,origin:Literal['unknown','observed','synthetic','all']='all',offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100)):
    query=select(EvidenceRef,Source.filename).join(Source,EvidenceRef.source_id==Source.id)
    if q.strip():
        tokens=re.findall(r'\w+',q,flags=re.UNICODE)[:12]
        if not tokens: return {'items':[],'total':0}
        expression=' AND '.join('"'+t.replace('"','')+'"*' for t in tokens)
        matched=db.execute(text('SELECT evidence_id FROM evidence_fts WHERE evidence_fts MATCH :query'),{'query':expression}).scalars().all()
        if not matched: return {'items':[],'total':0}
        query=query.where(EvidenceRef.id.in_(matched))
    if model: query=query.where(EvidenceRef.model==model)
    if source_id: query=query.where(EvidenceRef.source_id==source_id)
    else: query=query.where(Source.active==True)
    if kind: query=query.where(EvidenceRef.kind==kind)
    if origin!='all': query=query.where(EvidenceRef.origin==origin)
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.execute(query.order_by(EvidenceRef.id).offset(offset).limit(limit)).all()
    return {'items':[row_dict(e)|{'filename':filename} for e,filename in rows],'total':total}

@app.get('/api/v1/evidence/{evidence_id}')
def get_evidence(evidence_id:str,db:DB):
    return evidence_detail(db,evidence_id)

@app.get('/api/v1/baseline')
def baseline(db:DB,model:str='G60',kind:str|None=None,category:str|None=None,q:str='',status:str|None=None,offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100)):
    query=select(Fact).where(Fact.model==model)
    if kind: query=query.where(Fact.evidence_kind==kind)
    if category: query=query.where(Fact.category==category)
    if q: query=query.where(Fact.label.ilike(f'%{q}%'))
    if status: query=query.where(Fact.review_status==status)
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    facts=db.scalars(query.order_by(Fact.label,Fact.variant).offset(offset).limit(limit)).all()
    return {'items':[row_dict(f) for f in facts],'total':total,'market_notice':'German catalog specifications do not establish US equipment availability.'}

@app.post('/api/v1/facts/{fact_id}/review')
def fact_review(fact_id:str,request:FactReviewRequest,db:DB):
    db.execute(text('BEGIN IMMEDIATE'))
    fact=db.get(Fact,fact_id)
    if not fact: raise HTTPException(404,'Fact not found.')
    previous=fact.review_status;fact.review_status=request.status
    append_event(db,request.actor,'fact.reviewed',fact.id,{'previous':previous,'current':request.status,'rationale':request.rationale,'evidence_id':fact.evidence_id})
    db.commit();return row_dict(fact)

@app.get('/api/v1/mappings')
def mappings(db:DB,model:str='G60',status:str='pending',offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100)):
    query=select(Aspect,Feedback,Feature).join(Feedback,Aspect.feedback_id==Feedback.id).join(Feature,Aspect.feature_id==Feature.id).where(Feedback.model==model,Aspect.mapping_status==status)
    count=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.execute(query.order_by(Aspect.id).offset(offset).limit(limit)).all()
    return {'total':count,'items':[row_dict(a)|{'external_id':f.external_id,'country':f.country,'feature':feat.name,'category':feat.category} for a,f,feat in rows]}

@app.get('/api/v1/features')
def features(db:DB):
    return [row_dict(f) for f in db.scalars(select(Feature).order_by(Feature.name))]

@app.post('/api/v1/mappings/{aspect_id}/review')
def mapping_review(aspect_id:str,request:MappingReviewRequest,db:DB):
    db.execute(text('BEGIN IMMEDIATE'))
    aspect=db.get(Aspect,aspect_id)
    if not aspect: raise HTTPException(404,'Mapping not found.')
    previous={'status':aspect.mapping_status,'feature_id':aspect.feature_id}
    if request.feature_id and request.feature_id!=aspect.feature_id:
        if not db.get(Feature,request.feature_id):raise HTTPException(422,'Unknown canonical feature.')
        duplicate=db.scalar(select(Aspect).where(Aspect.feedback_id==aspect.feedback_id,Aspect.feature_id==request.feature_id,Aspect.feedback_type==aspect.feedback_type,Aspect.id!=aspect.id))
        if duplicate: raise HTTPException(409,'That record already has a mapping to this feature and feedback type.')
        aspect.feature_id=request.feature_id
    aspect.mapping_status=request.status;aspect.mapping_reason=request.rationale
    append_event(db,request.actor,'mapping.reviewed',aspect.id,{'previous':previous,'current':{'status':aspect.mapping_status,'feature_id':aspect.feature_id},'rationale':request.rationale,'evidence_id':aspect.evidence_id})
    from .services import seed_requirements
    seed_requirements(db)
    db.commit();return row_dict(aspect)

@app.post('/api/v1/imports',response_model=JobView)
def import_sources(request:ImportRequest,db:DB):
    path=Path(request.path).resolve()
    if not path.is_file() or path.suffix.lower()!='.zip': raise HTTPException(422,'Provide an existing local BMW source ZIP file.')
    return enqueue(db,'import',{'path':str(path)})

@app.post('/api/v1/connectors/web',response_model=JobView)
def connect_web(request:WebConnectorRequest,db:DB):
    return enqueue(db,'web_connector',request.model_dump())

@app.post('/api/v1/analysis',response_model=JobView)
def start_analysis(request:AnalysisRequest,db:DB):
    detail(db,request.requirement_id,request.cohort)
    return enqueue(db,'analysis',request.model_dump())

@app.get('/api/v1/analysis/{run_id}/proposal',response_model=AnalysisProposal)
def analysis_proposal(run_id:str,db:DB):
    run=db.get(AnalysisRun,run_id)
    if not run:raise HTTPException(404,'Analysis not found.')
    return AnalysisProposal.model_validate(run.output)

@app.get('/api/v1/jobs',response_model=list[JobView])
def jobs(db:DB):
    return db.scalars(select(Job).order_by(Job.created_at.desc()).limit(25)).all()

@app.get('/api/v1/jobs/{job_id}',response_model=JobView)
def job_status(job_id:str,db:DB):
    job=db.get(Job,job_id)
    if not job:raise HTTPException(404,'Job not found.')
    result=JobView.model_validate(job)
    result.progress=progress_messages.get(job_id,result.progress)
    return result

@app.post('/api/v1/jobs/{job_id}/retry',response_model=JobView)
def retry_job(job_id:str,db:DB):
    job=db.get(Job,job_id)
    if not job or job.state not in ('failed','interrupted'):raise HTTPException(409,'Only failed or interrupted jobs can be retried.')
    if job.kind=='reddit_pipeline':raise HTTPException(409,'Enter your API key on Reviews & Comments to start a new collection.')
    return enqueue(db,job.kind,job.input)

@app.get('/api/v1/comparisons')
def comparisons(db:DB): return comparison(db)

@app.get('/api/v1/usp',response_model=UspResponse)
def usp(db:DB,cohort:COHORT,cost_ratio_low:float=Query(DEFAULT_COST_RATIO_LOW,gt=0,le=1),cost_ratio_high:float=Query(DEFAULT_COST_RATIO_HIGH,gt=0,le=1)):
    if cost_ratio_low>cost_ratio_high: raise HTTPException(422,'The low cost ratio cannot exceed the high cost ratio.')
    return usp_evaluation(db,cohort,cost_ratio_low,cost_ratio_high)

@app.get('/api/v1/trends',response_model=TrendResponse)
def trends(db:DB,cohort:COHORT,category:str|None=None,horizon:Horizon|None=None,market:Market|None=None):
    if category and category not in CATEGORIES: raise HTTPException(422,'Unknown product category.')
    return trend_evaluation(db,cohort,category,horizon,market)

@app.get('/api/v1/successor',response_model=SuccessorResponse)
def successor(db:DB,cohort:COHORT):
    return successor_brief(db,cohort)

@app.post('/api/v1/successor/{proposal_id}/review')
def successor_review(proposal_id:str,request:SuccessorReviewRequest,db:DB):
    return review_proposal(db,proposal_id,request)

@app.get('/api/v1/decisions')
def decisions(db:DB,limit:int=Query(50,le=200,ge=1)):
    rows=db.scalars(select(Decision).order_by(Decision.created_at.desc()).limit(limit)).all()
    return [{k:v for k,v in row_dict(d).items() if k!='snapshot'}|{'cohort':d.snapshot['cohort'],'demand_snapshot':d.snapshot['denominator']} for d in rows]

@app.get('/api/v1/audit')
def audit(db:DB):
    return {'integrity':verify_audit(db),'events':[row_dict(e) for e in db.scalars(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(100))]}

@app.get('/api/v1/evaluation')
def evaluation(db:DB):
    rows=db.scalars(select(EvaluationLabel).order_by(EvaluationLabel.feedback_id)).all()
    return evaluation_metrics(db)|{'items':[row_dict(r)|{'text':db.get(Feedback,r.feedback_id).text,'model':db.get(Feedback,r.feedback_id).model,'country':db.get(Feedback,r.feedback_id).country} for r in rows]}

@app.post('/api/v1/evaluation/{feedback_id}')
def label_evaluation(feedback_id:str,request:EvaluationRequest,db:DB):
    db.execute(text('BEGIN IMMEDIATE'))
    label=db.get(EvaluationLabel,feedback_id)
    if not label:raise HTTPException(404,'Evaluation record not found.')
    old=label.expected_categories;label.expected_categories=sorted(set(request.categories));label.actor=request.actor;label.rationale=request.rationale;label.labeled_at=now()
    append_event(db,request.actor,'evaluation.labeled',feedback_id,{'previous':old,'current':label.expected_categories,'rationale':request.rationale,'split':label.split})
    db.commit();return evaluation_metrics(db)

@app.post('/api/v1/exports',response_model=JobView)
def start_export(request:ExportRequest,db:DB): return enqueue(db,'export',request.model_dump())

@app.get('/api/v1/exports')
def exports(db:DB):
    return [{'id':e.id,'created_at':e.created_at,'cohort':e.snapshot['cohort'],'approved':len(e.snapshot['approved']),'filename':Path(e.path).name} for e in db.scalars(select(Export).order_by(Export.created_at.desc()))]

@app.get('/api/v1/exports/{export_id}/download')
def download_export(export_id:str,db:DB):
    record=db.get(Export,export_id)
    if not record:raise HTTPException(404,'Export not found.')
    return FileResponse(record.path,filename=Path(record.path).name,media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')

@app.get('/api/v1/exports/{export_id}/snapshot')
def export_snapshot(export_id:str,db:DB):
    record=db.get(Export,export_id)
    if not record:raise HTTPException(404,'Export not found.')
    return JSONResponse(record.snapshot,headers={'Content-Disposition':f'attachment; filename="{export_id}-snapshot.json"'})
