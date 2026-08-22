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


class SequenceFakeAgent(FakeAgent):
    def __init__(self, responses: list[dict]):
        self.responses = responses
        self.calls = 0

    async def run(self, _prompt: str):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return SimpleNamespace(text=json.dumps(response, ensure_ascii=False))


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


@pytest.mark.asyncio
async def test_meeting_workflow_retries_english_generated_prose(monkeypatch) -> None:
    sample = next(item for item in load_samples() if item.id == "sprint-planning")
    turns = parse_transcript(sample.transcript)
    coaching = analyze_self(turns, sample.recommended_self)
    english = coaching.model_copy(deep=True)
    english.summary = "This English explanation must trigger one bounded correction retry."
    stakeholders = analyze_stakeholders(turns, sample.recommended_self)
    plan = analyze_actions(turns)
    self_agent = SequenceFakeAgent(
        [english.model_dump(mode="json"), coaching.model_dump(mode="json")]
    )
    agents = {
        "SelfCoachAgent": self_agent,
        "StakeholderAgent": FakeAgent(
            {"stakeholders": [item.model_dump(mode="json") for item in stakeholders]}
        ),
        "ActionPlannerAgent": FakeAgent(
            {
                "executive_summary": meeting_executive_summary(
                    coaching, stakeholders, plan
                ).model_dump(mode="json"),
                "action_plan": plan.model_dump(mode="json"),
            }
        ),
    }
    monkeypatch.setattr(
        meeting_agents,
        "_make_agent",
        lambda name, _instructions: agents[name],
    )
    request = AnalysisRequest(
        transcript=sample.transcript,
        self_speaker=sample.recommended_self,
        mode="live",
        consent_confirmed=True,
    )

    result = await meeting_agents.run_live_pipeline(turns, request, None)

    assert self_agent.calls == 2
    assert "분리해 분석" in result.self_coaching.summary


@pytest.mark.asyncio
async def test_presentation_workflow_retries_english_generated_prose(
    monkeypatch,
) -> None:
    sample = next(item for item in load_samples() if item.id == "product-pitch")
    turns = parse_transcript(sample.transcript)
    coaching = analyze_presentation(turns, sample.recommended_self)
    english_finding = coaching.strengths[0].model_copy(
        update={
            "observation": (
                "This long English explanation should be rejected while its source quote is preserved."
            )
        }
    )
    structure_agent = SequenceFakeAgent(
        [
            {"findings": [english_finding.model_dump(mode="json")]},
            {
                "findings": [
                    item.model_dump(mode="json") for item in coaching.strengths
                ]
            },
        ]
    )
    agents = {
        "PresentationStructureAgent": structure_agent,
        "PresentationClarityAgent": FakeAgent(
            {
                "findings": [
                    item.model_dump(mode="json") for item in coaching.improvements
                ]
            }
        ),
        "PresentationRehearsalAgent": FakeAgent(
            {
                "executive_summary": presentation_executive_summary(
                    coaching
                ).model_dump(mode="json"),
                "presentation_coaching": coaching.model_dump(mode="json"),
            }
        ),
    }
    monkeypatch.setattr(
        presentation_agents,
        "_make_agent",
        lambda name, _instructions: agents[name],
    )
    request = AnalysisRequest(
        transcript=sample.transcript,
        self_speaker=sample.recommended_self,
        product_mode=ProductMode.PRESENTATION_COACH,
        mode="live",
        consent_confirmed=True,
    )

    await presentation_agents.run_live_presentation_pipeline(turns, request, None)

    assert structure_agent.calls == 2


@pytest.mark.asyncio
async def test_persistent_english_failure_is_explicit_and_quotes_are_excluded() -> None:
    sample = next(item for item in load_samples() if item.id == "sprint-planning")
    turns = parse_transcript(sample.transcript)
    coaching = analyze_self(turns, sample.recommended_self)
    coaching.strengths[0].evidence[0].quote = (
        "This quoted source may remain in its original English language."
    )
    accepted = await meeting_agents._run_validated(
        FakeAgent(coaching.model_dump(mode="json")),
        "prompt",
        type(coaching),
        "SelfCoachAgent",
    )
    assert accepted.strengths[0].evidence[0].quote.startswith("This quoted")

    english = coaching.model_copy(deep=True)
    english.summary = "This persistent English report text must fail after exactly two attempts."
    failing_agent = SequenceFakeAgent([english.model_dump(mode="json")])
    with pytest.raises(meeting_agents.AgentOutputError, match="두 번 연속 한국어"):
        await meeting_agents._run_validated(
            failing_agent, "prompt", type(coaching), "SelfCoachAgent"
        )
    assert failing_agent.calls == 2
