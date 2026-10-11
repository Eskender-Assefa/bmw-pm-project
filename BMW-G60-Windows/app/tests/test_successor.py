"""Successor brief: Keep / Fix / Lead proposals and their audited PM review."""
import pytest
from sqlalchemy import select

from backend.audit import verify_audit
from backend.models import AuditEvent

G60_US = 'model=G60&country=US&powertrain=all&origin=unknown'
COHORT = {'model': 'G60', 'country': 'US', 'powertrain': 'all', 'origin': 'unknown'}


def brief(client, query=G60_US):
    response = client.get(f'/api/v1/successor?{query}')
    assert response.status_code == 200
    return response.json()


def by_id(body):
    return {proposal['id']: proposal for proposal in body['proposals']}


def test_successor_brief_groups_proposals_and_labels_their_basis(client):
    body = brief(client)
    kinds = {proposal['kind'] for proposal in body['proposals']}
    assert kinds == {'keep', 'fix', 'lead'}
    assert all(proposal['basis'] == ('assumption' if proposal['kind'] == 'lead' else 'evidence') for proposal in body['proposals'])
    assert body['summary']['keep'] + body['summary']['fix'] + body['summary']['lead'] == len(body['proposals'])
    assert body['summary']['assumption_based'] == body['summary']['lead']


def test_successor_brief_keep_proposals_are_the_cohort_usps(client):
    body = brief(client)
    usps = {item['feature_id'] for item in client.get(f'/api/v1/usp?{G60_US}').json()['items'] if item['is_usp']}
    keep = {proposal['feature_id'] for proposal in body['proposals'] if proposal['kind'] == 'keep'}
    assert keep == usps
    drivetrain = by_id(body)['keep:G60:drivetrain']
    assert drivetrain['likes'] == 268 and drivetrain['denominator'] == 3610
    assert any('unmet need' in conflict for conflict in drivetrain['conflicts'])


def test_successor_brief_fix_proposals_point_at_reviewable_requirements(client):
    body = brief(client)
    requirements = {item['id']: item for item in client.get(f'/api/v1/requirements?{G60_US}').json()['requirements']}
    fixes = [proposal for proposal in body['proposals'] if proposal['kind'] == 'fix']
    assert fixes
    for proposal in fixes:
        assert proposal['requirement_id'] in requirements
        assert proposal['complaints'] > proposal['likes']
        assert proposal['review']['status'] == requirements[proposal['requirement_id']]['status']


def test_successor_brief_lead_proposals_are_criticised_trends_with_sources(client):
    body = brief(client)
    trends = {trend['id']: trend for trend in client.get(f'/api/v1/trends?{G60_US}').json()['trends']}
    leads = [proposal for proposal in body['proposals'] if proposal['kind'] == 'lead']
    assert {proposal['trend_id'] for proposal in leads} == {key for key, trend in trends.items() if trend['customer']['signal'] == 'criticised'}
    assert all(proposal['sources'] and proposal['horizon'] for proposal in leads)
    charging = by_id(body)['lead:G60:ultra-fast-charging']
    assert any('market' in conflict for conflict in charging['conflicts'])


def test_successor_review_records_decision_in_the_audit_chain(client, session):
    before = verify_audit(session)['events']
    response = client.post('/api/v1/successor/keep:G60:drivetrain/review', json={'cohort': COHORT, 'action': 'accept', 'rationale': ''})
    assert response.status_code == 200 and response.json()['status'] == 'accepted'
    review = by_id(brief(client))['keep:G60:drivetrain']['review']
    assert review['status'] == 'accepted' and review['actor'] == 'Demo PM'
    session.expire_all()
    audit = verify_audit(session)
    assert audit['valid'] and audit['events'] == before + 1
    event = session.scalar(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1))
    assert event.action == 'successor.reviewed' and event.payload['proposal']['title'].startswith('Preserve')


def test_successor_review_latest_decision_wins_and_is_cohort_specific(client):
    url = '/api/v1/successor/lead:G60:digital-key/review'
    client.post(url, json={'cohort': COHORT, 'action': 'accept', 'rationale': ''})
    client.post(url, json={'cohort': COHORT, 'action': 'reject', 'rationale': 'Not a priority for this market.'})
    assert by_id(brief(client))['lead:G60:digital-key']['review']['status'] == 'rejected'
    other = by_id(brief(client, 'model=G60&country=all&powertrain=all&origin=unknown'))['lead:G60:digital-key']
    assert other['review']['status'] == 'proposed'


@pytest.mark.parametrize('payload,status', [
    ({'cohort': COHORT, 'action': 'reject', 'rationale': ''}, 422),
    ({'cohort': COHORT, 'action': 'defer', 'rationale': 'no'}, 422),
    ({'cohort': COHORT, 'action': 'approve', 'rationale': 'x' * 10}, 422),
])
def test_successor_review_when_request_is_invalid_is_rejected(client, payload, status):
    assert client.post('/api/v1/successor/keep:G60:drivetrain/review', json=payload).status_code == status


def test_successor_review_when_proposal_is_unknown_returns_not_found(client):
    response = client.post('/api/v1/successor/keep:G60:no-such-feature/review', json={'cohort': COHORT, 'action': 'accept', 'rationale': ''})
    assert response.status_code == 404


def test_successor_review_when_proposal_is_a_requirement_points_to_requirement_review(client):
    fix = next(proposal for proposal in brief(client)['proposals'] if proposal['kind'] == 'fix')
    response = client.post(f"/api/v1/successor/{fix['id']}/review", json={'cohort': COHORT, 'action': 'accept', 'rationale': ''})
    assert response.status_code == 409


def test_successor_brief_when_cohort_is_empty_has_no_evidence_proposals(client):
    body = brief(client, 'model=G60&country=ZZ&powertrain=all&origin=unknown')
    assert body['denominator'] == 0 and body['proposals'] == []
