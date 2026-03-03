# Playbook Tools

Playbook Tools is a structured AI workflow runtime built as a systems engineering portfolio project. The goal is to build a deterministic, schema-driven execution engine for AI workflows — with strong validation, observability, and architectural discipline.

## Current Architecture

The project is organized as a monorepo:

- **`apps/web/`**: React frontend (Vite + TypeScript + Tailwind CSS + daisyUI)
- **`services/api/`**: FastAPI backend
- **`packages/schemas/`**: Versioned Pydantic schema contracts for tools and workflows
- **`.data/`**: Local storage for the vector database and files (ignored by git)

### Key Design Principles

- Versioned schema contracts
- Strict separation of API, schemas, and execution logic
- Runtime validation via Pydantic
- Docker-based development for reproducibility

## Getting Started

### Requirements

- Node.js (Optional, for running `npm` convenience scripts)
- Docker and Docker Compose installed and running

### Environment Setup

Before running the application, you need to create an environment file for the backend API.

1. Create a `.env` file in `services/api/`:
   ```bash
   touch services/api/.env
   ```
2. Add the following required variables to `services/api/.env` (adjust values as needed):
   ```env
   ENVIRONMENT=local
   LOG_LEVEL=debug
   APP_NAME="Playbook Tools API (Local)"
   OPENAI_API_KEY=your_openai_api_key_here
   ```

### Running Locally

You can run the application using either the provided `npm` convenience scripts or using raw `docker compose` commands if you don't have Node.js installed.

1. **Start the development environment**:

   **Using `npm`:**

   ```bash
   npm run dev
   ```

   _(To rebuild the images during startup, use `npm run dev:build`)_

   **Using pure Docker:**

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
   ```

   _(To rebuild the images during startup, append `--build`)_

2. **Access the locally running services**:
   - **Frontend UI**: [http://localhost:5173](http://localhost:5173)
   - **Backend API**: [http://localhost:8000](http://localhost:8000)

3. **Verify the backend health**:

   ```bash
   curl http://localhost:8000/health
   ```

4. **View logs**:

   **Using `npm`:**

   ```bash
   npm run logs
   ```

   **Using pure Docker:**

   ```bash
   docker compose logs -f --tail=200
   ```

5. **Stop the development environment**:

   **Using `npm`:**

   ```bash
   npm run dev:down
   ```

   **Using pure Docker:**

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml down
   ```

### Running in Production

To run the production deployment setup:

- **Start**: `npm run prod` or `docker compose up -d`
- **Rebuild**: `npm run prod:build` or `docker compose up -d --build`
- **Stop**: `npm run prod:down` or `docker compose down`

## License

MIT
