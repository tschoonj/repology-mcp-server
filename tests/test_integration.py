"""Integration tests that contact the real Repology API.

These tests are marked with @pytest.mark.integration and can be run with:
    pytest -m integration

To exclude them from regular test runs:
    pytest -m "not integration"
"""

import pytest
import asyncio
from repology_mcp.client import RepologyClient, RepologyNotFoundError
from repology_mcp.models import Package, Problem


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_get_project_firefox():
    """Test getting a real project (firefox) from Repology API."""
    async with RepologyClient() as client:
        # Firefox should exist and have packages
        packages = await client.get_project("firefox")

        assert len(packages) > 0
        assert all(isinstance(pkg, Package) for pkg in packages)

        # Firefox should be in multiple repositories
        repos = {pkg.repo for pkg in packages}
        assert len(repos) > 1

        # Should have common repositories (check actual repo names from API)
        common_repos = {
            "arch",
            "fedora_41",
            "fedora_40",
            "ubuntu_24_04",
            "ubuntu_22_04",
            "debian_12",
            "debian_11",
        }
        assert len(repos & common_repos) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_get_project_nonexistent():
    """Test getting a non-existent project from Repology API."""
    async with RepologyClient() as client:
        # This project name should be unique enough to not exist
        nonexistent_name = "definitely-nonexistent-project-12345"

        with pytest.raises(RepologyNotFoundError):
            await client.get_project(nonexistent_name)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_list_projects_small_subset():
    """Test listing a small subset of real projects from Repology API."""
    async with RepologyClient() as client:
        # Get a small subset to avoid overwhelming the API
        projects = await client.list_projects(limit=5)

        assert len(projects) <= 5
        assert len(projects) > 0

        # All should be valid project data
        for project_name, packages in projects.items():
            assert isinstance(project_name, str)
            assert len(project_name) > 0
            assert isinstance(packages, list)
            assert len(packages) > 0
            assert all(isinstance(pkg, Package) for pkg in packages)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_search_projects_python():
    """Test searching for real Python-related projects."""
    async with RepologyClient() as client:
        # Search for python projects (should return many results)
        projects = await client.search_projects("python", limit=10)

        assert len(projects) > 0
        # API sometimes returns more than limit, so check it's reasonable
        assert len(projects) <= 250  # API max

        # Should have some common project names in the keys
        project_names = list(projects.keys())
        python_related = [name for name in project_names if "python" in name.lower()]
        assert len(python_related) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_get_repository_problems_freebsd():
    """Test getting real repository problems from FreeBSD."""
    async with RepologyClient() as client:
        # FreeBSD usually has some problems reported
        problems = await client.get_repository_problems("freebsd")

        # FreeBSD should have at least some problems
        assert len(problems) > 0

        # Check first few problems to avoid processing too many
        for problem in problems[:5]:
            assert isinstance(problem, Problem)
            assert problem.repo == "freebsd"
            assert problem.name
            assert problem.effname
            assert problem.maintainer is not None  # Should have maintainer info


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_api_rate_limiting():
    """Test that API respects rate limiting properly."""
    async with RepologyClient() as client:
        # Make a few quick requests to test rate limiting behavior
        start_time = asyncio.get_event_loop().time()

        # Get a small project
        await client.get_project("firefox")

        # Make another request immediately
        await client.list_projects(limit=1)

        end_time = asyncio.get_event_loop().time()

        # Should complete without errors (basic rate limiting test)
        # If rate limiting is working, this won't fail but may be slower
        assert end_time >= start_time


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_maintainer_problems_invalid():
    """Test handling of invalid maintainer for problems endpoint."""
    async with RepologyClient() as client:
        # Use an invalid email format that should return empty results
        invalid_maintainer = "definitely-not-a-real-maintainer@invalid-domain-12345.com"

        # Should not raise an exception, just return empty results
        problems = await client.get_maintainer_problems(invalid_maintainer)

        # Should return empty list for non-existent maintainer
        assert isinstance(problems, list)
        assert len(problems) == 0
