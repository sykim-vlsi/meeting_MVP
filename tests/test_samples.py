from app.samples import load_samples
from app.transcript import get_speakers, parse_transcript


def test_all_required_samples_load_and_parse() -> None:
    samples = load_samples()

    assert len(samples) == 5
    assert {sample.id for sample in samples} == {
        "sprint-planning",
        "design-review",
        "client-requirements",
        "research-team",
        "incident-review",
    }
    for sample in samples:
        turns = parse_transcript(sample.transcript)
        assert len(turns) >= 10
        assert 3 <= len(get_speakers(turns)) <= 5
        assert all(turn.timestamp for turn in turns)
