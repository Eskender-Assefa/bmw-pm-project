"""Unique selling points and what they may cost to build.

A USP here is a feature that a cohort praises more often than it criticises, judged conservatively: the lower
confidence bound of the praise share minus the upper bound of the complaint share. Cost is not in the supplied
sources. It is estimated from printed German option prices under an explicit, adjustable cost-ratio assumption.
"""
import math
from collections import defaultdict
from dataclasses import dataclass
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Aspect, Fact, Feature, Feedback
from .schemas import Cohort, UspAssumptions, UspCost, UspItem, UspOption, UspResponse, UspSummary
from .services import UNMET, cohort_query
from .taxonomy import feature_slug

USP_VERSION = 'usp-v1.0'
VAT_RATE = 0.19
DEFAULT_COST_RATIO_LOW = 0.40
DEFAULT_COST_RATIO_HIGH = 0.70
Z_95 = 1.959964
EXCLUDED_MAPPINGS = ('rejected', 'pending')
ASSUMPTION_NOTICE = ('Estimate, not BMW cost data. Cost is the printed German option price without VAT multiplied by an '
                     'assumed cost ratio. German prices do not establish equipment or pricing in other markets, and '
                     'features without a separately priced option have no estimate.')

# Explicit German option-title keywords, first match wins. Bundles and paints are deliberately absent: a package
# price cannot be attributed to one feature.
OPTION_FEATURE_LINKS = (
    ('autobahn', 'Highway assistant'),
    ('driving assistant', 'Driver assistance, automated driving, overall technology'),
    ('parking assistant', 'Parking Assistant'),
    ('bowers', 'Audio mode, sound'),
    ('harman', 'Audio mode, sound'),
    ('lenkradheizung', 'Heated steering wheel'),
    ('lenkrad', 'Steering wheel'),
    ('standheizung', 'Auxiliary heater function'),
    ('sitzverstellung', 'Seat memory'),
    ('komfortsitze', 'Seats'),
    ('sportsitze', 'Seats'),
    ('aktivsitz', 'Seats'),
    ('glasdach', 'Panorama glass roof'),
    ('fahrwerk', 'Cushioning / damping vehicle'),
    ('chassis control', 'Cushioning / damping vehicle'),
    ('räder', 'Wheels / tires'),
    ('ac-laden', 'Charge high-voltage battery'),
    ('ladekabel', 'Charging cable'),
    ('anhängerkupplung', 'Trailer, use'),
    ('automatiktüren', 'Automatic doors'),
    ('heckklappe', 'Trunk lid'),
    ('sonnenschutz', 'Sun protection'),
    ('scheinwerfer', 'Exterior lighting'),
    ('interieurleisten', 'Upholstery / interior trim'),
    ('dachhimmel', 'Upholstery / interior trim'),
    ('sicherheitsgurte', 'Seat belts'),
)
BUNDLE_MARKERS = ('paket',)


@dataclass(frozen=True)
class Score:
    praise_share: float | None
    praise_lower: float | None
    complaint_share: float | None
    complaint_upper: float | None
    score: float | None


@dataclass(frozen=True)
class Cost:
    net_price_min: float
    net_price_median: float
    net_price_max: float
    low: float
    mid: float
    high: float


def wilson_interval(successes: int, total: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for a proportion. Stays inside [0, 1] and behaves at small samples."""
    if total < 0 or successes < 0 or successes > total:
        raise ValueError('Counts must satisfy 0 <= successes <= total.')
    if total == 0:
        return 0.0, 1.0
    share = successes / total
    denominator = 1 + z * z / total
    centre = (share + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(share * (1 - share) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def usp_score(likes: int, complaints: int, denominator: int) -> Score:
    if denominator == 0:
        return Score(None, None, None, None, None)
    praise_lower, _ = wilson_interval(likes, denominator)
    _, complaint_upper = wilson_interval(complaints, denominator)
    return Score(likes / denominator, praise_lower, complaints / denominator, complaint_upper, praise_lower - complaint_upper)


def link_option(label: str) -> str | None:
    title = label.casefold()
    if any(marker in title for marker in BUNDLE_MARKERS):
        return None
    return next((feature for keyword, feature in OPTION_FEATURE_LINKS if keyword in title), None)


def net_price(printed: float, raw_price: str) -> float:
    # The price lists print net prices in square brackets beside some gross prices.
    return printed if raw_price.strip().startswith('[') else printed / (1 + VAT_RATE)


def estimate_cost(net_prices: list[float], ratio_low: float, ratio_high: float) -> Cost | None:
    if not net_prices:
        return None
    lowest, middle, highest = min(net_prices), median(net_prices), max(net_prices)
    return Cost(lowest, middle, highest, lowest * ratio_low, middle * (ratio_low + ratio_high) / 2, highest * ratio_high)


def efficient_frontier(points: list[tuple[str, float, float]]) -> list[str]:
    """Identifiers of (id, cost, score) points that no cheaper-or-equal point beats on score."""
    frontier, best = [], -math.inf
    for identifier, _, score in sorted(points, key=lambda point: (point[1], -point[2])):
        if score > best:
            frontier.append(identifier)
            best = score
    return frontier


def priced_options(session: Session, model: str) -> dict[str, list[UspOption]]:
    """Distinct priced options of a model, grouped by the feature their title names."""
    rows = session.execute(select(Fact.label, Fact.conditions, Fact.evidence_id).where(
        Fact.model == model, Fact.evidence_kind == 'published_specification').order_by(Fact.label, Fact.evidence_id))
    grouped, seen = defaultdict(list), set()
    for label, conditions, evidence_id in rows:
        printed, code = conditions.get('price_eur_including_vat'), conditions.get('option_code')
        feature = link_option(label)
        if not printed or not code or not feature or (code, label, printed) in seen:
            continue
        seen.add((code, label, printed))
        grouped[feature_slug(feature)].append(UspOption(
            option_code=code, label=label, price_eur_including_vat=printed,
            net_price_eur=net_price(printed, conditions.get('raw_price') or ''), evidence_id=evidence_id))
    return grouped


def feature_records(session: Session, cohort: Cohort) -> tuple[int, dict[str, set[str]], dict[str, set[str]]]:
    """Cohort size, and per feature the distinct records that praise it and that report an unmet need."""
    cohort_ids = cohort_query(cohort).with_only_columns(Feedback.id)
    denominator = len(session.scalars(cohort_ids).all())
    rows = session.execute(select(Aspect.feature_id, Aspect.feedback_type, Aspect.feedback_id).where(
        Aspect.feedback_id.in_(cohort_ids), Aspect.mapping_status.not_in(EXCLUDED_MAPPINGS)))
    likes, complaints = defaultdict(set), defaultdict(set)
    for feature_id, feedback_type, feedback_id in rows:
        if feedback_type == 'Likes':
            likes[feature_id].add(feedback_id)
        elif feedback_type in UNMET:
            complaints[feature_id].add(feedback_id)
    return denominator, likes, complaints


def build_item(feature: Feature, likes: int, complaints: int, denominator: int, options: list[UspOption],
               ratio_low: float, ratio_high: float) -> UspItem:
    score = usp_score(likes, complaints, denominator)
    cost = estimate_cost([option.net_price_eur for option in options], ratio_low, ratio_high)
    return UspItem(
        feature_id=feature.id, feature=feature.name, category=feature.category, likes=likes, complaints=complaints,
        praise_share=score.praise_share, praise_lower=score.praise_lower, complaint_share=score.complaint_share,
        complaint_upper=score.complaint_upper, score=score.score, is_usp=score.score > 0,
        cost=UspCost(options=options, **cost.__dict__) if cost else None,
        efficiency=score.score * 100 / (cost.mid / 100) if cost else None, on_frontier=False)


def usp_evaluation(session: Session, cohort: Cohort, ratio_low: float, ratio_high: float) -> UspResponse:
    denominator, likes, complaints = feature_records(session, cohort)
    options = priced_options(session, cohort.model)
    assumptions = UspAssumptions(cost_basis='estimate', vat_rate=VAT_RATE, cost_ratio_low=ratio_low,
                                 cost_ratio_high=ratio_high, confidence_level=0.95, notice=ASSUMPTION_NOTICE)
    feature_ids = set(likes) | set(complaints) if denominator else set()
    features = session.scalars(select(Feature).where(Feature.id.in_(feature_ids))).all()
    drafts = [build_item(feature, len(likes[feature.id]), len(complaints[feature.id]), denominator,
                         options.get(feature.id, []), ratio_low, ratio_high) for feature in features]
    frontier = set(efficient_frontier([(item.feature_id, item.cost.mid, item.score) for item in drafts if item.cost]))
    items = sorted((item.model_copy(update={'on_frontier': item.feature_id in frontier}) for item in drafts),
                   key=lambda item: (-item.score, item.feature_id))
    summary = UspSummary(usps=sum(item.is_usp for item in items), costed_features=sum(item.cost is not None for item in items),
                         costed_usps=sum(item.is_usp and item.cost is not None for item in items),
                         priced_options=sum(len(group) for group in options.values()))
    return UspResponse(cohort=cohort, denominator=denominator, assumptions=assumptions, summary=summary, items=items,
                       usp_version=USP_VERSION)
