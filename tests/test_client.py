"""Tests for the Repology client."""

import pytest
import respx
import httpx
from unittest.mock import AsyncMock

from repology_mcp.client import (
    RepologyClient, 
    RepologyAPIError, 
    RepologyNotFoundError,
    RepologyRateLimitError
)
from repology_mcp.models import Package, Problem
from .conftest import SAMPLE_PACKAGE, SAMPLE_PROBLEM, SAMPLE_PROJECT_PACKAGES


class TestRepologyClient:
    """Test cases for RepologyClient."""
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_project_success(self, repology_client):
        """Test successful project retrieval."""
        project_name = "firefox"
        response_data = [SAMPLE_PACKAGE]
        
        respx.get(f"https://repology.org/api/v1/project/{project_name}").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        
        packages = await repology_client.get_project(project_name)
        
        assert len(packages) == 1
        assert isinstance(packages[0], Package)
        assert packages[0].repo == "freebsd"
        assert packages[0].version == "50.1.0"
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_project_not_found(self, repology_client):
        """Test project not found error."""
        project_name = "nonexistent"
        
        respx.get(f"https://repology.org/api/v1/project/{project_name}").mock(
            return_value=httpx.Response(404)
        )
        
        with pytest.raises(RepologyNotFoundError):
            await repology_client.get_project(project_name)
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_projects_success(self, repology_client):
        """Test successful project listing."""
        respx.get("https://repology.org/api/v1/projects/").mock(
            return_value=httpx.Response(200, json=SAMPLE_PROJECT_PACKAGES)
        )
        
        projects = await repology_client.list_projects()
        
        assert len(projects) == 2
        assert "firefox" in projects
        assert "chromium" in projects
        assert isinstance(projects["firefox"][0], Package)
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_projects_with_filters(self, repology_client):
        """Test project listing with filters."""
        respx.get("https://repology.org/api/v1/projects/").mock(
            return_value=httpx.Response(200, json=SAMPLE_PROJECT_PACKAGES)
        )
        
        projects = await repology_client.list_projects(
            maintainer="test@example.com",
            category="www",
            inrepo="freebsd"
        )
        
        # Verify the request was made with query parameters
        request = respx.calls.last.request
        assert "maintainer=test%40example.com" in str(request.url)
        assert "category=www" in str(request.url)
        assert "inrepo=freebsd" in str(request.url)
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_search_projects_success(self, repology_client):
        """Test successful project search."""
        respx.get("https://repology.org/api/v1/projects/").mock(
            return_value=httpx.Response(200, json=SAMPLE_PROJECT_PACKAGES)
        )
        
        projects = await repology_client.search_projects("firefox", limit=10)
        
        # Verify the request was made with search parameter
        request = respx.calls.last.request
        assert "search=firefox" in str(request.url)
        assert len(projects) >= 1
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_repository_problems_success(self, repology_client):
        """Test successful repository problems retrieval."""
        repository = "freebsd"
        response_data = [SAMPLE_PROBLEM]
        
        respx.get(f"https://repology.org/api/v1/repository/{repository}/problems").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        
        problems = await repology_client.get_repository_problems(repository)
        
        assert len(problems) == 1
        assert isinstance(problems[0], Problem)
        assert problems[0].type == "homepage_dead"
        assert problems[0].project_name == "test-project"
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_maintainer_problems_success(self, repology_client):
        """Test successful maintainer problems retrieval."""
        maintainer = "test@example.com"
        response_data = [SAMPLE_PROBLEM]
        
        respx.get(f"https://repology.org/api/v1/maintainer/{maintainer}/problems").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        
        problems = await repology_client.get_maintainer_problems(maintainer)
        
        assert len(problems) == 1
        assert isinstance(problems[0], Problem)
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_maintainer_problems_for_repo(self, repology_client):
        """Test maintainer problems for specific repository."""
        maintainer = "test@example.com"
        repository = "freebsd"
        response_data = [SAMPLE_PROBLEM]
        
        respx.get(
            f"https://repology.org/api/v1/maintainer/{maintainer}/problems-for-repo/{repository}"
        ).mock(return_value=httpx.Response(200, json=response_data))
        
        problems = await repology_client.get_maintainer_problems(
            maintainer, repository=repository
        )
        
        assert len(problems) == 1
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limiting_429(self, repology_client):
        """Test rate limiting error handling."""
        respx.get("https://repology.org/api/v1/project/test").mock(
            return_value=httpx.Response(429)
        )
        
        with pytest.raises(RepologyRateLimitError):
            await repology_client.get_project("test")
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_server_error_retries(self, repology_client):
        """Test server error retry logic."""
        # First two requests fail, third succeeds
        respx.get("https://repology.org/api/v1/project/test").mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(500),
                httpx.Response(200, json=[SAMPLE_PACKAGE])
            ]
        )
        
        packages = await repology_client.get_project("test")
        assert len(packages) == 1
        assert len(respx.calls) == 3
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_invalid_json_response(self, repology_client):
        """Test handling of invalid JSON responses."""
        respx.get("https://repology.org/api/v1/project/test").mock(
            return_value=httpx.Response(200, text="invalid json")
        )
        
        with pytest.raises(RepologyAPIError, match="Invalid JSON response"):
            await repology_client.get_project("test")
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_url_encoding(self, repology_client):
        """Test proper URL encoding of project names and maintainers."""
        project_name = "project with spaces"
        
        respx.get("https://repology.org/api/v1/project/project%20with%20spaces").mock(
            return_value=httpx.Response(200, json=[SAMPLE_PACKAGE])
        )
        
        await repology_client.get_project(project_name)
        
        # Verify the URL was properly encoded
        request = respx.calls.last.request
        assert "project%20with%20spaces" in str(request.url)
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_user_agent_header(self, repology_client):
        """Test that proper User-Agent header is sent."""
        respx.get("https://repology.org/api/v1/project/test").mock(
            return_value=httpx.Response(200, json=[SAMPLE_PACKAGE])
        )
        
        await repology_client.get_project("test")
        
        request = respx.calls.last.request
        assert "repology-mcp-server" in request.headers["User-Agent"]
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test client as async context manager."""
        async with RepologyClient() as client:
            assert client._client is not None
        
        # Client should be closed after context exit
        assert client._client.is_closed
    
    @pytest.mark.asyncio
    async def test_manual_close(self):
        """Test manual client closure."""
        client = RepologyClient()
        assert not client._client.is_closed
        
        await client.close()
        assert client._client.is_closed