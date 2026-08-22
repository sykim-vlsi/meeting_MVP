from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class AnalysisMode(str, Enum):
    AUTO = "auto"
    LIVE = "live"
    DEMO = "demo"


class TranscriptTurn(BaseModel):
    speaker: str
    text: str
    timestamp: str | None = None


class TranscriptSample(BaseModel):
    id: str
    title: str
    description: str
    transcript: str
    recommended_self: str
    speakers: list[str]


class AnalysisRequest(BaseModel):
    transcript: str = Field(min_length=20, max_length=50_000)
    self_speaker: str = Field(min_length=1, max_length=30)
    mode: AnalysisMode = AnalysisMode.AUTO
    consent_confirmed: bool = False

    @field_validator("self_speaker")
    @classmethod
    def normalize_speaker(cls, value: str) -> str:
        return value.strip()


class Citation(BaseModel):
    speaker: str
    quote: str
    timestamp: str | None = None


class CoachingInsight(BaseModel):
    title: str
    observation: str
    evidence: list[Citation]
    next_behavior: str


class SelfCoaching(BaseModel):
    speaker: str
    summary: str
    strengths: list[CoachingInsight]
    improvements: list[CoachingInsight]


class StakeholderHypothesis(BaseModel):
    possible_goal_or_concern: str
    confidence: str
    observed_cues: list[str]
    citations: list[Citation]
    confirmation_question: str


class StakeholderProfile(BaseModel):
    speaker: str
    explicit_requests: list[str]
    concerns: list[str]
    hypotheses: list[StakeholderHypothesis]


class ActionItem(BaseModel):
    owner: str
    deadline: str
    action: str
    evidence: list[Citation]
    status: str = "제안"


class ActionPlan(BaseModel):
    decisions: list[str]
    unresolved_questions: list[str]
    action_items: list[ActionItem]
    recommended_followups: list[str]


class PipelineStage(BaseModel):
    id: str
    name: str
    status: str
    detail: str


class AnalysisResponse(BaseModel):
    analysis_id: str
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    mode: str
    mode_label: str
    pipeline: list[PipelineStage]
    self_coaching: SelfCoaching
    stakeholders: list[StakeholderProfile]
    action_plan: ActionPlan
    disclaimer: str
