"""Trend register served against a disposable backup of the imported sources."""
import pytest

G60_US = 'model=G60&country=US&powertrain=all&origin=unknown'


def by_id(body):
    return {trend['id']: trend for trend in body['trends']}


def test_trends_endpoint_returns_classified_register_with_customer_signal(client):
    response = client.get(f'/api/v1/trends?{G60_US}')
    assert response.status_code == 200
    body = response.json()
    assert body['denominator'] == 3610
    assert body['provenance']['review_status'] == 'pending' and body['provenance']['origin'] == 'observed'
    assert body['summary']['total'] == len(body['trends']) >= 15
    assert sum(body['summary']['by_horizon'].values()) == body['summary']['total']
    key = by_id(body)['digital-key']
    assert key['customer']['signal'] == 'criticised'
    assert key['customer']['complaints'] > key['customer']['likes']
    assert key['stance'] == 'Close the gap'
    assert key['relevant_to_cohort'] is True
    assert key['sources'][0]['url'].startswith('https://')
    assert by_id(body)['physical-controls-return']['relevant_to_cohort'] is False


def test_trends_endpoint_when_trend_has_no_linked_feature_reports_not_linked(client):
    trend = by_id(client.get(f'/api/v1/trends?{G60_US}').json())['battery-passport']
    assert trend['customer'] == {'signal': 'not_linked', 'likes': 0, 'complaints': 0, 'features': []}
    assert trend['stance'] == 'Watch'


def test_trends_endpoint_counts_each_record_once_across_linked_features(client):
    trend = by_id(client.get(f'/api/v1/trends?{G60_US}').json())['level-3-retreat']
    usp = {item['feature']: item for item in client.get(f'/api/v1/usp?{G60_US}').json()['items']}
    linked = [usp[name] for name in trend['customer']['features'] if name in usp]
    assert max(item['likes'] for item in linked) <= trend['customer']['likes'] <= sum(item['likes'] for item in linked)


@pytest.mark.parametrize('query,check', [
    ('category=C09', lambda trend: 'C09' in trend['categories']),
    ('horizon=later', lambda trend: trend['horizon'] == 'later'),
    ('market=China', lambda trend: 'China' in trend['markets']),
])
def test_trends_endpoint_filters_by_target(client, query, check):
    body = client.get(f'/api/v1/trends?{G60_US}&{query}').json()
    assert body['trends'] and all(check(trend) for trend in body['trends'])
    assert body['summary']['total'] == len(body['trends'])


def test_trends_endpoint_marks_relevance_from_cohort_market_and_powertrain(client):
    us = by_id(client.get(f'/api/v1/trends?{G60_US}').json())
    assert us['nacs-charging-port']['relevant_to_cohort'] is True
    ice = by_id(client.get('/api/v1/trends?model=G60&country=US&powertrain=ICE&origin=unknown').json())
    assert ice['nacs-charging-port']['relevant_to_cohort'] is False


@pytest.mark.parametrize('query', ['category=C99', 'horizon=soon', 'market=Mars'])
def test_trends_endpoint_when_filter_is_unknown_rejects_request(client, query):
    assert client.get(f'/api/v1/trends?{G60_US}&{query}').status_code == 422


def test_trends_endpoint_when_cohort_is_empty_still_lists_trends(client):
    body = client.get('/api/v1/trends?model=G60&country=ZZ&powertrain=all&origin=unknown').json()
    assert body['denominator'] == 0 and body['trends']
    assert all(trend['customer']['signal'] in ('silent', 'not_linked') for trend in body['trends'])
