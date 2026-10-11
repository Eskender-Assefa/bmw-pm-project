from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict

class Cohort(BaseModel):
    model: Literal['F70','G60','G68','G70','G60_G68'] = 'G60'
    country: str = 'US'
    powertrain: Literal['all','ICE','BEV','PHEV'] = 'all'
    origin: Literal['unknown','observed','synthetic','all'] = 'unknown'

class RequirementView(BaseModel):
    id: str
    feature_id: str
    feature: str
    category: str
    title: str
    description: str
    acceptance_criteria: list[str]
    revision: int
    status: str
    band: str
    critical: bool
    numerator: int
    denominator: int
    demand: float | None
    likes: int
    sentiment: float | None
    mapping_status: str
    evidence_ids: list[str]
    supporting_ids: list[str]
    evidence_samples: list[dict[str,Any]]
    conflicts: list[str]
    generated_by: str
    created_at: str

class RankingResponse(BaseModel):
    cohort: Cohort
    denominator: int
    mapped_records: int
    mapping_coverage: float | None
    reviewed_mapping_records: int
    requirements: list[RequirementView]
    source_checksums: dict[str,str]
    ranking_version: str
    time_coverage: str = 'Unknown: supplied feedback has no dates'

class DecisionRequest(BaseModel):
    cohort: Cohort
    expected_revision: int
    action: Literal['approve','edit','reject','postpone','set_band']
    actor: str = Field(default='Demo PM', min_length=1, max_length=100)
    rationale: str = Field(default='', max_length=4000)
    band: Literal['High','Medium','Low','Unscored'] | None = None
    title: str | None = Field(default=None, min_length=5, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=4000)
    acceptance_criteria: list[str] | None = None
    analysis_run_id: str | None = None

class ImportRequest(BaseModel):
    path: str

class WebConnectorRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=10)
    model: Literal['F70','G60','G68','G70','G60_G68'] = 'G60'
    country: str = Field(default='US', min_length=1, max_length=40)
    powertrain: Literal['ICE','BEV','PHEV','unknown'] = 'unknown'
    source_label: str | None = Field(default=None, max_length=120)

class JobView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    state: str
    input: dict[str,Any]
    result: dict[str,Any] | None
    error: str | None
    progress: str
    created_at: str
    updated_at: str

class AnalysisRequest(BaseModel):
    cohort: Cohort
    requirement_id: str
    mode: Literal['live','replay'] = 'replay'

class AnalysisAspect(BaseModel):
    evidence_id: str
    quote: str
    category: Literal['C01','C02','C03','C04','C05','C06','C07','C08','C09','C10']
    feature_id: str
    feedback_type: Literal['Likes','Wants','Difficult to Use','Defect','Unclassified']
    sentiment: int = Field(ge=-100,le=100)
    explanation: str

class AnalysisProposal(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[str]
    evidence_ids: list[str]
    uncertainties: list[str]
    aspects: list[AnalysisAspect]

class ExportRequest(BaseModel):
    cohort: Cohort
    include_scenario: bool = True

class MappingReviewRequest(BaseModel):
    status: Literal['reviewed','rejected','pending']
    rationale: str = Field(min_length=5,max_length=2000)
    actor: str = Field(default='Demo PM',min_length=1,max_length=100)
    feature_id: str | None = None

class FactReviewRequest(BaseModel):
    status: Literal['reviewed','rejected','pending']
    rationale: str = Field(min_length=5,max_length=2000)
    actor: str = Field(default='Demo PM',min_length=1,max_length=100)

class EvaluationRequest(BaseModel):
    categories: list[Literal['C01','C02','C03','C04','C05','C06','C07','C08','C09','C10']]
    rationale: str = Field(min_length=5,max_length=2000)
    actor: str = Field(default='Demo PM',min_length=1,max_length=100)
