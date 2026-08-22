import json
from types import SimpleNamespace

import pytest

import app.agents as meeting_agents
import app.presentation_agents as presentation_agents
from app.demo_analyzer import analyze_actions, analyze_self, analyze_stakeholders
from app.models import AnalysisRequest, ProductMode
from app.presentation_analyzer import analyze_presentation
from app.samples import load_samples
from app.summaries import (
    meeting_executive_summary,
    presentation_executive_summary,
)
from app.transcript import parse_transcript


class FakeAgent:
    def __init__(self, response: dict):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def run(self, _prompt: str):
        return SimpleNamespace(text=json.dumps(self.response, ensure_ascii=False))


@pytest.mark.asyncio
async def test_meeting_live_workflow_allows_no_progress_callback(monkeypatch) -> None:
    sample = next(item for item in load_samples() if item.id == "sprint-planning")
    turns = parse_transcript(sample.transcript)
    coaching = analyze_self(turns, sample.recommended_self)
    stakeholders = analyze_stakeholders(turns, sample.recommended_self)
    plan = analyze_actions(turns)
    responses = {
        "SelfCoachAgent": coaching.model_dump(mode="json"),
        "StakeholderAgent": {
            "stakeholders": [
                item.model_dump(mode="json") for item in stakeholders
            ]
        },
        "ActionPlannerAgent": {
            "executive_summary": meeting_executive_summary(
                coaching, stakeholders, plan
            ).model_dump(mode="json"),
            "action_plan": plan.model_dump(mode="json"),
        },
    }
    monkeypatch.setattr(
        meeting_agents,
        "_make_agent",
        lambda name, _instructions: FakeAgent(responses[name]),
    )
    request = AnalysisRequest(
        transcript=sample.transcript,
        self_speaker=sample.recommended_self,
        mode="live",
        consent_confirmed=True,
    )

    result = await meeting_agents.run_live_pipeline(turns, request, None)

    assert result.mode == "live"
    assert len(result.pipeline) == 3
    assert result.executive_summary.headline


@pytest.mark.asyncio
async def test_meeting_live_workflow_emits_six_progress_events(monkeypatch) -> None:
    sample = next(item for item in load_samples() if item.id == "sprint-planning")
    turns = parse_transcript(sample.transcript)
    coaching = analyze_self(turns, sample.recommended_self)
    stakeholders = analyze_stakeholders(turns, sample.recommended_self)
    plan = analyze_actions(turns)
    responses = {
        "SelfCoachAgent": coaching.model_dump(mode="json"),
        "StakeholderAgent": {
            "stakeholders": [item.model_dump(mode="json") for item in stakeholders]
        },
        "ActionPlannerAgent": {
            "executive_summary": meeting_executive_summary(
                coaching, stakeholders, plan
            ).model_dump(mode="json"),
            "action_plan": plan.model_dump(mode="json"),
        },
    }
    monkeypatch.setattr(
        meeting_agents,
        "_make_agent",
        lambda name, _instructions: FakeAgent(responses[name]),
    )
    events: list[tuple[str, str]] = []

    async def progress(stage: str, status: str, _detail: str) -> None:
        events.append((stage, status))

    request = AnalysisRequest(
        transcript=sample.transcript,
        self_speaker=sample.recommended_self,
        mode="live",
        consent_confirmed=True,
    )
    await meeting_agents.run_live_pipeline(turns, request, progress)

    assert len(events) == 6
    assert events[0] == ("self-coach", "running")
    assert events[-1] == ("action-planner", "complete")


@pytest.mark.asyncio
async def test_presentation_live_workflow_allows_no_progress_callback(
    monkeypatch,
) -> None:
    sample = next(item for item in load_samples() if item.id == "product-pitch")
    turns = parse_transcript(sample.transcript)
    coaching = analyze_presentation(turns, sample.recommended_self)
    responses = {
        "PresentationStructureAgent": {
            "findings": [
                item.model_dump(mode="json") for item in coaching.strengths
            ]
        },
        "PresentationClarityAgent": {
            "findings": [
                item.model_dump(mode="json") for item in coaching.improvements
            ]
        },
        "PresentationRehearsalAgent": {
            "executive_summary": presentation_executive_summary(
                coaching
            ).model_dump(mode="json"),
            "presentation_coaching": coaching.model_dump(mode="json"),
        },
    }
    monkeypatch.setattr(
        presentation_agents,
        "_make_agent",
        lambda name, _instructions: FakeAgent(responses[name]),
    )
    request = AnalysisRequest(
        transcript=sample.transcript,
        self_speaker=sample.recommended_self,
        product_mode=ProductMode.PRESENTATION_COACH,
        mode="live",
        consent_confirmed=True,
    )

    result = await presentation_agents.run_live_presentation_pipeline(
        turns, request, None
    )

    assert result.mode == "live"
    assert len(result.pipeline) == 3
    assert result.presentation_coaching.next_presentation_checklist
