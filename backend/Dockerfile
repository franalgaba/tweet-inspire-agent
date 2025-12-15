FROM python:3.12-slim

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (without cache mount for Railway compatibility)
RUN uv sync --locked --no-install-project

# Copy the rest of the application code
COPY . /app

# Install the project itself
RUN uv sync --locked

# Expose port
EXPOSE 8000

# Run the application using uvicorn with dual-stack binding for Railway
# Uses :: to bind to both IPv4 and IPv6 per Railway docs
CMD ["/app/.venv/bin/uvicorn", "twitter_agent.api.main:app", "--host", "::", "--port", "8000"]

