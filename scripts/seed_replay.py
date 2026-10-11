"""Explicit live analysis of one small supplied-evidence batch; saves a genuine replay."""
import argparse
import json
from backend.db import SessionLocal
from backend.models import Job
from backend.services import ranking
from backend.schemas import Cohort
from backend.jobs import execute

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--feature',default='Touch screen, operation')
    args=parser.parse_args()
    with SessionLocal() as session:
        candidates=ranking(session,Cohort()).requirements
        chosen=next((r for r in candidates if args.feature.lower() in r.feature.lower()),None)
        if chosen is None:
            raise SystemExit('No matching feature. Choose a feature from the Requirements view.')
        job=Job(kind='analysis',input={'cohort':Cohort().model_dump(),'requirement_id':chosen.id,'mode':'live'})
        session.add(job);session.commit();job_id=job.id
        print(json.dumps({'feature':chosen.feature,'requirement_id':chosen.id,'job_id':job_id}),flush=True)
    execute(job_id)
    with SessionLocal() as session:
        job=session.get(Job,job_id)
        print(json.dumps({'state':job.state,'error':job.error,'run_id':(job.result or {}).get('run_id'),'generated_at':(job.result or {}).get('generated_at')},indent=2))
        if job.state!='succeeded':raise SystemExit(1)

if __name__=='__main__':main()
