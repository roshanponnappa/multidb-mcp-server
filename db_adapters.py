#!/usr/bin/env python3
"""
Database adapters for different database types
Provides a unified interface for PostgreSQL, MySQL, SQL Server, and SQLite
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import json


class DatabaseAdapter(ABC):
    """Abstract base class for database adapters"""
    
    @abstractmethod
    async def connect(self, config: Dict[str, Any]) -> Any:
        """Create and return a connection pool"""
        pass
    
    @abstractmethod
    async def execute_query(self, pool: Any, query: str) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dictionaries"""
        pass
    
    @abstractmethod
    async def list_tables(self, pool: Any, schema: str = "public") -> List[Dict[str, Any]]:
        """List all tables in a schema"""
        pass
    
    @abstractmethod
    async def describe_table(self, pool: Any, table_name: str, schema: str = "public") -> List[Dict[str, Any]]:
        """Get schema information for a table"""
        pass
    
    @abstractmethod
    async def list_schemas(self, pool: Any) -> List[str]:
        """List all schemas in the database"""
        pass
    
    @abstractmethod
    async def close(self, pool: Any):
        """Close the connection pool"""
        pass


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL adapter using asyncpg"""
    
    async def connect(self, config: Dict[str, Any]) -> Any:
        import asyncpg
        return await asyncpg.create_pool(
            host=config["host"],
            port=config.get("port", 5432),
            user=config["user"],
            password=config["password"],
            database=config["database"],
            min_size=1,
            max_size=5
        )
    
    async def execute_query(self, pool: Any, query: str) -> List[Dict[str, Any]]:
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]
    
    async def list_tables(self, pool: Any, schema: str = "public") -> List[Dict[str, Any]]:
        query = """
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = $1
            ORDER BY table_name;
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, schema)
            return [{"name": row["table_name"], "type": row["table_type"]} for row in rows]
    
    async def describe_table(self, pool: Any, table_name: str, schema: str = "public") -> List[Dict[str, Any]]:
        query = """
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position;
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, schema, table_name)
            return [
                {
                    "name": row["column_name"],
                    "type": row["data_type"],
                    "nullable": row["is_nullable"] == "YES",
                    "default": row["column_default"],
                    "max_length": row["character_maximum_length"]
                }
                for row in rows
            ]
    
    async def list_schemas(self, pool: Any) -> List[str]:
        query = """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY schema_name;
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [row["schema_name"] for row in rows]
    
    async def close(self, pool: Any):
        await pool.close()


class MySQLAdapter(DatabaseAdapter):
    """MySQL/MariaDB adapter using aiomysql"""
    
    async def connect(self, config: Dict[str, Any]) -> Any:
        import aiomysql
        return await aiomysql.create_pool(
            host=config["host"],
            port=config.get("port", 3306),
            user=config["user"],
            password=config["password"],
            db=config["database"],
            minsize=1,
            maxsize=5
        )
    
    async def execute_query(self, pool: Any, query: str) -> List[Dict[str, Any]]:
        import aiomysql
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query)
                rows = await cur.fetchall()
                return [dict(row) for row in rows]
    
    async def list_tables(self, pool: Any, schema: str = None) -> List[Dict[str, Any]]:
        import aiomysql
        # MySQL uses database name as schema
        if schema:
            query = """
                SELECT table_name as name, 'BASE TABLE' as type
                FROM information_schema.tables
                WHERE table_schema = %s
                ORDER BY table_name;
            """
            params = (schema,)
        else:
            query = """
                SELECT table_name as name, 'BASE TABLE' as type
                FROM information_schema.tables
                WHERE table_schema = database()
                ORDER BY table_name;
            """
            params = ()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                await cur.execute(query)
                rows = await cur.fetchall()
                return [{"name": row["name"], "type": row["type"]} for row in rows]
    
    async def describe_table(self, pool: Any, table_name: str, schema: str = None) -> List[Dict[str, Any]]:
        import aiomysql
        if schema:
            query = """
                SELECT 
                    column_name as name,
                    data_type as type,
                    is_nullable,
                    column_default as default_value,
                    character_maximum_length as max_length
                FROM information_schema.columns
                WHERE table_schema = %s 
                AND table_name = %s
                ORDER BY ordinal_position;
            """
            params = (schema, table_name)
        else:
            query = """
                SELECT 
                    column_name as name,
                    data_type as type,
                    is_nullable,
                    column_default as default_value,
                    character_maximum_length as max_length
                FROM information_schema.columns
                WHERE table_schema = database() 
                AND table_name = %s
                ORDER BY ordinal_position;
            """
            params = (table_name,)
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
                return [
                    {
                        "name": row["name"],
                        "type": row["type"],
                        "nullable": row["is_nullable"] == "YES",
                        "default": row["default_value"],
                        "max_length": row["max_length"]
                    }
                    for row in rows
                ]
    
    async def list_schemas(self, pool: Any) -> List[str]:
        import aiomysql
        query = "SELECT schema_name FROM information_schema.schemata ORDER BY schema_name;"
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                rows = await cur.fetchall()
                return [row[0] for row in rows]
    
    async def close(self, pool: Any):
        pool.close()
        await pool.wait_closed()


class SQLServerAdapter(DatabaseAdapter):
    """SQL Server adapter using pyodbc with asyncio"""
    
    async def connect(self, config: Dict[str, Any]) -> Any:
        import pyodbc
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        # Detect installed ODBC drivers and prefer modern MS drivers
        installed_drivers = [d for d in pyodbc.drivers()]
        preferred = [
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 13 for SQL Server",
            "SQL Server Native Client 11.0"
        ]

        driver_to_use = None
        for pd in preferred:
            if pd in installed_drivers:
                driver_to_use = pd
                break

        if driver_to_use is None:
            # Fall back to any available driver if present
            if installed_drivers:
                driver_to_use = installed_drivers[0]
            else:
                raise ValueError(
                    "No ODBC drivers detected. Install Microsoft ODBC Driver for SQL Server (msodbcsql) in the container."
                )

        # Allow optional TLS/driver options from config (useful for self-signed certs)
        # Config keys:
        #   encrypt: true/false (string or bool) -> sets Encrypt=Yes/No
        #   trust_server_certificate: true/false (string or bool) -> sets TrustServerCertificate=Yes/No
        def _bool(v):
            if isinstance(v, bool):
                return v
            if v is None:
                return None
            return str(v).lower() in ("1", "true", "yes")

        options = []
        encrypt_cfg = _bool(config.get("encrypt"))
        trust_cfg = _bool(config.get("trust_server_certificate"))

        if encrypt_cfg is not None:
            options.append(f"Encrypt={'Yes' if encrypt_cfg else 'No'}")
        if trust_cfg is not None:
            options.append(f"TrustServerCertificate={'Yes' if trust_cfg else 'No'}")

        # Build the connection string with optional driver options
        base = (
            f"DRIVER={{{driver_to_use}}};"
            f"SERVER={config['host']},{config.get('port', 1433)};"
            f"DATABASE={config['database']};"
            f"UID={config['user']};"
            f"PWD={config['password']}"
        )
        connection_string = base + (";" + ";".join(options) if options else "")

        # Store executor for async operations
        executor = ThreadPoolExecutor(max_workers=5)

        def create_connection():
            return pyodbc.connect(connection_string)

        # Create connection pool (simple list-based pool)
        pool = []
        loop = asyncio.get_event_loop()
        for _ in range(5):
            pool.append(await loop.run_in_executor(executor, create_connection))

        return {"pool": pool, "executor": executor, "current": 0}
    
    async def _get_connection(self, pool_obj: Any):
        """Get a connection from the pool (round-robin)"""
        pool = pool_obj["pool"]
        idx = pool_obj["current"]
        pool_obj["current"] = (idx + 1) % len(pool)
        return pool[idx]
    
    async def execute_query(self, pool_obj: Any, query: str) -> List[Dict[str, Any]]:
        conn = await self._get_connection(pool_obj)
        
        def execute():
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            cursor.close()
            return [dict(zip(columns, row)) for row in rows]
        
        return await asyncio.get_event_loop().run_in_executor(pool_obj["executor"], execute)
    
    async def list_tables(self, pool_obj: Any, schema: str = "dbo") -> List[Dict[str, Any]]:
        query = f"""
            SELECT table_name as name, 'BASE TABLE' as type
            FROM information_schema.tables
            WHERE table_schema = '{schema}'
            ORDER BY table_name;
        """
        return await self.execute_query(pool_obj, query)
    
    async def describe_table(self, pool_obj: Any, table_name: str, schema: str = "dbo") -> List[Dict[str, Any]]:
        query = f"""
            SELECT 
                column_name as name,
                data_type as type,
                is_nullable,
                column_default as default_value,
                character_maximum_length as max_length
            FROM information_schema.columns
            WHERE table_schema = '{schema}' AND table_name = '{table_name}'
            ORDER BY ordinal_position;
        """
        rows = await self.execute_query(pool_obj, query)
        return [
            {
                "name": row["name"],
                "type": row["type"],
                "nullable": row["is_nullable"] == "YES",
                "default": row["default_value"],
                "max_length": row["max_length"]
            }
            for row in rows
        ]
    
    async def list_schemas(self, pool_obj: Any) -> List[str]:
        query = "SELECT schema_name FROM information_schema.schemata ORDER BY schema_name;"
        rows = await self.execute_query(pool_obj, query)
        return [row["schema_name"] for row in rows]
    
    async def close(self, pool_obj: Any):
        for conn in pool_obj["pool"]:
            conn.close()
        pool_obj["executor"].shutdown(wait=True)


class SQLiteAdapter(DatabaseAdapter):
    """SQLite adapter using aiosqlite"""
    
    async def connect(self, config: Dict[str, Any]) -> Any:
        import aiosqlite
        
        # SQLite uses file path instead of host
        db_path = config.get("database") or config.get("path", ":memory:")
        
        # Create a simple connection pool (list of connections)
        pool = []
        for _ in range(5):
            conn = await aiosqlite.connect(db_path)
            pool.append(conn)
        
        return {"pool": pool, "current": 0}
    
    async def _get_connection(self, pool_obj: Any):
        """Get a connection from the pool (round-robin)"""
        pool = pool_obj["pool"]
        idx = pool_obj["current"]
        pool_obj["current"] = (idx + 1) % len(pool)
        return pool[idx]
    
    async def execute_query(self, pool_obj: Any, query: str) -> List[Dict[str, Any]]:
        conn = await self._get_connection(pool_obj)
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description] if cursor.description else []
            return [dict(zip(columns, row)) for row in rows]
    
    async def list_tables(self, pool_obj: Any, schema: str = None) -> List[Dict[str, Any]]:
        query = """
            SELECT name, 'BASE TABLE' as type
            FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name;
        """
        rows = await self.execute_query(pool_obj, query)
        return [{"name": row["name"], "type": row["type"]} for row in rows]
    
    async def describe_table(self, pool_obj: Any, table_name: str, schema: str = None) -> List[Dict[str, Any]]:
        conn = await self._get_connection(pool_obj)
        async with conn.execute(f"PRAGMA table_info({table_name})") as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "name": row[1],
                    "type": row[2],
                    "nullable": not row[3],
                    "default": row[4],
                    "max_length": None
                }
                for row in rows
            ]
    
    async def list_schemas(self, pool_obj: Any) -> List[str]:
        # SQLite doesn't have schemas in the traditional sense
        return ["main"]
    
    async def close(self, pool_obj: Any):
        for conn in pool_obj["pool"]:
            await conn.close()


def get_adapter(db_type: str) -> DatabaseAdapter:
    """Factory function to get the appropriate database adapter"""
    db_type_lower = db_type.lower()
    
    if db_type_lower in ["postgres", "postgresql", "pg"]:
        return PostgreSQLAdapter()
    elif db_type_lower in ["mysql", "mariadb"]:
        return MySQLAdapter()
    elif db_type_lower in ["sqlserver", "mssql", "sql server"]:
        return SQLServerAdapter()
    elif db_type_lower in ["sqlite", "sqlite3"]:
        return SQLiteAdapter()
    else:
        raise ValueError(f"Unsupported database type: {db_type}. Supported types: postgresql, mysql, sqlserver, sqlite")
