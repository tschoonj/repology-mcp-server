"""Tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from repology_mcp.models import Package, Problem


class TestPackageModel:
    """Test cases for Package model."""
    
    def test_package_minimal_valid(self):
        """Test package with minimal required fields."""
        data = {
            "repo": "freebsd",
            "visiblename": "firefox",
            "version": "91.0",
            "status": "newest"
        }
        
        package = Package.model_validate(data)
        assert package.repo == "freebsd"
        assert package.visiblename == "firefox"
        assert package.version == "91.0"
        assert package.status == "newest"
        assert package.srcname is None
        assert package.categories is None
    
    def test_package_full_valid(self):
        """Test package with all fields."""
        data = {
            "repo": "freebsd",
            "subrepo": "main",
            "srcname": "www/firefox",
            "binname": "firefox",
            "binnames": ["firefox", "firefox-bin"],
            "visiblename": "www/firefox",
            "version": "91.0.4472.114",
            "origversion": "91.0.4472.114_1",
            "status": "newest",
            "summary": "Popular web browser",
            "categories": ["www", "network"],
            "licenses": ["MPL", "GPL"],
            "maintainers": ["maintainer@example.com"]
        }
        
        package = Package.model_validate(data)
        assert package.repo == "freebsd"
        assert package.subrepo == "main"
        assert package.srcname == "www/firefox"
        assert package.binnames == ["firefox", "firefox-bin"]
        assert len(package.categories) == 2
        assert len(package.maintainers) == 1
    
    def test_package_invalid_status(self):
        """Test package with invalid status."""
        data = {
            "repo": "freebsd",
            "visiblename": "firefox",
            "version": "91.0",
            "status": "invalid_status"
        }
        
        with pytest.raises(ValidationError):
            Package.model_validate(data)
    
    def test_package_missing_required_fields(self):
        """Test package missing required fields."""
        data = {
            "repo": "freebsd",
            # Missing visiblename and version
            "status": "newest"
        }
        
        with pytest.raises(ValidationError):
            Package.model_validate(data)


class TestProblemModel:
    """Test cases for Problem model."""
    
    def test_problem_valid(self):
        """Test valid problem data."""
        data = {
            "type": "homepage_dead",
            "data": {"url": "http://example.com", "code": 404},
            "project_name": "test-project",
            "version": "1.0.0",
            "srcname": "test/test-project",
            "binname": "test-project",
            "rawversion": "1.0.0_1"
        }
        
        problem = Problem.model_validate(data)
        assert problem.type == "homepage_dead"
        assert problem.data["url"] == "http://example.com"
        assert problem.project_name == "test-project"
        assert problem.version == "1.0.0"
    
    def test_problem_minimal_valid(self):
        """Test problem with minimal required fields."""
        data = {
            "type": "homepage_dead",
            "data": {},
            "project_name": "test-project",
            "version": "1.0.0"
        }
        
        problem = Problem.model_validate(data)
        assert problem.type == "homepage_dead"
        assert problem.project_name == "test-project"
        assert problem.srcname is None
        assert problem.binname is None
    
    def test_problem_missing_required_fields(self):
        """Test problem missing required fields."""
        data = {
            "type": "homepage_dead",
            # Missing data, project_name, version
        }
        
        with pytest.raises(ValidationError):
            Problem.model_validate(data)