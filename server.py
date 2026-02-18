#!/usr/bin/env python3
"""
MCP Server for Multiple Databases
Supports simultaneous access to multiple database types: PostgreSQL, MySQL, SQL Server, and SQLite
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool
import mcp.types as types

from db_adapters import get_adapter, DatabaseAdapter


class MultiDatabaseMCPServer:
    """MCP Server that manages multiple database connections of different types"""
    
    def __init__(self):
        self.server = Server("multidb")
        self.connections: Dict[str, Any] = {}
        self.adapters: Dict[str, DatabaseAdapter] = {}
        self.config: Dict[str, Any] = {}
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup MCP tool handlers"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available tools"""
            return [
                Tool(
                    name="list_databases",
                    description="List all configured database connections with their types",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    }
                ),
                Tool(
                    name="query_database",
                    description="Execute a SQL query on a specific database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "database_name": {
                                "type": "string",
                                "description": "Name of the database connection to query"
                            },
                            "query": {
                                "type": "string",
                                "description": "SQL query to execute"
                            }
                        },
                        "required": ["database_name", "query"]
                    }
                ),
                Tool(
                    name="list_tables",
                    description="List all tables in a specific database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "database_name": {
                                "type": "string",
                                "description": "Name of the database connection"
                            },
                            "schema": {
                                "type": "string",
                                "description": "Schema name (default varies by database: 'public' for PostgreSQL, 'dbo' for SQL Server, database name for MySQL, 'main' for SQLite)"
                            }
                        },
                        "required": ["database_name"]
                    }
                ),
                Tool(
                    name="describe_table",
                    description="Get schema information for a specific table",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "database_name": {
                                "type": "string",
                                "description": "Name of the database connection"
                            },
                            "table_name": {
                                "type": "string",
                                "description": "Name of the table to describe"
                            },
                            "schema": {
                                "type": "string",
                                "description": "Schema name (default varies by database type)"
                            }
                        },
                        "required": ["database_name", "table_name"]
                    }
                ),
                Tool(
                    name="list_schemas",
                    description="List all schemas in a specific database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "database_name": {
                                "type": "string",
                                "description": "Name of the database connection"
                            }
                        },
                        "required": ["database_name"]
                    }
                ),
                Tool(
                    name="query_multiple_databases",
                    description="Execute the same query on multiple databases simultaneously",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "database_names": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of database connection names"
                            },
                            "query": {
                                "type": "string",
                                "description": "SQL query to execute on all databases"
                            }
                        },
                        "required": ["database_names", "query"]
                    }
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Handle tool calls"""
            try:
                if name == "list_databases":
                    return await self._list_databases()
                elif name == "query_database":
                    return await self._query_database(
                        arguments["database_name"],
                        arguments["query"]
                    )
                elif name == "list_tables":
                    return await self._list_tables(
                        arguments["database_name"],
                        arguments.get("schema")
                    )
                elif name == "describe_table":
                    return await self._describe_table(
                        arguments["database_name"],
                        arguments["table_name"],
                        arguments.get("schema")
                    )
                elif name == "list_schemas":
                    return await self._list_schemas(arguments["database_name"])
                elif name == "query_multiple_databases":
                    return await self._query_multiple_databases(
                        arguments["database_names"],
                        arguments["query"]
                    )
                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                return [types.TextContent(
                    type="text",
                    text=f"Error: {str(e)}"
                )]
    
    def _get_default_schema(self, db_type: str) -> Optional[str]:
        """Get default schema name based on database type"""
        db_type_lower = db_type.lower()
        if db_type_lower in ["postgres", "postgresql", "pg"]:
            return "public"
        elif db_type_lower in ["sqlserver", "mssql", "sql server"]:
            return "dbo"
        elif db_type_lower in ["mysql", "mariadb"]:
            return None  # MySQL uses database name
        elif db_type_lower in ["sqlite", "sqlite3"]:
            return "main"
        return "public"
    
    async def _ensure_connection(self, db_name: str) -> Tuple[Any, DatabaseAdapter]:
        """Ensure a database connection pool exists and return pool and adapter"""
        await self._load_database_connections()
        
        if db_name not in self.config:
            available = list(self.config.keys())
            raise ValueError(
                f"Database '{db_name}' not found in configuration. "
                f"Available databases: {available}"
            )
        
        if db_name not in self.connections:
            # Try to connect
            db_config = self.config[db_name]
            db_type = db_config.get("type", "postgresql").lower()
            
            try:
                adapter = get_adapter(db_type)
                pool = await adapter.connect(db_config)
                self.connections[db_name] = pool
                self.adapters[db_name] = adapter
            except Exception as e:
                raise ValueError(
                    f"Failed to connect to database '{db_name}': {e}. "
                    f"Please check your connection settings."
                )
        
        return self.connections[db_name], self.adapters[db_name]
    
    def _normalize_config(self, raw_config: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize configuration to flat structure from nested format"""
        normalized = {}
        
        # Config must be nested by database type: { "postgresql": { "db1": {...}, "db2": {...} } }
        known_types = ["postgresql", "postgres", "pg", "mysql", "mariadb", "sqlserver", "mssql", "sql server", "sqlite", "sqlite3"]
        
        for db_type, connections in raw_config.items():
            db_type_normalized = db_type.lower()
            
            # Validate that this is a known database type
            if db_type_normalized not in known_types:
                raise ValueError(
                    f"Unknown database type '{db_type}'. "
                    f"Expected one of: {', '.join(known_types)}. "
                    f"Configuration must be nested by database type."
                )
            
            # Map aliases to standard types
            if db_type_normalized in ["postgres", "pg"]:
                db_type_normalized = "postgresql"
            elif db_type_normalized == "mariadb":
                db_type_normalized = "mysql"
            elif db_type_normalized in ["mssql", "sql server"]:
                db_type_normalized = "sqlserver"
            elif db_type_normalized == "sqlite3":
                db_type_normalized = "sqlite"
            
            if isinstance(connections, dict):
                for db_name, db_config in connections.items():
                    if isinstance(db_config, dict):
                        # Add type to config
                        db_config_with_type = db_config.copy()
                        db_config_with_type["type"] = db_type_normalized
                        normalized[db_name] = db_config_with_type
            else:
                raise ValueError(
                    f"Invalid configuration for database type '{db_type}'. "
                    f"Expected a dictionary of database connections."
                )
        
        return normalized
    
    async def _load_database_connections(self):
        """Load database connections from configuration"""
        config_path = os.getenv("DB_CONFIG_PATH", "/app/databases.json")
        
        try:
            with open(config_path, "r") as f:
                raw_config = json.load(f)
        except FileNotFoundError:
            raise ValueError(f"Database configuration file not found: {config_path}")
        except Exception as e:
            raise ValueError(f"Error reading configuration file: {e}")
        
        # Normalize config to flat structure
        self.config = self._normalize_config(raw_config)
        
        # Pre-connect to databases (optional, can be lazy-loaded)
        for db_name, db_config in self.config.items():
            if db_name not in self.connections:
                db_type = db_config.get("type", "postgresql").lower()
                try:
                    adapter = get_adapter(db_type)
                    pool = await adapter.connect(db_config)
                    self.connections[db_name] = pool
                    self.adapters[db_name] = adapter
                except Exception as e:
                    print(f"Warning: Failed to connect to database '{db_name}': {e}", flush=True)
    
    async def _list_databases(self) -> List[types.TextContent]:
        """List all configured databases"""
        await self._load_database_connections()
        
        # List all configured databases with connection status and type
        db_list = []
        for db_name in self.config.keys():
            status = "connected" if db_name in self.connections else "disconnected"
            db_config = self.config[db_name]
            db_type = db_config.get("type", "postgresql")
            db_list.append({
                "name": db_name,
                "type": db_type,
                "status": status,
                "database": db_config.get("database", db_config.get("path", "unknown"))
            })
        
        result = {
            "databases": db_list,
            "count": len(db_list),
            "connected": len(self.connections)
        }
        
        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    async def _query_database(
        self, 
        database_name: str, 
        query: str
    ) -> List[types.TextContent]:
        """Execute a query on a specific database"""
        pool, adapter = await self._ensure_connection(database_name)
        
        result = await adapter.execute_query(pool, query)
        
        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str)
        )]
    
    async def _list_tables(
        self, 
        database_name: str, 
        schema: Optional[str] = None
    ) -> List[types.TextContent]:
        """List all tables in a database schema"""
        pool, adapter = await self._ensure_connection(database_name)
        
        # Get default schema if not provided
        if schema is None:
            db_config = self.config[database_name]
            db_type = db_config.get("type", "postgresql")
            schema = self._get_default_schema(db_type)
        
        tables = await adapter.list_tables(pool, schema)
        
        result = {
            "database": database_name,
            "schema": schema,
            "tables": tables,
            "count": len(tables)
        }
        
        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    async def _describe_table(
        self, 
        database_name: str, 
        table_name: str, 
        schema: Optional[str] = None
    ) -> List[types.TextContent]:
        """Get schema information for a table"""
        pool, adapter = await self._ensure_connection(database_name)
        
        # Get default schema if not provided
        if schema is None:
            db_config = self.config[database_name]
            db_type = db_config.get("type", "postgresql")
            schema = self._get_default_schema(db_type)
        
        columns = await adapter.describe_table(pool, table_name, schema)
        
        result = {
            "database": database_name,
            "schema": schema,
            "table": table_name,
            "columns": columns
        }
        
        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    async def _list_schemas(self, database_name: str) -> List[types.TextContent]:
        """List all schemas in a database"""
        pool, adapter = await self._ensure_connection(database_name)
        
        schemas = await adapter.list_schemas(pool)
        
        result = {
            "database": database_name,
            "schemas": schemas,
            "count": len(schemas)
        }
        
        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    async def _query_multiple_databases(
        self, 
        database_names: List[str], 
        query: str
    ) -> List[types.TextContent]:
        """Execute the same query on multiple databases simultaneously"""
        tasks = []
        for db_name in database_names:
            tasks.append(self._query_database(db_name, query))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        combined_result = {}
        for i, db_name in enumerate(database_names):
            if isinstance(results[i], Exception):
                combined_result[db_name] = {"error": str(results[i])}
            else:
                # Extract the text content from the result
                result_text = results[i][0].text
                combined_result[db_name] = json.loads(result_text)
        
        return [types.TextContent(
            type="text",
            text=json.dumps(combined_result, indent=2, default=str)
        )]
    
    async def cleanup(self):
        """Close all database connections"""
        for db_name, pool in self.connections.items():
            adapter = self.adapters.get(db_name)
            if adapter:
                await adapter.close(pool)
        self.connections.clear()
        self.adapters.clear()


async def main():
    """Main entry point"""
    server_instance = MultiDatabaseMCPServer()
    
    async with stdio_server() as (read_stream, write_stream):
        await server_instance.server.run(
            read_stream,
            write_stream,
            server_instance.server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
