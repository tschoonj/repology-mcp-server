"""Pydantic models for Repology API data structures."""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, AnyHttpUrl


class Package(BaseModel):
    """A package in a repository."""
    
    repo: str = Field(description="Repository name")
    subrepo: Optional[str] = Field(None, description="Subrepository name")
    srcname: Optional[str] = Field(None, description="Source package name")
    binname: Optional[str] = Field(None, description="Binary package name")
    binnames: Optional[List[str]] = Field(None, description="All binary package names")
    visiblename: str = Field(description="Package name as shown by Repology")
    version: str = Field(description="Package version (sanitized)")
    origversion: Optional[str] = Field(None, description="Original package version")
    status: Literal[
        "newest", "devel", "unique", "outdated", "legacy", 
        "rolling", "noscheme", "incorrect", "untrusted", "ignored"
    ] = Field(description="Package status")
    summary: Optional[str] = Field(None, description="Package description")
    categories: Optional[List[str]] = Field(None, description="Package categories")
    licenses: Optional[List[str]] = Field(None, description="Package licenses")
    maintainers: Optional[List[str]] = Field(None, description="Package maintainers")


class Problem(BaseModel):
    """A problem reported for a package."""
    
    type: str = Field(description="Problem type")
    data: Dict[str, Any] = Field(description="Additional problem details")
    project_name: str = Field(description="Repology project name")
    version: str = Field(description="Package version")
    srcname: Optional[str] = Field(None, description="Source package name")
    binname: Optional[str] = Field(None, description="Binary package name")
    rawversion: Optional[str] = Field(None, description="Raw package version")


class ProjectSummary(BaseModel):
    """Summary information about a project."""
    
    name: str = Field(description="Project name")
    newest_version: Optional[str] = Field(None, description="Newest version")
    outdated_repos: int = Field(0, description="Number of outdated repositories")
    total_repos: int = Field(0, description="Total number of repositories")
    categories: List[str] = Field(default_factory=list, description="Project categories")
    maintainers: List[str] = Field(default_factory=list, description="Project maintainers")


# Type aliases for API responses
ProjectPackages = Dict[str, List[Package]]
ProjectData = List[Package]
ProblemsData = List[Problem]