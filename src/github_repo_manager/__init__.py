"""GitHub Repository Manager — list, manage, and export your GitHub repos."""

from github_repo_manager.client import GitHubClient
from github_repo_manager.excel import write_excel

__all__ = ["GitHubClient", "__version__", "write_excel"]
__version__ = "0.1.0"
