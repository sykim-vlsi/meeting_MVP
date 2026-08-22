from __future__ import annotations

import re

from app.models import TranscriptTurn

TIMESTAMPED_LINE = re.compile(
    r"^\s*(?:\[(?P<bracket_time>\d{1,2}:\d{2}(?::\d{2})?)\]|"
    r"(?P<plain_time>\d{1,2}:\d{2}(?::\d{2})?))?\s*"
    r"(?P<speaker>[A-Za-z가-힣][A-Za-z0-9가-힣 _-]{0,29})\s*[:：]\s*"
    r"(?P<text>.+?)\s*$"
)


class TranscriptValidationError(ValueError):
    pass


def parse_transcript(transcript: str) -> list[TranscriptTurn]:
    turns: list[TranscriptTurn] = []
    rejected: list[int] = []

    for line_number, raw_line in enumerate(transcript.splitlines(), start=1):
        if not raw_line.strip():
            continue
        match = TIMESTAMPED_LINE.match(raw_line)
        if not match:
            rejected.append(line_number)
            continue
        turns.append(
            TranscriptTurn(
                speaker=match.group("speaker").strip(),
                text=match.group("text").strip(),
                timestamp=match.group("bracket_time") or match.group("plain_time"),
            )
        )

    if rejected:
        lines = ", ".join(str(number) for number in rejected[:5])
        suffix = " 외" if len(rejected) > 5 else ""
        raise TranscriptValidationError(
            f"화자: 발화 형식을 확인해 주세요. 인식하지 못한 줄: {lines}{suffix}"
        )
    if len(turns) < 3:
        raise TranscriptValidationError("분석하려면 최소 3개의 발화가 필요합니다.")
    if len({turn.speaker for turn in turns}) < 2:
        raise TranscriptValidationError("최소 2명의 화자가 필요합니다.")
    return turns


def get_speakers(turns: list[TranscriptTurn]) -> list[str]:
    return list(dict.fromkeys(turn.speaker for turn in turns))
