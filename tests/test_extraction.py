from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.extraction import ExtractionError, extract_docx, extract_pdf, extract_text
from app.main import app

FIXTURES = Path(__file__).parent.parent / "fixtures"
client = TestClient(app)


def test_first_party_fixture_round_trips() -> None:
    txt = extract_text((FIXTURES / "meeting-sprint.txt").read_bytes())
    pdf = extract_pdf((FIXTURES / "presentation-pitch.pdf").read_bytes())
    docx = extract_docx((FIXTURES / "presentation-pitch.docx").read_bytes())

    assert "[00:00] A:" in txt
    assert "Meeting Mirror" in pdf
    assert "[00:00] A:" in docx


@pytest.mark.parametrize(
    ("filename", "mime"),
    [
        ("meeting-sprint.txt", "text/plain"),
        ("presentation-pitch.pdf", "application/pdf"),
        (
            "presentation-pitch.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    ],
)
def test_extract_api_accepts_required_formats(filename: str, mime: str) -> None:
    response = client.post(
        "/api/extract",
        files={"file": (filename, (FIXTURES / filename).read_bytes(), mime)},
    )

    assert response.status_code == 200
    assert response.json()["transcript"]
    assert response.json()["filename"] == filename


def test_batch_extract_combines_sources_and_reports_each_file() -> None:
    response = client.post(
        "/api/extract/batch",
        files=[
            (
                "files",
                (
                    "meeting-sprint.txt",
                    (FIXTURES / "meeting-sprint.txt").read_bytes(),
                    "text/plain",
                ),
            ),
            (
                "files",
                (
                    "presentation-pitch.docx",
                    (FIXTURES / "presentation-pitch.docx").read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ),
        ],
    )

    assert response.status_code == 200
    result = response.json()
    assert result["successful_files"] == 2
    assert "--- 파일: meeting-sprint.txt ---" in result["combined_transcript"]
    assert "--- 파일: presentation-pitch.docx ---" in result["combined_transcript"]


def test_markdown_upload_is_supported() -> None:
    content = "# 회의\n\n[00:00] A: 시작합니다.\n[00:10] B: 요청입니다.\n[00:20] A: 확인합니다."
    response = client.post(
        "/api/extract",
        files={"file": ("notes.md", content.encode(), "text/markdown")},
    )

    assert response.status_code == 200
    assert "[00:10] B:" in response.json()["transcript"]


def test_rejects_image_only_pdf() -> None:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.showPage()
    pdf.save()

    with pytest.raises(ExtractionError, match="이미지형 PDF"):
        extract_pdf(buffer.getvalue())


def test_mp3_is_explicitly_gated_without_speech_config() -> None:
    response = client.post(
        "/api/extract",
        files={"file": ("demo.mp3", b"ID3" + b"\x00" * 100, "audio/mpeg")},
    )

    assert response.status_code == 503
    assert "Azure Speech" in response.json()["detail"]
