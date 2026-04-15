FROM python:3.11-slim

# Install system dependencies (FFmpeg is required)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install latest yt-dlp from master to ensure frequent updates work
# This overwrites the one from requirements.txt if needed
RUN pip install --no-cache-dir -U --force-reinstall https://github.com/yt-dlp/yt-dlp/archive/master.zip

# Copy application code
COPY . .

# Create temp directory for downloads
RUN mkdir -p /tmp/vidgetnow_downloads && chmod 777 /tmp/vidgetnow_downloads

# Environment variables
ENV PORT=5000
ENV FLASK_APP=app.py

# Run with Gunicorn (Production Server)
# Workers = 2 * CPU + 1, timeouts increased for long downloads
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 300 app:app
