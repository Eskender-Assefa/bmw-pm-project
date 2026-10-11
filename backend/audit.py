import hashlib
import json
from sqlalchemy import select
from .models import AuditEvent, now

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def append_event(session, actor, action, entity_id, payload):
    previous = session.scalar(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1))
    data = {'timestamp': now(), 'actor': actor, 'action': action, 'entity_id': entity_id, 'payload': payload,
            'previous_hash': previous.event_hash if previous else '0' * 64}
    record = AuditEvent(**data, event_hash=digest(data))
    session.add(record)
    session.flush()
    return record

def verify_audit(session):
    previous = '0' * 64
    events = session.scalars(select(AuditEvent).order_by(AuditEvent.seq)).all()
    for event in events:
        data = {key: getattr(event, key) for key in ('timestamp', 'actor', 'action', 'entity_id', 'payload', 'previous_hash')}
        if event.previous_hash != previous or digest(data) != event.event_hash:
            return {'valid': False, 'events': len(events), 'broken_at': event.seq}
        previous = event.event_hash
    return {'valid': True, 'events': len(events), 'head': previous, 'limitation': 'Application append-only history. Not external immutable storage.'}
