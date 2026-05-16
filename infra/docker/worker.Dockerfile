FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app
COPY apps/api/pyproject.toml /app/apps/api/pyproject.toml
COPY agents /app/agents
COPY tools /app/tools
WORKDIR /app/apps/api
RUN pip install --no-cache-dir -e ".[dev,tooluniverse]"
COPY apps/api /app/apps/api
CMD ["python", "-m", "app.services.queue_worker"]

