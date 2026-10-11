"""Remote service integration for GitHub, GitLab, Bitbucket, and other Git hosting services.

Provides service detection, pull request management, and API integration
for popular Git hosting platforms.
"""

import os
import json
import re
import urllib.parse
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path


class ServiceType(Enum):
    """Supported Git hosting services."""
    GITHUB = auto()
    GITLAB = auto()
    BITBUCKET = auto()
    BITBUCKET_SERVER = auto()
    GITEA = auto()
    AZURE_DEVOPS = auto()
    SOURCEHUT = auto()
    UNKNOWN = auto()


@dataclass
class ServiceInfo:
    """Detected service information for a remote."""
    service_type: ServiceType
    service_name: str
    host: str
    owner: str
    repo: str
    api_url: str
    web_url: str
    is_ssh: bool = False


@dataclass
class PullRequest:
    """Represents a pull request / merge request."""
    id: int
    title: str
    description: str
    source_branch: str
    target_branch: str
    author: str
    state: str  # 'open', 'closed', 'merged'
    created_at: str
    updated_at: str
    web_url: str
    source_repo_owner: str = ''
    source_repo_name: str = ''
    is_draft: bool = False
    labels: List[str] = field(default_factory=list)
    reviewers: List[str] = field(default_factory=list)


# ── Service Detection ──────────────────────────────────────────

# Patterns for parsing remote URLs
_REMOTE_PATTERNS = {
    ServiceType.GITHUB: [
        re.compile(r'github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$'),
    ],
    ServiceType.GITLAB: [
        re.compile(r'gitlab\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$'),
        re.compile(r'gitlab\.[^/:]+[:/]([^/]+)/([^/]+?)(?:\.git)?$'),
    ],
    ServiceType.BITBUCKET: [
        re.compile(r'bitbucket\.org[:/]([^/]+)/([^/]+?)(?:\.git)?$'),
    ],
    ServiceType.BITBUCKET_SERVER: [
        re.compile(r'/scm/([^/]+)/([^/]+?)(?:\.git)?$'),
        re.compile(r'/projects/([^/]+)/repos/([^/]+?)(?:\.git)?$'),
    ],
    ServiceType.GITEA: [
        re.compile(r'gitea\.[^/:]+[:/]([^/]+)/([^/]+?)(?:\.git)?$'),
    ],
    ServiceType.AZURE_DEVOPS: [
        re.compile(r'dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/]+?)(?:\.git)?$'),
        re.compile(r'visualstudio\.com/([^/]+)/([^/]+)/_git/([^/]+?)(?:\.git)?$'),
        re.compile(r'ssh\.dev\.azure\.com/v3/([^/]+)/([^/]+)/([^/]+?)(?:\.git)?$'),
    ],
    ServiceType.SOURCEHUT: [
        re.compile(r'git\.sr\.ht[:/]~([^/]+)/([^/]+?)(?:\.git)?$'),
    ],
}


def detect_service(url: str) -> ServiceInfo:
    """Detect the hosting service from a remote URL.

    Args:
        url: A git remote URL (HTTPS or SSH).

    Returns:
        ServiceInfo with detected service details, or UNKNOWN if not recognized.
    """
    url = url.strip()

    # Determine if SSH
    is_ssh = url.startswith('git@') or url.startswith('ssh://')

    # Normalize URL for pattern matching
    normalized = url
    if url.startswith('git@'):
        normalized = url.replace(':', '/', 1)
    if normalized.startswith('ssh://'):
        normalized = re.sub(r'^ssh://[^@]+@', '', normalized)
        normalized = re.sub(r'^ssh://', '', normalized)

    # Try each service pattern
    for service_type, patterns in _REMOTE_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(normalized)
            if match:
                groups = match.groups()
                if service_type == ServiceType.AZURE_DEVOPS:
                    owner = groups[0]
                    repo = groups[2]
                    host = 'dev.azure.com'
                else:
                    owner = groups[0]
                    repo = groups[1]
                    # Extract host from the matched URL
                    host_match = re.match(r'https?://([^/]+)', normalized) or re.match(r'([^/:]+)', normalized)
                    host = host_match.group(1) if host_match else ''

                # Clean .git suffix
                repo = re.sub(r'\.git$', '', repo)

                return _build_service_info(service_type, url, host, owner, repo, is_ssh)

    # Try generic HTTPS URL parsing
    https_match = re.match(r'https?://([^/]+)/(.+?)(?:\.git)?$', url)
    if https_match:
        host = https_match.group(1)
        path_parts = https_match.group(2).split('/')
        if len(path_parts) >= 2:
            owner = path_parts[0]
            repo = re.sub(r'\.git$', '', path_parts[-1])
            return _build_service_info(ServiceType.UNKNOWN, url, host, owner, repo, is_ssh)

    return ServiceInfo(
        service_type=ServiceType.UNKNOWN,
        service_name='Unknown',
        host='',
        owner='',
        repo='',
        api_url='',
        web_url='',
        is_ssh=is_ssh,
    )


def _build_service_info(service_type: ServiceType, url: str,
                        host: str, owner: str, repo: str,
                        is_ssh: bool) -> ServiceInfo:
    """Build a ServiceInfo with API and web URLs."""
    service_names = {
        ServiceType.GITHUB: 'GitHub',
        ServiceType.GITLAB: 'GitLab',
        ServiceType.BITBUCKET: 'Bitbucket',
        ServiceType.BITBUCKET_SERVER: 'Bitbucket Server',
        ServiceType.GITEA: 'Gitea',
        ServiceType.AZURE_DEVOPS: 'Azure DevOps',
        ServiceType.SOURCEHUT: 'SourceHut',
        ServiceType.UNKNOWN: 'Unknown',
    }

    api_url = _build_api_url(service_type, host, owner, repo)
    web_url = _build_web_url(service_type, host, owner, repo)

    return ServiceInfo(
        service_type=service_type,
        service_name=service_names.get(service_type, 'Unknown'),
        host=host,
        owner=owner,
        repo=repo,
        api_url=api_url,
        web_url=web_url,
        is_ssh=is_ssh,
    )


def _build_api_url(service_type: ServiceType, host: str,
                   owner: str, repo: str) -> str:
    """Build the API base URL for a service."""
    if service_type == ServiceType.GITHUB:
        return f'https://api.github.com/repos/{owner}/{repo}'
    elif service_type == ServiceType.GITLAB:
        return f'https://gitlab.com/api/v4/projects/{urllib.parse.quote(f"{owner}/{repo}", safe="")}'
    elif service_type == ServiceType.BITBUCKET:
        return f'https://api.bitbucket.org/2.0/repositories/{owner}/{repo}'
    elif service_type == ServiceType.BITBUCKET_SERVER:
        return f'https://{host}/rest/api/1.0/projects/{owner}/repos/{repo}'
    elif service_type == ServiceType.GITEA:
        return f'https://{host}/api/v1/repos/{owner}/{repo}'
    elif service_type == ServiceType.AZURE_DEVOPS:
        return f'https://dev.azure.com/{owner}/{repo}/_apis/git'
    elif service_type == ServiceType.SOURCEHUT:
        return f'https://git.sr.ht/api/{owner}/{repo}'
    return ''


def _build_web_url(service_type: ServiceType, host: str,
                   owner: str, repo: str) -> str:
    """Build the web URL for a service."""
    if service_type == ServiceType.GITHUB:
        return f'https://github.com/{owner}/{repo}'
    elif service_type == ServiceType.GITLAB:
        return f'https://gitlab.com/{owner}/{repo}'
    elif service_type == ServiceType.BITBUCKET:
        return f'https://bitbucket.org/{owner}/{repo}'
    elif service_type == ServiceType.BITBUCKET_SERVER:
        return f'https://{host}/projects/{owner}/repos/{repo}'
    elif service_type == ServiceType.GITEA:
        return f'https://{host}/{owner}/{repo}'
    elif service_type == ServiceType.AZURE_DEVOPS:
        return f'https://dev.azure.com/{owner}/{repo}'
    elif service_type == ServiceType.SOURCEHUT:
        return f'https://git.sr.ht/~{owner}/{repo}'
    return f'https://{host}/{owner}/{repo}'


# ── API Client ─────────────────────────────────────────────────

class ServiceClient:
    """API client for interacting with Git hosting services.

    Supports GitHub, GitLab, and Bitbucket pull request operations.
    """

    def __init__(self, service_info: ServiceInfo, token: str = ''):
        self._service = service_info
        self._token = token or self._load_token(service_info)

    @staticmethod
    def _load_token(service_info: ServiceInfo) -> str:
        """Load API token from environment or config file."""
        # Check environment variables
        env_map = {
            ServiceType.GITHUB: 'GITHUB_TOKEN',
            ServiceType.GITLAB: 'GITLAB_TOKEN',
            ServiceType.BITBUCKET: 'BITBUCKET_TOKEN',
            ServiceType.BITBUCKET_SERVER: 'BITBUCKET_TOKEN',
            ServiceType.GITEA: 'GITEA_TOKEN',
            ServiceType.AZURE_DEVOPS: 'AZURE_DEVOPS_TOKEN',
            ServiceType.SOURCEHUT: 'SOURCEHUT_TOKEN',
        }
        env_var = env_map.get(service_info.service_type)
        if env_var:
            token = os.environ.get(env_var, '')
            if token:
                return token

        # Check config file
        config_path = Path.home() / '.igit' / 'services.json'
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                service_key = service_info.service_type.name.lower()
                return data.get(service_key, {}).get('token', '')
            except (json.JSONDecodeError, OSError):
                pass

        return ''

    @property
    def has_token(self) -> bool:
        return bool(self._token)

    @property
    def service_name(self) -> str:
        return self._service.service_name

    @property
    def service_type(self) -> ServiceType:
        return self._service.service_type

    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'iGit/1.0',
        }
        if self._token:
            if self._service.service_type == ServiceType.GITHUB:
                headers['Authorization'] = f'Bearer {self._token}'
                headers['X-GitHub-Api-Version'] = '2022-11-28'
            elif self._service.service_type == ServiceType.GITLAB:
                headers['Authorization'] = f'Bearer {self._token}'
            elif self._service.service_type == ServiceType.BITBUCKET:
                headers['Authorization'] = f'Bearer {self._token}'
            elif self._service.service_type == ServiceType.BITBUCKET_SERVER:
                headers['Authorization'] = f'Bearer {self._token}'
            elif self._service.service_type == ServiceType.GITEA:
                headers['Authorization'] = f'token {self._token}'
            elif self._service.service_type == ServiceType.AZURE_DEVOPS:
                headers['Authorization'] = f'Basic {self._token}'
        return headers

    # ── Pull Requests ───────────────────────────────────────────

    def list_pull_requests(self, state: str = 'open') -> Tuple[bool, List[PullRequest], str]:
        """List pull requests for the repository.

        Args:
            state: 'open', 'closed', 'all'

        Returns:
            (success, pull_requests, error_message)
        """
        if not self._service.api_url:
            return False, [], 'No API URL configured'

        try:
            import requests
        except ImportError:
            return False, [], 'The "requests" library is required. Install with: pip install requests'

        try:
            if self._service.service_type == ServiceType.GITHUB:
                return self._list_github_prs(state)
            elif self._service.service_type == ServiceType.GITLAB:
                return self._list_gitlab_mrs(state)
            elif self._service.service_type == ServiceType.BITBUCKET:
                return self._list_bitbucket_prs(state)
            else:
                return False, [], f'{self._service.service_name} PR listing not yet supported'
        except Exception as e:
            return False, [], str(e)

    def get_pull_request(self, pr_id: int) -> Tuple[bool, Optional[PullRequest], str]:
        """Get details of a specific pull request."""
        try:
            import requests
        except ImportError:
            return False, None, 'The "requests" library is required.'

        try:
            if self._service.service_type == ServiceType.GITHUB:
                return self._get_github_pr(pr_id)
            elif self._service.service_type == ServiceType.GITLAB:
                return self._get_gitlab_mr(pr_id)
            elif self._service.service_type == ServiceType.BITBUCKET:
                return self._get_bitbucket_pr(pr_id)
            else:
                return False, None, f'{self._service.service_name} not supported'
        except Exception as e:
            return False, None, str(e)

    def create_pull_request(self, title: str, description: str,
                            source_branch: str, target_branch: str = 'main',
                            draft: bool = False) -> Tuple[bool, Optional[PullRequest], str]:
        """Create a pull request.

        Args:
            title: PR title
            description: PR description/body
            source_branch: The branch with changes
            target_branch: The branch to merge into
            draft: Whether to create as draft PR

        Returns:
            (success, pull_request, error_message)
        """
        try:
            import requests
        except ImportError:
            return False, None, 'The "requests" library is required.'

        try:
            if self._service.service_type == ServiceType.GITHUB:
                return self._create_github_pr(title, description, source_branch, target_branch, draft)
            elif self._service.service_type == ServiceType.GITLAB:
                return self._create_gitlab_mr(title, description, source_branch, target_branch, draft)
            elif self._service.service_type == ServiceType.BITBUCKET:
                return self._create_bitbucket_pr(title, description, source_branch, target_branch)
            else:
                return False, None, f'{self._service.service_name} PR creation not yet supported'
        except Exception as e:
            return False, None, str(e)

    def merge_pull_request(self, pr_id: int, method: str = 'merge') -> Tuple[bool, str]:
        """Merge a pull request.

        Args:
            pr_id: Pull request ID/number
            method: 'merge', 'squash', 'rebase'

        Returns:
            (success, message)
        """
        try:
            import requests
        except ImportError:
            return False, 'The "requests" library is required.'

        try:
            if self._service.service_type == ServiceType.GITHUB:
                return self._merge_github_pr(pr_id, method)
            elif self._service.service_type == ServiceType.GITLAB:
                return self._merge_gitlab_mr(pr_id, method)
            elif self._service.service_type == ServiceType.BITBUCKET:
                return self._merge_bitbucket_pr(pr_id)
            else:
                return False, f'{self._service.service_name} PR merge not yet supported'
        except Exception as e:
            return False, str(e)

    def close_pull_request(self, pr_id: int) -> Tuple[bool, str]:
        """Close a pull request without merging."""
        try:
            import requests
        except ImportError:
            return False, 'The "requests" library is required.'

        try:
            if self._service.service_type == ServiceType.GITHUB:
                return self._close_github_pr(pr_id)
            elif self._service.service_type == ServiceType.GITLAB:
                return self._close_gitlab_mr(pr_id)
            elif self._service.service_type == ServiceType.BITBUCKET:
                return self._close_bitbucket_pr(pr_id)
            else:
                return False, f'{self._service.service_name} PR close not yet supported'
        except Exception as e:
            return False, str(e)

    # ── GitHub API Implementations ──────────────────────────────

    def _list_github_prs(self, state: str) -> Tuple[bool, List[PullRequest], str]:
        import requests
        state_param = 'all' if state == 'all' else state
        url = f'{self._service.api_url}/pulls?state={state_param}&per_page=50'
        resp = requests.get(url, headers=self.get_headers(), timeout=30)
        if resp.status_code != 200:
            return False, [], f'GitHub API error: {resp.status_code} {resp.text[:200]}'

        prs = []
        for data in resp.json():
            prs.append(PullRequest(
                id=data['number'],
                title=data['title'],
                description=data.get('body', '') or '',
                source_branch=data['head']['ref'],
                target_branch=data['base']['ref'],
                author=data['user']['login'],
                state='merged' if data.get('merged_at') else data['state'],
                created_at=data['created_at'],
                updated_at=data['updated_at'],
                web_url=data['html_url'],
                source_repo_owner=data['head']['repo']['owner']['login'] if data.get('head', {}).get('repo') else '',
                source_repo_name=data['head']['repo']['name'] if data.get('head', {}).get('repo') else '',
                is_draft=data.get('draft', False),
                labels=[l['name'] for l in data.get('labels', [])],
            ))
        return True, prs, ''

    def _get_github_pr(self, pr_id: int) -> Tuple[bool, Optional[PullRequest], str]:
        import requests
        url = f'{self._service.api_url}/pulls/{pr_id}'
        resp = requests.get(url, headers=self.get_headers(), timeout=30)
        if resp.status_code != 200:
            return False, None, f'GitHub API error: {resp.status_code}'

        data = resp.json()
        pr = PullRequest(
            id=data['number'],
            title=data['title'],
            description=data.get('body', '') or '',
            source_branch=data['head']['ref'],
            target_branch=data['base']['ref'],
            author=data['user']['login'],
            state='merged' if data.get('merged_at') else data['state'],
            created_at=data['created_at'],
            updated_at=data['updated_at'],
            web_url=data['html_url'],
            is_draft=data.get('draft', False),
            labels=[l['name'] for l in data.get('labels', [])],
        )
        return True, pr, ''

    def _create_github_pr(self, title: str, description: str,
                          source_branch: str, target_branch: str,
                          draft: bool) -> Tuple[bool, Optional[PullRequest], str]:
        import requests
        payload = {
            'title': title,
            'body': description,
            'head': source_branch,
            'base': target_branch,
            'draft': draft,
        }
        url = f'{self._service.api_url}/pulls'
        resp = requests.post(url, json=payload, headers=self.get_headers(), timeout=30)
        if resp.status_code not in (200, 201):
            return False, None, f'GitHub API error: {resp.status_code} {resp.text[:300]}'

        data = resp.json()
        pr = PullRequest(
            id=data['number'],
            title=data['title'],
            description=data.get('body', '') or '',
            source_branch=data['head']['ref'],
            target_branch=data['base']['ref'],
            author=data['user']['login'],
            state=data['state'],
            created_at=data['created_at'],
            updated_at=data['updated_at'],
            web_url=data['html_url'],
            is_draft=data.get('draft', False),
        )
        return True, pr, ''

    def _merge_github_pr(self, pr_id: int, method: str) -> Tuple[bool, str]:
        import requests
        merge_methods = {'merge': 'merge', 'squash': 'squash', 'rebase': 'rebase'}
        payload = {
            'merge_method': merge_methods.get(method, 'merge'),
        }
        url = f'{self._service.api_url}/pulls/{pr_id}/merge'
        resp = requests.put(url, json=payload, headers=self.get_headers(), timeout=30)
        if resp.status_code == 200:
            return True, 'Pull request merged successfully'
        elif resp.status_code == 405:
            return False, 'Pull request cannot be merged (conflicts or requirements not met)'
        else:
            return False, f'GitHub API error: {resp.status_code} {resp.text[:200]}'

    def _close_github_pr(self, pr_id: int) -> Tuple[bool, str]:
        import requests
        url = f'{self._service.api_url}/pulls/{pr_id}'
        resp = requests.patch(url, json={'state': 'closed'}, headers=self.get_headers(), timeout=30)
        if resp.status_code == 200:
            return True, 'Pull request closed'
        return False, f'GitHub API error: {resp.status_code}'

    # ── GitLab API Implementations ──────────────────────────────

    def _list_gitlab_mrs(self, state: str) -> Tuple[bool, List[PullRequest], str]:
        import requests
        state_param = 'opened' if state == 'open' else state
        url = f'{self._service.api_url}/merge_requests?state={state_param}&per_page=50'
        resp = requests.get(url, headers=self.get_headers(), timeout=30)
        if resp.status_code != 200:
            return False, [], f'GitLab API error: {resp.status_code}'

        prs = []
        for data in resp.json():
            prs.append(PullRequest(
                id=data['iid'],
                title=data['title'],
                description=data.get('description', '') or '',
                source_branch=data['source_branch'],
                target_branch=data['target_branch'],
                author=data['author']['username'],
                state='merged' if data.get('state') == 'merged' else data['state'],
                created_at=data['created_at'],
                updated_at=data['updated_at'],
                web_url=data['web_url'],
                is_draft=data.get('draft', False) or data.get('work_in_progress', False),
                labels=data.get('labels', []),
            ))
        return True, prs, ''

    def _get_gitlab_mr(self, mr_id: int) -> Tuple[bool, Optional[PullRequest], str]:
        import requests
        url = f'{self._service.api_url}/merge_requests/{mr_id}'
        resp = requests.get(url, headers=self.get_headers(), timeout=30)
        if resp.status_code != 200:
            return False, None, f'GitLab API error: {resp.status_code}'

        data = resp.json()
        pr = PullRequest(
            id=data['iid'],
            title=data['title'],
            description=data.get('description', '') or '',
            source_branch=data['source_branch'],
            target_branch=data['target_branch'],
            author=data['author']['username'],
            state='merged' if data.get('state') == 'merged' else data['state'],
            created_at=data['created_at'],
            updated_at=data['updated_at'],
            web_url=data['web_url'],
            is_draft=data.get('draft', False) or data.get('work_in_progress', False),
            labels=data.get('labels', []),
        )
        return True, pr, ''

    def _create_gitlab_mr(self, title: str, description: str,
                          source_branch: str, target_branch: str,
                          draft: bool) -> Tuple[bool, Optional[PullRequest], str]:
        import requests
        payload = {
            'title': title,
            'description': description,
            'source_branch': source_branch,
            'target_branch': target_branch,
            'draft': draft,
        }
        url = f'{self._service.api_url}/merge_requests'
        resp = requests.post(url, json=payload, headers=self.get_headers(), timeout=30)
        if resp.status_code not in (200, 201):
            return False, None, f'GitLab API error: {resp.status_code} {resp.text[:300]}'

        data = resp.json()
        pr = PullRequest(
            id=data['iid'],
            title=data['title'],
            description=data.get('description', '') or '',
            source_branch=data['source_branch'],
            target_branch=data['target_branch'],
            author=data['author']['username'],
            state=data['state'],
            created_at=data['created_at'],
            updated_at=data['updated_at'],
            web_url=data['web_url'],
            is_draft=data.get('draft', False) or data.get('work_in_progress', False),
        )
        return True, pr, ''

    def _merge_gitlab_mr(self, mr_id: int, method: str) -> Tuple[bool, str]:
        import requests
        payload = {}
        if method == 'squash':
            payload['squash'] = True
        url = f'{self._service.api_url}/merge_requests/{mr_id}/merge'
        resp = requests.put(url, json=payload, headers=self.get_headers(), timeout=30)
        if resp.status_code == 200:
            return True, 'Merge request merged successfully'
        return False, f'GitLab API error: {resp.status_code} {resp.text[:200]}'

    def _close_gitlab_mr(self, mr_id: int) -> Tuple[bool, str]:
        import requests
        url = f'{self._service.api_url}/merge_requests/{mr_id}'
        resp = requests.put(url, json={'state_event': 'close'}, headers=self.get_headers(), timeout=30)
        if resp.status_code == 200:
            return True, 'Merge request closed'
        return False, f'GitLab API error: {resp.status_code}'

    # ── Bitbucket API Implementations ───────────────────────────

    def _list_bitbucket_prs(self, state: str) -> Tuple[bool, List[PullRequest], str]:
        import requests
        state_param = {'open': 'OPEN', 'closed': 'MERGED,CLOSED,DECLINED', 'all': 'ALL'}
        url = f'{self._service.api_url}/pullrequests?state={state_param.get(state, "OPEN")}'
        resp = requests.get(url, headers=self.get_headers(), timeout=30)
        if resp.status_code != 200:
            return False, [], f'Bitbucket API error: {resp.status_code}'

        prs = []
        for data in resp.json().get('values', []):
            prs.append(PullRequest(
                id=data['id'],
                title=data['title'],
                description=data.get('description', '') or '',
                source_branch=data['source']['branch']['name'],
                target_branch=data['destination']['branch']['name'],
                author=data['author']['display_name'],
                state=data.get('state', '').lower(),
                created_at=data['created_on'],
                updated_at=data['updated_on'],
                web_url=data['links']['html']['href'],
            ))
        return True, prs, ''

    def _get_bitbucket_pr(self, pr_id: int) -> Tuple[bool, Optional[PullRequest], str]:
        import requests
        url = f'{self._service.api_url}/pullrequests/{pr_id}'
        resp = requests.get(url, headers=self.get_headers(), timeout=30)
        if resp.status_code != 200:
            return False, None, f'Bitbucket API error: {resp.status_code}'

        data = resp.json()
        pr = PullRequest(
            id=data['id'],
            title=data['title'],
            description=data.get('description', '') or '',
            source_branch=data['source']['branch']['name'],
            target_branch=data['destination']['branch']['name'],
            author=data['author']['display_name'],
            state=data.get('state', '').lower(),
            created_at=data['created_on'],
            updated_at=data['updated_on'],
            web_url=data['links']['html']['href'],
        )
        return True, pr, ''

    def _create_bitbucket_pr(self, title: str, description: str,
                             source_branch: str, target_branch: str) -> Tuple[bool, Optional[PullRequest], str]:
        import requests
        payload = {
            'title': title,
            'description': description,
            'source': {'branch': {'name': source_branch}},
            'destination': {'branch': {'name': target_branch}},
        }
        url = f'{self._service.api_url}/pullrequests'
        resp = requests.post(url, json=payload, headers=self.get_headers(), timeout=30)
        if resp.status_code not in (200, 201):
            return False, None, f'Bitbucket API error: {resp.status_code} {resp.text[:300]}'

        data = resp.json()
        pr = PullRequest(
            id=data['id'],
            title=data['title'],
            description=data.get('description', '') or '',
            source_branch=data['source']['branch']['name'],
            target_branch=data['destination']['branch']['name'],
            author=data['author']['display_name'],
            state=data.get('state', '').lower(),
            created_at=data['created_on'],
            updated_at=data['updated_on'],
            web_url=data['links']['html']['href'],
        )
        return True, pr, ''

    def _merge_bitbucket_pr(self, pr_id: int) -> Tuple[bool, str]:
        import requests
        url = f'{self._service.api_url}/pullrequests/{pr_id}/merge'
        resp = requests.post(url, headers=self.get_headers(), timeout=30)
        if resp.status_code == 200:
            return True, 'Pull request merged successfully'
        return False, f'Bitbucket API error: {resp.status_code} {resp.text[:200]}'

    def _close_bitbucket_pr(self, pr_id: int) -> Tuple[bool, str]:
        import requests
        # Bitbucket uses "decline" to close without merging
        url = f'{self._service.api_url}/pullrequests/{pr_id}/decline'
        resp = requests.post(url, headers=self.get_headers(), timeout=30)
        if resp.status_code == 200:
            return True, 'Pull request declined/closed'
        return False, f'Bitbucket API error: {resp.status_code}'


# ── Token Management ───────────────────────────────────────────

def save_token(service_type: ServiceType, token: str) -> bool:
    """Save an API token for a service to the config file."""
    config_dir = Path.home() / '.igit'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'services.json'

    data = {}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    service_key = service_type.name.lower()
    if service_key not in data:
        data[service_key] = {}
    data[service_key]['token'] = token

    try:
        config_path.write_text(json.dumps(data, indent=2))
        return True
    except OSError:
        return False


def get_token(service_type: ServiceType) -> str:
    """Get the saved API token for a service."""
    config_path = Path.home() / '.igit' / 'services.json'
    if not config_path.exists():
        return ''

    try:
        data = json.loads(config_path.read_text())
        service_key = service_type.name.lower()
        return data.get(service_key, {}).get('token', '')
    except (json.JSONDecodeError, OSError):
        return ''
