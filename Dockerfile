# Efficient Dockerfile for Meshbot Weather
FROM python:3.13-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create and set working directory
WORKDIR /app

# Install system dependencies (for serial, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for better caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY meshbot.py ./
COPY settings.yaml ./
COPY modules/ ./modules/
COPY img/ ./img/

# Create a non-root user for security
RUN useradd -m meshbotuser
USER meshbotuser

# Entrypoint
ENTRYPOINT ["python", "meshbot.py"]
