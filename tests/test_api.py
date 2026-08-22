from fastapi.testclient import TestClient

from app.main import app
from app.models import AnalysisResponse, PresentationAnalysisResponse
from app.samples import load_samples

client = TestClient(app)


def demo_request(sample_id: str = "sprint-planning") -> dict:
    sample = next(item for item in load_samples() if item.id == sample_id)
    return {
        "transcript": sample.transcript,
        "self_speaker": sample.recommended_self,
        "product_mode": sample.product_mode,
        "mode": "demo",
        "consent_confirmed": True,
    }


def test_health_and_runtime() -> None:
    assert client.get("/health").json()["status"] == "ok"
    runtime = client.get("/api/runtime").json()
    assert runtime["default_mode"] in {"live", "demo"}


def test_demo_analysis_matches_contract() -> None:
    response = client.post("/api/analyze", json=demo_request())

    assert response.status_code == 200
    result = AnalysisResponse.model_validate(response.json())
    assert result.mode == "demo"
    assert result.self_coaching.speaker == "A"
    assert {item.speaker for item in result.stakeholders} == {"B", "C", "D"}
    assert all(item.core_perspective for item in result.stakeholders)
    assert len(result.pipeline) == 3
    assert result.executive_summary.headline
    assert result.executive_summary.immediate_actions
    assert result.action_plan.action_items


def test_schedule_is_preserved_and_used_in_summary() -> None:
    payload = demo_request()
    payload["schedule"] = {
        "title": "스프린트 계획",
        "date": "2026-08-24",
        "start_time": "09:30",
        "duration_minutes": 45,
        "timezone": "Asia/Seoul",
        "location": "회의실 A",
        "purpose": "출시 범위 확정",
    }

    response = client.post("/api/analyze", json=payload)

    assert response.status_code == 200
    result = response.json()
    assert result["schedule"]["location"] == "회의실 A"
    assert "2026-08-24" in result["executive_summary"]["headline"]


def test_presentation_demo_has_distinct_contract() -> None:
    response = client.post("/api/analyze", json=demo_request("product-pitch"))

    assert response.status_code == 200
    result = PresentationAnalysisResponse.model_validate(response.json())
    assert result.product_mode == "presentation-coach"
    assert result.presentation_coaching.speaker == "A"
    assert result.presentation_coaching.strengths
    assert result.presentation_coaching.improvements
    assert result.presentation_coaching.next_presentation_checklist
    assert result.executive_summary.immediate_actions


def test_stream_emits_all_stages_and_result() -> None:
    response = client.post("/api/analyze/stream", json=demo_request())

    assert response.status_code == 200
    body = response.text
    assert body.count('"type": "progress"') == 6
    assert '"stage": "self-coach"' in body
    assert '"stage": "stakeholder"' in body
    assert '"stage": "action-planner"' in body
    assert '"type": "result"' in body


def test_consent_is_required() -> None:
    payload = demo_request()
    payload["consent_confirmed"] = False

    response = client.post("/api/analyze", json=payload)

    assert response.status_code == 400


def test_selected_speaker_must_exist() -> None:
    payload = demo_request()
    payload["self_speaker"] = "Z"

    response = client.post("/api/analyze", json=payload)

    assert response.status_code == 422
