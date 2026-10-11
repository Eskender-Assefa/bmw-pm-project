"""Pure USP and cost-estimate logic. No database is needed, so the seed backup is skipped."""
import pytest

from backend.taxonomy import TAG_MAP
from backend.usp import (OPTION_FEATURE_LINKS, VAT_RATE, efficient_frontier, estimate_cost, link_option, net_price,
                         usp_score, wilson_interval)


@pytest.fixture(autouse=True)
def isolated_database():
    yield


def test_wilson_interval_when_no_observations_returns_full_uncertainty():
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_wilson_interval_when_half_of_hundred_matches_published_value():
    lower, upper = wilson_interval(50, 100)
    assert lower == pytest.approx(0.4038, abs=1e-4)
    assert upper == pytest.approx(0.5962, abs=1e-4)


def test_wilson_interval_when_all_succeed_keeps_upper_bound_at_one():
    lower, upper = wilson_interval(10, 10)
    assert lower == pytest.approx(0.7225, abs=1e-4)
    assert upper == pytest.approx(1.0)


def test_wilson_interval_when_none_succeed_keeps_lower_bound_at_zero():
    lower, upper = wilson_interval(0, 10)
    assert lower == pytest.approx(0.0)
    assert upper == pytest.approx(0.2775, abs=1e-4)


@pytest.mark.parametrize('successes,total', [(-1, 10), (11, 10), (1, -1)])
def test_wilson_interval_when_counts_are_impossible_raises(successes, total):
    with pytest.raises(ValueError):
        wilson_interval(successes, total)


def test_usp_score_when_praise_clearly_exceeds_complaints_is_positive():
    score = usp_score(likes=300, complaints=20, denominator=3000)
    assert score.praise_share == pytest.approx(0.1)
    assert score.praise_lower < 0.1 < score.complaint_upper + 0.1
    assert score.score == pytest.approx(score.praise_lower - score.complaint_upper)
    assert score.score > 0


def test_usp_score_when_sample_is_tiny_does_not_reward_a_lucky_ratio():
    small = usp_score(likes=3, complaints=0, denominator=10)
    large = usp_score(likes=300, complaints=0, denominator=1000)
    assert small.praise_share == large.praise_share
    assert small.score < large.score


def test_usp_score_when_complaints_dominate_is_negative():
    assert usp_score(likes=5, complaints=80, denominator=1000).score < 0


def test_usp_score_when_cohort_is_empty_has_no_score():
    score = usp_score(likes=0, complaints=0, denominator=0)
    assert score.score is None and score.praise_share is None


def test_net_price_when_printed_price_includes_vat_removes_it():
    assert net_price(1190.0, '1.190,–') == pytest.approx(1000.0)


def test_net_price_when_printed_price_is_bracketed_is_already_net():
    assert net_price(941.18, '[941,18]') == pytest.approx(941.18)


def test_estimate_cost_when_one_option_applies_ratio_band():
    cost = estimate_cost([1000.0], ratio_low=0.4, ratio_high=0.7)
    assert (cost.low, cost.mid, cost.high) == pytest.approx((400.0, 550.0, 700.0))


def test_estimate_cost_when_several_options_spans_cheapest_to_dearest():
    cost = estimate_cost([500.0, 1000.0, 4000.0], ratio_low=0.4, ratio_high=0.7)
    assert cost.low == pytest.approx(200.0)
    assert cost.mid == pytest.approx(550.0)
    assert cost.high == pytest.approx(2800.0)
    assert cost.net_price_median == pytest.approx(1000.0)


def test_estimate_cost_when_no_priced_option_is_none():
    assert estimate_cost([], ratio_low=0.4, ratio_high=0.7) is None


@pytest.mark.parametrize('label,feature', [
    ('Autobahnassistent', 'Highway assistant'),
    ('Autobahn- & City-Assistent (laufzeitbegrenzt)1,2', 'Highway assistant'),
    ('Driving Assistant Professional', 'Driver assistance, automated driving, overall technology'),
    ('Bowers & Wilkins Surround Sound System', 'Audio mode, sound'),
    ('Lenkradheizung', 'Heated steering wheel'),
    ('M Lederlenkrad', 'Steering wheel'),
    ('Sitzverstellung, elektrisch, mit Memory', 'Seat memory'),
    ('Komfortsitze vorn, elektrisch verstellbar', 'Seats'),
    ('Adaptives Fahrwerk Professional', 'Cushioning / damping vehicle'),
    ('19" Aerodynamikräder 934 Bicolor', 'Wheels / tires'),
    ('Panorama Glasdach inkl. Dachlackierung in Schwarz Hochglanz', 'Panorama glass roof'),
])
def test_link_option_when_title_names_a_feature_returns_that_feature(label, feature):
    assert link_option(label) == feature


@pytest.mark.parametrize('label', ['COMFORT PAKET', 'M SPORTPAKET PRO', 'BMW Individual Tansanitblau metallic', 'Alpinweiß', ''])
def test_link_option_when_title_is_a_bundle_or_paint_returns_none(label):
    assert link_option(label) is None


def test_option_feature_links_only_name_features_in_the_taxonomy():
    assert all(feature.casefold() in TAG_MAP for _, feature in OPTION_FEATURE_LINKS)


def test_efficient_frontier_keeps_only_undominated_points():
    points = [('cheap-good', 100.0, 0.05), ('cheap-poor', 120.0, 0.01), ('dear-best', 900.0, 0.09), ('dear-poor', 950.0, 0.02)]
    assert efficient_frontier(points) == ['cheap-good', 'dear-best']


def test_efficient_frontier_when_costs_tie_keeps_the_higher_score():
    assert efficient_frontier([('a', 100.0, 0.02), ('b', 100.0, 0.04)]) == ['b']


def test_efficient_frontier_when_empty_is_empty():
    assert efficient_frontier([]) == []


def test_vat_rate_is_german_standard_rate():
    assert VAT_RATE == 0.19
