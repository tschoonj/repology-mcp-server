"""Tests for the MCP server implementation."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from repology_mcp.server import (
    search_projects,
    get_project,
    list_projects,
    get_repository_problems,
    get_maintainer_problems,
    _filter_packages_by_repo,
    _filter_project_packages_by_repo,
    _packages_to_json,
    _project_packages_to_json,
    AppContext,
    app_lifespan,
    main,
)
from repology_mcp.client import RepologyNotFoundError, RepologyAPIError
from repology_mcp.models import Package, Problem
from .conftest import SAMPLE_PACKAGE, SAMPLE_PROBLEM


class TestAppContext:
    """Test cases for AppContext class."""

    def test_app_context_init(self):
        """Test AppContext initialization."""
        mock_client = MagicMock()
        context = AppContext(repology_client=mock_client)

        assert context.repology_client is mock_client


class TestAppLifespan:
    """Test cases for app_lifespan function."""

    @pytest.mark.asyncio
    async def test_app_lifespan_context_manager(self):
        """Test app_lifespan context manager."""
        mock_server = MagicMock()

        with patch("repology_mcp.server.RepologyClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value = mock_client_instance

            async with app_lifespan(mock_server) as context:
                assert isinstance(context, AppContext)
                assert context.repology_client is mock_client_instance

            # Verify client.close() was called on exit
            mock_client_instance.close.assert_called_once()


class TestMainFunction:
    """Test cases for main function."""

    @patch("repology_mcp.server.mcp")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_stdio_transport(self, mock_parse_args, mock_mcp):
        """Test main function with stdio transport."""
        mock_args = MagicMock()
        mock_args.transport = "stdio"
        mock_parse_args.return_value = mock_args

        main()

        mock_mcp.run.assert_called_once_with()

    @patch("repology_mcp.server.mcp")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_http_transport(self, mock_parse_args, mock_mcp):
        """Test main function with HTTP transport."""
        mock_args = MagicMock()
        mock_args.transport = "http"
        mock_args.port = 8080
        mock_args.host = "0.0.0.0"
        mock_parse_args.return_value = mock_args

        main()

        mock_mcp.run.assert_called_once_with(
            transport="http", port=8080, host="0.0.0.0"
        )

    @patch("repology_mcp.server.mcp")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_sse_transport(self, mock_parse_args, mock_mcp):
        """Test main function with SSE transport."""
        mock_args = MagicMock()
        mock_args.transport = "sse"
        mock_args.port = 9000
        mock_args.host = "127.0.0.1"
        mock_parse_args.return_value = mock_args

        main()

        mock_mcp.run.assert_called_once_with(
            transport="sse", port=9000, host="127.0.0.1"
        )

    @patch("repology_mcp.server.mcp")
    def test_main_if_name_main_branch(self, mock_mcp):
        """Test the if __name__ == '__main__' branch."""
        # This tests line 376 in the main function
        with patch("sys.argv", ["server.py"]):
            from repology_mcp.server import main

            # Calling main directly triggers the if __name__ == "__main__" equivalent behavior
            main()

        mock_mcp.run.assert_called_once()


class MockContext:
    """Mock context for testing MCP tools."""

    def __init__(self, repology_client_mock):
        self.request_context = MagicMock()
        self.request_context.lifespan_context = MagicMock()
        self.request_context.lifespan_context.repology_client = repology_client_mock
        self._logs = []

    async def error(self, message: str):
        """Mock error logging."""
        self._logs.append(("error", message))


class TestClientSideFiltering:
    """Test cases for client-side filtering functions."""

    def test_filter_packages_by_repo_success(self):
        """Test filtering packages by repository."""
        packages = [
            Package.model_validate({**SAMPLE_PACKAGE, "repo": "freebsd"}),
            Package.model_validate({**SAMPLE_PACKAGE, "repo": "debian"}),
            Package.model_validate({**SAMPLE_PACKAGE, "repo": "freebsd"}),
        ]

        filtered = _filter_packages_by_repo(packages, "freebsd")

        assert len(filtered) == 2
        assert all(pkg.repo == "freebsd" for pkg in filtered)

    def test_filter_packages_by_repo_no_matches(self):
        """Test filtering packages when no packages match the repository."""
        packages = [
            Package.model_validate({**SAMPLE_PACKAGE, "repo": "debian"}),
            Package.model_validate({**SAMPLE_PACKAGE, "repo": "ubuntu"}),
        ]

        filtered = _filter_packages_by_repo(packages, "freebsd")

        assert len(filtered) == 0

    def test_filter_packages_by_repo_empty_list(self):
        """Test filtering empty package list."""
        packages = []

        filtered = _filter_packages_by_repo(packages, "freebsd")

        assert len(filtered) == 0

    def test_filter_project_packages_by_repo_success(self):
        """Test filtering project packages by repository."""
        project_packages = {
            "firefox": [
                Package.model_validate({**SAMPLE_PACKAGE, "repo": "freebsd"}),
                Package.model_validate({**SAMPLE_PACKAGE, "repo": "debian"}),
            ],
            "chromium": [
                Package.model_validate({**SAMPLE_PACKAGE, "repo": "debian"}),
            ],
            "nginx": [
                Package.model_validate({**SAMPLE_PACKAGE, "repo": "freebsd"}),
            ],
        }

        filtered = _filter_project_packages_by_repo(project_packages, "freebsd")

        assert len(filtered) == 2  # firefox and nginx
        assert "firefox" in filtered
        assert "nginx" in filtered
        assert "chromium" not in filtered
        assert len(filtered["firefox"]) == 1
        assert filtered["firefox"][0].repo == "freebsd"
        assert len(filtered["nginx"]) == 1
        assert filtered["nginx"][0].repo == "freebsd"

    def test_filter_project_packages_by_repo_no_matches(self):
        """Test filtering project packages when no packages match."""
        project_packages = {
            "firefox": [
                Package.model_validate({**SAMPLE_PACKAGE, "repo": "debian"}),
            ],
            "chromium": [
                Package.model_validate({**SAMPLE_PACKAGE, "repo": "ubuntu"}),
            ],
        }

        filtered = _filter_project_packages_by_repo(project_packages, "freebsd")

        assert len(filtered) == 0

    def test_filter_project_packages_by_repo_empty_dict(self):
        """Test filtering empty project packages dict."""
        project_packages = {}

        filtered = _filter_project_packages_by_repo(project_packages, "freebsd")

        assert len(filtered) == 0


class TestJSONConversionFunctions:
    """Test cases for JSON conversion functions."""

    def test_packages_to_json(self):
        """Test converting packages list to JSON."""
        packages = [
            Package.model_validate(SAMPLE_PACKAGE),
            Package.model_validate({**SAMPLE_PACKAGE, "version": "51.0.0"}),
        ]

        result = _packages_to_json(packages)

        assert isinstance(result, str)
        result_data = json.loads(result)
        assert isinstance(result_data, list)
        assert len(result_data) == 2
        assert result_data[0]["repo"] == "freebsd"
        assert result_data[1]["version"] == "51.0.0"

    def test_packages_to_json_empty(self):
        """Test converting empty packages list to JSON."""
        packages = []

        result = _packages_to_json(packages)

        assert isinstance(result, str)
        result_data = json.loads(result)
        assert isinstance(result_data, list)
        assert len(result_data) == 0

    def test_project_packages_to_json(self):
        """Test converting project packages dict to JSON."""
        project_packages = {
            "firefox": [Package.model_validate(SAMPLE_PACKAGE)],
            "chromium": [
                Package.model_validate({**SAMPLE_PACKAGE, "visiblename": "chromium"})
            ],
        }

        result = _project_packages_to_json(project_packages)

        assert isinstance(result, str)
        result_data = json.loads(result)
        assert isinstance(result_data, dict)
        assert "firefox" in result_data
        assert "chromium" in result_data
        assert len(result_data["firefox"]) == 1
        assert result_data["chromium"][0]["visiblename"] == "chromium"

    def test_project_packages_to_json_empty(self):
        """Test converting empty project packages dict to JSON."""
        project_packages = {}

        result = _project_packages_to_json(project_packages)

        assert isinstance(result, str)
        result_data = json.loads(result)
        assert isinstance(result_data, dict)
        assert len(result_data) == 0


class TestMCPServerTools:
    """Test cases for MCP server tools."""

    @pytest.mark.asyncio
    async def test_search_projects_success(self):
        """Test successful project search."""
        # Create mock client
        client_mock = AsyncMock()
        client_mock.search_projects.return_value = {
            "firefox": [Package.model_validate(SAMPLE_PACKAGE)]
        }

        ctx = MockContext(client_mock)

        result = await search_projects(query="firefox", limit=10, ctx=ctx)

        # Verify client was called correctly
        client_mock.search_projects.assert_called_once_with(query="firefox", limit=10)

        # Verify JSON response
        result_data = json.loads(result)
        assert "firefox" in result_data
        assert len(result_data["firefox"]) == 1
        assert result_data["firefox"][0]["repo"] == "freebsd"

    @pytest.mark.asyncio
    async def test_search_projects_with_filters(self):
        """Test project search with filters."""
        client_mock = AsyncMock()
        client_mock.search_projects.return_value = {}

        ctx = MockContext(client_mock)

        await search_projects(
            query="firefox",
            limit=5,
            maintainer="test@example.com",
            category="www",
            inrepo="freebsd",
            ctx=ctx,
        )

        # Verify filters were passed
        client_mock.search_projects.assert_called_once_with(
            query="firefox",
            limit=5,
            maintainer="test@example.com",
            category="www",
            inrepo="freebsd",
        )

    @pytest.mark.asyncio
    async def test_search_projects_limit_enforcement(self):
        """Test that search projects enforces maximum limit."""
        client_mock = AsyncMock()
        client_mock.search_projects.return_value = {}

        ctx = MockContext(client_mock)

        await search_projects(query="test", limit=150, ctx=ctx)

        # Should be capped at 100
        client_mock.search_projects.assert_called_once_with(query="test", limit=100)

    @pytest.mark.asyncio
    async def test_search_projects_no_results(self):
        """Test search with no results."""
        client_mock = AsyncMock()
        client_mock.search_projects.return_value = {}

        ctx = MockContext(client_mock)

        result = await search_projects(query="nonexistent", ctx=ctx)

        result_data = json.loads(result)
        assert "message" in result_data
        assert "No projects found" in result_data["message"]

    @pytest.mark.asyncio
    async def test_search_projects_api_error(self):
        """Test search with API error."""
        client_mock = AsyncMock()
        client_mock.search_projects.side_effect = RepologyAPIError("API error")

        ctx = MockContext(client_mock)

        result = await search_projects(query="test", ctx=ctx)

        result_data = json.loads(result)
        assert "error" in result_data
        assert "API error" in result_data["error"]

        # Verify error was logged
        assert len(ctx._logs) == 1
        assert ctx._logs[0][0] == "error"

    @pytest.mark.asyncio
    async def test_search_projects_with_repository_filtering(self):
        """Test search projects with client-side repository filtering."""
        # Mock client to return packages from multiple repositories
        client_mock = AsyncMock()
        client_mock.search_projects.return_value = {
            "firefox": [
                Package.model_validate({**SAMPLE_PACKAGE, "repo": "freebsd"}),
                Package.model_validate(
                    {**SAMPLE_PACKAGE, "repo": "debian", "version": "91.0"}
                ),
            ],
            "chromium": [
                Package.model_validate(
                    {**SAMPLE_PACKAGE, "repo": "debian", "visiblename": "chromium"}
                ),
            ],
        }

        ctx = MockContext(client_mock)

        result = await search_projects(
            query="browser",
            inrepo="freebsd",  # Should filter to only FreeBSD packages
            ctx=ctx,
        )

        # Verify API was called with inrepo filter
        client_mock.search_projects.assert_called_once_with(
            query="browser", limit=10, inrepo="freebsd"
        )

        # Verify client-side filtering was applied
        result_data = json.loads(result)
        assert "firefox" in result_data  # Should have firefox (has FreeBSD package)
        assert (
            "chromium" not in result_data
        )  # Should not have chromium (no FreeBSD packages)
        assert len(result_data["firefox"]) == 1
        assert result_data["firefox"][0]["repo"] == "freebsd"

    @pytest.mark.asyncio
    async def test_search_projects_with_notinrepo_filtering(self):
        """Test search projects with notinrepo filtering (no client-side filtering)."""
        client_mock = AsyncMock()
        client_mock.search_projects.return_value = {
            "firefox": [Package.model_validate(SAMPLE_PACKAGE)]
        }

        ctx = MockContext(client_mock)

        result = await search_projects(
            query="firefox",
            notinrepo="debian",  # Should pass through without client-side filtering
            ctx=ctx,
        )

        # Verify API was called with notinrepo filter
        client_mock.search_projects.assert_called_once_with(
            query="firefox", limit=10, notinrepo="debian"
        )

        # Verify no client-side filtering was applied
        result_data = json.loads(result)
        assert "firefox" in result_data

    @pytest.mark.asyncio
    async def test_search_projects_both_inrepo_and_notinrepo(self):
        """Test search projects with both inrepo and notinrepo (both passed to API)."""
        client_mock = AsyncMock()
        client_mock.search_projects.return_value = {
            "firefox": [Package.model_validate(SAMPLE_PACKAGE)]
        }

        ctx = MockContext(client_mock)

        await search_projects(
            query="firefox",
            inrepo="freebsd",
            notinrepo="debian",  # Both should be passed to API
            ctx=ctx,
        )

        # Should only pass inrepo to API
        client_mock.search_projects.assert_called_once_with(
            query="firefox", limit=10, inrepo="freebsd", notinrepo="debian"
        )

    @pytest.mark.asyncio
    async def test_get_project_success(self):
        """Test successful project retrieval."""
        client_mock = AsyncMock()
        client_mock.get_project.return_value = [Package.model_validate(SAMPLE_PACKAGE)]

        ctx = MockContext(client_mock)

        result = await get_project(project_name="firefox", ctx=ctx)

        client_mock.get_project.assert_called_once_with("firefox")

        result_data = json.loads(result)
        assert isinstance(result_data, list)
        assert len(result_data) == 1
        assert result_data[0]["repo"] == "freebsd"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self):
        """Test project not found."""
        client_mock = AsyncMock()
        client_mock.get_project.side_effect = RepologyNotFoundError("Not found")

        ctx = MockContext(client_mock)

        result = await get_project(project_name="nonexistent", ctx=ctx)

        result_data = json.loads(result)
        assert "error" in result_data
        assert "not found" in result_data["error"].lower()

    @pytest.mark.asyncio
    async def test_get_project_with_repository_filtering(self):
        """Test get project with client-side repository filtering."""
        client_mock = AsyncMock()
        client_mock.get_project.return_value = [
            Package.model_validate({**SAMPLE_PACKAGE, "repo": "freebsd"}),
            Package.model_validate(
                {**SAMPLE_PACKAGE, "repo": "debian", "version": "91.0"}
            ),
            Package.model_validate(
                {**SAMPLE_PACKAGE, "repo": "ubuntu", "version": "92.0"}
            ),
        ]

        ctx = MockContext(client_mock)

        result = await get_project(project_name="firefox", repository="debian", ctx=ctx)

        client_mock.get_project.assert_called_once_with("firefox")

        # Verify client-side filtering was applied
        result_data = json.loads(result)
        assert isinstance(result_data, list)
        assert len(result_data) == 1  # Only debian package should remain
        assert result_data[0]["repo"] == "debian"
        assert result_data[0]["version"] == "91.0"

    @pytest.mark.asyncio
    async def test_get_project_with_repository_filtering_no_matches(self):
        """Test get project with repository filtering when no packages match."""
        client_mock = AsyncMock()
        client_mock.get_project.return_value = [
            Package.model_validate({**SAMPLE_PACKAGE, "repo": "freebsd"}),
            Package.model_validate({**SAMPLE_PACKAGE, "repo": "ubuntu"}),
        ]

        ctx = MockContext(client_mock)

        result = await get_project(
            project_name="firefox",
            repository="debian",  # No debian packages available
            ctx=ctx,
        )

        # Should return empty message since no packages match after filtering
        result_data = json.loads(result)
        assert "message" in result_data
        assert "No packages found" in result_data["message"]

    @pytest.mark.asyncio
    async def test_list_projects_success(self):
        """Test successful project listing."""
        client_mock = AsyncMock()
        client_mock.list_projects.return_value = {
            "firefox": [Package.model_validate(SAMPLE_PACKAGE)]
        }

        ctx = MockContext(client_mock)

        result = await list_projects(
            start_from="firefox", limit=50, maintainer="test@example.com", ctx=ctx
        )

        client_mock.list_projects.assert_called_once_with(
            start_from="firefox", limit=50, maintainer="test@example.com"
        )

        result_data = json.loads(result)
        assert "firefox" in result_data

    @pytest.mark.asyncio
    async def test_list_projects_limit_enforcement(self):
        """Test that list projects enforces maximum limit."""
        client_mock = AsyncMock()
        client_mock.list_projects.return_value = {}

        ctx = MockContext(client_mock)

        await list_projects(limit=300, ctx=ctx)

        # Should be capped at 200
        client_mock.list_projects.assert_called_once_with(start_from=None, limit=200)

    @pytest.mark.asyncio
    async def test_list_projects_boolean_filters(self):
        """Test list projects with boolean filters."""
        client_mock = AsyncMock()
        client_mock.list_projects.return_value = {}

        ctx = MockContext(client_mock)

        await list_projects(newest=True, outdated=True, problematic=False, ctx=ctx)

        # Boolean filters should be converted to "1" strings
        client_mock.list_projects.assert_called_once_with(
            start_from=None, limit=10, newest="1", outdated="1"
        )

    @pytest.mark.asyncio
    async def test_list_projects_with_repository_filtering(self):
        """Test list projects with client-side repository filtering."""
        client_mock = AsyncMock()
        client_mock.list_projects.return_value = {
            "project1": [
                Package.model_validate({**SAMPLE_PACKAGE, "repo": "debian"}),
                Package.model_validate({**SAMPLE_PACKAGE, "repo": "freebsd"}),
            ],
            "project2": [
                Package.model_validate({**SAMPLE_PACKAGE, "repo": "debian"}),
            ],
            "project3": [
                Package.model_validate({**SAMPLE_PACKAGE, "repo": "ubuntu"}),
            ],
        }

        ctx = MockContext(client_mock)

        result = await list_projects(inrepo="debian", limit=50, ctx=ctx)

        # Verify API was called with inrepo filter
        client_mock.list_projects.assert_called_once_with(
            start_from=None, limit=50, inrepo="debian"
        )

        # Verify client-side filtering was applied
        result_data = json.loads(result)
        assert "project1" in result_data  # Should have project1 (has debian package)
        assert "project2" in result_data  # Should have project2 (has debian package)
        assert (
            "project3" not in result_data
        )  # Should not have project3 (no debian packages)
        # All packages should be from debian
        for project_name, packages in result_data.items():
            for package in packages:
                assert package["repo"] == "debian"

    @pytest.mark.asyncio
    async def test_list_projects_with_notinrepo_filtering(self):
        """Test list projects with notinrepo filtering (no client-side filtering)."""
        client_mock = AsyncMock()
        client_mock.list_projects.return_value = {
            "firefox": [Package.model_validate(SAMPLE_PACKAGE)]
        }

        ctx = MockContext(client_mock)

        result = await list_projects(
            notinrepo="debian",  # Should pass through without client-side filtering
            ctx=ctx,
        )

        # Verify API was called with notinrepo filter
        client_mock.list_projects.assert_called_once_with(
            start_from=None, limit=10, notinrepo="debian"
        )

        # Verify no client-side filtering was applied
        result_data = json.loads(result)
        assert "firefox" in result_data

    @pytest.mark.asyncio
    async def test_get_repository_problems_success(self):
        """Test successful repository problems retrieval."""
        client_mock = AsyncMock()
        client_mock.get_repository_problems.return_value = [
            Problem.model_validate(SAMPLE_PROBLEM)
        ]

        ctx = MockContext(client_mock)

        result = await get_repository_problems(
            repository="freebsd", start_from="test", ctx=ctx
        )

        client_mock.get_repository_problems.assert_called_once_with(
            repository="freebsd", start_from="test"
        )

        result_data = json.loads(result)
        assert isinstance(result_data, list)
        assert len(result_data) == 1
        assert result_data[0]["type"] == "homepage_dead"

    @pytest.mark.asyncio
    async def test_get_repository_problems_not_found(self):
        """Test repository problems not found."""
        client_mock = AsyncMock()
        client_mock.get_repository_problems.side_effect = RepologyNotFoundError(
            "Not found"
        )

        ctx = MockContext(client_mock)

        result = await get_repository_problems(repository="nonexistent", ctx=ctx)

        result_data = json.loads(result)
        assert "error" in result_data
        assert "not found" in result_data["error"].lower()

    @pytest.mark.asyncio
    async def test_get_maintainer_problems_success(self):
        """Test successful maintainer problems retrieval."""
        client_mock = AsyncMock()
        client_mock.get_maintainer_problems.return_value = [
            Problem.model_validate(SAMPLE_PROBLEM)
        ]

        ctx = MockContext(client_mock)

        result = await get_maintainer_problems(
            maintainer="test@example.com", repository="freebsd", ctx=ctx
        )

        client_mock.get_maintainer_problems.assert_called_once_with(
            maintainer="test@example.com", repository="freebsd", start_from=None
        )

        result_data = json.loads(result)
        assert isinstance(result_data, list)
        assert len(result_data) == 1

    @pytest.mark.asyncio
    async def test_get_maintainer_problems_no_results(self):
        """Test maintainer problems with no results."""
        client_mock = AsyncMock()
        client_mock.get_maintainer_problems.return_value = []

        ctx = MockContext(client_mock)

        result = await get_maintainer_problems(maintainer="test@example.com", ctx=ctx)

        result_data = json.loads(result)
        assert "message" in result_data
        assert "No problems found" in result_data["message"]

    @pytest.mark.asyncio
    async def test_unexpected_error_handling(self):
        """Test handling of unexpected errors."""
        client_mock = AsyncMock()
        client_mock.get_project.side_effect = ValueError("Unexpected error")

        ctx = MockContext(client_mock)

        result = await get_project(project_name="test", ctx=ctx)

        result_data = json.loads(result)
        assert "error" in result_data
        assert "Unexpected error" in result_data["error"]

        # Verify error was logged
        assert len(ctx._logs) == 1
        assert ctx._logs[0][0] == "error"

    @pytest.mark.asyncio
    async def test_get_project_empty_packages(self):
        """Test get project when client returns empty packages list."""
        client_mock = AsyncMock()
        client_mock.get_project.return_value = []

        ctx = MockContext(client_mock)

        result = await get_project(project_name="nonexistent", ctx=ctx)

        result_data = json.loads(result)
        assert "message" in result_data
        assert "No packages found for project 'nonexistent'" in result_data["message"]

    @pytest.mark.asyncio
    async def test_get_project_api_error(self):
        """Test get project with API error."""
        client_mock = AsyncMock()
        client_mock.get_project.side_effect = RepologyAPIError("API failed")

        ctx = MockContext(client_mock)

        result = await get_project(project_name="test", ctx=ctx)

        result_data = json.loads(result)
        assert "error" in result_data
        assert "API failed" in result_data["error"]

        # Verify error was logged
        assert len(ctx._logs) == 1
        assert ctx._logs[0][0] == "error"

    @pytest.mark.asyncio
    async def test_list_projects_no_results(self):
        """Test list projects with no results."""
        client_mock = AsyncMock()
        client_mock.list_projects.return_value = {}

        ctx = MockContext(client_mock)

        result = await list_projects(ctx=ctx)

        result_data = json.loads(result)
        assert "message" in result_data
        assert "No projects found" in result_data["message"]

    @pytest.mark.asyncio
    async def test_list_projects_api_error(self):
        """Test list projects with API error."""
        client_mock = AsyncMock()
        client_mock.list_projects.side_effect = RepologyAPIError("List failed")

        ctx = MockContext(client_mock)

        result = await list_projects(ctx=ctx)

        result_data = json.loads(result)
        assert "error" in result_data
        assert "List failed" in result_data["error"]

        # Verify error was logged
        assert len(ctx._logs) == 1
        assert ctx._logs[0][0] == "error"

    @pytest.mark.asyncio
    async def test_list_projects_with_all_filters(self):
        """Test list projects with all available filters."""
        client_mock = AsyncMock()
        client_mock.list_projects.return_value = {
            "test": [Package.model_validate(SAMPLE_PACKAGE)]
        }

        ctx = MockContext(client_mock)

        await list_projects(
            start_from="a",
            limit=50,
            maintainer="test@example.com",
            category="www",
            inrepo="freebsd",
            notinrepo="debian",
            repos="5",
            families="3",
            newest=True,
            outdated=False,
            problematic=True,
            ctx=ctx,
        )

        # Verify all filters were passed correctly
        client_mock.list_projects.assert_called_once_with(
            start_from="a",
            limit=50,
            maintainer="test@example.com",
            category="www",
            inrepo="freebsd",
            notinrepo="debian",
            repos="5",
            families="3",
            newest="1",
            problematic="1",
        )

    @pytest.mark.asyncio
    async def test_get_repository_problems_api_error(self):
        """Test get repository problems with API error."""
        client_mock = AsyncMock()
        client_mock.get_repository_problems.side_effect = RepologyAPIError(
            "Problems API failed"
        )

        ctx = MockContext(client_mock)

        result = await get_repository_problems(repository="freebsd", ctx=ctx)

        result_data = json.loads(result)
        assert "error" in result_data
        assert "Problems API failed" in result_data["error"]

        # Verify error was logged
        assert len(ctx._logs) == 1
        assert ctx._logs[0][0] == "error"

    @pytest.mark.asyncio
    async def test_get_maintainer_problems_api_error(self):
        """Test get maintainer problems with API error."""
        client_mock = AsyncMock()
        client_mock.get_maintainer_problems.side_effect = RepologyAPIError(
            "Maintainer API failed"
        )

        ctx = MockContext(client_mock)

        result = await get_maintainer_problems(maintainer="test@example.com", ctx=ctx)

        result_data = json.loads(result)
        assert "error" in result_data
        assert "Maintainer API failed" in result_data["error"]

        # Verify error was logged
        assert len(ctx._logs) == 1
        assert ctx._logs[0][0] == "error"

    @pytest.mark.asyncio
    async def test_search_projects_unexpected_error(self):
        """Test search_projects unexpected error handling."""
        client_mock = AsyncMock()
        client_mock.search_projects.side_effect = Exception("Test exception")

        ctx = MockContext(client_mock)

        result = await search_projects(query="test", ctx=ctx)

        result_data = json.loads(result)
        assert "error" in result_data
        assert "Unexpected error: Test exception" in result_data["error"]

        # Verify error was logged
        assert len(ctx._logs) == 1
        assert ctx._logs[0][0] == "error"

    @pytest.mark.asyncio
    async def test_list_projects_unexpected_error(self):
        """Test list_projects unexpected error handling."""
        client_mock = AsyncMock()
        client_mock.list_projects.side_effect = Exception("Test exception")

        ctx = MockContext(client_mock)

        result = await list_projects(ctx=ctx)

        result_data = json.loads(result)
        assert "error" in result_data
        assert "Unexpected error: Test exception" in result_data["error"]

        # Verify error was logged
        assert len(ctx._logs) == 1
        assert ctx._logs[0][0] == "error"

    @pytest.mark.asyncio
    async def test_get_repository_problems_no_problems_empty_response(self):
        """Test get_repository_problems when no problems are found."""
        client_mock = AsyncMock()
        client_mock.get_repository_problems.return_value = []

        ctx = MockContext(client_mock)

        result = await get_repository_problems(repository="empty-repo", ctx=ctx)

        result_data = json.loads(result)
        assert "message" in result_data
        assert "No problems found for repository 'empty-repo'" in result_data["message"]

    @pytest.mark.asyncio
    async def test_get_repository_problems_not_found_error(self):
        """Test get_repository_problems with repository not found."""
        client_mock = AsyncMock()
        client_mock.get_repository_problems.side_effect = RepologyNotFoundError(
            "Repository not found"
        )

        ctx = MockContext(client_mock)

        result = await get_repository_problems(repository="nonexistent", ctx=ctx)

        result_data = json.loads(result)
        assert "error" in result_data
        assert "Repository 'nonexistent' not found" in result_data["error"]

    @pytest.mark.asyncio
    async def test_get_repository_problems_unexpected_error(self):
        """Test get_repository_problems unexpected error handling."""
        client_mock = AsyncMock()
        client_mock.get_repository_problems.side_effect = Exception("Test exception")

        ctx = MockContext(client_mock)

        result = await get_repository_problems(repository="test", ctx=ctx)

        result_data = json.loads(result)
        assert "error" in result_data
        assert "Unexpected error: Test exception" in result_data["error"]

        # Verify error was logged
        assert len(ctx._logs) == 1
        assert ctx._logs[0][0] == "error"

    @pytest.mark.asyncio
    async def test_get_maintainer_problems_no_problems_empty_response(self):
        """Test get_maintainer_problems when no problems are found."""
        client_mock = AsyncMock()
        client_mock.get_maintainer_problems.return_value = []

        ctx = MockContext(client_mock)

        result = await get_maintainer_problems(maintainer="test@example.com", ctx=ctx)

        result_data = json.loads(result)
        assert "message" in result_data
        assert (
            "No problems found for maintainer 'test@example.com'"
            in result_data["message"]
        )

    @pytest.mark.asyncio
    async def test_get_maintainer_problems_no_problems_with_repository(self):
        """Test get_maintainer_problems when no problems are found with repository filter."""
        client_mock = AsyncMock()
        client_mock.get_maintainer_problems.return_value = []

        ctx = MockContext(client_mock)

        result = await get_maintainer_problems(
            maintainer="test@example.com", repository="debian", ctx=ctx
        )

        result_data = json.loads(result)
        assert "message" in result_data
        assert (
            "No problems found for maintainer 'test@example.com' in repository 'debian'"
            in result_data["message"]
        )

    @pytest.mark.asyncio
    async def test_get_maintainer_problems_not_found_error(self):
        """Test get_maintainer_problems with maintainer not found."""
        client_mock = AsyncMock()
        client_mock.get_maintainer_problems.side_effect = RepologyNotFoundError(
            "Maintainer not found"
        )

        ctx = MockContext(client_mock)

        result = await get_maintainer_problems(
            maintainer="nonexistent@example.com", ctx=ctx
        )

        result_data = json.loads(result)
        assert "error" in result_data
        assert "Maintainer 'nonexistent@example.com' not found" in result_data["error"]

    @pytest.mark.asyncio
    async def test_get_maintainer_problems_unexpected_error(self):
        """Test get_maintainer_problems unexpected error handling."""
        client_mock = AsyncMock()
        client_mock.get_maintainer_problems.side_effect = Exception("Test exception")

        ctx = MockContext(client_mock)

        result = await get_maintainer_problems(maintainer="test@example.com", ctx=ctx)

        result_data = json.loads(result)
        assert "error" in result_data
        assert "Unexpected error: Test exception" in result_data["error"]

        # Verify error was logged
        assert len(ctx._logs) == 1
        assert ctx._logs[0][0] == "error"
