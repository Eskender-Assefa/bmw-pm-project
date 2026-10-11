"""Global market and technology trends, classified by target and set against the cohort's own feedback.

The register is a reviewed-by-hand fixture of cited public reporting, never generated text. Each trend carries a
product category, a time horizon, the markets and powertrains it concerns, and the taxonomy features it touches. The
customer signal says whether the selected cohort reliably praises or criticises those features.
"""
import json
from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from .config import ROOT
from .schemas import Cohort
from .taxonomy import CATEGORIES, TAG_MAP, feature_slug
from .usp import feature_records, wilson_interval

TRENDS_VERSION = 'trends-v1.0'
REGISTER_PATH = ROOT / 'fixtures' / 'market-trends.json'
HORIZONS = ('now', 'next', 'later')
MARKETS = ('US', 'Europe', 'China', 'Global')
EUROPE = frozenset({'AT', 'BE', 'CH', 'CZ', 'DE', 'DK', 'ES', 'FI', 'FR', 'GB', 'IE', 'IT', 'LV', 'NL', 'NO', 'PL', 'PT', 'SE'})
Horizon = Literal['now', 'next', 'later']
Market = Literal['US', 'Europe', 'China', 'Global']
Powertrain = Literal['ICE', 'PHEV', 'BEV']
Signal = Literal['praised', 'criticised', 'mixed', 'silent', 'not_linked']
STANCES = {
    ('criticised', True): 'Close the gap', ('criticised', False): 'Plan a response',
    ('praised', True): 'Defend the strength', ('praised', False): 'Extend the lead',
    ('mixed', True): 'Investigate', ('mixed', False): 'Investigate',
    ('silent', True): 'Check exposure', ('silent', False): 'Watch',
    ('not_linked', True): 'Check exposure', ('not_linked', False): 'Watch',
}


class TrendSource(BaseModel):
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    url: str
    published: str | None

    @field_validator('url')
    @classmethod
    def https_only(cls, value: str) -> str:
        if not value.startswith('https://'):
            raise ValueError('Trend sources must be https links.')
        return value


class TrendRecord(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    categories: list[str] = Field(min_length=1)
    horizon: Horizon
    markets: list[Market] = Field(min_length=1)
    powertrains: list[Powertrain] = Field(min_length=1)
    features: list[str]
    sources: list[TrendSource] = Field(min_length=1)

    @field_validator('categories')
    @classmethod
    def known_categories(cls, value: list[str]) -> list[str]:
        if unknown := [category for category in value if category not in CATEGORIES]:
            raise ValueError(f'Unknown categories: {unknown}')
        return value

    @field_validator('features')
    @classmethod
    def known_features(cls, value: list[str]) -> list[str]:
        if unknown := [feature for feature in value if feature.casefold() not in TAG_MAP]:
            raise ValueError(f'Features outside the taxonomy: {unknown}')
        return value


class TrendRegister(BaseModel):
    id: str
    version: str
    title: str
    origin: Literal['observed']
    review_status: Literal['pending', 'reviewed']
    collected_at: str
    generator: str
    notice: str
    trends: list[TrendRecord]


class RegisterInfo(BaseModel):
    id: str
    version: str
    origin: str
    review_status: str
    collected_at: str
    generator: str
    notice: str


class CustomerSignal(BaseModel):
    signal: Signal
    likes: int
    complaints: int
    features: list[str]


class TrendView(TrendRecord):
    customer: CustomerSignal
    stance: str
    relevant_to_cohort: bool


class TrendSummary(BaseModel):
    total: int
    relevant: int
    by_horizon: dict[str, int]
    by_category: dict[str, int]
    by_signal: dict[str, int]


class TrendResponse(BaseModel):
    cohort: Cohort
    denominator: int
    provenance: RegisterInfo
    summary: TrendSummary
    trends: list[TrendView]
    trends_version: str


def load_register() -> TrendRegister:
    return TrendRegister.model_validate(json.loads(REGISTER_PATH.read_text(encoding='utf-8')))


def market_for_country(country: str) -> str | None:
    if country == 'US':
        return 'US'
    if country == 'CN':
        return 'China'
    return 'Europe' if country in EUROPE else None


def relevant_to_cohort(trend: TrendRecord, country: str, powertrain: str) -> bool:
    market = market_for_country(country)
    market_match = country == 'all' or 'Global' in trend.markets or (market is not None and market in trend.markets)
    return market_match and (powertrain == 'all' or powertrain in trend.powertrains)


def customer_signal(likes: int, complaints: int, denominator: int, linked: bool) -> Signal:
    """Praised or criticised only when one share's lower bound clears the other's upper bound."""
    if not linked:
        return 'not_linked'
    if denominator == 0 or likes + complaints == 0:
        return 'silent'
    praise_lower, praise_upper = wilson_interval(likes, denominator)
    complaint_lower, complaint_upper = wilson_interval(complaints, denominator)
    if praise_lower > complaint_upper:
        return 'praised'
    return 'criticised' if complaint_lower > praise_upper else 'mixed'


def suggested_stance(signal: Signal, horizon: Horizon) -> str:
    return STANCES[(signal, horizon == 'now')]


def view(trend: TrendRecord, cohort: Cohort, denominator: int, likes: dict[str, set[str]],
         complaints: dict[str, set[str]]) -> TrendView:
    slugs = [feature_slug(feature) for feature in trend.features]
    liked = set().union(*(likes.get(slug, set()) for slug in slugs))
    criticised = set().union(*(complaints.get(slug, set()) for slug in slugs))
    signal = customer_signal(len(liked), len(criticised), denominator, linked=bool(slugs))
    return TrendView(**trend.model_dump(), stance=suggested_stance(signal, trend.horizon),
                     relevant_to_cohort=relevant_to_cohort(trend, cohort.country, cohort.powertrain),
                     customer=CustomerSignal(signal=signal, likes=len(liked), complaints=len(criticised), features=trend.features))


def trend_evaluation(session: Session, cohort: Cohort, category: str | None = None, horizon: str | None = None,
                     market: str | None = None) -> TrendResponse:
    register = load_register()
    denominator, likes, complaints = feature_records(session, cohort)
    selected = [trend for trend in register.trends
                if (not category or category in trend.categories) and (not horizon or trend.horizon == horizon)
                and (not market or market in trend.markets)]
    views = sorted((view(trend, cohort, denominator, likes, complaints) for trend in selected),
                   key=lambda item: (HORIZONS.index(item.horizon), not item.relevant_to_cohort, item.id))
    summary = TrendSummary(
        total=len(views), relevant=sum(item.relevant_to_cohort for item in views),
        by_horizon={name: sum(item.horizon == name for item in views) for name in HORIZONS},
        by_category=dict(sorted(Counter(code for item in views for code in item.categories).items())),
        by_signal=dict(sorted(Counter(item.customer.signal for item in views).items())))
    return TrendResponse(cohort=cohort, denominator=denominator, provenance=RegisterInfo(**register.model_dump(exclude={'trends', 'title'})),
                         summary=summary, trends=views, trends_version=TRENDS_VERSION)
