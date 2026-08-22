from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.agents import LiveConfigurationError, live_is_configured
from app.models import AnalysisRequest
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
        "default_mode": "live" if live_is_configured() else "demo",
    }


@app.get("/api/samples")
async def samples():
    return load_samples()


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
