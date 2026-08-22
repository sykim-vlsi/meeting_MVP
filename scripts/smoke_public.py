from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


def request_json(
    url: str, method: str = "GET", payload: dict | None = None
) -> object:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return json.load(response)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/smoke_public.py https://<azure-host>")
    base_url = sys.argv[1].rstrip("/")

    with urllib.request.urlopen(base_url, timeout=30) as response:
        html = response.read().decode()
        assert response.status == 200
        assert 'id="analyze"' in html
        assert 'id="consent"' in html

    health = request_json(f"{base_url}/health")
    assert health["status"] == "ok"

    samples = request_json(f"{base_url}/api/samples")
    assert len(samples) == 5
    sample = samples[0]
    result = request_json(
        f"{base_url}/api/analyze",
        method="POST",
        payload={
            "transcript": sample["transcript"],
            "self_speaker": sample["recommended_self"],
            "mode": "demo",
            "consent_confirmed": True,
        },
    )
    assert result["mode"] == "demo"
    assert len(result["pipeline"]) == 3
    assert len(result["stakeholders"]) == len(sample["speakers"]) - 1
    assert result["self_coaching"]["strengths"]
    assert result["self_coaching"]["improvements"]
    assert result["action_plan"]["action_items"]
    print(f"Public smoke passed: {base_url}")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, urllib.error.URLError) as exc:
        raise SystemExit(f"Public smoke failed: {exc}") from exc
