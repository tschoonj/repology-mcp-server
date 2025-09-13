"""Test configuration and fixtures."""

import pytest_asyncio

from repology_mcp.client import RepologyClient


@pytest_asyncio.fixture
async def repology_client():
    """Create a RepologyClient for testing."""
    client = RepologyClient(rate_limit_delay=0.0)  # Disable rate limiting for tests
    yield client
    await client.close()


# Sample test data
SAMPLE_PACKAGE = {
    "repo": "freebsd",
    "srcname": "www/firefox",
    "binname": "firefox",
    "visiblename": "www/firefox",
    "version": "50.1.0",
    "origversion": "50.1.0_4,1",
    "status": "newest",
    "summary": "Widely used web browser",
    "categories": ["www"],
    "licenses": ["GPLv2+"],
    "maintainers": ["gecko@FreeBSD.org"],
}

SAMPLE_PROBLEM = {
    "type": "homepage_dead",
    "data": {"url": "http://example.com", "code": 500},
    "project_name": "test-project",
    "version": "1.0",
    "binname": "test-bin",
    "srcname": "test/test-src",
    "rawversion": "1.0_1",
}

SAMPLE_PROJECT_PACKAGES = {
    "firefox": [SAMPLE_PACKAGE],
    "chromium": [
        {
            "repo": "debian",
            "visiblename": "chromium",
            "version": "91.0.4472.114",
            "status": "outdated",
            "summary": "Chromium web browser",
        }
    ],
}

# Additional test data for filtering tests
DEBIAN_PACKAGE = {
    "repo": "debian",
    "srcname": "firefox",
    "binname": "firefox",
    "visiblename": "firefox",
    "version": "91.0",
    "origversion": "91.0-1",
    "status": "outdated",
    "summary": "Widely used web browser",
    "categories": ["www"],
    "licenses": ["GPLv2+"],
    "maintainers": ["debian-mozilla@lists.debian.org"],
}

UBUNTU_PACKAGE = {
    "repo": "ubuntu",
    "srcname": "firefox",
    "binname": "firefox",
    "visiblename": "firefox",
    "version": "92.0",
    "origversion": "92.0-1ubuntu1",
    "status": "newest",
    "summary": "Widely used web browser",
    "categories": ["www"],
    "licenses": ["GPLv2+"],
    "maintainers": ["ubuntu-mozilla@lists.ubuntu.com"],
}
