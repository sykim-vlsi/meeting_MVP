from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.models import TranscriptSample
from app.transcript import get_speakers, parse_transcript

SAMPLES_PATH = Path(__file__).parent / "data" / "samples.json"


@lru_cache
def load_samples() -> list[TranscriptSample]:
    raw_samples = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    samples: list[TranscriptSample] = []
    seen_ids: set[str] = set()

    for raw_sample in raw_samples:
        sample = TranscriptSample.model_validate(raw_sample)
        if sample.id in seen_ids:
            raise ValueError(f"Duplicate sample id: {sample.id}")
        parsed_speakers = get_speakers(parse_transcript(sample.transcript))
        if set(parsed_speakers) != set(sample.speakers):
            raise ValueError(
                f"Sample {sample.id} speaker metadata does not match transcript"
            )
        if sample.recommended_self not in sample.speakers:
            raise ValueError(f"Invalid recommended speaker for sample {sample.id}")
        seen_ids.add(sample.id)
        samples.append(sample)

    return samples
