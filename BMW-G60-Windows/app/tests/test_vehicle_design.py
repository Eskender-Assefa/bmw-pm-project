from backend.schemas import Cohort, DecisionRequest
from backend.services import ranking, decide
from backend.db import SessionLocal

def test_accepted_design_persists_and_is_scoped(session):
    item=next(r for r in ranking(session,Cohort()).requirements if r.feature=='Touch screen, operation')
    session.rollback()
    result=decide(session,item.id,DecisionRequest(cohort=Cohort(),expected_revision=item.revision,action='approve',design_concept='screen'))
    assert result['design_concept']=='screen'
    with SessionLocal() as reopened:
        saved=next(r for r in ranking(reopened,Cohort()).requirements if r.id==item.id)
        assert saved.status=='approved' and saved.design_concept=='screen'
        other=next(r for r in ranking(reopened,Cohort(country='GB')).requirements if r.id==item.id)
        assert other.design_concept is None
    session.rollback()
    decide(session,item.id,DecisionRequest(cohort=Cohort(),expected_revision=item.revision,action='set_band',band='High',rationale='Retain the accepted design.'))
    assert next(r for r in ranking(session,Cohort()).requirements if r.id==item.id).design_concept=='screen'
    session.rollback()
    decide(session,item.id,DecisionRequest(cohort=Cohort(),expected_revision=item.revision,action='reject',rationale='Withdraw this design concept.'))
    assert next(r for r in ranking(session,Cohort()).requirements if r.id==item.id).design_concept is None

def test_edit_invalidates_accepted_design(session):
    item=next(r for r in ranking(session,Cohort()).requirements if r.feature=='Touch screen, operation')
    session.rollback()
    decide(session,item.id,DecisionRequest(cohort=Cohort(),expected_revision=item.revision,action='approve',design_concept='screen'))
    decide(session,item.id,DecisionRequest(cohort=Cohort(),expected_revision=item.revision,action='edit',title='Reconsider the display design',rationale='New revision needs another review.'))
    item=next(r for r in ranking(session,Cohort()).requirements if r.id==item.id)
    assert item.status=='proposed' and item.design_concept is None
