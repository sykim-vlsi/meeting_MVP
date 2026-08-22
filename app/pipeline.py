from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable

from app.agents import LiveConfigurationError, live_is_configured, run_live_pipeline
from app.demo_analyzer import analyze_actions, analyze_self, analyze_stakeholders
from app.models import (
    AnalysisMode,
    AnalysisRequest,
    AnalysisResponse,
    AnalysisResult,
    PipelineStage,
    PresentationAnalysisResponse,
    ProductMode,
    TranscriptTurn,
)
from app.presentation_agents import run_live_presentation_pipeline
from app.presentation_analyzer import analyze_presentation
from app.summaries import (
    meeting_executive_summary,
    presentation_executive_summary,
)

ProgressCallback = Callable[[str, str, str], Awaitable[None]]


async def _demo_pipeline(
    turns: list[TranscriptTurn],
    request: AnalysisRequest,
    progress: ProgressCallback | None = None,
) -> AnalysisResponse:
    async def emit(stage: str, status: str, detail: str) -> None:
        if progress:
            await progress(stage, status, detail)

    await emit("self-coach", "running", "선택한 화자의 발화만 분리해 코칭합니다.")
    await asyncio.sleep(0.25)
    self_coaching = analyze_self(turns, request.self_speaker)
    await emit("self-coach", "complete", "강점과 다음 회의 행동을 찾았습니다.")

    await emit(
        "stakeholder",
        "running",
        "다른 화자의 명시적 요구와 가설을 분리합니다.",
    )
    await asyncio.sleep(0.25)
    stakeholders = analyze_stakeholders(turns, request.self_speaker)
    await emit(
        "stakeholder",
        "complete",
        f"{len(stakeholders)}명의 관점을 근거와 함께 정리했습니다.",
    )

    await emit("action-planner", "running", "결정, 미해결 질문, 후속 행동을 종합합니다.")
    await asyncio.sleep(0.25)
    action_plan = analyze_actions(turns)
    await emit("action-planner", "complete", "실행 가능한 후속 계획을 만들었습니다.")

    return AnalysisResponse(
        analysis_id=str(uuid.uuid4()),
        mode="demo",
        mode_label="빠른 기본 분석 · 규칙 기반",
        schedule=request.schedule,
        pipeline=[
            PipelineStage(
                id="self-coach",
                name="SelfCoachAgent",
                status="complete",
                detail="선택한 화자 코칭 완료",
            ),
            PipelineStage(
                id="stakeholder",
                name="StakeholderAgent",
                status="complete",
                detail="이해관계자 맵 완료",
            ),
            PipelineStage(
                id="action-planner",
                name="ActionPlannerAgent",
                status="complete",
                detail="후속 행동 계획 완료",
            ),
        ],
        executive_summary=meeting_executive_summary(
            self_coaching, stakeholders, action_plan, request.schedule
        ),
        self_coaching=self_coaching,
        stakeholders=stakeholders,
        action_plan=action_plan,
        disclaimer=(
            "목표와 우려에 대한 가설은 사실이 아닙니다. 인용 근거와 확인 질문을 사용해 "
            "당사자에게 직접 확인하세요. 성격, 감정, 기만 여부 또는 민감한 특성을 추론하지 않습니다."
        ),
    )


async def _demo_presentation_pipeline(
    turns: list[TranscriptTurn],
    request: AnalysisRequest,
    progress: ProgressCallback | None = None,
) -> PresentationAnalysisResponse:
    async def emit(stage: str, status: str, detail: str) -> None:
        if progress:
            await progress(stage, status, detail)

    await emit(
        "presentation-structure", "running", "발표의 구조와 근거 흐름을 분석합니다."
    )
    await asyncio.sleep(0.25)
    await emit(
        "presentation-structure", "complete", "구조와 근거 분석을 완료했습니다."
    )
    await emit(
        "presentation-clarity",
        "running",
        "명료성, 간결성, 반복 표현과 Q&A를 점검합니다.",
    )
    await asyncio.sleep(0.25)
    coaching = analyze_presentation(turns, request.self_speaker)
    await emit(
        "presentation-clarity", "complete", "문장과 질문 대응 점검을 완료했습니다."
    )
    await emit(
        "presentation-rehearsal",
        "running",
        "분석을 다음 발표 리허설 계획으로 종합합니다.",
    )
    await asyncio.sleep(0.25)
    await emit(
        "presentation-rehearsal", "complete", "리허설 체크리스트를 완성했습니다."
    )
    return PresentationAnalysisResponse(
        analysis_id=str(uuid.uuid4()),
        mode="demo",
        mode_label="빠른 기본 분석 · 규칙 기반",
        product_mode=ProductMode.PRESENTATION_COACH,
        schedule=request.schedule,
        pipeline=[
            PipelineStage(
                id="presentation-structure",
                name="PresentationStructureAgent",
                status="complete",
                detail="구조·근거 분석 완료",
            ),
            PipelineStage(
                id="presentation-clarity",
                name="PresentationClarityAgent",
                status="complete",
                detail="명료성·Q&A 분석 완료",
            ),
            PipelineStage(
                id="presentation-rehearsal",
                name="PresentationRehearsalAgent",
                status="complete",
                detail="리허설 계획 완료",
            ),
        ],
        executive_summary=presentation_executive_summary(
            coaching, request.schedule
        ),
        presentation_coaching=coaching,
        disclaimer=(
            "이 평가는 대화록에 관찰되는 구조와 표현만 다룹니다. "
            "음성 톤, 감정, 성격, 카리스마 또는 민감한 특성을 추론하지 않습니다."
        ),
    )


async def run_pipeline(
    turns: list[TranscriptTurn],
    request: AnalysisRequest,
    progress: ProgressCallback | None = None,
) -> AnalysisResult:
    if request.mode == AnalysisMode.LIVE and not live_is_configured():
        raise LiveConfigurationError(
            "Live mode is not configured. Use demo mode or configure BYOK settings."
        )
    if request.mode == AnalysisMode.LIVE or (
        request.mode == AnalysisMode.AUTO and live_is_configured()
    ):
        if request.product_mode == ProductMode.PRESENTATION_COACH:
            return await run_live_presentation_pipeline(turns, request, progress)
        return await run_live_pipeline(turns, request, progress)
    if request.product_mode == ProductMode.PRESENTATION_COACH:
        return await _demo_presentation_pipeline(turns, request, progress)
    return await _demo_pipeline(turns, request, progress)
