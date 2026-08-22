from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


def request_json(
    url: str,
    method: str = "GET",
    payload: dict | None = None,
    timeout: int = 180,
) -> object:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return json.load(response)


def upload_files(
    url: str, files: list[tuple[str, bytes, str]]
) -> dict:
    boundary = "----MeetingMirrorSmokeBoundary"
    chunks: list[bytes] = []
    for filename, content, content_type in files:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="files"; '
                    f'filename="{filename}"\r\n'
                ).encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                content,
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    body = b"".join(chunks)
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def main() -> None:
    if len(sys.argv) not in {2, 3} or (
        len(sys.argv) == 3 and sys.argv[2] != "--live"
    ):
        raise SystemExit(
            "Usage: python scripts/smoke_public.py https://<azure-host> [--live]"
        )
    base_url = sys.argv[1].rstrip("/")

    with urllib.request.urlopen(base_url, timeout=30) as response:
        html = response.read().decode()
        assert response.status == 200
        assert 'id="analyze"' in html
        assert 'id="consent"' in html
        assert 'id="calendar-grid"' in html
        assert 'id="ai-deep-analysis"' in html
        assert 'id="file-input"' in html

    health = request_json(f"{base_url}/health")
    assert health["status"] == "ok"

    samples = request_json(f"{base_url}/api/samples")
    assert len(samples) == 7
    engine_modes = ["demo"]
    runtime = request_json(f"{base_url}/api/runtime")
    if "--live" in sys.argv and runtime["live_available"]:
        engine_modes.append("live")
    for product_mode in ("meeting-insight", "presentation-coach"):
        sample = next(
            item for item in samples if item["product_mode"] == product_mode
        )
        for engine_mode in engine_modes:
            result = request_json(
                f"{base_url}/api/analyze",
                method="POST",
                payload={
                    "transcript": sample["transcript"],
                    "self_speaker": sample["recommended_self"],
                    "product_mode": product_mode,
                    "mode": engine_mode,
                    "consent_confirmed": True,
                },
            )
            assert result["mode"] == engine_mode
            assert len(result["pipeline"]) == 3
            assert result["executive_summary"]["headline"]
            if product_mode == "meeting-insight":
                assert len(result["stakeholders"]) == len(sample["speakers"]) - 1
                assert result["action_plan"]["action_items"]
            else:
                assert result["presentation_coaching"]["improvements"]

    fixtures = request_json(f"{base_url}/api/fixtures")
    fixture_payloads = []
    for fixture in fixtures:
        with urllib.request.urlopen(
            f"{base_url}{fixture['download_url']}", timeout=30
        ) as response:
            content = response.read()
        fixture_payloads.append(
            (
                fixture["filename"],
                content,
                {
                "TXT": "text/plain",
                "PDF": "application/pdf",
                "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                }[fixture["format"]],
            )
        )
    extracted = upload_files(
        f"{base_url}/api/extract/batch", fixture_payloads
    )
    assert extracted["successful_files"] == 3
    assert all(item["status"] == "complete" for item in extracted["files"])

    calendar_response = urllib.request.Request(
        f"{base_url}/api/calendar",
        data=json.dumps(
            {
                "title": "공개 스모크 미팅",
                "date": "2026-08-24",
                "start_time": "09:00",
                "duration_minutes": 30,
                "timezone": "Asia/Seoul",
                "location": "온라인",
                "purpose": "배포 검증",
            }
        ).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(calendar_response, timeout=30) as response:
        assert response.status == 200
        assert b"BEGIN:VCALENDAR" in response.read()
    print(f"Public smoke passed: {base_url}")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, urllib.error.URLError) as exc:
        raise SystemExit(f"Public smoke failed: {exc}") from exc
