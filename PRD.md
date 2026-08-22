# Meeting Mirror — Product Requirements

## Product statement

Meeting Mirror is a login-free web app with two modes: a presentation coach and a meeting insight coach. Both turn source-cited observations into concrete rehearsal or follow-up actions.

## Target user and problem

Knowledge workers, team leads, students, researchers, and customer-facing professionals often leave a meeting with notes but little actionable feedback about their own communication. Existing summaries also blur what someone said with what a model imagines they meant. The product must create useful reflection without pretending to know hidden mental states.

### Target productivity outcome

In future moderated usability testing, target completion of post-meeting self-review and first-draft follow-up planning in **under five minutes**, compared with a user-recorded baseline. This is a product target, not a measured result. Leading indicators are: every action has an owner/deadline state, every stakeholder hypothesis has a verification question, and the report is copyable in one click.

## Golden path

1. Open the public page without an account and choose 발표 개선 or 회의 맥락·참여자 목적 분석.
2. Upload up to five TXT/MD/PDF/DOCX files, paste a labeled transcript, or load a mode-specific sample.
3. Select the speaker representing the user and confirm analysis consent.
4. Start analysis and watch SelfCoachAgent → StakeholderAgent → ActionPlannerAgent progress.
5. Review coaching, all other participants, and an executable action plan.
6. Copy the readable report or download the structured JSON.
7. Optionally save non-sensitive schedule metadata in the browser calendar or download an ICS file.

## Functional requirements

- Accept lines formatted as `[MM:SS] Speaker: text`, `MM:SS Speaker: text`, or `Speaker: text`.
- Reject malformed, one-speaker, or shorter-than-three-turn transcripts clearly.
- Include five polished Korean meeting samples and two Korean presentation samples.
- Presentation mode analyzes observable structure, clarity, concision, evidence/examples, repeated wording, and question handling; it outputs rewritten phrases and a rehearsal checklist.
- Provide bounded in-memory TXT/MD/PDF/DOCX extraction. Reject image-only PDFs with OCR guidance. MP3 is shown as Azure Speech-gated and never reports false success.
- Default to live agents when BYOK is configured; otherwise use a clearly labeled deterministic demo. Users can explicitly choose either mode.
- Self coaching includes strengths, specific improvements, quote/timestamp evidence, and next-meeting behaviors.
- Every non-self speaker receives explicit requests, explicit concerns, possible-goal hypotheses, confidence, citations, and a confirmation question.
- Action planning includes decisions, unresolved questions, owner/deadline/action items, evidence, and recommended follow-ups.
- Expose all three pipeline stages through server-sent progress events.
- Support reset, copy, download, loading, and error states.
- Put a typed `한눈에 보는 핵심` before details with headline, priority insights, and immediate actions.
- Provide an IndexedDB month calendar with date filtering, seeded examples, CRUD, optional transcript/result save (off by default), and ICS export.

## Nonfunctional requirements

- Responsive at mobile and desktop widths and keyboard operable.
- No login or third-party account for the public demo path.
- No server database. Calendar persistence is browser-local IndexedDB; transcript/result storage is explicit opt-in.
- Health endpoint at `/health`.
- Input capped at 50,000 characters.
- Typed and validated request/response contracts.
- Azure Container Apps deployment can scale to zero and uses HTTPS ingress.

## Responsible-AI behavior

- Hypotheses are not facts and must be visibly labeled.
- Do not claim emotions, personality, deception, hidden intent, or sensitive/protected traits.
- Use only observed conversational cues and source quotes.
- Ask the user to verify hypotheses directly with the participant.
- Require confirmation that the user has the right and participant consent to analyze the transcript.
- Do not store transcripts. Azure platform request logs must not include bodies.

## Acceptance criteria

- An automated judge can load a sample, select a speaker, confirm consent, run all three stages, and see all required output without credentials.
- Every included sample loads and parses in tests.
- API responses validate against `AnalysisResponse`.
- Live configuration selects the Agent Framework/Copilot SDK workflow rather than the deterministic implementation.
- `/health` and the public root URL return HTTP 200 after deployment.
- Both deterministic modes, TXT/PDF/DOCX fixture extraction, calendar metadata, and ICS generation pass against the public URL.

## 심사 기준 대응표

| Official weight | Implemented evidence |
|---|---|
| Copilot SDK + Microsoft Agent Framework · 25% | Real three-node `WorkflowBuilder` in `app/agents.py`; three `GitHubCopilotAgent` roles use Copilot SDK BYOK, pass validated context forward, and emit UI progress. Demo provenance is visibly different. |
| Productivity/problem fit · 18% | Personal coaching, stakeholder verification questions, owner/deadline/action output, copy/download, and the under-five-minute target above. |
| Azure · 18% | Public HTTPS web app on Azure Container Apps, Bicep/azd assets, managed identity ACR pull, health probes, Log Analytics, and secretless deployment OIDC. |
| Completeness · 16% | Golden paths for both modes, seven samples, document extraction, validation, SSE progress, errors, response contracts, timeout, unit/API/public smoke tests. |
| UX/workflow · 12% | Primary upload portal, optional one-click examples, consent → analyze flow, semantic labels/IDs, responsive layout, loading/error/status announcements, copy/download/reset. |
| Responsible AI/security · 6% | Explicit vs hypothesis separation, citations/confidence/verification, consent, no retention, no external actions or hidden-trait claims. |
| Originality · 5% | A personal meeting performance coach and stakeholder-understanding verifier, not a generic summary product. |

## Current limitations

- The public deployment has a server-configured Azure model: AI 심층 분석 runs the real agent path, while the default-off fast rule-based path remains predictable and provenance is explicit.
- Deterministic analysis uses language cues and is less nuanced than the live three-agent path.
- Korean labeled text transcripts only; no audio, diarization, file upload, or external follow-up execution.

## Non-goals

OAuth calendar sync, server-side history, audio diarization, live meeting participation, emotion/sentiment detection, employee scoring, organization analytics, and sending follow-up messages.
