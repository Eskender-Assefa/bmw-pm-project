from typing import Literal
from pydantic import BaseModel, Field

CategoryId = Literal['C01', 'C02', 'C03', 'C04', 'C05', 'C06', 'C07', 'C08', 'C09', 'C10']
ScopeLayer = Literal['fixed', 'variable', 'hypothetical', 'unknown']


class DocumentMetadata(BaseModel):
    model: str | None = Field(None, max_length=64, pattern=r'^[A-Za-z0-9_ /-]+$')
    market: str | None = Field(None, max_length=30)
    origin: Literal['unknown', 'observed', 'synthetic'] = 'unknown'
    header_row: int = Field(1, ge=1, le=100)


class RagFilters(BaseModel):
    model: str | None = Field(None, max_length=64)
    source_id: str | None = Field(None, max_length=64)
    category: CategoryId | None = None
    scope_layer: ScopeLayer | None = None
    review_status: Literal['pending', 'reviewed', 'rejected'] | None = None
    origin: Literal['unknown', 'observed', 'synthetic'] | None = None
    market: str | None = Field(None, max_length=30)


class RagSearchRequest(RagFilters):
    query: str = Field('', max_length=1000)
    limit: int = Field(20, ge=1, le=50)
    offset: int = Field(0, ge=0, le=100000)


class RagIndexRequest(BaseModel):
    source_ids: list[str] = Field(default_factory=list, max_length=100)


class CategoryAssignment(BaseModel):
    category: CategoryId
    scope_layer: ScopeLayer
    quote: str = Field(min_length=1, max_length=1800)
    rationale: str = Field(min_length=5, max_length=1500)
    feature: str | None = Field(None, min_length=1, max_length=160)
    value: str | None = Field(None, min_length=1, max_length=240)
    unit: str | None = Field(None, min_length=1, max_length=40)
    variant: str | None = Field(None, min_length=1, max_length=160)


class ChunkClassification(BaseModel):
    chunk_id: str
    assignments: list[CategoryAssignment] = Field(min_length=1, max_length=20)


class ClassificationOutput(BaseModel):
    chunks: list[ChunkClassification] = Field(min_length=1, max_length=12)


class RagClassifyRequest(BaseModel):
    chunk_ids: list[str] = Field(min_length=1, max_length=12)
    allow_live: bool = False


class RagAnswerRequest(RagFilters):
    question: str = Field(min_length=3, max_length=1000)
    allow_live: bool = False


class Citation(BaseModel):
    chunk_id: str
    quote: str = Field(min_length=1, max_length=1800)


class GroundedClaim(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    citations: list[Citation] = Field(min_length=1, max_length=8)


class RagAnswerOutput(BaseModel):
    abstained: bool
    claims: list[GroundedClaim] = Field(max_length=8)
    limitations: list[str] = Field(min_length=1, max_length=12)


class RagReviewRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    status: Literal['reviewed', 'rejected', 'pending']
    assignments: list[CategoryAssignment] = Field(min_length=1, max_length=20)
    rationale: str = Field(min_length=5, max_length=2000)
    actor: str = Field('Demo PM', min_length=1, max_length=100)
