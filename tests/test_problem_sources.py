from backend.schemas import Cohort
from backend.services import ranking
from backend.models import EvidenceRef, Source


def test_problem_citations_resolve_to_original_source(session):
    result = ranking(session, Cohort())
    assert result.requirements
    for item in result.requirements:
        for citation in item.evidence_samples:
            evidence = session.get(EvidenceRef, citation['id'])
            source = session.get(Source, evidence.source_id)
            assert citation['source'] == {'id': source.id, 'filename': source.filename, 'kind': source.kind}
            assert citation['locator'] == evidence.locator
            assert citation['quote']
