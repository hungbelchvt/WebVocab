# =====================================================================
# WebVocab Production Dockerfile (Python 3.12 Slim)
# Suitable for Render Container Deployment and Local Development
# =====================================================================

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

# Set working directory
WORKDIR /app

# Install minimal OS dependencies for network utilities & health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for container security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose container port (documentation metadata)
EXPOSE 5000

# Start WebVocab using Gunicorn with production configuration
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:create_app()"]
