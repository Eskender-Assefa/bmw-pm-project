"""Successor brief: what the next generation should keep, fix and lead on.

Keep proposals are the cohort's unique selling points. Fix proposals are existing requirements whose feature the
cohort reliably criticises. Lead proposals are market trends that touch features the cohort already criticises; they
are forward-looking assumptions and carry their sources. Keep and Lead reviews are appended to the audit chain; Fix
proposals are reviewed as requirements.
"""
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .audit import append_event
from .models import AuditEvent
from .schemas import Cohort, RequirementView, UspItem
from .services import ranking
from .trends import TrendSource, TrendView, trend_evaluation
from .usp import DEFAULT_COST_RATIO_HIGH, DEFAULT_COST_RATIO_LOW, usp_evaluation, wilson_interval

SUCCESSOR_VERSION = 'successor-v1.0'
REVIEW_EVENT = 'successor.reviewed'
MIN_RATIONALE = 5
STATUS = {'accept': 'accepted', 'reject': 'rejected', 'defer': 'deferred'}
Kind = Literal['keep', 'fix', 'lead']


class Review(BaseModel):
    status: str
    actor: str | None = None
    rationale: str | None = None
    reviewed_at: str | None = None


class Proposal(BaseModel):
    id: str
    kind: Kind
    basis: Literal['evidence', 'assumption']
    title: str
    statement: str
    categories: list[str]
    likes: int
    complaints: int
    denominator: int
    feature_id: str | None = None
    requirement_id: str | None = None
    trend_id: str | None = None
    horizon: str | None = None
    sources: list[TrendSource] = []
    conflicts: list[str] = []
    review: Review = Review(status='proposed')


class SuccessorSummary(BaseModel):
    keep: int
    fix: int
    lead: int
    evidence_based: int
    assumption_based: int
    with_conflicts: int
    reviewed: int


class SuccessorResponse(BaseModel):
    cohort: Cohort
    denominator: int
    summary: SuccessorSummary
    proposals: list[Proposal]
    notice: str
    successor_version: str


class SuccessorReviewRequest(BaseModel):
    cohort: Cohort
    action: Literal['accept', 'reject', 'defer']
    actor: str = Field(default='Demo PM', min_length=1, max_length=100)
    rationale: str = Field(default='', max_length=4000)


def reliably_criticised(likes: int, complaints: int, denominator: int) -> bool:
    if denominator == 0:
        return False
    return wilson_interval(complaints, denominator)[0] > wilson_interval(likes, denominator)[1]


def keep_proposal(item: UspItem, cohort: Cohort, denominator: int) -> Proposal:
    conflicts = [f'{item.complaints} records also report an unmet need on this feature.'] if item.complaints else []
    return Proposal(
        id=f'keep:{cohort.model}:{item.feature_id}', kind='keep', basis='evidence', title=f'Preserve {item.feature}',
        statement=f'The successor must not fall behind today on {item.feature}: {item.likes} of {denominator} records praise it.',
        categories=[item.category], likes=item.likes, complaints=item.complaints, denominator=denominator,
        feature_id=item.feature_id, conflicts=conflicts)


def fix_proposal(requirement: RequirementView, complaints: int) -> Proposal:
    return Proposal(
        id=f'fix:{requirement.id}', kind='fix', basis='evidence', title=requirement.title, statement=requirement.description,
        categories=[requirement.category], likes=requirement.likes, complaints=complaints, denominator=requirement.denominator,
        feature_id=requirement.feature_id, requirement_id=requirement.id, conflicts=requirement.conflicts,
        review=Review(status=requirement.status))


def lead_proposal(trend: TrendView, cohort: Cohort, denominator: int, strengths: dict[str, str]) -> Proposal:
    conflicts = [f'Touches a strength customers praise: {name}.' for name in trend.features if name in strengths.values()]
    if not trend.relevant_to_cohort:
        conflicts.append(f"The sources concern {', '.join(trend.markets)} and {', '.join(trend.powertrains)}; "
                         'this cohort is outside that market or powertrain.')
    return Proposal(
        id=f'lead:{cohort.model}:{trend.id}', kind='lead', basis='assumption', title=trend.title,
        statement=(f'Forward-looking assumption: {trend.summary} In this cohort {trend.customer.complaints} records already '
                   f"criticise {', '.join(trend.features)}."),
        categories=trend.categories, likes=trend.customer.likes, complaints=trend.customer.complaints, denominator=denominator,
        trend_id=trend.id, horizon=trend.horizon, sources=trend.sources, conflicts=conflicts)


def latest_reviews(session: Session, cohort: Cohort) -> dict[str, Review]:
    events = session.scalars(select(AuditEvent).where(AuditEvent.action == REVIEW_EVENT).order_by(AuditEvent.seq))
    return {event.entity_id: Review(status=event.payload['status'], actor=event.actor, rationale=event.payload['rationale'],
                                    reviewed_at=event.timestamp)
            for event in events if event.payload['cohort'] == cohort.model_dump()}


def build_proposals(session: Session, cohort: Cohort) -> tuple[int, list[Proposal]]:
    usps = usp_evaluation(session, cohort, DEFAULT_COST_RATIO_LOW, DEFAULT_COST_RATIO_HIGH)
    denominator = usps.denominator
    by_feature = {item.feature_id: item for item in usps.items}
    strengths = {item.feature_id: item.feature for item in usps.items if item.is_usp}
    keep = [keep_proposal(item, cohort, denominator) for item in usps.items if item.is_usp]
    fix = [fix_proposal(requirement, by_feature[requirement.feature_id].complaints)
           for requirement in ranking(session, cohort).requirements
           if requirement.feature_id in by_feature and reliably_criticised(
               by_feature[requirement.feature_id].likes, by_feature[requirement.feature_id].complaints, denominator)]
    lead = [lead_proposal(trend, cohort, denominator, strengths)
            for trend in trend_evaluation(session, cohort).trends if trend.customer.signal == 'criticised']
    return denominator, keep + sorted(fix, key=lambda proposal: -proposal.complaints) + lead


def successor_brief(session: Session, cohort: Cohort) -> SuccessorResponse:
    denominator, drafts = build_proposals(session, cohort)
    reviews = latest_reviews(session, cohort)
    proposals = [draft.model_copy(update={'review': reviews[draft.id]}) if draft.id in reviews else draft for draft in drafts]
    summary = SuccessorSummary(
        keep=sum(p.kind == 'keep' for p in proposals), fix=sum(p.kind == 'fix' for p in proposals),
        lead=sum(p.kind == 'lead' for p in proposals), evidence_based=sum(p.basis == 'evidence' for p in proposals),
        assumption_based=sum(p.basis == 'assumption' for p in proposals), with_conflicts=sum(bool(p.conflicts) for p in proposals),
        reviewed=sum(p.review.status != 'proposed' for p in proposals))
    return SuccessorResponse(
        cohort=cohort, denominator=denominator, summary=summary, proposals=proposals, successor_version=SUCCESSOR_VERSION,
        notice=('Keep and Fix rest on this cohort\'s feedback. Lead rests on public trend reporting that has not been verified '
                'against the original articles; treat it as an assumption until a product manager has checked the sources.'))


def review_proposal(session: Session, proposal_id: str, request: SuccessorReviewRequest) -> dict:
    if proposal_id.startswith('fix:'):
        raise HTTPException(409, 'Fix proposals are requirements. Review them in the requirement drawer.')
    rationale = request.rationale.strip()
    if request.action != 'accept' and len(rationale) < MIN_RATIONALE:
        raise HTTPException(422, 'A rationale of at least five characters is required to reject or defer.')
    session.execute(text('BEGIN IMMEDIATE'))
    proposal = next((item for item in build_proposals(session, request.cohort)[1] if item.id == proposal_id), None)
    if not proposal:
        raise HTTPException(404, 'Proposal not found in this cohort.')
    status = STATUS[request.action]
    append_event(session, request.actor, REVIEW_EVENT, proposal_id, {
        'status': status, 'rationale': rationale or 'Accepted against the attached evidence.', 'cohort': request.cohort.model_dump(),
        'proposal': proposal.model_dump(exclude={'review'})})
    session.commit()
    return {'id': proposal_id, 'status': status}
