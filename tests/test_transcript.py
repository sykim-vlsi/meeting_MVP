import pytest

from app.transcript import TranscriptValidationError, get_speakers, parse_transcript


def test_parses_timestamped_and_plain_turns() -> None:
    turns = parse_transcript("[00:01] A: 안녕하세요\nB: 반갑습니다\n00:20 A: 시작할까요?")

    assert len(turns) == 3
    assert turns[0].timestamp == "00:01"
    assert turns[1].timestamp is None
    assert get_speakers(turns) == ["A", "B"]


def test_rejects_unlabelled_lines() -> None:
    with pytest.raises(TranscriptValidationError, match="인식하지 못한 줄"):
        parse_transcript("A: 첫 발화\n화자 없는 문장\nB: 두 번째\nA: 세 번째")


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
