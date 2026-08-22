# Meeting Mirror — Ideation

## Opportunity

Most meeting summaries optimize organizational recall. They do not answer a personal question: “How did I communicate, what did each colleague explicitly need, and what should I do next?” Meeting Mirror makes that reflection concrete while keeping uncertain interpretation visibly uncertain.

## Alternatives considered

| Concept | Strength | Why not selected |
|---|---|---|
| Generic meeting summarizer | Familiar, easy to demo | Crowded category; weak personal behavior change |
| Live meeting bot | Immediate coaching | Consent, OAuth, audio, latency, and platform integration exceed hackathon scope |
| Emotion/intent detector | Visually dramatic | Scientifically fragile and irresponsible; hidden-state claims harm trust |
| Team performance dashboard | Longitudinal value | Requires accounts, server storage, and surveillance-like aggregation |
| **Evidence-first personal coach** | Distinct, useful, safe to demo from text | Selected |

## Differentiation

- The user explicitly chooses which speaker is “self”; the coach does not guess identity.
- Other participants’ direct statements are separated from possible goals or concerns.
- Every inference carries a quote, confidence, and confirmation question.
- The three agents have distinct responsibilities and visible hand-offs.
- A deterministic path makes the complete product demonstrable without credentials.

## Scope cuts

No server database, accounts, OAuth, calendar/email actions, live bot, sentiment scoring, or long-term participant profiles. A browser-only IndexedDB calendar and ICS export were retained because they add planning value without public server storage. TXT/MD/PDF/DOCX extraction is implemented; MP3 is honestly gated on Azure Speech configuration.

## Key risks and mitigations

- **Overclaiming intent:** label hypotheses; require evidence, confidence, and verification questions.
- **Transcript exposure:** request-memory processing only; no transcript logging or persistence.
- **Model unavailability:** deterministic demo mode remains explicit and fully functional.
- **Malformed model output:** validate every agent response against Pydantic contracts and fail clearly.
- **Deployment build constraints:** use `azd` ACR remote builds rather than local Docker.
