# Playbook Tools

Playbook Tools is a deterministic AI workflow runtime that executes structured
tool chains with strict schema validation, verification passes, and full execution traceability.

This project is built as a systems engineering portfolio piece focused on
architectural discipline rather than product features.

---

## Why Playbook Tools?

Most AI applications today are thin wrappers around LLM APIs.

Playbook Tools is designed as a structured workflow execution engine that:

- Converts tasks into explicit, linear workflow steps
- Executes tools sequentially through a registered tool registry
- Enforces strict JSON schema validation on all tool inputs and outputs
- Maintains intermediate state across steps
- Logs every tool invocation and intermediate artifact
- Performs verification passes to reduce hallucination and unsupported claims
- Produces both structured JSON outputs and human-readable reports
- Tracks execution traces, timing, and cost metrics
- Supports document ingestion (text-based PDFs + OCR for scanned documents)

The system prioritizes determinism, reproducibility, and observability over autonomy.

---

## Core Concepts

### Workflow Definition

A structured definition of a linear workflow.

In v1:

- Linear execution only
- Maximum 6 steps
- No parallel execution
- No dynamic graph rewriting
- One retry per failed step

---

### Tool Registry

All tools are explicitly registered and bound to strict JSON schemas.

Each tool:

- Declares an input schema
- Declares an output schema
- Validates its output before returning
- Can be retried once on failure

---

### Execution Record

Each workflow execution persists structured metadata including:

- Workflow definition snapshot
- Step-by-step execution logs
- Tool inputs and outputs
- Validation results
- Retry attempts
- Execution timing
- Final structured output
- Human-readable report

Executions are designed to be reproducible and inspectable.

---

### Determinism

Playbook Tools enforces:

- Explicit step definitions
- Controlled model parameters
- Retry limits
- Schema validation gates
- Logged intermediate state

The goal is not maximum autonomy — it is controlled, explainable execution.

---

## Architecture

Playbook Tools is structured as a monorepo:


```
apps/
  web/          - React frontend
services/
  api/          - FastAPI execution service
packages/
  engine/       - Core workflow runtime
  tools/        - Tool implementations
  schemas/      - JSON schema definitions
docs/
infra/
tests/
```


Separation of concerns:

- `engine/` contains the deterministic workflow execution loop
- `tools/` contains schema-bound tool implementations
- `api/` exposes execution endpoints
- `web/` provides a run console interface
- `schemas/` defines versioned JSON schema contracts

---

## Example Execution Flow

1. User uploads document(s)
2. User submits a task query
3. A structured workflow definition is constructed
4. The engine executes steps sequentially:
   - Retrieve relevant document chunks
   - Extract structured data
   - Compute derived values
   - Verify claims against source citations
5. Execution metadata is recorded
6. The system returns:
   - Structured JSON output
   - Human-readable summary report

---

## Current Status

🚧 In active development.

Planned milestones:

- [ ] Define workflow definition schema
- [ ] Implement core engine execution loop
- [ ] Tool registry abstraction
- [ ] Execution record persistence
- [ ] Verification pass
- [ ] Deterministic configuration controls
- [ ] Document ingestion with OCR support
- [ ] Frontend run console UI
- [ ] CI/CD pipeline

---

## Local Development (Planned)

Clone repository:
```
git clone https://github.com/hwale/playbook-tools.git
cd playbook-tools
```
Backend:
```
cd services/api
pip install -r requirements.txt
uvicorn main:app --reload
```
Frontend:
```
cd apps/web
npm install
npm run dev
```

---

## Design Philosophy

Playbook Tools is intentionally constrained.

It is NOT:

- A general agent framework
- A multi-branch workflow engine
- A LangGraph or Airflow clone
- An autonomous system

It is a minimal, architecturally disciplined AI workflow runtime built to demonstrate:

- Structured reasoning
- Tool orchestration
- Schema enforcement
- Verification loops
- Execution traceability
- Systems-level thinking

---

## License

MIT
