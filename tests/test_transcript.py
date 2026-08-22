import pytest

from app.transcript import (
    TranscriptValidationError,
    get_speakers,
    parse_transcript,
    parse_transcript_with_metadata,
)


def test_parses_timestamped_and_plain_turns() -> None:
    turns = parse_transcript("[00:01] A: 안녕하세요\nB: 반갑습니다\n00:20 A: 시작할까요?")

    assert len(turns) == 3
    assert turns[0].timestamp == "00:01"
    assert turns[1].timestamp is None
    assert get_speakers(turns) == ["A", "B"]


def test_appends_unlabelled_continuation_lines() -> None:
    turns = parse_transcript(
        "A: 첫 발화\n이어지는 설명\n추가 문장\nB: 두 번째\nA: 세 번째"
    )

    assert turns[0].text == "첫 발화 이어지는 설명 추가 문장"


def test_rejects_prose_before_first_speaker() -> None:
    with pytest.raises(TranscriptValidationError, match="인식하지 못한 줄: 1"):
        parse_transcript("회의 메모\nA: 첫 발화\nB: 두 번째\nA: 세 번째")


def test_requires_multiple_speakers() -> None:
    with pytest.raises(TranscriptValidationError, match="최소 2명"):
        parse_transcript("A: 하나\nA: 둘\nA: 셋")


def test_tracks_multi_file_source_delimiters() -> None:
    turns = parse_transcript(
        "--- 파일: first.txt ---\nA: 하나\nB: 둘\n"
        "--- 파일: second.md ---\nA: 셋"
    )

    assert [turn.source for turn in turns] == [
        "first.txt",
        "first.txt",
        "second.md",
    ]


def test_normalizes_common_bullets_timestamps_and_speaker_labels() -> None:
    turns = parse_transcript(
        "1. (00:01) 화자 1 - 첫 발화\n"
        "설명이 다음 줄에 이어집니다\n"
        "• [00:08] 참석자 A：두 번째 발화\n"
        "- 00:15 Speaker 1: 세 번째 발화"
    )

    assert [turn.speaker for turn in turns] == ["화자 1", "참석자 A", "Speaker 1"]
    assert turns[0].text.endswith("이어집니다")
    assert [turn.timestamp for turn in turns] == ["00:01", "00:08", "00:15"]


def test_normalizes_literal_newlines_and_real_continuations() -> None:
    transcript = (
        "[00:00] A: 첫 문장\\n두 번째 줄\\r\\n세 번째 줄\n"
        "[00:20] B: 응답입니다.\n"
        "이어지는 열네 번째 줄\n"
        "이어지는 열다섯 번째 줄\\n"
        "[00:40] A: 마무리합니다."
    )

    turns, normalized_lines = parse_transcript_with_metadata(transcript)

    assert len(turns) == 3
    assert normalized_lines == 4
    assert turns[0].text == "첫 문장 두 번째 줄 세 번째 줄"
    assert turns[1].text.endswith("이어지는 열네 번째 줄 이어지는 열다섯 번째 줄")
