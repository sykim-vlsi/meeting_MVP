from fastapi.testclient import TestClient

from app.main import app
from app.models import AnalysisResponse
from app.samples import load_samples

client = TestClient(app)


def demo_request() -> dict:
    sample = load_samples()[0]
    return {
        "transcript": sample.transcript,
        "self_speaker": sample.recommended_self,
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
    assert len(result.pipeline) == 3
    assert result.action_plan.action_items


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
