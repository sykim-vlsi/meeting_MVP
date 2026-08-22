from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models import MeetingMetadata


class CalendarError(ValueError):
    pass


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str, limit: int = 73) -> list[str]:
    encoded = line.encode("utf-8")
    if len(encoded) <= limit:
        return [line]
    parts: list[str] = []
    current = ""
    for character in line:
        candidate = current + character
        if len(candidate.encode("utf-8")) > limit:
            parts.append(current)
            current = " " + character
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def build_ics(metadata: MeetingMetadata) -> str:
    try:
        timezone = ZoneInfo(metadata.timezone)
    except ZoneInfoNotFoundError as exc:
        raise CalendarError("유효한 IANA 시간대를 입력해 주세요.") from exc
    start_local = datetime.combine(
        metadata.date, metadata.start_time, tzinfo=timezone
    )
    end_local = start_local + timedelta(minutes=metadata.duration_minutes)
    start_utc = start_local.astimezone(UTC)
    end_utc = end_local.astimezone(UTC)
    uid_source = (
        f"{metadata.title}|{start_local.isoformat()}|{metadata.duration_minutes}"
    )
    uid = hashlib.sha256(uid_source.encode()).hexdigest()[:24]
    purpose = f" 목적: {metadata.purpose}" if metadata.purpose else ""
    description = (
        "Meeting Mirror 분석 일정입니다."
        f"{purpose} 대화록과 분석 내용은 캘린더에 포함되지 않습니다."
    )
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Meeting Mirror//Calendar//KO",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-TIMEZONE:{_escape(metadata.timezone)}",
        "BEGIN:VEVENT",
        f"UID:{uid}@meeting-mirror",
        f"DTSTAMP:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{start_utc.strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{end_utc.strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{_escape(metadata.title)}",
        f"DESCRIPTION:{_escape(description)}",
        *(
            [f"LOCATION:{_escape(metadata.location)}"]
            if metadata.location
            else []
        ),
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(part for line in lines for part in _fold(line)) + "\r\n"
