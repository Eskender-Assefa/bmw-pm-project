from sqlalchemy import Column, String, Integer, Float, Boolean, Text, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone
import uuid

def uid():
    return uuid.uuid4().hex

def now():
    return datetime.now(timezone.utc).isoformat()

class Base(DeclarativeBase):
    pass


class RagChunk(Base):
    __tablename__ = 'rag_chunks'
    id = Column(String, primary_key=True)
    evidence_id = Column(String, ForeignKey('evidence.id'), nullable=False, index=True)
    source_id = Column(String, ForeignKey('sources.id'), nullable=False, index=True)
    model = Column(String, nullable=True, index=True)
    text = Column(Text, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    index_version = Column(String, nullable=False)
    assignments = Column(JSON, nullable=False, default=list)
    review_status = Column(String, nullable=False, default='pending', index=True)
    method = Column(String, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(String, nullable=False, default=now)


class RagRun(Base):
    __tablename__ = 'rag_runs'
    id = Column(String, primary_key=True, default=uid)
    kind = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    prompt_version = Column(String, nullable=False)
    inputs = Column(JSON, nullable=False)
    output = Column(JSON, nullable=False)
    created_at = Column(String, nullable=False, default=now)

class Source(Base):
    __tablename__ = 'sources'
    id = Column(String, primary_key=True, default=uid)
    filename = Column(String, nullable=False)
    checksum = Column(String, nullable=False, unique=True)
    format = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    origin = Column(String, nullable=False, default='unknown')
    language = Column(String, nullable=False, default='en')
    market = Column(String, nullable=True)
    source_date = Column(String, nullable=True)
    edition = Column(String, nullable=True)
    retrieved_at = Column(String, nullable=False, default=now)
    path = Column(String, nullable=False)
    extraction_version = Column(String, nullable=False)
    record_count = Column(Integer, nullable=False, default=0)
    row_count = Column(Integer, nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)

class EvidenceRef(Base):
    __tablename__ = 'evidence'
    id = Column(String, primary_key=True, default=uid)
    source_id = Column(String, ForeignKey('sources.id'), nullable=False, index=True)
    locator = Column(JSON, nullable=False)
    text = Column(Text, nullable=False)
    kind = Column(String, nullable=False)
    origin = Column(String, nullable=False, default='unknown')
    model = Column(String, nullable=True, index=True)

class Vehicle(Base):
    __tablename__ = 'vehicles'
    id = Column(String, primary_key=True)
    brand = Column(String, nullable=False, default='BMW')
    model = Column(String, nullable=False)
    name = Column(String, nullable=False)
    variant = Column(String, nullable=True)
    powertrain = Column(String, nullable=True)
    market = Column(String, nullable=True)
    aliases = Column(JSON, nullable=False, default=list)

class Category(Base):
    __tablename__ = 'categories'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)

class Feature(Base):
    __tablename__ = 'features'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, ForeignKey('categories.id'), nullable=False, index=True)
    secondary_tags = Column(JSON, nullable=False, default=list)
    taxonomy_version = Column(String, nullable=False, default='2.0')
    mapping_reason = Column(Text, nullable=False)

class Fact(Base):
    __tablename__ = 'facts'
    id = Column(String, primary_key=True, default=uid)
    evidence_id = Column(String, ForeignKey('evidence.id'), nullable=False)
    vehicle_id = Column(String, ForeignKey('vehicles.id'), nullable=True)
    feature_id = Column(String, ForeignKey('features.id'), nullable=True)
    model = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False)
    label = Column(String, nullable=False)
    value = Column(JSON, nullable=True)
    unit = Column(String, nullable=True)
    market = Column(String, nullable=True)
    variant = Column(String, nullable=True)
    conditions = Column(JSON, nullable=False, default=dict)
    knowledge_state = Column(String, nullable=False, default='known')
    review_status = Column(String, nullable=False, default='pending')
    scope_layer = Column(String, nullable=False, default='fixed')
    evidence_kind = Column(String, nullable=False)
    origin = Column(String, nullable=False, default='unknown')

class Feedback(Base):
    __tablename__ = 'feedback'
    id = Column(String, primary_key=True)
    source_id = Column(String, ForeignKey('sources.id'), nullable=False, index=True)
    external_id = Column(String, nullable=False)
    model = Column(String, nullable=False, index=True)
    country = Column(String, nullable=False, index=True)
    powertrain = Column(String, nullable=False, index=True)
    raw_powertrain = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    text_hash = Column(String, nullable=False, index=True)
    origin = Column(String, nullable=False, default='unknown')
    source_label = Column(String, nullable=True)
    source_date = Column(String, nullable=True)
    tags = Column(JSON, nullable=False)
    duplicate_text = Column(Boolean, nullable=False, default=False)
    __table_args__ = (UniqueConstraint('source_id', 'external_id'),)

class Aspect(Base):
    __tablename__ = 'aspects'
    id = Column(String, primary_key=True, default=uid)
    feedback_id = Column(String, ForeignKey('feedback.id'), nullable=False, index=True)
    evidence_id = Column(String, ForeignKey('evidence.id'), nullable=False)
    feature_id = Column(String, ForeignKey('features.id'), nullable=False, index=True)
    feedback_type = Column(String, nullable=False)
    quote = Column(Text, nullable=False)
    mapping_status = Column(String, nullable=False, default='suggested')
    mapping_reason = Column(Text, nullable=False)
    mapping_version = Column(String, nullable=False)
    sentiment = Column(Float, nullable=True)
    critical = Column(Boolean, nullable=False, default=False)
    __table_args__ = (UniqueConstraint('feedback_id', 'feature_id', 'feedback_type'),)

class Requirement(Base):
    __tablename__ = 'requirements'
    id = Column(String, primary_key=True)
    feature_id = Column(String, ForeignKey('features.id'), nullable=False)
    model = Column(String, nullable=False, index=True)
    current_revision = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default='proposed')
    band = Column(String, nullable=False, default='Unscored')
    scope_layer = Column(String, nullable=False, default='variable')
    origin = Column(String, nullable=False, default='unknown')
    created_at = Column(String, nullable=False, default=now)

class RequirementRevision(Base):
    __tablename__ = 'requirement_revisions'
    id = Column(String, primary_key=True, default=uid)
    requirement_id = Column(String, ForeignKey('requirements.id'), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    acceptance_criteria = Column(JSON, nullable=False)
    evidence_ids = Column(JSON, nullable=False)
    actor = Column(String, nullable=False)
    rationale = Column(Text, nullable=False)
    generated_by = Column(String, nullable=False)
    created_at = Column(String, nullable=False, default=now)
    __table_args__ = (UniqueConstraint('requirement_id', 'revision'),)

class PriorityRun(Base):
    __tablename__ = 'priority_runs'
    id = Column(String, primary_key=True, default=uid)
    cohort = Column(JSON, nullable=False)
    snapshot = Column(JSON, nullable=False)
    version = Column(String, nullable=False)
    created_at = Column(String, nullable=False, default=now)

class Decision(Base):
    __tablename__ = 'decisions'
    id = Column(String, primary_key=True, default=uid)
    requirement_id = Column(String, ForeignKey('requirements.id'), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    action = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    rationale = Column(Text, nullable=False)
    previous = Column(JSON, nullable=False)
    current = Column(JSON, nullable=False)
    snapshot = Column(JSON, nullable=False)
    created_at = Column(String, nullable=False, default=now)

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    seq = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    previous_hash = Column(String, nullable=False)
    event_hash = Column(String, nullable=False)

class Job(Base):
    __tablename__ = 'jobs'
    id = Column(String, primary_key=True, default=uid)
    kind = Column(String, nullable=False)
    state = Column(String, nullable=False, default='queued')
    input = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    progress = Column(String, nullable=False, default='Queued')
    created_at = Column(String, nullable=False, default=now)
    updated_at = Column(String, nullable=False, default=now)

class AnalysisRun(Base):
    __tablename__ = 'analysis_runs'
    id = Column(String, primary_key=True, default=uid)
    input_hash = Column(String, nullable=False, index=True)
    pipeline_version = Column(String, nullable=False)
    prompt_version = Column(String, nullable=False)
    schema_version = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    mode = Column(String, nullable=False)
    inputs = Column(JSON, nullable=False)
    output = Column(JSON, nullable=False)
    created_at = Column(String, nullable=False, default=now)

class Export(Base):
    __tablename__ = 'exports'
    id = Column(String, primary_key=True, default=uid)
    priority_run_id = Column(String, ForeignKey('priority_runs.id'), nullable=False)
    snapshot = Column(JSON, nullable=False)
    path = Column(String, nullable=False)
    created_at = Column(String, nullable=False, default=now)

class EvaluationLabel(Base):
    __tablename__ = 'evaluation_labels'
    feedback_id = Column(String, ForeignKey('feedback.id'), primary_key=True)
    split = Column(String, nullable=False)
    expected_categories = Column(JSON, nullable=True)
    actor = Column(String, nullable=True)
    rationale = Column(Text, nullable=True)
    labeled_at = Column(String, nullable=True)
