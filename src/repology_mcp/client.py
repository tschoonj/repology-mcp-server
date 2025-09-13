"""HTTP client for Repology API."""

import asyncio
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlencode, quote

import httpx
from pydantic import ValidationError

from .models import Package, Problem, ProjectPackages, ProjectData, ProblemsData


class RepologyAPIError(Exception):
    """Base exception for Repology API errors."""

    pass


class RepologyRateLimitError(RepologyAPIError):
    """Raised when rate limit is exceeded."""

    pass


class RepologyNotFoundError(RepologyAPIError):
    """Raised when a resource is not found."""

    pass


class RepologyClient:
    """Async HTTP client for Repology API."""

    BASE_URL = "https://repology.org/api/v1"
    USER_AGENT = "repology-mcp-server/0.1.0 (https://github.com/modelcontextprotocol/repology-mcp-server)"

    def __init__(
        self,
        timeout: float = 30.0,
        rate_limit_delay: float = 1.1,  # Slightly over 1 second to be safe
        max_retries: int = 3,
    ):
        """Initialize the Repology client.

        Args:
            timeout: Request timeout in seconds
            rate_limit_delay: Delay between requests to respect rate limits
            max_retries: Maximum number of retries for failed requests
        """
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self._last_request_time = 0.0

        # Create HTTP client with proper headers
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={"User-Agent": self.USER_AGENT},
            follow_redirects=True,
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        import time

        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self.rate_limit_delay:
            delay = self.rate_limit_delay - time_since_last
            await asyncio.sleep(delay)

        self._last_request_time = time.time()

    async def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Make an HTTP request to the Repology API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            RepologyAPIError: For API errors
            RepologyRateLimitError: For rate limit errors
            RepologyNotFoundError: For not found errors
        """
        url = f"{self.BASE_URL}/{endpoint}"

        # Build query string if params provided
        if params:
            # Filter out None values and encode properly
            clean_params = {k: v for k, v in params.items() if v is not None}
            if clean_params:
                url += "?" + urlencode(clean_params)

        for attempt in range(self.max_retries + 1):
            try:
                # Enforce rate limiting
                await self._rate_limit()

                response = await self._client.get(url)

                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError as e:
                        raise RepologyAPIError(f"Invalid JSON response: {e}")

                elif response.status_code == 404:
                    raise RepologyNotFoundError(f"Resource not found: {endpoint}")

                elif response.status_code == 429:
                    if attempt < self.max_retries:
                        # Exponential backoff for rate limits
                        delay = (2**attempt) * self.rate_limit_delay
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise RepologyRateLimitError("Rate limit exceeded")

                elif response.status_code >= 500:
                    if attempt < self.max_retries:
                        # Exponential backoff for server errors
                        delay = (2**attempt) * 2
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise RepologyAPIError(
                            f"Server error {response.status_code}: {response.text}"
                        )

                else:
                    raise RepologyAPIError(
                        f"HTTP {response.status_code}: {response.text}"
                    )

            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    delay = (2**attempt) * 2
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise RepologyAPIError(f"Request failed: {e}")

        raise RepologyAPIError("Max retries exceeded")

    async def get_project(self, project_name: str) -> ProjectData:
        """Get package data for a specific project.

        Args:
            project_name: Name of the project

        Returns:
            List of packages for the project

        Raises:
            RepologyNotFoundError: If project doesn't exist
        """
        endpoint = f"project/{quote(project_name)}"

        try:
            data = await self._make_request(endpoint)
            # API returns a list of package dictionaries
            if not isinstance(data, list):
                raise RepologyAPIError(f"Expected list, got {type(data)}")

            packages = []
            for item in data:
                try:
                    packages.append(Package.model_validate(item))
                except ValidationError as e:
                    # Log validation error but continue with other packages
                    print(f"Warning: Failed to validate package data: {e}")
                    continue

            return packages

        except RepologyNotFoundError:
            # Re-raise not found errors
            raise
        except RepologyRateLimitError:
            # Re-raise rate limit errors
            raise
        except Exception as e:
            raise RepologyAPIError(f"Failed to get project {project_name}: {e}")

    async def list_projects(
        self,
        start_from: Optional[str] = None,
        end_at: Optional[str] = None,
        limit: int = 200,
        **filters: Any,
    ) -> ProjectPackages:
        """List projects with optional filtering.

        Args:
            start_from: Project name to start from (inclusive)
            end_at: Project name to end at (inclusive)
            limit: Maximum number of projects (max 200)
            **filters: Additional filters (maintainer, category, inrepo, etc.)

        Returns:
            Dictionary mapping project names to package lists
        """
        # Build endpoint path
        if start_from and end_at:
            endpoint = f"projects/{quote(start_from)}/..{quote(end_at)}/"
        elif start_from:
            endpoint = f"projects/{quote(start_from)}/"
        elif end_at:
            endpoint = f"projects/..{quote(end_at)}/"
        else:
            endpoint = "projects/"

        # Add query parameters for filters
        params = {}
        for key, value in filters.items():
            if value is not None:
                params[key] = value

        try:
            data = await self._make_request(endpoint, params)

            if not isinstance(data, dict):
                raise RepologyAPIError(f"Expected dict, got {type(data)}")

            result = {}
            for project_name, packages_data in data.items():
                packages = []
                for item in packages_data:
                    try:
                        packages.append(Package.model_validate(item))
                    except ValidationError as e:
                        print(f"Warning: Failed to validate package data: {e}")
                        continue
                result[project_name] = packages

            return result

        except Exception as e:
            raise RepologyAPIError(f"Failed to list projects: {e}")

    async def search_projects(
        self, query: str, limit: int = 10, **filters: Any
    ) -> ProjectPackages:
        """Search for projects by name.

        Args:
            query: Search term to match against project names
            limit: Maximum number of results
            **filters: Additional filters

        Returns:
            Dictionary mapping project names to package lists
        """
        # Use the search filter in list_projects
        filters["search"] = query
        return await self.list_projects(limit=min(limit, 200), **filters)

    async def get_repository_problems(
        self, repository: str, start_from: Optional[str] = None
    ) -> ProblemsData:
        """Get problems for a specific repository.

        Args:
            repository: Repository name
            start_from: Project name to start from for pagination

        Returns:
            List of problems
        """
        endpoint = f"repository/{quote(repository)}/problems"
        params = {}
        if start_from:
            params["start"] = start_from

        try:
            data = await self._make_request(endpoint, params)

            if not isinstance(data, list):
                raise RepologyAPIError(f"Expected list, got {type(data)}")

            problems = []
            for item in data:
                try:
                    problems.append(Problem.model_validate(item))
                except ValidationError as e:
                    print(f"Warning: Failed to validate problem data: {e}")
                    continue

            return problems

        except Exception as e:
            raise RepologyAPIError(f"Failed to get repository problems: {e}")

    async def get_maintainer_problems(
        self,
        maintainer: str,
        repository: Optional[str] = None,
        start_from: Optional[str] = None,
    ) -> ProblemsData:
        """Get problems for packages maintained by a specific person.

        Args:
            maintainer: Maintainer email address
            repository: Optional repository to limit results to
            start_from: Project name to start from for pagination

        Returns:
            List of problems
        """
        if repository:
            endpoint = (
                f"maintainer/{quote(maintainer)}/problems-for-repo/{quote(repository)}"
            )
        else:
            endpoint = f"maintainer/{quote(maintainer)}/problems"

        params = {}
        if start_from:
            params["start"] = start_from

        try:
            data = await self._make_request(endpoint, params)

            if not isinstance(data, list):
                raise RepologyAPIError(f"Expected list, got {type(data)}")

            problems = []
            for item in data:
                try:
                    problems.append(Problem.model_validate(item))
                except ValidationError as e:
                    print(f"Warning: Failed to validate problem data: {e}")
                    continue

            return problems

        except Exception as e:
            raise RepologyAPIError(f"Failed to get maintainer problems: {e}")
