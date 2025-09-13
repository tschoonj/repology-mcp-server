"""Tests for the MCP server implementation."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from repology_mcp.server import (
    search_projects, 
    get_project, 
    list_projects,
    get_repository_problems,
    get_maintainer_problems
)
from repology_mcp.client import RepologyNotFoundError, RepologyAPIError
from repology_mcp.models import Package, Problem
from .conftest import SAMPLE_PACKAGE, SAMPLE_PROBLEM


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
        
        result = await search_projects(
            query="firefox",
            limit=10,
            ctx=ctx
        )
        
        # Verify client was called correctly
        client_mock.search_projects.assert_called_once_with(
            query="firefox",
            limit=10
        )
        
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
            ctx=ctx
        )
        
        # Verify filters were passed
        client_mock.search_projects.assert_called_once_with(
            query="firefox",
            limit=5,
            maintainer="test@example.com",
            category="www",
            inrepo="freebsd"
        )
    
    @pytest.mark.asyncio
    async def test_search_projects_limit_enforcement(self):
        """Test that search projects enforces maximum limit."""
        client_mock = AsyncMock()
        client_mock.search_projects.return_value = {}
        
        ctx = MockContext(client_mock)
        
        await search_projects(query="test", limit=150, ctx=ctx)
        
        # Should be capped at 100
        client_mock.search_projects.assert_called_once_with(
            query="test",
            limit=100
        )
    
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
    async def test_get_project_success(self):
        """Test successful project retrieval."""
        client_mock = AsyncMock()
        client_mock.get_project.return_value = [
            Package.model_validate(SAMPLE_PACKAGE)
        ]
        
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
    async def test_list_projects_success(self):
        """Test successful project listing."""
        client_mock = AsyncMock()
        client_mock.list_projects.return_value = {
            "firefox": [Package.model_validate(SAMPLE_PACKAGE)]
        }
        
        ctx = MockContext(client_mock)
        
        result = await list_projects(
            start_from="firefox",
            limit=50,
            maintainer="test@example.com",
            ctx=ctx
        )
        
        client_mock.list_projects.assert_called_once_with(
            start_from="firefox",
            limit=50,
            maintainer="test@example.com"
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
        client_mock.list_projects.assert_called_once_with(
            start_from=None,
            limit=200
        )
    
    @pytest.mark.asyncio
    async def test_list_projects_boolean_filters(self):
        """Test list projects with boolean filters."""
        client_mock = AsyncMock()
        client_mock.list_projects.return_value = {}
        
        ctx = MockContext(client_mock)
        
        await list_projects(
            newest=True,
            outdated=True,
            problematic=False,
            ctx=ctx
        )
        
        # Boolean filters should be converted to "1" strings
        client_mock.list_projects.assert_called_once_with(
            start_from=None,
            limit=10,
            newest="1",
            outdated="1"
        )
    
    @pytest.mark.asyncio
    async def test_get_repository_problems_success(self):
        """Test successful repository problems retrieval."""
        client_mock = AsyncMock()
        client_mock.get_repository_problems.return_value = [
            Problem.model_validate(SAMPLE_PROBLEM)
        ]
        
        ctx = MockContext(client_mock)
        
        result = await get_repository_problems(
            repository="freebsd",
            start_from="test",
            ctx=ctx
        )
        
        client_mock.get_repository_problems.assert_called_once_with(
            repository="freebsd",
            start_from="test"
        )
        
        result_data = json.loads(result)
        assert isinstance(result_data, list)
        assert len(result_data) == 1
        assert result_data[0]["type"] == "homepage_dead"
    
    @pytest.mark.asyncio
    async def test_get_repository_problems_not_found(self):
        """Test repository problems not found."""
        client_mock = AsyncMock()
        client_mock.get_repository_problems.side_effect = RepologyNotFoundError("Not found")
        
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
            maintainer="test@example.com",
            repository="freebsd",
            ctx=ctx
        )
        
        client_mock.get_maintainer_problems.assert_called_once_with(
            maintainer="test@example.com",
            repository="freebsd",
            start_from=None
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
        
        result = await get_maintainer_problems(
            maintainer="test@example.com",
            ctx=ctx
        )
        
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