# Use a standard Python image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libstdc++6 \
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

# Start command using Gunicorn
CMD ["sh", "-c", "gunicorn -w 4 -b 0.0.0.0:$PORT api_server:app"]
