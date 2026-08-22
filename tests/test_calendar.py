from fastapi.testclient import TestClient

from app.calendar import build_ics
from app.main import app
from app.models import MeetingMetadata

client = TestClient(app)


def metadata() -> MeetingMetadata:
    return MeetingMetadata(
        title="제품 피치, 리허설",
        date="2026-08-24",
        start_time="09:00",
        duration_minutes=60,
        timezone="Asia/Seoul",
        location="회의실; A",
        purpose="핵심 메시지 확인",
    )


def test_ics_uses_utc_and_escapes_korean_metadata() -> None:
    content = build_ics(metadata())

    assert "\r\n" in content
    assert "DTSTART:20260824T000000Z" in content
    assert "DTEND:20260824T010000Z" in content
    assert "SUMMARY:제품 피치\\, 리허설" in content
    assert "LOCATION:회의실\\; A" in content
    assert "대화록" in content


def test_calendar_endpoint_returns_download() -> None:
    response = client.post("/api/calendar", json=metadata().model_dump(mode="json"))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert 'filename="meeting-mirror.ics"' in response.headers[
        "content-disposition"
    ]
