from sqlalchemy import select, func
from backend.models import Feedback, Source, Aspect, Feature
from backend.services import cohort_query
from backend.schemas import Cohort


def test_feedback_register_cohort_counts_and_pagination(client, session):
    cohort = Cohort(model='G60', country='US', powertrain='all', origin='unknown')
    expected = session.scalar(select(func.count()).select_from(cohort_query(cohort).subquery()))
    response = client.get('/api/v1/feedback', params=cohort.model_dump() | {'limit': 7})
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == expected
    assert len(data['items']) == min(7, expected)
    assert all(r['country'] == 'US' and r['model'] == 'G60' and r['origin'] == 'unknown' for r in data['items'])
    assert len({r['id'] for r in data['items']}) == len(data['items'])
    second = client.get('/api/v1/feedback', params=cohort.model_dump() | {'limit': 7, 'offset': 7}).json()
    assert not {r['id'] for r in data['items']} & {r['id'] for r in second['items']}
    for row in data['items']:
        assert row['evidence_id']
        original = client.get('/api/v1/evidence/' + row['evidence_id']).json()
        assert original['feedback']['external_id'] == row['external_id']
        assert original['text'] == row['text']


def test_feedback_filters_use_distinct_records_and_literal_search(client, session):
    params = {'model': 'G60', 'country': 'all', 'powertrain': 'all', 'origin': 'all'}
    category = 'C07'
    matched_ids = session.scalars(select(Feedback.id).join(Source).join(Aspect).join(Feature)
        .where(Source.active == True, Feedback.model == 'G60', Feature.category == category).distinct()).all()
    data = client.get('/api/v1/feedback', params=params | {'category': category}).json()
    assert data['total'] == len(matched_ids)
    assert all(any(a['category'] == category for a in r['aspects']) for r in data['items'])
    assert data['items']
    row = data['items'][0]
    searched = client.get('/api/v1/feedback', params=params | {'q': row['external_id'], 'source_id': row['source_id']}).json()
    assert row['id'] in {r['id'] for r in searched['items']}
    assert all(r['source_id'] == row['source_id'] for r in searched['items'])
    empty = client.get('/api/v1/feedback', params=params | {'q': 'no-such-comment-7b1f9a%_'}).json()
    assert empty == {'items': [], 'total': 0, 'source_count': 0, 'critical_count': 0}
    assert client.get('/api/v1/feedback?limit=101').status_code == 422
    assert client.get('/api/v1/feedback?offset=-1').status_code == 422
