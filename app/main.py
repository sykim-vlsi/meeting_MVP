from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.agents import (
    AgentOutputError,
    DemoModeDisabledError,
    LiveConfigurationError,
    live_is_configured,
)
from app.calendar import CalendarError, build_ics
from app.extraction import (
    EXTRACTION_TIMEOUT_SECONDS,
    MAX_AGGREGATE_BYTES,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_FILES,
    ExtractionError,
    SpeechUnavailableError,
    extract_upload,
    sanitize_filename,
    speech_is_configured,
)
from app.fixtures import FIXTURE_CATALOG, FIXTURES_DIR
from app.models import AnalysisRequest, MeetingMetadata
from app.pipeline import run_pipeline
from app.samples import load_samples
from app.transcript import TranscriptValidationError, get_speakers, parse_transcript

app = FastAPI(
    title="Meeting Mirror",
    description="Evidence-first personal meeting coaching",
    version="0.1.0",
)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/fixtures", StaticFiles(directory=FIXTURES_DIR), name="fixtures")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
        "base-uri 'self'; frame-ancestors 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


def validate_request(request: AnalysisRequest):
    if not request.consent_confirmed:
        raise HTTPException(
            status_code=400,
            detail="분석 권한과 참여자 동의를 확인해 주세요.",
        )
    try:
        turns = parse_transcript(request.transcript)
    except TranscriptValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    speakers = get_speakers(turns)
    if request.self_speaker not in speakers:
        raise HTTPException(
            status_code=422,
            detail=f"선택한 화자 '{request.self_speaker}'를 대화록에서 찾을 수 없습니다.",
        )
    return turns


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "meeting-mirror"}


@app.get("/api/runtime")
async def runtime() -> dict[str, str | bool]:
    return {
        "live_available": live_is_configured(),
        "default_mode": "live",
        "demo_available": os.environ.get("ALLOW_DEMO_MODE", "").lower() == "true",
        "speech_available": speech_is_configured(),
    }


@app.get("/api/samples")
async def samples():
    return load_samples()


@app.get("/api/fixtures")
async def fixtures():
    return [
        {
            **fixture,
            "download_url": f"/fixtures/{fixture['filename']}",
        }
        for fixture in FIXTURE_CATALOG
    ]


@app.post("/api/calendar")
async def calendar_download(metadata: MeetingMetadata) -> Response:
    try:
        content = build_ics(metadata)
    except CalendarError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="meeting-mirror.ics"'
        },
    )


@app.post("/api/extract")
async def extract(file: Annotated[UploadFile, File()]):
    filename = sanitize_filename(file.filename or "upload")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        async with asyncio.timeout(EXTRACTION_TIMEOUT_SECONDS + 5):
            transcript, requires_labels, message = await extract_upload(
                filename, file.content_type, data
            )
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SpeechUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "filename": filename,
        "content_type": file.content_type or "application/octet-stream",
        "size": len(data),
        "transcript": transcript,
        "requires_speaker_labels": requires_labels,
        "message": message,
    }


@app.post("/api/extract/batch")
async def extract_batch(files: Annotated[list[UploadFile], File()]):
    if not files or len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"파일은 한 번에 1개부터 {MAX_UPLOAD_FILES}개까지 선택할 수 있습니다.",
        )
    total_size = 0
    results: list[dict] = []
    combined: list[str] = []
    for upload in files:
        filename = sanitize_filename(upload.filename or "upload")
        data = await upload.read(MAX_UPLOAD_BYTES + 1)
        total_size += len(data)
        if total_size > MAX_AGGREGATE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="전체 파일 크기는 최대 25MB입니다.",
            )
        try:
            async with asyncio.timeout(EXTRACTION_TIMEOUT_SECONDS + 5):
                transcript, requires_labels, message = await extract_upload(
                    filename, upload.content_type, data
                )
            results.append(
                {
                    "filename": filename,
                    "content_type": upload.content_type
                    or "application/octet-stream",
                    "size": len(data),
                    "status": "complete",
                    "requires_speaker_labels": requires_labels,
                    "message": message,
                }
            )
            combined.append(f"--- 파일: {filename} ---\n{transcript}")
        except (ExtractionError, SpeechUnavailableError) as exc:
            results.append(
                {
                    "filename": filename,
                    "content_type": upload.content_type
                    or "application/octet-stream",
                    "size": len(data),
                    "status": "error",
                    "error": str(exc),
                }
            )
    return {
        "files": results,
        "combined_transcript": "\n\n".join(combined),
        "successful_files": len(combined),
        "total_files": len(files),
        "aggregate_size": total_size,
    }


@app.post("/api/parse")
async def parse(request: AnalysisRequest) -> dict[str, list[str]]:
    turns = validate_request(request)
    return {"speakers": get_speakers(turns)}


@app.post("/api/analyze")
async def analyze(request: AnalysisRequest):
    turns = validate_request(request)
    try:
        return await run_pipeline(turns, request)
    except LiveConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DemoModeDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="AI 심층 분석이 시간 제한을 초과했습니다. 다시 시도해 주세요.",
        ) from exc
    except AgentOutputError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI 심층 분석 실행에 실패했습니다: {exc}",
        ) from exc


@app.post("/api/analyze/stream")
async def analyze_stream(request: AnalysisRequest) -> StreamingResponse:
    turns = validate_request(request)

    async def events():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def progress(stage: str, status: str, detail: str) -> None:
            await queue.put(
                {
                    "type": "progress",
                    "stage": stage,
                    "status": status,
                    "detail": detail,
                }
            )

        async def execute() -> None:
            try:
                result = await run_pipeline(turns, request, progress)
                await queue.put(
                    {
                        "type": "result",
                        "data": result.model_dump(mode="json"),
                    }
                )
            except Exception as exc:
                await queue.put({"type": "error", "message": str(exc)})
            finally:
                await queue.put(None)

        task = asyncio.create_task(execute())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
