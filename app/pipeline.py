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
    PipelineStage,
    TranscriptTurn,
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
        mode_label="Deterministic demo mode",
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
        self_coaching=self_coaching,
        stakeholders=stakeholders,
        action_plan=action_plan,
        disclaimer=(
            "목표와 우려에 대한 가설은 사실이 아닙니다. 인용 근거와 확인 질문을 사용해 "
            "당사자에게 직접 확인하세요. 성격, 감정, 기만 여부 또는 민감한 특성을 추론하지 않습니다."
        ),
    )


async def run_pipeline(
    turns: list[TranscriptTurn],
    request: AnalysisRequest,
    progress: ProgressCallback | None = None,
) -> AnalysisResponse:
    if request.mode == AnalysisMode.LIVE and not live_is_configured():
        raise LiveConfigurationError(
            "Live mode is not configured. Use demo mode or configure BYOK settings."
        )
    if request.mode == AnalysisMode.LIVE or (
        request.mode == AnalysisMode.AUTO and live_is_configured()
    ):
        return await run_live_pipeline(turns, request, progress)
    return await _demo_pipeline(turns, request, progress)
