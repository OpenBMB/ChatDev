# ---- Builder: install deps with compilers and uv ----
FROM python:3.12-slim AS builder
ARG DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# System deps required to build Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    build-essential \
    python3-dev \
    libcairo2-dev \
 && rm -rf /var/lib/apt/lists/*

# Install uv just for dependency resolution/install
RUN pip install --no-cache-dir uv

# Install the project virtualenv outside /app so bind-mounts don't hide it
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Copy dependency files first to maximize cache
COPY pyproject.toml ./
# reproducible builds:
COPY uv.lock ./

# Create the project virtualenv and install deps
RUN uv sync --no-cache --frozen

# ---- Runtime: minimal image with only runtime libs + app ----
FROM python:3.12-slim AS runtime
ARG DEBIAN_FRONTEND=noninteractive
ARG BACKEND_BIND=0.0.0.0

WORKDIR /app

# Install only runtime system libraries (no compilers)
# Keep libcairo if your deps need it; remove if unnecessary
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
 && rm -rf /var/lib/apt/lists/*

# Copy the prebuilt virtualenv from the builder
COPY --from=builder /opt/venv /opt/venv

# Copy the rest of the application code
COPY . .

# Use the venv Python by default and keep Python output unbuffered.
# Bake default bind/port into the image; can be overridden at runtime.
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BACKEND_BIND=${BACKEND_BIND}

# Drop privileges
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# EXPOSE is informational; compose controls published ports
EXPOSE 6400

# Command to run the backend server, parameterized by env
CMD ["sh", "-c", "python server_main.py --port 6400 --host ${BACKEND_BIND:-0.0.0.0}"]
