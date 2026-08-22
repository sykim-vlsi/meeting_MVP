from __future__ import annotations

from datetime import UTC, date, datetime, time
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class AnalysisMode(str, Enum):
    AUTO = "auto"
    LIVE = "live"
    DEMO = "demo"


class ProductMode(str, Enum):
    MEETING_INSIGHT = "meeting-insight"
    PRESENTATION_COACH = "presentation-coach"


class MeetingMetadata(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    date: date
    start_time: time
    duration_minutes: int = Field(default=60, ge=5, le=480)
    timezone: str = Field(default="Asia/Seoul", min_length=1, max_length=64)
    location: str | None = Field(default=None, max_length=160)
    purpose: str | None = Field(default=None, max_length=300)


class TranscriptTurn(BaseModel):
    speaker: str
    text: str
    timestamp: str | None = None
    source: str | None = None


class TranscriptSample(BaseModel):
    id: str
    title: str
    description: str
    transcript: str
    recommended_self: str
    speakers: list[str]
    product_mode: ProductMode = ProductMode.MEETING_INSIGHT


class AnalysisRequest(BaseModel):
    transcript: str = Field(min_length=20, max_length=50_000)
    self_speaker: str = Field(min_length=1, max_length=30)
    mode: AnalysisMode = AnalysisMode.AUTO
    product_mode: ProductMode = ProductMode.MEETING_INSIGHT
    schedule: MeetingMetadata | None = None
    consent_confirmed: bool = False

    @field_validator("self_speaker")
    @classmethod
    def normalize_speaker(cls, value: str) -> str:
        return value.strip()


class Citation(BaseModel):
    speaker: str
    quote: str
    timestamp: str | None = None
    source: str | None = None


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
    core_perspective: str
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


class ExecutiveSummary(BaseModel):
    headline: str
    priority_insights: list[str] = Field(min_length=2, max_length=4)
    immediate_actions: list[str] = Field(min_length=1, max_length=3)
    responsible_ai_note: str


class PresentationFinding(BaseModel):
    dimension: str
    title: str
    observation: str
    evidence: list[Citation]
    rewritten_phrase: str
    rehearsal_action: str


class PresentationCoaching(BaseModel):
    speaker: str
    overview: str
    strengths: list[PresentationFinding]
    improvements: list[PresentationFinding]
    next_presentation_checklist: list[str]


class AnalysisResponse(BaseModel):
    analysis_id: str
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    mode: str
    mode_label: str
    product_mode: ProductMode = ProductMode.MEETING_INSIGHT
    schedule: MeetingMetadata | None = None
    pipeline: list[PipelineStage]
    executive_summary: ExecutiveSummary
    self_coaching: SelfCoaching
    stakeholders: list[StakeholderProfile]
    action_plan: ActionPlan
    disclaimer: str


class PresentationAnalysisResponse(BaseModel):
    analysis_id: str
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    mode: str
    mode_label: str
    product_mode: ProductMode = ProductMode.PRESENTATION_COACH
    schedule: MeetingMetadata | None = None
    pipeline: list[PipelineStage]
    executive_summary: ExecutiveSummary
    presentation_coaching: PresentationCoaching
    disclaimer: str


AnalysisResult = AnalysisResponse | PresentationAnalysisResponse
