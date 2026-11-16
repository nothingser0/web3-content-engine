FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=Asia/Jakarta

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and directories
COPY src/ ./src/
COPY tools/ ./tools/
COPY prompts/ ./prompts/
COPY data/ ./data/
COPY scheduler.py .
COPY run_daily_auto.py .
COPY run_batch_5x_auto.py .
COPY run_manual.py .
COPY run_twitter.py .

# Create directories for runtime output and logs
RUN mkdir -p output logs

# Default command: run internal scheduler daemon
CMD ["python", "scheduler.py"]
