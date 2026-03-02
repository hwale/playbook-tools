FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /repo

# Copy only dependency manifests first (better caching)
COPY services/api/pyproject.toml /repo/services/api/pyproject.toml
COPY packages/schemas/pyproject.toml /repo/packages/schemas/pyproject.toml

# Copy source code
COPY services/api /repo/services/api
COPY packages/schemas /repo/packages/schemas

# Install packages (schemas first, then api)
RUN pip install --no-cache-dir -e /repo/packages/schemas \
    && pip install --no-cache-dir -e /repo/services/api

EXPOSE 8000

WORKDIR /repo/services/api

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]