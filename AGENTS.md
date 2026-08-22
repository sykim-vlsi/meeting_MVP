# Agent Guide

This project was built with the microsoft-foundry skill. Before working on or answering questions about foundry agents, read the microsoft-foundry skill first.

## Product boundary

Meeting Mirror is a login-free meeting and presentation coach. Keep server transcript processing request-scoped: do not add server persistence, user accounts, recording bots, OAuth calendar, or email integrations. The only persistence is the documented browser-local IndexedDB calendar, with transcript/result save opt-in and off by default. Treat stakeholder goals as hypotheses, never facts, and do not infer personality, emotion, deception, health, identity, or other sensitive traits.

## Architecture and ownership

- `app/main.py`: HTTP endpoints, validation boundary, static hosting, SSE transport.
- `app/agents.py`: Microsoft Agent Framework workflow and GitHub Copilot SDK BYOK integration.
- `app/pipeline.py`: typed product-mode routing and progress contract.
- `app/demo_analyzer.py`: deterministic development/test fixture, disabled in production.
- `app/models.py`: shared API contracts. Update tests and UI renderers with contract changes.
- `app/transcript.py`, `app/data/samples.json`: transcript grammar and built-in demos.
- `app/static/`: dependency-free browser UI.
- `infra/`, `azure.yaml`, `Dockerfile`: Azure Container Apps remote-build deployment.

Do not silently fall back from a live agent failure. Production is AI-only; demo requests require the explicit `ALLOW_DEMO_MODE=true` development flag.

## Commands

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Before any `azd` command, set `AZURE_DEV_USER_AGENT=microsoft_foundry_skill` for that process. Deploy with `azd up --no-prompt`; `azure.yaml` uses an ACR remote build, so local Docker is not required.

## Completion criteria

1. All seven samples parse and expose 3–5 speakers.
2. Both disjoint live workflows produce Korean-dominant, contract-valid reports; direct quotations retain their source language.
3. Each mode uses exactly its three named Copilot agents through a real Agent Framework workflow.
4. Tests and Ruff pass, `/health` returns 200, and the public URL supports the golden path without login.
5. Documentation describes only behavior present in the current code.
6. The deployment uses a raw `*.azurecontainerapps.io` URL and the remote SHA contains root `PRD.md` and `TRD.md`.
