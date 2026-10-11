from collections import defaultdict, Counter
from sqlalchemy import select, text, func
from fastapi import HTTPException
from .models import (Source, EvidenceRef, Feedback, Aspect, Feature, Requirement, RequirementRevision, Decision,
                     PriorityRun, Fact, AuditEvent, EvaluationLabel, now)
from .schemas import Cohort, RankingResponse, RequirementView, DecisionRequest
from .config import RANKING_VERSION
from .audit import digest, append_event

UNMET = {'Wants','Difficult to Use','Defect'}

def cohort_query(cohort):
    query=select(Feedback).join(Source,Feedback.source_id==Source.id).where(Feedback.model==cohort.model,Source.active==True)
    if cohort.country!='all': query=query.where(Feedback.country==cohort.country)
    if cohort.powertrain!='all': query=query.where(Feedback.powertrain==cohort.powertrain)
    if cohort.origin!='all': query=query.where(Feedback.origin==cohort.origin)
    return query

def seed_requirements(session):
    rows=session.execute(select(Aspect,Feedback,Feature).join(Feedback,Aspect.feedback_id==Feedback.id).join(Feature,Aspect.feature_id==Feature.id).where(Aspect.feedback_type.in_(UNMET),Aspect.mapping_status!='pending')).all()
    groups=defaultdict(list)
    for aspect,feedback,feature in rows:
        groups[(feedback.model,feature.id)].append((aspect,feedback,feature))
    for (model,feature_id),items in groups.items():
        req_id=f'{model}-{digest(feature_id)[:10]}'
        if session.get(Requirement,req_id): continue
        feature=items[0][2]
        refs=list(dict.fromkeys(a.evidence_id for a,_,_ in items))[:8]
        session.add(Requirement(id=req_id,model=model,feature_id=feature_id))
        session.flush()
        session.add(RequirementRevision(requirement_id=req_id,revision=1,title=f'Improve {feature.name.lower()}',
            description=f'Address the reported customer difficulties and unmet needs involving {feature.name.lower()}. Confirm the affected configurations and the intended behavior with the PM before engineering assessment.',
            acceptance_criteria=['Proposed: reproduce the cited customer difficulty on the applicable variant.', 'Proposed: validate the revised experience with customers from this cohort.'],
            evidence_ids=refs,actor='Rules engine',rationale='Candidate derived from supplied feedback tags. Mapping and acceptance criteria require review.',generated_by='Deterministic template, not AI'))
    session.flush()

def ranking(session, cohort: Cohort, category=None):
    records=session.scalars(cohort_query(cohort)).all()
    record_map={r.id:r for r in records}
    denominator=len(records)
    # Join rather than an SQLite parameter list containing thousands of IDs.
    query=select(Aspect,Feedback,Feature).join(Feedback,Aspect.feedback_id==Feedback.id).join(Feature,Aspect.feature_id==Feature.id).where(Feedback.model==cohort.model)
    groups=defaultdict(list); mapped=set(); reviewed=set()
    for aspect,feedback,feature in session.execute(query):
        if feedback.id not in record_map or aspect.mapping_status=='rejected': continue
        if aspect.mapping_status!='pending': mapped.add(feedback.id)
        if aspect.mapping_status=='reviewed': reviewed.add(feedback.id)
        groups[feature.id].append((aspect,feedback,feature))
    requirements=session.scalars(select(Requirement).where(Requirement.model==cohort.model)).all()
    revisions={r.requirement_id:r for r in session.scalars(select(RequirementRevision).join(Requirement, Requirement.id==RequirementRevision.requirement_id).where(Requirement.model==cohort.model,RequirementRevision.revision==Requirement.current_revision))}
    decisions=session.scalars(select(Decision).join(Requirement,Requirement.id==Decision.requirement_id).where(Requirement.model==cohort.model).order_by(Decision.created_at)).all()
    state={}
    for decision in decisions:
        if decision.snapshot.get('cohort')==cohort.model_dump():
            state[decision.requirement_id]=decision
    output=[]
    sources={source.id:source for source in session.scalars(select(Source))}
    for req in requirements:
        items=groups.get(req.feature_id,[])
        if not items: continue
        feature=items[0][2]
        if category and feature.category!=category: continue
        unmet=[(a,f) for a,f,_ in items if a.feedback_type in UNMET and a.mapping_status!='pending']
        if not unmet: continue
        supporting=sorted({f.id for _,f in unmet})
        likes={f.id for a,f,_ in items if a.feedback_type=='Likes'}
        evidence_ids=list(dict.fromkeys(a.evidence_id for a,_ in unmet))
        samples=[]
        for a,f in unmet:
            if len(samples)>=3: break
            if any(s['feedback_id']==f.id for s in samples): continue
            ref=session.get(EvidenceRef,a.evidence_id)
            source=sources.get(ref.source_id)
            samples.append({'source':{'id':source.id,'filename':source.filename,'kind':source.kind} if source else None,'id':ref.id,'feedback_id':f.id,'external_id':f.external_id,'quote':a.quote,'country':f.country,'type':a.feedback_type,'locator':ref.locator})
        revision=revisions[req.id]
        decision=state.get(req.id)
        current=decision.current if decision and decision.revision==req.current_revision else {'status':'proposed','band':'Unscored'}
        sentiment_by_record=defaultdict(list)
        for a,f,_ in items:
            if a.sentiment is not None: sentiment_by_record[f.id].append(a.sentiment)
        means=[sum(s)/len(s) for s in sentiment_by_record.values()]
        conflicts=[]
        if likes: conflicts.append(f'Strength to preserve: {len(likes)} records praise this feature. Positive and unmet-need counts may overlap.')
        if any(f.duplicate_text for _,f in unmet): conflicts.append('Identical wording occurs under different source IDs; these records have not been merged.')
        output.append(RequirementView(id=req.id,feature_id=feature.id,feature=feature.name,category=feature.category,
          title=revision.title,description=revision.description,acceptance_criteria=revision.acceptance_criteria,revision=req.current_revision,
          design_concept=current.get('design_concept') if current.get('status')=='approved' else None,
          status=current.get('status','proposed'),band=current.get('band','Unscored'),critical=any(a.critical for a,_,_ in items),
          numerator=len(supporting),denominator=denominator,demand=len(supporting)/denominator if denominator else None,likes=len(likes),
          sentiment=sum(means)/len(means) if means else None,mapping_status='reviewed' if all(a.mapping_status=='reviewed' for a,_ in unmet) else 'suggested',
          evidence_ids=evidence_ids,supporting_ids=supporting,evidence_samples=samples,conflicts=conflicts,generated_by=revision.generated_by,created_at=revision.created_at))
    bands={'High':0,'Medium':1,'Low':2,'Unscored':3}
    output.sort(key=lambda r:(not r.critical,bands[r.band],-(r.demand or 0),r.id))
    checksums={s.id:s.checksum for s in session.scalars(select(Source).where(Source.active==True))}
    return RankingResponse(cohort=cohort,denominator=denominator,mapped_records=len(mapped),mapping_coverage=len(mapped)/denominator if denominator else None,
                           reviewed_mapping_records=len(reviewed),requirements=output,source_checksums=checksums,ranking_version=RANKING_VERSION)

def detail(session, req_id, cohort):
    result=ranking(session,cohort)
    item=next((r for r in result.requirements if r.id==req_id),None)
    if not item: raise HTTPException(404,'Requirement has no eligible unmet-need evidence in this cohort.')
    return item,result

def save_priority_run(session, snapshot):
    run=PriorityRun(cohort=snapshot.cohort.model_dump(),snapshot=snapshot.model_dump(),version=RANKING_VERSION)
    session.add(run); session.flush()
    return run

def decide(session, req_id, request: DecisionRequest):
    session.execute(text('BEGIN IMMEDIATE'))
    req=session.get(Requirement,req_id)
    if not req: raise HTTPException(404,'Requirement not found.')
    if req.current_revision!=request.expected_revision: raise HTTPException(409,'This requirement changed. Refresh before reviewing.')
    current,snapshot=detail(session,req_id,request.cohort)
    rationale=request.rationale.strip()
    override=request.band is not None and request.band!=current.band
    if (request.action in ('reject','postpone','edit','set_band') or override) and len(rationale)<5:
        raise HTTPException(422,'A rationale of at least five characters is required for this decision or override.')
    previous={'status':current.status,'band':current.band,'revision':current.revision,'title':current.title,'description':current.description,'acceptance_criteria':current.acceptance_criteria,'design_concept':current.design_concept}
    state={'status':current.status,'band':request.band or current.band,'revision':current.revision,'title':current.title,'description':current.description,'acceptance_criteria':current.acceptance_criteria,'design_concept':current.design_concept}
    if request.action=='edit':
        generated_by='PM revision'
        if request.analysis_run_id:
            from .models import AnalysisRun
            from .analysis import prepare_input, validate_output
            from .schemas import AnalysisRequest
            run=session.get(AnalysisRun,request.analysis_run_id)
            if not run or run.inputs!=prepare_input(session,AnalysisRequest(cohort=request.cohort,requirement_id=req_id)):
                raise HTTPException(409,'The analysis does not match the current requirement and cohort. Generate it again.')
            proposal=validate_output(run.inputs,run.output)
            request.title=proposal.title; request.description=proposal.description; request.acceptance_criteria=proposal.acceptance_criteria
            generated_by=f'AI draft adopted by PM; run {run.id}'
        req.current_revision+=1
        old=session.scalar(select(RequirementRevision).where(RequirementRevision.requirement_id==req_id,RequirementRevision.revision==request.expected_revision))
        criteria=request.acceptance_criteria if request.acceptance_criteria is not None else old.acceptance_criteria
        if not criteria or any(not c.strip() or len(c)>1000 for c in criteria): raise HTTPException(422,'Supply non-empty acceptance criteria of at most 1,000 characters each.')
        revision=RequirementRevision(requirement_id=req_id,revision=req.current_revision,title=request.title or old.title,description=request.description or old.description,
            acceptance_criteria=criteria,evidence_ids=current.evidence_ids,actor=request.actor,rationale=rationale,generated_by=generated_by)
        session.add(revision)
        state.update({'status':'proposed','band':'Unscored','revision':req.current_revision,'title':revision.title,'description':revision.description,'acceptance_criteria':criteria})
    else:
        state['status']={'approve':'approved','reject':'rejected','postpone':'postponed','set_band':current.status}[request.action]
    if request.design_concept and (request.action!='approve' or request.cohort.model!='G60'):
        raise HTTPException(422,'Design concepts can only be attached to G60 approvals.')
    if request.action=='approve' and 'design_concept' in request.model_fields_set:
        state['design_concept']=request.design_concept
    if state['status']!='approved':
        state['design_concept']=None
    req.status=state['status']; req.band=state['band']
    # Snapshot includes all cohort denominators, supporting IDs and source checksums.
    decision=Decision(requirement_id=req_id,revision=req.current_revision,action=request.action,actor=request.actor,rationale=rationale or 'Approved against the attached evidence snapshot.',previous=previous,current=state,snapshot=snapshot.model_dump())
    session.add(decision); session.flush()
    append_event(session,request.actor,request.action,req_id,{'decision_id':decision.id,'previous':previous,'current':state,'rationale':decision.rationale,'cohort':request.cohort.model_dump(),'snapshot_hash':digest(decision.snapshot)})
    session.commit()
    return {'decision_id':decision.id,**state}

def evidence_detail(session, evidence_id):
    item=session.get(EvidenceRef,evidence_id)
    if not item: raise HTTPException(404,'Evidence not found.')
    source=session.get(Source,item.source_id)
    feedback=session.scalar(select(Feedback).where(Feedback.source_id==source.id,Feedback.external_id==item.locator.get('external_id','')))
    if not feedback:
        feedback=session.scalar(select(Feedback).join(Aspect,Aspect.feedback_id==Feedback.id).where(Aspect.evidence_id==item.id))
    aspects=session.scalars(select(Aspect).where(Aspect.feedback_id==feedback.id)).all() if feedback else []
    return {'id':item.id,'text':item.text,'locator':item.locator,'kind':item.kind,'origin':item.origin,'model':item.model,
            'source':{'id':source.id,'filename':source.filename,'checksum':source.checksum,'market':source.market,'edition':source.edition,'date':source.source_date,'format':source.format},
            'feedback': {'id':feedback.id,'external_id':feedback.external_id,'country':feedback.country,'powertrain':feedback.powertrain,'source_date':None,'duplicate_text':feedback.duplicate_text,'tags':feedback.tags} if feedback else None,
            'aspects':[{'id':a.id,'feature_id':a.feature_id,'type':a.feedback_type,'quote':a.quote,'status':a.mapping_status,'reason':a.mapping_reason,'sentiment':a.sentiment,'critical':a.critical} for a in aspects]}

def evaluation_metrics(session):
    labels=session.scalars(select(EvaluationLabel)).all()
    report={}
    for split in ('calibration','held_out'):
        subset=[l for l in labels if l.split==split]
        labeled=[l for l in subset if l.expected_categories is not None]
        matches=0
        for label in labeled:
            predicted=set(session.scalars(select(Feature.category).join(Aspect,Aspect.feature_id==Feature.id).where(Aspect.feedback_id==label.feedback_id,Aspect.mapping_status!='rejected')))
            matches+=predicted==set(label.expected_categories)
        report[split]={'records':len(subset),'human_labeled':len(labeled),'exact_category_accuracy':matches/len(labeled) if labeled else None}
    return {'splits':report,'status':'Uncalibrated; human labels required' if not all(l.expected_categories is not None for l in labels) else 'Measured on entered human labels','automatic_promotion':False}
