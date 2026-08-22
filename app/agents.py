from __future__ import annotations

import asyncio
import json
import os
import re
from contextlib import AsyncExitStack
from typing import Literal, Never, cast

from agent_framework import WorkflowBuilder, WorkflowContext, executor
from agent_framework.github import GitHubCopilotAgent, GitHubCopilotOptions
from copilot.session import ProviderConfig
from pydantic import BaseModel, ValidationError

from app.models import (
    ActionPlan,
    AnalysisRequest,
    AnalysisResponse,
    ExecutiveSummary,
    PipelineStage,
    SelfCoaching,
    StakeholderProfile,
    TranscriptTurn,
)


class LiveConfigurationError(RuntimeError):
    pass


class AgentOutputError(RuntimeError):
    pass


class StakeholderOutput(BaseModel):
    stakeholders: list[StakeholderProfile]


class MeetingSynthesis(BaseModel):
    executive_summary: ExecutiveSummary
    action_plan: ActionPlan


JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
REQUIRED_LIVE_SETTINGS = ("BYOK_BASE_URL", "BYOK_API_KEY", "BYOK_MODEL_ID")


def live_is_configured() -> bool:
    return all(os.environ.get(name) for name in REQUIRED_LIVE_SETTINGS)


def _extract_json(text: str) -> object:
    candidate = text.strip()
    fenced = JSON_FENCE.search(candidate)
    if fenced:
        candidate = fenced.group(1).strip()
    else:
        start = min(
            (index for index in (candidate.find("{"), candidate.find("[")) if index >= 0),
            default=-1,
        )
        end = max(candidate.rfind("}"), candidate.rfind("]"))
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise AgentOutputError("에이전트가 유효한 JSON을 반환하지 않았습니다.") from exc


def _provider_options() -> GitHubCopilotOptions:
    missing = [name for name in REQUIRED_LIVE_SETTINGS if not os.environ.get(name)]
    if missing:
        raise LiveConfigurationError(
            "Live agent mode requires: " + ", ".join(missing)
        )
    model_id = os.environ["BYOK_MODEL_ID"]
    provider_type = cast(
        Literal["openai", "azure", "anthropic"],
        os.environ.get("BYOK_PROVIDER_TYPE", "azure"),
    )
    provider: ProviderConfig = {
        "type": provider_type,
        "base_url": os.environ["BYOK_BASE_URL"],
        "api_key": os.environ["BYOK_API_KEY"],
        "wire_api": cast(
            Literal["completions", "responses"],
            os.environ.get("BYOK_WIRE_API", "completions"),
        ),
        "model_id": model_id,
    }
    return GitHubCopilotOptions(model=model_id, provider=provider)


def _make_agent(name: str, instructions: str) -> GitHubCopilotAgent:
    return GitHubCopilotAgent(
        name=name,
        instructions=instructions,
        default_options=_provider_options(),
    )


def _turns_payload(turns: list[TranscriptTurn]) -> list[dict[str, str | None]]:
    return [turn.model_dump() for turn in turns]


async def run_live_pipeline(
    turns: list[TranscriptTurn],
    request: AnalysisRequest,
    progress,
) -> AnalysisResponse:
    async def emit(stage: str, status: str, detail: str) -> None:
        if progress:
            await progress(stage, status, detail)

    self_schema = json.dumps(SelfCoaching.model_json_schema(), ensure_ascii=False)
    stakeholder_schema = json.dumps(
        StakeholderOutput.model_json_schema(), ensure_ascii=False
    )
    action_schema = json.dumps(
        MeetingSynthesis.model_json_schema(), ensure_ascii=False
    )

    self_agent = _make_agent(
        "SelfCoachAgent",
        (
            "당신은 근거 중심 회의 코치입니다. 오직 선택된 본인 화자의 발화만 코칭하세요. "
            "성격, 감정, 숨은 의도, 기만, 민감하거나 보호되는 특성을 추론하지 마세요. "
            "강점과 개선점마다 대화록의 정확한 인용과 타임스탬프, 다음 회의 행동을 제시하세요. "
            "주어진 JSON Schema를 정확히 따르는 JSON만 반환하세요."
        ),
    )
    stakeholder_agent = _make_agent(
        "StakeholderAgent",
        (
            "당신은 이해관계자 분석가입니다. 본인을 제외한 모든 화자를 빠짐없이 다루세요. "
            "명시적으로 말한 요청/우려와 가능한 목표 가설을 엄격히 분리하세요. 가설은 관찰된 "
            "대화 단서로만 뒷받침하고 신뢰도, 정확한 인용, 당사자 확인 질문을 포함하세요. "
            "성격, 감정, 숨은 의도, 기만, 민감하거나 보호되는 특성을 추론하지 마세요. "
            "주어진 JSON Schema를 정확히 따르는 JSON만 반환하세요."
        ),
    )
    action_agent = _make_agent(
        "ActionPlannerAgent",
        (
            "당신은 실행 계획 에이전트입니다. 원본 대화록과 앞선 두 분석을 종합해 명시적 결정, "
            "미해결 질문, 담당자/기한/행동 항목, 추천 후속 조치를 만드세요. 대화에 없는 담당자나 "
            "기한은 사실처럼 만들지 말고 '확인 필요'로 표시하세요. 모든 행동에는 인용 근거를 "
            "연결하세요. 10초 안에 읽을 한눈에 보는 핵심도 함께 만드세요. "
            "주어진 JSON Schema를 정확히 따르는 JSON만 반환하세요."
        ),
    )

    @executor(id="self-coach")
    async def self_coach_node(payload: str, ctx: WorkflowContext[str]) -> None:
        await emit(
            "self-coach", "running", "Copilot SDK가 본인 발화를 근거 중심으로 분석합니다."
        )
        source = json.loads(payload)
        prompt = (
            f"본인 화자: {source['self_speaker']}\n"
            f"대화록(JSON): {json.dumps(source['turns'], ensure_ascii=False)}\n"
            f"출력 JSON Schema: {self_schema}"
        )
        response = await self_agent.run(prompt)
        try:
            coaching = SelfCoaching.model_validate(_extract_json(response.text))
        except ValidationError as exc:
            raise AgentOutputError(
                "SelfCoachAgent 응답이 계약을 충족하지 않았습니다."
            ) from exc
        source["self_coaching"] = coaching.model_dump()
        await emit("self-coach", "complete", "본인 코칭을 완료했습니다.")
        await ctx.send_message(json.dumps(source, ensure_ascii=False))

    @executor(id="stakeholder")
    async def stakeholder_node(payload: str, ctx: WorkflowContext[str]) -> None:
        await emit(
            "stakeholder", "running", "다른 화자의 명시적 요구와 가설을 분리합니다."
        )
        source = json.loads(payload)
        prompt = (
            f"본인 화자: {source['self_speaker']}\n"
            f"대화록(JSON): {json.dumps(source['turns'], ensure_ascii=False)}\n"
            f"본인 코칭(JSON): {json.dumps(source['self_coaching'], ensure_ascii=False)}\n"
            f"출력 JSON Schema: {stakeholder_schema}"
        )
        response = await stakeholder_agent.run(prompt)
        try:
            output = StakeholderOutput.model_validate(_extract_json(response.text))
        except ValidationError as exc:
            raise AgentOutputError(
                "StakeholderAgent 응답이 계약을 충족하지 않았습니다."
            ) from exc
        expected = {
            turn.speaker for turn in turns if turn.speaker != request.self_speaker
        }
        actual = {profile.speaker for profile in output.stakeholders}
        if actual != expected:
            raise AgentOutputError(
                "StakeholderAgent가 모든 다른 화자를 정확히 포함하지 않았습니다."
            )
        source["stakeholders"] = output.model_dump()["stakeholders"]
        await emit(
            "stakeholder",
            "complete",
            f"{len(output.stakeholders)}명의 근거 기반 맵을 완성했습니다.",
        )
        await ctx.send_message(json.dumps(source, ensure_ascii=False))

    @executor(id="action-planner")
    async def action_node(
        payload: str, ctx: WorkflowContext[Never, str]
    ) -> None:
        await emit(
            "action-planner", "running", "이전 에이전트 출력을 실행 계획으로 종합합니다."
        )
        source = json.loads(payload)
        prompt = (
            f"대화록(JSON): {json.dumps(source['turns'], ensure_ascii=False)}\n"
            f"본인 코칭(JSON): {json.dumps(source['self_coaching'], ensure_ascii=False)}\n"
            f"이해관계자 맵(JSON): {json.dumps(source['stakeholders'], ensure_ascii=False)}\n"
            f"일정(JSON, 없으면 null): {json.dumps(source['schedule'], ensure_ascii=False)}\n"
            "일정에 없는 마감은 만들지 마세요.\n"
            f"출력 JSON Schema: {action_schema}"
        )
        response = await action_agent.run(prompt)
        try:
            synthesis = MeetingSynthesis.model_validate(
                _extract_json(response.text)
            )
        except ValidationError as exc:
            raise AgentOutputError(
                "ActionPlannerAgent 응답이 계약을 충족하지 않았습니다."
            ) from exc
        source["executive_summary"] = synthesis.executive_summary.model_dump()
        source["action_plan"] = synthesis.action_plan.model_dump()
        await emit("action-planner", "complete", "실행 계획을 완성했습니다.")
        await ctx.yield_output(json.dumps(source, ensure_ascii=False))

    workflow = (
        WorkflowBuilder(start_executor=self_coach_node)
        .add_edge(self_coach_node, stakeholder_node)
        .add_edge(stakeholder_node, action_node)
        .build()
    )
    initial = json.dumps(
        {
            "self_speaker": request.self_speaker,
            "turns": _turns_payload(turns),
            "schedule": request.schedule.model_dump(mode="json")
            if request.schedule
            else None,
        },
        ensure_ascii=False,
    )

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(self_agent)
        await stack.enter_async_context(stakeholder_agent)
        await stack.enter_async_context(action_agent)
        timeout_seconds = float(os.environ.get("LIVE_AGENT_TIMEOUT_SECONDS", "120"))
        async with asyncio.timeout(timeout_seconds):
            workflow_result = await workflow.run(initial)

    outputs = workflow_result.get_outputs()
    if not outputs:
        raise AgentOutputError("Agent Framework workflow returned no output.")
    payload = json.loads(outputs[-1])
    return AnalysisResponse(
        analysis_id=os.urandom(16).hex(),
        mode="live",
        mode_label="AI 심층 분석 · MAF + Copilot SDK",
        schedule=request.schedule,
        pipeline=[
            PipelineStage(
                id="self-coach",
                name="SelfCoachAgent",
                status="complete",
                detail="Copilot SDK BYOK 분석 완료",
            ),
            PipelineStage(
                id="stakeholder",
                name="StakeholderAgent",
                status="complete",
                detail="Copilot SDK BYOK 분석 완료",
            ),
            PipelineStage(
                id="action-planner",
                name="ActionPlannerAgent",
                status="complete",
                detail="MAF workflow 종합 완료",
            ),
        ],
        executive_summary=ExecutiveSummary.model_validate(
            payload["executive_summary"]
        ),
        self_coaching=SelfCoaching.model_validate(payload["self_coaching"]),
        stakeholders=[
            StakeholderProfile.model_validate(item)
            for item in payload["stakeholders"]
        ],
        action_plan=ActionPlan.model_validate(payload["action_plan"]),
        disclaimer=(
            "목표와 우려에 대한 가설은 사실이 아닙니다. 인용 근거와 확인 질문을 사용해 "
            "당사자에게 직접 확인하세요. 성격, 감정, 기만 여부 또는 민감한 특성을 추론하지 않습니다."
        ),
    )
