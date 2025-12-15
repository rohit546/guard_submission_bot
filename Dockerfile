# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright and Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    fonts-unifont \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Note: We skip 'playwright install-deps' because:
# 1. We already install all necessary system dependencies above
# 2. Some font packages (ttf-ubuntu-font-family, ttf-unifont) may not be available
#    in newer Debian versions, causing build failures
# 3. The manually installed dependencies are sufficient for Chromium to run

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs sessions traces debug

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV BROWSER_HEADLESS=true
ENV WEBHOOK_HOST=0.0.0.0
ENV WEBHOOK_PORT=8080
ENV PORT=8080

# Expose webhook port
EXPOSE 8080
# Expose remote debugging port (9222) if needed for debugging
EXPOSE 9222

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health', timeout=5)" || exit 1

# Run webhook server with gunicorn for production
CMD gunicorn --bind 0.0.0.0:8080 --workers 1 --threads 4 --timeout 300 --access-logfile - --error-logfile - --preload webhook_server:app

