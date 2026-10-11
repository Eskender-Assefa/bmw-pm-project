"""Read-only customer comment register; each result is a source-scoped feedback ID."""
from sqlalchemy import select, func
from .models import Feedback, Source, Aspect, Feature, EvidenceRef
from .services import cohort_query


def list_feedback(db, cohort, q='', category='', source_id='', offset=0, limit=20):
    query = cohort_query(cohort)
    if q.strip():
        term = q.strip()
        query = query.where(Feedback.text.contains(term, autoescape=True) |
                            Feedback.external_id.contains(term, autoescape=True))
    if category:
        matching = select(Aspect.id).join(Feature, Aspect.feature_id == Feature.id).where(
            Aspect.feedback_id == Feedback.id, Feature.category == category).exists()
        query = query.where(matching)
    if source_id:
        query = query.where(Feedback.source_id == source_id)
    matched = query.subquery()
    total = db.scalar(select(func.count()).select_from(matched))
    source_count = db.scalar(select(func.count(func.distinct(matched.c.source_id))))
    critical = select(Aspect.id).where(Aspect.feedback_id == matched.c.id, Aspect.critical == True).exists()
    critical_count = db.scalar(select(func.count()).select_from(matched).where(critical))
    records = db.scalars(query.order_by(Feedback.external_id, Feedback.id).offset(offset).limit(limit)).all()
    if not records:
        return {'items': [], 'total': total, 'source_count': source_count, 'critical_count': critical_count}
    sources = {s.id: s for s in db.scalars(select(Source).where(Source.id.in_({r.source_id for r in records})))}
    aspects = {}
    for aspect, feature in db.execute(select(Aspect, Feature).join(Feature, Aspect.feature_id == Feature.id)
                                      .where(Aspect.feedback_id.in_([r.id for r in records])).order_by(Feature.category, Feature.name, Aspect.id)):
        aspects.setdefault(aspect.feedback_id, []).append({
            'feature': feature.name, 'category': feature.category, 'type': aspect.feedback_type,
            'status': aspect.mapping_status, 'critical': aspect.critical, 'evidence_id': aspect.evidence_id})
    evidence_ids = {tag['evidence_id'] for r in records for tag in r.tags if isinstance(tag, dict) and tag.get('evidence_id')}
    evidence_ids.update(a['evidence_id'] for rows in aspects.values() for a in rows)
    refs = {e.id: e for e in db.scalars(select(EvidenceRef).where(EvidenceRef.id.in_(evidence_ids)))}
    items = []
    for record in records:
        mappings = aspects.get(record.id, [])
        candidates = [tag.get('evidence_id') for tag in record.tags if isinstance(tag, dict)]
        candidates.extend(a['evidence_id'] for a in mappings)
        ref = next((refs[eid] for eid in candidates if eid in refs and refs[eid].source_id == record.source_id), None)
        items.append({
            'id': record.id, 'external_id': record.external_id, 'text': record.text,
            'model': record.model, 'country': record.country, 'powertrain': record.powertrain,
            'origin': record.origin, 'source_date': record.source_date, 'source_label': record.source_label,
            'source_id': record.source_id, 'filename': sources[record.source_id].filename,
            'duplicate_text': record.duplicate_text, 'aspects': mappings,
            'evidence_id': ref.id if ref else None, 'locator': ref.locator if ref else None,
        })
    return {'items': items, 'total': total, 'source_count': source_count, 'critical_count': critical_count}
