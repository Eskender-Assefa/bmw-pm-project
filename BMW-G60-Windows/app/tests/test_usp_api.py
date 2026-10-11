"""USP evaluation against a disposable backup of the imported sources."""
import pytest
from sqlalchemy import select

from backend.models import Aspect, Fact, Feedback
from backend.schemas import Cohort
from backend.usp import usp_evaluation

G60_US = 'model=G60&country=US&powertrain=all&origin=unknown'


def by_feature(response):
    return {item['feature']: item for item in response['items']}


def test_usp_endpoint_when_default_cohort_ranks_praised_features_with_bounds(client):
    response = client.get(f'/api/v1/usp?{G60_US}')
    assert response.status_code == 200
    body = response.json()
    assert body['denominator'] == 3610
    scores = [item['score'] for item in body['items']]
    assert scores == sorted(scores, reverse=True)
    drivetrain = by_feature(body)['Drivetrain']
    assert drivetrain['is_usp'] is True
    assert drivetrain['praise_lower'] < drivetrain['praise_share'] == drivetrain['likes'] / 3610
    assert drivetrain['cost'] is None and drivetrain['on_frontier'] is False


def test_usp_endpoint_when_feature_has_priced_option_estimates_cost_band(client):
    body = client.get(f'/api/v1/usp?{G60_US}&cost_ratio_low=0.4&cost_ratio_high=0.7').json()
    highway = by_feature(body)['Highway assistant']
    cost = highway['cost']
    assert [option['label'] for option in cost['options']] == ['Autobahnassistent']
    assert cost['options'][0]['price_eur_including_vat'] == 850.0
    net = 850.0 / 1.19
    assert cost['net_price_median'] == pytest.approx(net, abs=0.01)
    assert (cost['low'], cost['mid'], cost['high']) == pytest.approx((net * 0.4, net * 0.55, net * 0.7), abs=0.01)
    assert highway['efficiency'] == pytest.approx(highway['score'] * 100 / (cost['mid'] / 100))


def test_usp_endpoint_when_ratios_change_moves_cost_but_not_score(client):
    narrow = by_feature(client.get(f'/api/v1/usp?{G60_US}&cost_ratio_low=0.5&cost_ratio_high=0.5').json())['Highway assistant']
    wide = by_feature(client.get(f'/api/v1/usp?{G60_US}&cost_ratio_low=0.2&cost_ratio_high=0.9').json())['Highway assistant']
    assert narrow['score'] == wide['score']
    assert narrow['cost']['low'] == narrow['cost']['high']
    assert wide['cost']['low'] < narrow['cost']['low'] < wide['cost']['high']


def test_usp_endpoint_marks_frontier_only_among_costed_features(client):
    items = client.get(f'/api/v1/usp?{G60_US}').json()['items']
    frontier = [item for item in items if item['on_frontier']]
    assert frontier and all(item['cost'] for item in frontier)
    costed = [item for item in items if item['cost']]
    for point in frontier:
        assert not any(other['cost']['mid'] <= point['cost']['mid'] and other['score'] > point['score'] for other in costed)


def test_usp_endpoint_states_assumptions_and_market_limits(client):
    body = client.get(f'/api/v1/usp?{G60_US}').json()
    assert body['assumptions']['cost_basis'] == 'estimate'
    assert body['assumptions']['vat_rate'] == 0.19
    assert 'not BMW cost data' in body['assumptions']['notice']
    assert body['summary']['usps'] == sum(item['is_usp'] for item in body['items'])
    assert body['summary']['costed_usps'] <= body['summary']['usps']


@pytest.mark.parametrize('query', ['cost_ratio_low=0.8&cost_ratio_high=0.4', 'cost_ratio_low=0', 'cost_ratio_high=1.5', 'cost_ratio_low=abc'])
def test_usp_endpoint_when_ratios_are_invalid_rejects_request(client, query):
    assert client.get(f'/api/v1/usp?{G60_US}&{query}').status_code == 422


def test_usp_endpoint_when_cohort_is_empty_returns_no_items(client):
    body = client.get('/api/v1/usp?model=G60&country=ZZ&powertrain=all&origin=unknown').json()
    assert body['denominator'] == 0 and body['items'] == []


def test_usp_endpoint_when_model_has_no_option_list_leaves_features_uncosted(client):
    body = client.get('/api/v1/usp?model=G60&country=US&powertrain=all&origin=unknown').json()
    assert body['summary']['priced_options'] > 0
    body = client.get('/api/v1/usp?model=G68&country=all&powertrain=all&origin=all').json()
    assert body['summary']['priced_options'] == 0
    assert all(item['cost'] is None for item in body['items'])


def highway(session, cohort):
    return next(item for item in usp_evaluation(session, cohort, 0.4, 0.7).items if item.feature_id == 'highway-assistant')


def test_usp_evaluation_when_mapping_is_rejected_drops_that_record(session):
    cohort = Cohort(model='G60', country='US', powertrain='all', origin='unknown')
    before = highway(session, cohort).likes
    aspect = session.scalar(select(Aspect).join(Feedback, Feedback.id == Aspect.feedback_id).where(
        Aspect.feature_id == 'highway-assistant', Aspect.feedback_type == 'Likes', Feedback.model == 'G60',
        Feedback.country == 'US', Feedback.origin == 'unknown').limit(1))
    aspect.mapping_status = 'rejected'
    session.flush()
    assert highway(session, cohort).likes == before - 1


def test_usp_evaluation_when_price_is_bracketed_treats_it_as_net(session):
    cohort = Cohort(model='G60', country='US', powertrain='all', origin='unknown')
    for fact in session.scalars(select(Fact).where(Fact.model == 'G60', Fact.label == 'Autobahnassistent')):
        fact.conditions = {**fact.conditions, 'raw_price': '[850,–]'}
    session.flush()
    assert highway(session, cohort).cost.net_price_median == pytest.approx(850.0)
