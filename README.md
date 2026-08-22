# Meeting Mirror

**An evidence-first personal meeting coach:** analyze your speaking behavior, map every other participant’s explicit needs and possible goals, and leave with concrete follow-up actions.

[![Python](https://img.shields.io/badge/Python-3.11%2B-335bd7)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116.1-009688)](https://fastapi.tiangolo.com/)
[![Microsoft Agent Framework](https://img.shields.io/badge/Microsoft-Agent_Framework-e14c2a)](https://github.com/microsoft/agent-framework)

## Demo

The public deployment is added here after the first Azure smoke test. No login is required: choose a Korean sample, select your speaker, confirm consent, and run the three-agent pipeline. The **Deterministic demo** option is always available without credentials.

Meeting Mirror never treats a model’s interpretation as hidden truth. Explicit statements are separate from hypotheses, and every hypothesis includes evidence, confidence, and a question to verify with that person.

## Architecture

```mermaid
flowchart LR
  UI[Static responsive UI] -->|SSE| API[FastAPI]
  API --> MAF[Agent Framework workflow]
  MAF --> A[SelfCoachAgent] --> B[StakeholderAgent] --> C[ActionPlannerAgent]
  A & B & C --> SDK[GitHub Copilot SDK BYOK]
  API --> Demo[Credential-free deterministic path]
```

The real path uses `agent-framework-github-copilot==1.0.3`, an Agent Framework `WorkflowBuilder`, and three `GitHubCopilotAgent` instances. Copilot SDK BYOK targets Azure OpenAI or a Microsoft Foundry-compatible endpoint. The public judge path is deterministic and visibly labeled.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Open <http://127.0.0.1:8000>. Demo mode needs no environment variables.

For live mode, copy `.env.example` values into the process environment. Never commit the key:

```powershell
$env:BYOK_PROVIDER_TYPE = "azure"
$env:BYOK_BASE_URL = "https://YOUR-RESOURCE.openai.azure.com/"
$env:BYOK_API_KEY = "..."
$env:BYOK_MODEL_ID = "gpt-4o-mini"
```

## Quality checks

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests
```

Tests cover transcript validation, all five sample files, API errors, SSE stage progress, and response contracts.

## Deploy to Azure

The template deploys one public Azure Container App and uses an ACR remote build, so local Docker is not required.

```powershell
$env:AZURE_DEV_USER_AGENT = "microsoft_foundry_skill"
azd auth login
azd up --no-prompt
```

For live mode, add `BYOK_API_KEY` as a Container Apps secret and set the other BYOK environment variables after provisioning. Without them the service defaults to the complete deterministic demo.

When ACR Tasks are disabled by subscription policy, dispatch `.github/workflows/deploy.yml`. It builds the same Dockerfile on a GitHub-hosted runner and deploys the SHA-tagged image to the already provisioned Container App using Azure OIDC.

## Privacy and consent

Transcripts and results are processed only in request memory and are not persisted by the application. Azure request logs do not contain bodies. Obtain participant consent and remove confidential or sensitive information before analysis.

See [PRD.md](PRD.md) for acceptance criteria, [TRD.md](TRD.md) for precise SDK/deployment details, and [IDEATION.md](IDEATION.md) for scope decisions.

## Final submission checklist

- [ ] GitHub issue author is registered as the team leader.
- [ ] Repository URL starts with `https://github.com/<issue-author>/`.
- [ ] Submitted commit SHA exists on the remote and contains root `PRD.md` and `TRD.md`.
- [ ] Deployment URL is the raw public `https://*.azurecontainerapps.io` hostname.
- [ ] Root, health, samples, and one full demo analysis pass `python scripts/smoke_public.py <URL>` without credentials.
- [ ] All submission acknowledgements are checked; no more than two submissions are filed, and the latest is intended for judging.

Do not submit automatically. Confirm every item against the exact remote SHA and public URL first.
