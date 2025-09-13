# Repology MCP Server

A Model Context Protocol (MCP) server that provides access to the [Repology](https://repology.org) package repository data through a standardized interface.

## Features

This MCP server exposes the following tools:

- **search_projects**: Search for projects by name
- **get_project**: Get detailed information about a specific project
- **list_projects**: List projects with optional filtering
- **get_repository_problems**: Get problems reported for repositories
- **get_maintainer_problems**: Get problems reported for specific maintainers

## Installation

### Using uv (recommended)

```bash
# Install dependencies
uv sync

# Install in development mode
uv pip install -e .
```

### Using pip

```bash
pip install -e .
```

## Usage

### As a standalone server

```bash
# Run with stdio transport (for Claude Desktop, etc.)
repology-mcp-server

# Run with HTTP transport
repology-mcp-server --transport http --port 8000
```

### With Claude Desktop

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "repology": {
      "command": "uv",
      "args": ["run", "repology-mcp-server"]
    }
  }
}
```

### With Docker for Claude Desktop

If you prefer using Docker:

```json
{
  "mcpServers": {
    "repology": {
      "command": "./docker-run.sh",
      "args": ["stdio"],
      "cwd": "/path/to/repology-mcp-server"
    }
  }
}
```

### As a development server

```bash
# Run in development mode with MCP inspector
uv run mcp dev src/repology_mcp/server.py
```

### Using Docker

```bash
# Build the Docker image
./docker-run.sh build

# Run with stdio transport (for MCP clients like Claude Desktop)
./docker-run.sh stdio

# Run with HTTP transport on port 8000
./docker-run.sh http

# Run with SSE transport on port 8001  
./docker-run.sh sse

# Using docker-compose
docker-compose up repology-mcp-http    # HTTP transport
docker-compose up repology-mcp-sse     # SSE transport (with profile)
```

## Development

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd repology-mcp-server

# Install development dependencies
uv sync --extra dev
```

### Running tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=repology_mcp --cov-report=html

# Run specific test file
uv run pytest tests/test_client.py -v
```

### Code formatting

```bash
# Format code
uv run black src tests
uv run isort src tests

# Type checking
uv run mypy src
```

## API Reference

### Tools

#### search_projects
Search for projects by name substring.

**Parameters:**
- `query` (string): Search term to match against project names
- `limit` (integer, optional): Maximum number of results (default: 10, max: 100)

#### get_project
Get detailed package information for a specific project.

**Parameters:**
- `project_name` (string): Exact name of the project to retrieve

#### list_projects  
List projects with optional filtering.

**Parameters:**
- `start_from` (string, optional): Project name to start listing from
- `limit` (integer, optional): Maximum number of results (default: 10, max: 200)
- `maintainer` (string, optional): Filter by maintainer email
- `category` (string, optional): Filter by category
- `inrepo` (string, optional): Filter by repository presence
- `notinrepo` (string, optional): Filter by repository absence

#### get_repository_problems
Get problems reported for a specific repository.

**Parameters:**
- `repository` (string): Repository name (e.g., "freebsd", "debian")
- `start_from` (string, optional): Project name to start from for pagination

#### get_maintainer_problems  
Get problems reported for packages maintained by a specific person.

**Parameters:**
- `maintainer` (string): Maintainer email address
- `repository` (string, optional): Limit to specific repository
- `start_from` (string, optional): Project name to start from for pagination

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request