FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app
COPY apps/api/pyproject.toml /app/apps/api/pyproject.toml
COPY agents /app/agents
COPY tools /app/tools
WORKDIR /app/apps/api
RUN pip install --no-cache-dir -e ".[dev]"
COPY apps/api /app/apps/api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
