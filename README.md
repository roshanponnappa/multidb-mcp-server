# Multi-Database MCP Server

An MCP (Model Context Protocol) server that provides tools to access multiple databases simultaneously. The server runs in Docker and supports querying multiple databases of different types in parallel. This server was inspired by needs to compare databases or support migrations.

## Features

- **Multiple Database Types**: Support for PostgreSQL, MySQL/MariaDB, SQL Server, and SQLite
- **Multiple Database Support**: Connect to and query multiple databases simultaneously (even different types)
- **Parallel Queries**: Execute the same query across multiple databases at once
- **Schema Exploration**: List databases, schemas, tables, and describe table structures
- **Dockerized**: Runs in a Docker container for easy deployment
- **Connection Pooling**: Efficient connection management for all database types
- **Flexible Configuration**: Organize databases by type

## Available Tools

1. **list_databases** - List all configured database connections
2. **query_database** - Execute a SQL query on a specific database
3. **list_tables** - List all tables in a database schema
4. **describe_table** - Get detailed schema information for a table
5. **list_schemas** - List all schemas in a database
6. **query_multiple_databases** - Execute the same query on multiple databases simultaneously

## Setup

### 1. Create Database Configuration

Copy the example configuration file and edit it with your database credentials:

```bash
cp databases.json.example databases.json
```

Edit `databases.json` with your database connection details. Organize databases by type at the root level:

```json
{
  "postgresql": {
    "postgres_db": {
      "host": "localhost",
      "port": 5432,
      "user": "postgres",
      "password": "your_password",
      "database": "database1"
    },
    "another_postgres": {
      "host": "remote.example.com",
      "port": 5432,
      "user": "admin",
      "password": "secret",
      "database": "production"
    }
  },
  "mysql": {
    "mysql_db": {
      "host": "localhost",
      "port": 3306,
      "user": "root",
      "password": "your_password",
      "database": "mydatabase"
    }
  },
  "sqlserver": {
    "sqlserver_db": {
      "host": "localhost",
      "port": 1433,
      "user": "sa",
      "password": "your_password",
      "database": "MyDatabase"
    }
  },
  "sqlite": {
    "sqlite_db": {
      "database": "/path/to/database.db"
    }
  }
}
```

### Supported Database Types

- **PostgreSQL** (`"postgresql"`, `"postgres"`, or `"pg"`)
- **MySQL/MariaDB** (`"mysql"` or `"mariadb"`)
- **SQL Server** (`"sqlserver"`, `"mssql"`, or `"sql server"`)
- **SQLite** (`"sqlite"` or `"sqlite3"`)

### 2. Build and Run with Docker Compose

```bash
docker-compose up --build
```

### 3. Build and Run with Docker

```bash
# Build the image
docker build -t multidb-mcp-server .

# Run the container
docker run -it \
  -v $(pwd)/databases.json:/app/databases.json:ro \
  multidb-mcp-server
```

### 4. Docker Connection Tips

When configuring database connections from within Docker, keep these tips in mind:

#### Network Connections (PostgreSQL, MySQL, SQL Server)

- **Accessing host machine databases**: Use `host.docker.internal` as the hostname (Windows/Mac) or `172.17.0.1` (Linux)
- **Accessing other containers**: Use the container name or service name from `docker-compose.yml`
- **Accessing remote databases**: Use the actual hostname or IP address

**Example for accessing PostgreSQL on host machine:**
```json
{
  "postgresql": {
    "local_db": {
      "host": "host.docker.internal",
      "port": 5432,
      "user": "postgres",
      "password": "password",
      "database": "mydb"
    }
  }
}
```

**Example for accessing database in another Docker container:**
```json
{
  "postgresql": {
    "container_db": {
      "host": "postgres-container",
      "port": 5432,
      "user": "postgres",
      "password": "password",
      "database": "mydb"
    }
  }
}
```

**Example for accessing SQL Server on host machine:**
```json
{
  "sqlserver": {
    "sqlserver_db": {
      "host": "host.docker.internal",
      "port": 1433,
      "user": "sa",
      "password": "password",
      "database": "MyDatabase"
    }
  }
}
```

**Note for SQL Server**: Ensure that SQL Server is configured to accept TCP/IP connections and that the SQL Server Browser service is running if using named instances. The default port is 1433.

#### File Paths (SQLite)

- **SQLite databases on host**: Mount the directory containing the database file as a volume and use the container path
- **SQLite databases in container**: Use absolute paths within the container

**Example Docker run command with SQLite volume:**
```bash
docker run -it \
  -v $(pwd)/databases.json:/app/databases.json:ro \
  -v $(pwd)/data:/app/data:ro \
  multidb-mcp-server
```

**Example SQLite configuration:**
```json
{
  "sqlite": {
    "local_db": {
      "database": "/app/data/mydatabase.db"
    }
  }
}
```

**Note**: The path `/app/data/mydatabase.db` is the path inside the container, which maps to `./data/mydatabase.db` on your host machine via the volume mount.

## Usage

The server communicates via stdio using the MCP protocol. Connect your MCP client to the Docker container's stdio streams.

### Example MCP Client Configuration

If using with an MCP client, configure it to connect to the Docker container:

```json
{
  "mcpServers": {
    "multidb": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "-v",
        "[YOUR/PATH]/databases.json:/app/databases.json:ro",
        "multidb-mcp-server"
      ]
    }
  }
}
```

## Tool Examples

### List All Databases

```json
{
  "tool": "list_databases",
  "arguments": {}
}
```

### Query a Single Database

```json
{
  "tool": "query_database",
  "arguments": {
    "database_name": "db1",
    "query": "SELECT * FROM users LIMIT 10"
  }
}
```

### List Tables

```json
{
  "tool": "list_tables",
  "arguments": {
    "database_name": "db1",
    "schema": "public"
  }
}
```

### Describe a Table

```json
{
  "tool": "describe_table",
  "arguments": {
    "database_name": "db1",
    "table_name": "users",
    "schema": "public"
  }
}
```

### Query Multiple Databases Simultaneously

You can query multiple databases of different types simultaneously:

```json
{
  "tool": "query_multiple_databases",
  "arguments": {
    "database_names": ["db1", "db2", "sqlserver_db"],
    "query": "SELECT COUNT(*) as total FROM users"
  }
}
```

**Note**: When querying multiple databases of different types, ensure the SQL syntax is compatible across all database types, or use database-specific queries for each database separately.

## Development

### Local Development (without Docker)

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variable:
```bash
export DB_CONFIG_PATH=./databases.json
```

3. Run the server:
```bash
python server.py
```

## Database-Specific Notes

### PostgreSQL
- Default port: 5432
- Default schema: `public`
- Uses `asyncpg` for async operations

### MySQL/MariaDB
- Default port: 3306
- Schema parameter is optional (uses current database)
- Uses `aiomysql` for async operations

### SQL Server
- Default port: 1433
- Default schema: `dbo`
- Requires ODBC Driver 17 for SQL Server (installed in Docker image)
- Uses `pyodbc` with asyncio wrapper
- **Important**: SQL Server must be configured to accept TCP/IP connections
- For named instances, ensure SQL Server Browser service is running
- Use `host.docker.internal` to connect to SQL Server on the host machine from Docker

### SQLite
- No network connection required
- Use `database` field to specify file path (or `:memory:` for in-memory)
- Default schema: `main`
- Uses `aiosqlite` for async operations

## Security Notes

- **Never commit `databases.json`** - It contains sensitive credentials
- Use environment variables or secrets management in production
- Consider using SSL/TLS connections for remote databases
- Limit network access to the Docker container
- For SQLite, ensure file paths are secure and accessible

## Troubleshooting

### Connection Issues

- Verify database credentials in `databases.json`
- Ensure databases are accessible from the Docker container
- Check network connectivity (use `docker network` for container-to-container communication)

### Permission Issues

- Ensure the `databases.json` file has proper read permissions
- Check that the Docker volume mount is correct

## License

MIT
