"""Entity resolution and clarification models (orchestration, not final report schema)."""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.rubric import SubjectType

RunStatusValue = Literal[
    "queued",
    "running",
    "clarification_required",
    "complete",
    "error",
]

AmbiguityLevel = Literal["low", "medium", "high"]


class CandidateEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    name: str
    country: Optional[str] = None
    industry: Optional[str] = None
    why_shown: str


class ClarificationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    label: str
    type: Literal["select", "text", "multiselect"] = "select"
    options: list[str] = Field(default_factory=list)
    required: bool = False


class ClarificationForm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[ClarificationQuestion]
    candidate_entities: list[CandidateEntity] = Field(default_factory=list)


class SubjectFieldBundle(BaseModel):
    """Country, industry, associations at a resolution layer."""

    model_config = ConfigDict(extra="forbid")

    country: Optional[str] = None
    industry: Optional[str] = None
    known_associations: list[str] = Field(default_factory=list)


class ResolvedSubject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_provided: SubjectFieldBundle
    inferred: SubjectFieldBundle
    confirmed: SubjectFieldBundle


class EntityResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ambiguity_level: AmbiguityLevel
    reason_codes: list[str]
    action: Literal["continue", "clarification_required", "continue_limited"]


class ClarificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: Optional[str] = None
    industry: Optional[str] = None
    known_associations: list[str] = Field(default_factory=list)
    candidate_id: Optional[str] = None
    notes: Optional[str] = None


class MinimalScreenRequest(BaseModel):
    """Documented minimal input: only subject_type and primary_name required."""

    subject_type: SubjectType
    primary_name: str = Field(min_length=1)
