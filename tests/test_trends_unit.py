"""Trend register rules. No database is needed, so the seed backup is skipped."""
import json

import pytest
from pydantic import ValidationError

from backend.config import ROOT
from backend.taxonomy import CATEGORIES, TAG_MAP
from backend.trends import (EUROPE, HORIZONS, MARKETS, TrendRecord, customer_signal, load_register, market_for_country,
                            relevant_to_cohort, suggested_stance)


@pytest.fixture(autouse=True)
def isolated_database():
    yield


def record(**changes):
    base = {'id': 'sample', 'title': 'Sample', 'summary': 'Summary.', 'categories': ['C07'], 'horizon': 'now',
            'markets': ['Europe'], 'powertrains': ['BEV'], 'features': [],
            'sources': [{'title': 'Source', 'publisher': 'Publisher', 'url': 'https://example.org/a', 'published': None}]}
    return TrendRecord(**{**base, **changes})


def test_load_register_every_trend_is_classified_and_cited():
    register = load_register()
    assert len(register.trends) >= 15
    assert len({trend.id for trend in register.trends}) == len(register.trends)
    for trend in register.trends:
        assert trend.categories and set(trend.categories) <= set(CATEGORIES)
        assert trend.horizon in HORIZONS
        assert trend.markets and set(trend.markets) <= set(MARKETS)
        assert trend.sources and all(source.url.startswith('https://') for source in trend.sources)
        assert all(feature.casefold() in TAG_MAP for feature in trend.features)


def test_load_register_is_marked_unreviewed_web_evidence():
    register = load_register()
    assert register.origin == 'observed' and register.review_status == 'pending'
    assert 'not been verified' in register.notice


def test_register_file_is_valid_json_with_one_register():
    data = json.loads((ROOT / 'fixtures' / 'market-trends.json').read_text(encoding='utf-8'))
    assert set(data) >= {'id', 'version', 'collected_at', 'trends'}


@pytest.mark.parametrize('changes', [
    {'categories': ['C99']}, {'categories': []}, {'horizon': 'soon'}, {'markets': ['Mars']}, {'powertrains': ['Steam']},
    {'sources': []}, {'sources': [{'title': 'x', 'publisher': 'y', 'url': 'javascript:alert(1)', 'published': None}]},
    {'sources': [{'title': 'x', 'publisher': 'y', 'url': 'http://example.org', 'published': None}]},
    {'features': ['Flux capacitor']},
])
def test_trend_record_when_classification_or_source_is_invalid_is_rejected(changes):
    with pytest.raises(ValidationError):
        record(**changes)


@pytest.mark.parametrize('country,market', [('US', 'US'), ('DE', 'Europe'), ('GB', 'Europe'), ('CN', 'China'), ('JP', None), ('all', None)])
def test_market_for_country_maps_feedback_country_to_trend_market(country, market):
    assert market_for_country(country) == market
    assert 'NO' in EUROPE


@pytest.mark.parametrize('likes,complaints,expected', [
    (0, 0, 'silent'), (120, 10, 'praised'), (10, 120, 'criticised'), (20, 22, 'mixed'), (3, 0, 'mixed'),
])
def test_customer_signal_requires_a_reliable_difference(likes, complaints, expected):
    assert customer_signal(likes, complaints, 3000, linked=True) == expected


def test_customer_signal_when_no_feature_is_linked_is_not_linked():
    assert customer_signal(0, 0, 3000, linked=False) == 'not_linked'


def test_customer_signal_when_cohort_is_empty_is_silent():
    assert customer_signal(0, 0, 0, linked=True) == 'silent'


@pytest.mark.parametrize('signal,horizon,stance', [
    ('criticised', 'now', 'Close the gap'), ('criticised', 'next', 'Plan a response'), ('criticised', 'later', 'Plan a response'),
    ('praised', 'now', 'Defend the strength'), ('praised', 'later', 'Extend the lead'), ('mixed', 'now', 'Investigate'),
    ('silent', 'now', 'Check exposure'), ('silent', 'later', 'Watch'), ('not_linked', 'now', 'Check exposure'),
    ('not_linked', 'next', 'Watch'),
])
def test_suggested_stance_follows_signal_and_horizon(signal, horizon, stance):
    assert suggested_stance(signal, horizon) == stance


@pytest.mark.parametrize('country,powertrain,markets,powertrains,expected', [
    ('US', 'all', ['US'], ['BEV'], True), ('US', 'BEV', ['Europe'], ['BEV'], False), ('US', 'ICE', ['US'], ['BEV'], False),
    ('JP', 'all', ['Global'], ['BEV'], True), ('JP', 'all', ['Europe'], ['BEV'], False), ('all', 'all', ['China'], ['PHEV'], True),
    ('DE', 'PHEV', ['Europe', 'China'], ['PHEV', 'BEV'], True),
])
def test_relevant_to_cohort_matches_market_and_powertrain(country, powertrain, markets, powertrains, expected):
    assert relevant_to_cohort(record(markets=markets, powertrains=powertrains), country, powertrain) is expected
