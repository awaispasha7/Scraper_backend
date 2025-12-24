# Use a standard Python image
FROM python:3.11-slim

# Install system dependencies for Selenium/Chromium
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libstdc++6 \
    chromium \
    chromium-driver \
    libnss3 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port Railway provides (default is often 8080, but Railway sets $PORT)
EXPOSE 8080

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Start command using Gunicorn (using 1 worker to maintain in-memory state consistency)
CMD ["sh", "-c", "gunicorn -w 1 -b 0.0.0.0:$PORT api_server:app"]
