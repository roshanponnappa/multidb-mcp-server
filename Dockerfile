FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and Microsoft ODBC driver (install before pip)
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    apt-transport-https \
    ca-certificates \
    lsb-release \
    gcc \
    g++ \
    unixodbc-dev \
    unixodbc \
    postgresql-client \
    && curl -sSL -O https://packages.microsoft.com/config/debian/$(grep VERSION_ID /etc/os-release | cut -d '"' -f 2 | cut -d '.' -f 1)/packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb \
    && rm packages-microsoft-prod.deb \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 mssql-tools18 libgssapi-krb5-2 \
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
