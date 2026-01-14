FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    unixodbc-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .
COPY db_adapters.py .

# Create directory for database configuration
RUN mkdir -p /app

# Set environment variable for config path
ENV DB_CONFIG_PATH=/app/databases.json

# Run the server
CMD ["python", "server.py"]
