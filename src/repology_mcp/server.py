"""MCP server implementation for Repology API."""

import argparse
import json
from typing import List, Dict, Optional
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession

from .client import RepologyClient, RepologyAPIError, RepologyNotFoundError
from .models import Package, Problem


# Application context for shared resources
class AppContext:
    """Application context with typed dependencies."""

    def __init__(self, repology_client: RepologyClient):
        self.repology_client = repology_client


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with shared Repology client."""
    # Initialize Repology client on startup
    repology_client = RepologyClient()
    try:
        yield AppContext(repology_client=repology_client)
    finally:
        # Cleanup on shutdown
        await repology_client.close()


# Create FastMCP server with lifespan management
mcp = FastMCP("Repology API Server", lifespan=app_lifespan)


def _packages_to_json(packages: List[Package]) -> str:
    """Convert packages list to formatted JSON string."""
    return json.dumps([pkg.model_dump() for pkg in packages], indent=2)


def _problems_to_json(problems: List[Problem]) -> str:
    """Convert problems list to formatted JSON string."""
    return json.dumps([prob.model_dump() for prob in problems], indent=2)


def _filter_packages_by_repo(packages: List[Package], repo: str) -> List[Package]:
    """Filter packages to only include those from a specific repository."""
    return [pkg for pkg in packages if pkg.repo == repo]


def _filter_project_packages_by_repo(
    project_packages: Dict[str, List[Package]], repo: str
) -> Dict[str, List[Package]]:
    """Filter project packages to only include those from a specific repository."""
    filtered = {}
    for project_name, packages in project_packages.items():
        filtered_packages = _filter_packages_by_repo(packages, repo)
        if (
            filtered_packages
        ):  # Only include projects that have packages in the specified repo
            filtered[project_name] = filtered_packages
    return filtered


def _project_packages_to_json(project_packages: Dict[str, List[Package]]) -> str:
    """Convert project packages dict to formatted JSON string."""
    result = {}
    for project_name, packages in project_packages.items():
        result[project_name] = [pkg.model_dump() for pkg in packages]
    return json.dumps(result, indent=2)


@mcp.tool()
async def search_projects(
    query: str,
    limit: int = 10,
    maintainer: Optional[str] = None,
    category: Optional[str] = None,
    inrepo: Optional[str] = None,
    notinrepo: Optional[str] = None,
    ctx: Context[ServerSession, AppContext] = None,
) -> str:
    """Search for projects by name substring.

    Args:
        query: Search term to match against project names
        limit: Maximum number of results (default: 10, max: 100)
        maintainer: Optional maintainer email filter
        category: Optional category filter
        inrepo: Optional repository presence filter
        notinrepo: Optional repository absence filter

    Returns:
        JSON formatted list of matching projects with their packages
    """
    if limit > 100:
        limit = 100

    try:
        client = ctx.request_context.lifespan_context.repology_client

        # Build filters
        filters = {}
        if maintainer:
            filters["maintainer"] = maintainer
        if category:
            filters["category"] = category
        if inrepo:
            filters["inrepo"] = inrepo
        if notinrepo:
            filters["notinrepo"] = notinrepo

        project_packages = await client.search_projects(
            query=query, limit=limit, **filters
        )

        # Apply client-side repository filtering if inrepo is specified
        if inrepo and project_packages:
            project_packages = _filter_project_packages_by_repo(
                project_packages, inrepo
            )

        if not project_packages:
            return json.dumps({"message": f"No projects found matching '{query}'"})

        return _project_packages_to_json(project_packages)

    except RepologyAPIError as e:
        await ctx.error(f"Repology API error: {e}")
        return json.dumps({"error": str(e)})
    except Exception as e:
        await ctx.error(f"Unexpected error searching projects: {e}")
        return json.dumps({"error": f"Unexpected error: {e}"})


@mcp.tool()
async def get_project(
    project_name: str,
    repository: Optional[str] = None,
    ctx: Context[ServerSession, AppContext] = None,
) -> str:
    """Get detailed information about a specific project.

    Args:
        project_name: Exact name of the project to retrieve
        repository: Optional repository filter to show only packages from that repository

    Returns:
        JSON formatted list of packages for the project
    """
    try:
        client = ctx.request_context.lifespan_context.repology_client
        packages = await client.get_project(project_name)

        if not packages:
            return json.dumps(
                {"message": f"No packages found for project '{project_name}'"}
            )

        # Apply client-side repository filtering if repository is specified
        if repository:
            packages = _filter_packages_by_repo(packages, repository)
            if not packages:
                return json.dumps(
                    {
                        "message": f"No packages found for project '{project_name}' in repository '{repository}'"
                    }
                )

        return _packages_to_json(packages)

    except RepologyNotFoundError:
        return json.dumps({"error": f"Project '{project_name}' not found"})
    except RepologyAPIError as e:
        await ctx.error(f"Repology API error: {e}")
        return json.dumps({"error": str(e)})
    except Exception as e:
        await ctx.error(f"Unexpected error getting project: {e}")
        return json.dumps({"error": f"Unexpected error: {e}"})


@mcp.tool()
async def list_projects(
    start_from: Optional[str] = None,
    limit: int = 10,
    maintainer: Optional[str] = None,
    category: Optional[str] = None,
    inrepo: Optional[str] = None,
    notinrepo: Optional[str] = None,
    repos: Optional[str] = None,
    families: Optional[str] = None,
    newest: Optional[bool] = None,
    outdated: Optional[bool] = None,
    problematic: Optional[bool] = None,
    ctx: Context[ServerSession, AppContext] = None,
) -> str:
    """List projects with optional filtering.

    Args:
        start_from: Project name to start listing from
        limit: Maximum number of results (default: 10, max: 200)
        maintainer: Filter by maintainer email
        category: Filter by category
        inrepo: Filter by repository presence
        notinrepo: Filter by repository absence
        repos: Filter by number of repositories (e.g., "1", "5-", "-5", "2-7")
        families: Filter by number of repository families
        newest: Show only newest projects
        outdated: Show only outdated projects
        problematic: Show only problematic projects

    Returns:
        JSON formatted dictionary of projects and their packages
    """
    if limit > 200:
        limit = 200

    try:
        client = ctx.request_context.lifespan_context.repology_client

        # Build filters
        filters = {}
        if maintainer:
            filters["maintainer"] = maintainer
        if category:
            filters["category"] = category
        if inrepo:
            filters["inrepo"] = inrepo
        if notinrepo:
            filters["notinrepo"] = notinrepo
        if repos:
            filters["repos"] = repos
        if families:
            filters["families"] = families
        if newest:
            filters["newest"] = "1"
        if outdated:
            filters["outdated"] = "1"
        if problematic:
            filters["problematic"] = "1"

        project_packages = await client.list_projects(
            start_from=start_from, limit=limit, **filters
        )

        # Apply client-side repository filtering if inrepo is specified
        if inrepo and project_packages:
            project_packages = _filter_project_packages_by_repo(
                project_packages, inrepo
            )

        if not project_packages:
            return json.dumps({"message": "No projects found matching the criteria"})

        return _project_packages_to_json(project_packages)

    except RepologyAPIError as e:
        await ctx.error(f"Repology API error: {e}")
        return json.dumps({"error": str(e)})
    except Exception as e:
        await ctx.error(f"Unexpected error listing projects: {e}")
        return json.dumps({"error": f"Unexpected error: {e}"})


@mcp.tool()
async def get_repository_problems(
    repository: str,
    start_from: Optional[str] = None,
    ctx: Context[ServerSession, AppContext] = None,
) -> str:
    """Get problems reported for a specific repository.

    Args:
        repository: Repository name (e.g., "freebsd", "debian")
        start_from: Project name to start from for pagination

    Returns:
        JSON formatted list of problems for the repository
    """
    try:
        client = ctx.request_context.lifespan_context.repology_client
        problems = await client.get_repository_problems(
            repository=repository, start_from=start_from
        )

        if not problems:
            return json.dumps(
                {"message": f"No problems found for repository '{repository}'"}
            )

        return _problems_to_json(problems)

    except RepologyNotFoundError:
        return json.dumps({"error": f"Repository '{repository}' not found"})
    except RepologyAPIError as e:
        await ctx.error(f"Repology API error: {e}")
        return json.dumps({"error": str(e)})
    except Exception as e:
        await ctx.error(f"Unexpected error getting repository problems: {e}")
        return json.dumps({"error": f"Unexpected error: {e}"})


@mcp.tool()
async def get_maintainer_problems(
    maintainer: str,
    repository: Optional[str] = None,
    start_from: Optional[str] = None,
    ctx: Context[ServerSession, AppContext] = None,
) -> str:
    """Get problems reported for packages maintained by a specific person.

    Args:
        maintainer: Maintainer email address
        repository: Optional repository to limit results to
        start_from: Project name to start from for pagination

    Returns:
        JSON formatted list of problems for the maintainer
    """
    try:
        client = ctx.request_context.lifespan_context.repology_client
        problems = await client.get_maintainer_problems(
            maintainer=maintainer, repository=repository, start_from=start_from
        )

        if not problems:
            msg = f"No problems found for maintainer '{maintainer}'"
            if repository:
                msg += f" in repository '{repository}'"
            return json.dumps({"message": msg})

        return _problems_to_json(problems)

    except RepologyNotFoundError:
        return json.dumps({"error": f"Maintainer '{maintainer}' not found"})
    except RepologyAPIError as e:
        await ctx.error(f"Repology API error: {e}")
        return json.dumps({"error": str(e)})
    except Exception as e:
        await ctx.error(f"Unexpected error getting maintainer problems: {e}")
        return json.dumps({"error": f"Unexpected error: {e}"})


def main():
    """Run the Repology MCP server."""
    parser = argparse.ArgumentParser(
        description="Run the Repology MCP server", prog="repology-mcp-server"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="Transport method (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP/SSE transport (default: 8000)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host for HTTP/SSE transport (default: localhost)",
    )

    args = parser.parse_args()

    # Run the server
    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport=args.transport, port=args.port, host=args.host)


if __name__ == "__main__":
    main()
