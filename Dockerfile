# Install uv
FROM ghcr.io/astral-sh/uv:0.4.29 AS uv
FROM python:3.12-slim AS builder
COPY --from=uv /uv /uvx /bin/

# Change the working directory to the `app` directory
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable

# Copy the project into the intermediate image
COPY . /app

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

FROM python:3.12-slim

# Set environment variables (e.g., set Python to run in unbuffered mode)
ENV PYTHONUNBUFFERED=1

# Install uv in the final image
COPY --from=uv /uv /uvx /bin/

# Copy the application code (including the virtual environment)
COPY --from=builder /app /app

# Set working directory
WORKDIR /app

EXPOSE 8000

# Use uv run to execute the application
CMD ["uv", "run", "python", "-m", "chainlit", "run", "main.py", "--host", "0.0.0.0", "--port", "8080"]