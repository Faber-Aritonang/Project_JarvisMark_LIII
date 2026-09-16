# ─── Dodol Docker Image ───────────────────────────────────────────────────────
# Build:   docker build -t dodol .
# Run:     docker run -p 8000:8000 -v dodol-data:/app/config dodol
#
# Note: Voice features (microphone/speaker) require host audio access.
#       Dashboard-only mode works headless.

FROM python:3.12-slim

LABEL maintainer="Dodol Project"
LABEL description="Dodol — Cross-platform personal AI assistant"

# System deps for opencv, audio, and GUI libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libportaudio2 \
    portaudio19-dev \
    libxkbcommon0 \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libdbus-1-3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer)
COPY pyproject.toml readme.md ./
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY actions/ actions/
COPY core/ core/
COPY memory/ memory/
COPY dashboard/ dashboard/
COPY plugins/ plugins/
COPY config/ config/
COPY main.py install.py ./

# Create data directories
RUN mkdir -p /app/config /app/logs /app/data

# Persist config and logs
VOLUME ["/app/config", "/app/logs"]

# Dashboard port
EXPOSE 8000

# Health check — dashboard responds on /
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

ENTRYPOINT ["python", "main.py"]
