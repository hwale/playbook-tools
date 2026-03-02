Playbook Tools

Playbook Tools is a structured AI workflow runtime built as a systems engineering portfolio project.

The goal is to build a deterministic, schema-driven execution engine for AI workflows — with strong validation, observability, and architectural discipline.

This repository currently contains:

A Dockerized FastAPI backend

A Vite + React frontend

A versioned schemas package

A clean monorepo structure

The foundation for tool-based workflow execution

Initial RAG (Retrieval-Augmented Generation) infrastructure

Current Architecture

Monorepo structure:

```
playbook-tools/
  apps/
    web/              # React frontend (Vite + TS + Tailwind + daisyUI)
  services/
    api/              # FastAPI backend
  packages/
    schemas/          # Versioned Pydantic schema contracts
  .data/              # Local storage (ignored by git)
  docker-compose.yml
```

Key design principles:

Versioned schema contracts (v1)

Runtime validation via Pydantic

Strict separation of API, schemas, and execution logic

Docker-based development for reproducibility

What Exists Today
Backend (FastAPI)

/health endpoint

/config endpoint

Versioned Pydantic schemas (installed as a local package)

Dockerized dev environment

Editable installs for monorepo packages

Ready for tool registry + workflow engine layer

Frontend (React)

Vite dev server

Dockerized

API proxy via /api

Health endpoint displayed in UI

Schema Package

packages/schemas contains:

WorkflowSpecV1

ToolSpecV1

RunRecordV1

StepRecordV1

FinalOutputV1

These define the contract for:

Workflow definitions

Tool interfaces

Execution records

All schema validation occurs at runtime via Pydantic.

Running Locally (Docker)
Requirements

Docker Desktop running

Docker Compose available

Start the system

From repo root:

```
docker compose up -d --build
```

Backend:

```
http://localhost:8000
```

Frontend:

```
http://localhost:5173
```

Verify backend

```
curl http://localhost:8000/health
```

Development Notes

The API image is built from the repo root to support monorepo packages.

packages/schemas is installed in editable mode during image build.

.data/ is mounted for local storage (PDFs, vector DB, etc).

Python packaging metadata (\*.egg-info) is gitignored.

Design Direction

Playbook Tools is evolving toward:

A deterministic linear workflow engine

Tool registry abstraction

Strict JSON schema validation for tool input/output

Execution trace recording

Verification pass layer

Structured final outputs

RAG-based document workflows

Production deployability via Docker

The system prioritizes:

Reproducibility

Observability

Deterministic behavior

Strong architectural boundaries

It is intentionally constrained — not an autonomous agent framework.

Next Milestones

Implement tool registry pattern

Add RAG tools (PDF extract, chunk, embed, retrieve)

Build minimal workflow runner

Add structured execution logging

Prepare production deployment (EC2 + Docker)

Introduce CI (GitHub Actions)

License

MIT
