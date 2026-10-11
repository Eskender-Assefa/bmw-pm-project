import json
from sqlalchemy import select
from .config import ROOT
from .models import Fact, EvidenceRef

def comparison(session):
    scenario=json.loads((ROOT/'fixtures'/'competitor-scenario.json').read_text(encoding='utf-8'))
    for row in scenario['rows']:
        facts=session.scalars(select(Fact).where(Fact.model=='G60',Fact.variant==scenario['bmw_variant'],Fact.market=='DE',Fact.label==row['label'],Fact.unit==row['unit'],Fact.review_status=='reviewed',Fact.knowledge_state=='known')).all()
        fact=facts[0] if len(facts)==1 else None
        row.update({'bmw':fact.value if fact else None,'bmw_evidence_id':fact.evidence_id if fact else None,
                    'comparison_status':'Compatible scenario assumptions; competitor values synthetic' if fact else 'Not comparable',
                    'reason':None if fact else 'No unique reviewed BMW baseline fact with matching variant, market and units.'})
    return scenario
