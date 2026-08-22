from app.models import ProductMode
from app.samples import load_samples
from app.transcript import get_speakers, parse_transcript


def test_all_required_samples_load_and_parse() -> None:
    samples = load_samples()

    assert len(samples) == 7
    assert {sample.id for sample in samples} == {
        "sprint-planning",
        "design-review",
        "client-requirements",
        "research-team",
        "incident-review",
        "product-pitch",
        "technical-demo",
    }
    assert sum(
        sample.product_mode == ProductMode.MEETING_INSIGHT for sample in samples
    ) == 5
    assert sum(
        sample.product_mode == ProductMode.PRESENTATION_COACH
        for sample in samples
    ) == 2
    for sample in samples:
        turns = parse_transcript(sample.transcript)
        assert len(turns) >= 10
        assert 3 <= len(get_speakers(turns)) <= 5
        assert all(turn.timestamp for turn in turns)
