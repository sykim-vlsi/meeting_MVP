from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

FIXTURE_CATALOG = [
    {
        "id": "meeting-sprint-txt",
        "name": "스프린트 회의 TXT",
        "filename": "meeting-sprint.txt",
        "format": "TXT",
        "product_mode": "meeting-insight",
        "description": "범위와 일정 충돌이 있는 회의 대화록",
    },
    {
        "id": "presentation-pitch-pdf",
        "name": "제품 피치 PDF",
        "filename": "presentation-pitch.pdf",
        "format": "PDF",
        "product_mode": "presentation-coach",
        "description": "구조가 늘어지는 제품 피치 대화록",
    },
    {
        "id": "presentation-pitch-docx",
        "name": "제품 피치 DOCX",
        "filename": "presentation-pitch.docx",
        "format": "DOCX",
        "product_mode": "presentation-coach",
        "description": "문단과 표가 포함된 발표 연습 파일",
    },
]
