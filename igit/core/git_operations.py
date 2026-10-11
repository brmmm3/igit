"""Core Git operations wrapper using GitPython."""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

import git
from git import Repo, GitCommandError, InvalidGitRepositoryError, NoSuchPathError


@dataclass
class FileStatus:
    """Represents a file's status in the working tree."""
    path: str
    staged: bool
    status: str  # 'M' modified, 'A' added, 'D' deleted, 'R' renamed, '?' untracked, '!!' ignored
    staged_status: str = ''
    unstaged_status: str = ''
    old_path: str = ''


@dataclass
class CommitInfo:
    """Represents a commit."""
    hexsha: str
    short_sha: str
    author_name: str
    author_email: str
    authored_datetime: datetime
    committer_name: str
    committer_email: str
    committed_datetime: datetime
    message: str
    summary: str
    parents: List[str] = field(default_factory=list)
    branches: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    is_head: bool = False


@dataclass
class BranchInfo:
    """Represents a branch."""
    name: str
    is_head: bool
    is_remote: bool
    remote_name: str = ''
    upstream: str = ''
    ahead: int = 0
    behind: int = 0
    commit_sha: str = ''


@dataclass
class StashInfo:
    """Represents a stash entry."""
    index: int
    message: str
    branch: str
    datetime: datetime


@dataclass
class TagInfo:
    """Represents a tag."""
    name: str
    commit_sha: str
    message: str = ''
    is_annotated: bool = False
    tagger_name: str = ''
    tagger_email: str = ''
    tag_date: Optional[datetime] = None


@dataclass
class RemoteInfo:
    """Represents a remote."""
    name: str
    url: str
    fetch_url: str = ''


@dataclass
class SubmoduleInfo:
    """Represents a submodule."""
    name: str
    path: str
    url: str
    branch: str = ''
    commit_sha: str = ''


@dataclass
class ConflictFile:
    """Represents a conflicted file."""
    path: str
    status: str  # 'both_modified', 'both_added', 'both_deleted', 'added_by_us', etc.


class GitOperations:
    """Wrapper around GitPython for all git operations."""

    def __init__(self, repo_path: Optional[str] = None):
        self._repo: Optional[Repo] = None
        if repo_path:
            self.open(repo_path)

    def open(self, path: str) -> bool:
        """Open a git repository at the given path."""
        try:
            self._repo = Repo(path, search_parent_directories=True)
            return True
        except (InvalidGitRepositoryError, NoSuchPathError):
            self._repo = None
            return False

    @property
    def is_open(self) -> bool:
        return self._repo is not None

    @property
    def repo(self) -> Repo:
        if self._repo is None:
            raise RuntimeError("No repository open")
        return self._repo

    @property
    def repo_path(self) -> str:
        return self.repo.working_tree_dir or ''

    @property
    def repo_name(self) -> str:
        return os.path.basename(self.repo_path) if self.repo_path else ''

    @property
    def current_branch(self) -> str:
        try:
            return self.repo.active_branch.name
        except (TypeError, ValueError):
            # Detached HEAD
            return f"HEAD detached at {self.repo.head.commit.hexsha[:7]}"

    @property
    def is_detached(self) -> bool:
        try:
            return self.repo.head.is_detached
        except Exception:
            return True

    # ── Repository ──────────────────────────────────────────────

    def init_repo(self, path: str) -> bool:
        """Initialize a new git repository."""
        try:
            self._repo = Repo.init(path)
            return True
        except Exception:
            return False

    def clone_repo(self, url: str, target_path: str, progress_callback=None) -> bool:
        """Clone a repository."""
        try:
            self._repo = Repo.clone_from(
                url, target_path,
                progress=progress_callback,
                multi_options=None
            )
            return True
        except Exception:
            return False

    # ── File Status ─────────────────────────────────────────────

    def get_file_status(self) -> List[FileStatus]:
        """Get the status of all files in the working tree."""
        result: List[FileStatus] = []
        if not self.is_open:
            return result

        repo = self.repo

        # Staged changes (index vs HEAD)
        staged_diffs = repo.index.diff(repo.head.commit) if repo.head.is_valid() else repo.index.diff(None)
        staged_files: Dict[str, FileStatus] = {}
        for diff in staged_diffs:
            path = diff.b_path or diff.a_path or ''
            status = self._diff_status_char(diff)
            fs = FileStatus(
                path=path,
                staged=True,
                status=status,
                staged_status=status,
                old_path=diff.a_path or ''
            )
            staged_files[path] = fs

        # Unstaged changes (working tree vs index)
        unstaged_diffs = repo.index.diff(None)
        for diff in unstaged_diffs:
            path = diff.b_path or diff.a_path or ''
            status = self._diff_status_char(diff)
            if path in staged_files:
                staged_files[path].unstaged_status = status
                staged_files[path].staged = False
            else:
                fs = FileStatus(
                    path=path,
                    staged=False,
                    status=status,
                    unstaged_status=status,
                    old_path=diff.a_path or ''
                )
                staged_files[path] = fs

        # Untracked files
        for path in repo.untracked_files:
            fs = FileStatus(
                path=path,
                staged=False,
                status='?',
                unstaged_status='?'
            )
            staged_files[path] = fs

        result = list(staged_files.values())
        result.sort(key=lambda x: x.path)
        return result

    def _diff_status_char(self, diff) -> str:
        if diff.new_file:
            return 'A'
        if diff.deleted_file:
            return 'D'
        if diff.renamed:
            return 'R'
        if diff.change_type == 'M':
            return 'M'
        return 'M'

    # ── Staging / Unstaging ────────────────────────────────────

    def stage_file(self, path: str) -> bool:
        """Stage a file."""
        try:
            self.repo.index.add([path])
            return True
        except GitCommandError:
            return False

    def stage_hunk(self, path: str, start_line: int, end_line: int) -> bool:
        """Stage a specific hunk in a file using git add -p."""
        try:
            # Use git directly for hunk staging
            patch = self._get_patch_for_lines(path, start_line, end_line)
            if patch:
                proc = subprocess.run(
                    ['git', '-C', self.repo_path, 'apply', '--cached', '--unidiff-zero'],
                    input=patch,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return proc.returncode == 0
            return False
        except Exception:
            return False

    def _get_patch_for_lines(self, path: str, start: int, end: int) -> str:
        """Generate a patch for specific lines in a file."""
        try:
            # Get the diff for the file
            result = subprocess.run(
                ['git', '-C', self.repo_path, 'diff', '--', path],
                capture_output=True, text=True, timeout=30
            )
            return result.stdout
        except Exception:
            return ''

    def unstage_file(self, path: str) -> bool:
        """Unstage a file."""
        try:
            self.repo.index.remove([path], working_tree=False, r=True)
            return True
        except GitCommandError:
            # Try reset instead
            try:
                subprocess.run(
                    ['git', '-C', self.repo_path, 'reset', 'HEAD', '--', path],
                    capture_output=True, timeout=30
                )
                return True
            except Exception:
                return False

    def discard_changes(self, path: str) -> bool:
        """Discard all changes in a file."""
        try:
            self.repo.index.checkout([path], force=True)
            return True
        except GitCommandError:
            return False

    def discard_hunk(self, path: str, start_line: int, end_line: int) -> bool:
        """Discard a specific hunk."""
        try:
            patch = self._get_patch_for_lines(path, start_line, end_line)
            if patch:
                # Reverse apply
                proc = subprocess.run(
                    ['git', '-C', self.repo_path, 'apply', '--reverse', '--unidiff-zero'],
                    input=patch,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return proc.returncode == 0
            return False
        except Exception:
            return False

    # ── Committing ──────────────────────────────────────────────

    def commit(self, message: str, author: Optional[str] = None,
               signoff: bool = False, gpg_sign: bool = False) -> Tuple[bool, str]:
        """Create a commit."""
        try:
            kwargs: Dict[str, Any] = {'message': message}
            if author:
                kwargs['author'] = author
                kwargs['committer'] = author
            if signoff:
                kwargs['signoff'] = True
            if gpg_sign:
                kwargs['gpg_sign'] = True
            self.repo.index.commit(**kwargs)
            return True, self.repo.head.commit.hexsha
        except GitCommandError as e:
            return False, str(e)

    def amend_commit(self, message: Optional[str] = None,
                     author: Optional[str] = None) -> bool:
        """Amend the last commit."""
        try:
            kwargs: Dict[str, Any] = {}
            if message:
                kwargs['message'] = message
            if author:
                kwargs['author'] = author
                kwargs['committer'] = author
            self.repo.index.commit(**kwargs)
            return True
        except GitCommandError:
            return False

    # ── Diff ────────────────────────────────────────────────────

    def get_diff(self, path: str = '', staged: bool = False,
                 commit_a: str = '', commit_b: str = '') -> str:
        """Get the diff for a file or between commits."""
        try:
            if commit_a and commit_b:
                diff = self.repo.git.diff(commit_a, commit_b, '--', path)
            elif staged:
                diff = self.repo.git.diff('--cached', '--', path)
            else:
                diff = self.repo.git.diff('--', path)
            return diff
        except GitCommandError:
            return ''

    # Canonical empty tree object for diffing the root commit
    _EMPTY_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'

    def _commit_base(self, commit_sha: str) -> str:
        """Return the diff base for a commit: its parent, or the empty tree
        if the commit is a root commit (has no parents)."""
        try:
            commit = self.repo.commit(commit_sha)
            if commit.parents:
                return commit.parents[0].hexsha
        except Exception:
            pass
        return self._EMPTY_TREE

    def get_diff_for_commit(self, commit_sha: str) -> str:
        """Get the diff for a specific commit."""
        try:
            base = self._commit_base(commit_sha)
            return self.repo.git.diff(base, commit_sha)
        except GitCommandError:
            return ''

    def get_diff_for_commit_range(self, newest_sha: str, oldest_sha: str) -> str:
        """Get the combined diff of a range of commits (oldest..newest).

        Uses the oldest commit's parent (or empty tree for a root commit) as
        the base, so the diff shows the total change introduced across all
        selected commits.
        """
        try:
            base = self._commit_base(oldest_sha)
            return self.repo.git.diff(base, newest_sha)
        except GitCommandError:
            return ''

    def get_commit_stats(self, commit_sha: str) -> Dict[str, Any]:
        """Get change statistics for a single commit.

        Returns a dict with:
          - 'files': list of {path, added, removed, bytes}
          - 'total_added', 'total_removed', 'total_files', 'total_bytes'
        """
        base = self._commit_base(commit_sha)
        return self._diff_stats(base, commit_sha)

    def get_commit_range_stats(self, newest_sha: str, oldest_sha: str) -> Dict[str, Any]:
        """Get change statistics for a range of commits (oldest..newest)."""
        base = self._commit_base(oldest_sha)
        return self._diff_stats(base, newest_sha)

    def _diff_stats(self, base: str, target: str) -> Dict[str, Any]:
        """Compute per-file and total change statistics between two refs."""
        result: Dict[str, Any] = {
            'files': [],
            'total_added': 0,
            'total_removed': 0,
            'total_files': 0,
            'total_bytes': 0,
        }
        try:
            # Per-file added/removed line counts via --numstat
            numstat = self.repo.git.diff('--numstat', base, target)
            for line in numstat.splitlines():
                parts = line.split('\t')
                if len(parts) < 3:
                    continue
                added_s, removed_s, path = parts[0], parts[1], parts[2]
                if added_s == '-' or removed_s == '-':
                    # Binary file
                    added = removed = 0
                else:
                    added = int(added_s)
                    removed = int(removed_s)
                result['files'].append({
                    'path': path,
                    'added': added,
                    'removed': removed,
                    'bytes': 0,
                })
                result['total_added'] += added
                result['total_removed'] += removed

            result['total_files'] = len(result['files'])

            # Per-file byte sizes of the target version
            for f in result['files']:
                try:
                    size = int(self.repo.git.cat_file('-s', f'{target}:{f["path"]}'))
                    f['bytes'] = size
                    result['total_bytes'] += size
                except GitCommandError:
                    # File deleted in target — try the base version
                    try:
                        size = int(self.repo.git.cat_file('-s', f'{base}:{f["path"]}'))
                        f['bytes'] = size
                        result['total_bytes'] += size
                    except GitCommandError:
                        pass
        except GitCommandError:
            pass
        return result

    # ── Log / History ───────────────────────────────────────────

    def get_commits(self, branch: str = '', max_count: int = 100,
                    skip: int = 0, path: str = '') -> List[CommitInfo]:
        """Get commit history."""
        commits: List[CommitInfo] = []
        try:
            kwargs: Dict[str, Any] = {
                'max_count': max_count,
                'skip': skip,
                'all': True
            }
            if branch:
                kwargs['rev'] = branch
            if path:
                kwargs['paths'] = path

            for commit in self.repo.iter_commits(**kwargs):
                ci = self._commit_to_info(commit)
                commits.append(ci)
        except Exception:
            pass
        return commits

    def _commit_to_info(self, commit) -> CommitInfo:
        """Convert a GitPython commit to CommitInfo."""
        branches = []
        try:
            for b in self.repo.branches:
                if b.commit == commit:
                    branches.append(b.name)
        except Exception:
            pass

        tags = []
        try:
            for t in self.repo.tags:
                if t.commit == commit:
                    tags.append(t.name)
        except Exception:
            pass

        return CommitInfo(
            hexsha=commit.hexsha,
            short_sha=commit.hexsha[:7],
            author_name=commit.author.name,
            author_email=commit.author.email,
            authored_datetime=commit.authored_datetime,
            committer_name=commit.committer.name,
            committer_email=commit.committer.email,
            committed_datetime=commit.committed_datetime,
            message=commit.message.strip(),
            summary=commit.summary,
            parents=[p.hexsha for p in commit.parents],
            branches=branches,
            tags=tags,
            is_head=(commit == self.repo.head.commit) if self.repo.head.is_valid() else False
        )

    def get_commit(self, sha: str) -> Optional[CommitInfo]:
        """Get a single commit by SHA."""
        try:
            commit = self.repo.commit(sha)
            return self._commit_to_info(commit)
        except Exception:
            return None

    # ── Branches ────────────────────────────────────────────────

    def get_branches(self) -> List[BranchInfo]:
        """Get all branches."""
        branches: List[BranchInfo] = []
        try:
            # Local branches
            for b in self.repo.branches:
                upstream = b.tracking_branch()
                ahead = behind = 0
                upstream_name = ''
                if upstream:
                    upstream_name = upstream.name
                    try:
                        ahead = sum(1 for _ in self.repo.iter_commits(f'{upstream.name}..{b.name}'))
                        behind = sum(1 for _ in self.repo.iter_commits(f'{b.name}..{upstream.name}'))
                    except Exception:
                        pass

                branches.append(BranchInfo(
                    name=b.name,
                    is_head=(b.name == self.current_branch),
                    is_remote=False,
                    upstream=upstream_name,
                    ahead=ahead,
                    behind=behind,
                    commit_sha=b.commit.hexsha[:7]
                ))

            # Remote branches (from locally cached refs; no network fetch here)
            for r in self.repo.remotes:
                for ref in r.refs:
                    name = ref.remote_head
                    if name and name != 'HEAD':
                        branches.append(BranchInfo(
                            name=f"{r.name}/{name}",
                            is_head=False,
                            is_remote=True,
                            remote_name=r.name,
                            commit_sha=ref.commit.hexsha[:7]
                        ))
        except Exception:
            pass
        return branches

    def create_branch(self, name: str, base: str = '') -> bool:
        """Create a new branch."""
        try:
            if base:
                base_commit = self.repo.commit(base)
                self.repo.create_head(name, base_commit)
            else:
                self.repo.create_head(name)
            return True
        except GitCommandError:
            return False

    def delete_branch(self, name: str, force: bool = False) -> bool:
        """Delete a branch."""
        try:
            head = self.repo.heads[name]
            self.repo.delete_head(head, force=force)
            return True
        except (GitCommandError, IndexError):
            return False

    def rename_branch(self, old_name: str, new_name: str) -> bool:
        """Rename a branch."""
        try:
            self.repo.git.branch('-m', old_name, new_name)
            return True
        except GitCommandError:
            return False

    def checkout_branch(self, name: str) -> bool:
        """Checkout a branch."""
        try:
            self.repo.git.checkout(name)
            return True
        except GitCommandError:
            return False

    def checkout_commit(self, sha: str) -> bool:
        """Checkout a specific commit (detached HEAD)."""
        try:
            self.repo.git.checkout(sha)
            return True
        except GitCommandError:
            return False

    def merge_branch(self, branch: str, commit_msg: str = '',
                     no_ff: bool = True, squash: bool = False) -> Tuple[bool, str]:
        """Merge a branch into the current branch."""
        try:
            args = [branch]
            if no_ff:
                args.insert(0, '--no-ff')
            if squash:
                args.insert(0, '--squash')
            if commit_msg:
                args.extend(['-m', commit_msg])
            self.repo.git.merge(*args)
            return True, ''
        except GitCommandError as e:
            return False, str(e)

    def rebase_branch(self, onto: str, branch: str = '') -> Tuple[bool, str]:
        """Rebase current branch onto another."""
        try:
            if branch:
                self.repo.git.rebase(branch, onto=onto)
            else:
                self.repo.git.rebase(onto)
            return True, ''
        except GitCommandError as e:
            return False, str(e)

    def abort_rebase(self) -> bool:
        """Abort a rebase in progress."""
        try:
            self.repo.git.rebase('--abort')
            return True
        except GitCommandError:
            return False

    def continue_rebase(self) -> bool:
        """Continue a rebase after resolving conflicts."""
        try:
            self.repo.git.rebase('--continue')
            return True
        except GitCommandError:
            return False

    # ── Tags ────────────────────────────────────────────────────

    def get_tags(self) -> List[TagInfo]:
        """Get all tags."""
        tags: List[TagInfo] = []
        try:
            for t in self.repo.tags:
                tag = TagInfo(
                    name=t.name,
                    commit_sha=t.commit.hexsha[:7],
                )
                # Check if annotated
                if t.tag:
                    tag.is_annotated = True
                    tag.message = t.tag.message.strip() if t.tag.message else ''
                    tag.tagger_name = t.tag.tagger.name if t.tag.tagger else ''
                    tag.tagger_email = t.tag.tagger.email if t.tag.tagger else ''
                    tag.tag_date = t.tag.tagged_datetime if hasattr(t.tag, 'tagged_datetime') else None
                tags.append(tag)
        except Exception:
            pass
        return tags

    def create_tag(self, name: str, message: str = '',
                   annotated: bool = False, ref: str = 'HEAD') -> bool:
        """Create a tag."""
        try:
            if annotated:
                self.repo.create_tag(name, ref=ref, message=message)
            else:
                self.repo.create_tag(name, ref=ref)
            return True
        except GitCommandError:
            return False

    def delete_tag(self, name: str) -> bool:
        """Delete a tag."""
        try:
            self.repo.delete_tag(name)
            return True
        except GitCommandError:
            return False

    # ── Stash ───────────────────────────────────────────────────

    def get_stashes(self) -> List[StashInfo]:
        """Get all stashes."""
        stashes: List[StashInfo] = []
        try:
            for i, entry in enumerate(self.repo.git.stash('list', '--format=%gd|%gs').split('\n')):
                if not entry.strip():
                    continue
                parts = entry.split('|', 1)
                ref = parts[0].strip()
                message = parts[1].strip() if len(parts) > 1 else ''
                # Parse stash@{0}: On branch: message
                branch = ''
                if 'On ' in message:
                    branch_part = message.split('On ')[1].split(':')[0]
                    branch = branch_part.strip()
                    msg = ':'.join(message.split(':')[1:]).strip()
                else:
                    msg = message
                stashes.append(StashInfo(
                    index=i,
                    message=msg,
                    branch=branch,
                    datetime=datetime.now()
                ))
        except Exception:
            pass
        return stashes

    def stash_save(self, message: str = '', include_untracked: bool = False) -> bool:
        """Save changes to stash."""
        try:
            if include_untracked:
                self.repo.git.stash('save', '--include-untracked', message)
            elif message:
                self.repo.git.stash('save', message)
            else:
                self.repo.git.stash('save')
            return True
        except GitCommandError:
            return False

    def stash_pop(self, index: int = 0) -> bool:
        """Pop a stash."""
        try:
            self.repo.git.stash('pop', f'stash@{{{index}}}')
            return True
        except GitCommandError:
            return False

    def stash_apply(self, index: int = 0) -> bool:
        """Apply a stash without dropping it."""
        try:
            self.repo.git.stash('apply', f'stash@{{{index}}}')
            return True
        except GitCommandError:
            return False

    def stash_drop(self, index: int = 0) -> bool:
        """Drop a stash."""
        try:
            self.repo.git.stash('drop', f'stash@{{{index}}}')
            return True
        except GitCommandError:
            return False

    def stash_show_diff(self, index: int = 0) -> str:
        """Show diff for a stash."""
        try:
            return self.repo.git.stash('show', '-p', f'stash@{{{index}}}')
        except GitCommandError:
            return ''

    # ── Remotes ─────────────────────────────────────────────────

    def get_remotes(self) -> List[RemoteInfo]:
        """Get all remotes."""
        remotes: List[RemoteInfo] = []
        try:
            for r in self.repo.remotes:
                urls = list(r.urls)
                remotes.append(RemoteInfo(
                    name=r.name,
                    url=urls[0] if urls else '',
                    fetch_url=r.url if hasattr(r, 'url') else ''
                ))
        except Exception:
            pass
        return remotes

    def add_remote(self, name: str, url: str) -> bool:
        """Add a remote."""
        try:
            self.repo.create_remote(name, url)
            return True
        except GitCommandError:
            return False

    def remove_remote(self, name: str) -> bool:
        """Remove a remote."""
        try:
            remote = self.repo.remotes[name]
            self.repo.delete_remote(remote)
            return True
        except (GitCommandError, IndexError):
            return False

    def rename_remote(self, old_name: str, new_name: str) -> bool:
        """Rename a remote."""
        try:
            self.repo.git.remote('rename', old_name, new_name)
            return True
        except GitCommandError:
            return False

    def set_remote_url(self, name: str, url: str) -> bool:
        """Set the URL of a remote."""
        try:
            self.repo.git.remote('set-url', name, url)
            return True
        except GitCommandError:
            return False

    def fetch(self, remote: str = '', prune: bool = False) -> Tuple[bool, str]:
        """Fetch from remote."""
        try:
            kwargs = {}
            if prune:
                kwargs['prune'] = True
            if remote:
                self.repo.git.fetch(remote, **kwargs)
            else:
                self.repo.git.fetch(**kwargs)
            return True, ''
        except GitCommandError as e:
            return False, str(e)

    def pull(self, remote: str = '', branch: str = '',
             rebase: bool = False) -> Tuple[bool, str]:
        """Pull from remote."""
        try:
            args = []
            if rebase:
                args.append('--rebase')
            if remote:
                args.append(remote)
            if branch:
                args.append(branch)
            self.repo.git.pull(*args)
            return True, ''
        except GitCommandError as e:
            return False, str(e)

    def push(self, remote: str = '', branch: str = '',
             set_upstream: bool = False, force: bool = False) -> Tuple[bool, str]:
        """Push to remote."""
        try:
            args = []
            if force:
                args.append('--force')
            if set_upstream:
                args.append('--set-upstream')
            if remote:
                args.append(remote)
            if branch:
                args.append(branch)
            self.repo.git.push(*args)
            return True, ''
        except GitCommandError as e:
            return False, str(e)

    def push_tags(self, remote: str = '') -> Tuple[bool, str]:
        """Push tags to remote."""
        try:
            args = ['--tags']
            if remote:
                args.append(remote)
            self.repo.git.push(*args)
            return True, ''
        except GitCommandError as e:
            return False, str(e)

    # ── Submodules ──────────────────────────────────────────────

    def get_submodules(self) -> List[SubmoduleInfo]:
        """Get all submodules."""
        submodules: List[SubmoduleInfo] = []
        try:
            for sm in self.repo.submodules:
                submodules.append(SubmoduleInfo(
                    name=sm.name,
                    path=sm.path,
                    url=sm.url or '',
                    branch=sm.branch or '',
                    commit_sha=sm.hexsha[:7] if sm.hexsha else ''
                ))
        except Exception:
            pass
        return submodules

    def submodule_update(self, recursive: bool = False, init: bool = False) -> bool:
        """Update submodules."""
        try:
            args = ['--init'] if init else []
            if recursive:
                args.append('--recursive')
            self.repo.git.submodule('update', *args)
            return True
        except GitCommandError:
            return False

    # ── Reflog ──────────────────────────────────────────────────

    def get_reflog(self, max_count: int = 100) -> List[Dict[str, Any]]:
        """Get the reflog."""
        entries: List[Dict[str, Any]] = []
        try:
            for entry in self.repo.head.log():
                entries.append({
                    'index': entry.index,
                    'old_sha': entry.old_hexsha[:7] if entry.old_hexsha else '0000000',
                    'new_sha': entry.new_hexsha[:7] if entry.new_hexsha else '0000000',
                    'committer': str(entry.committer),
                    'message': entry.message.strip(),
                    'timestamp': entry.time[0] if entry.time else 0,
                })
        except Exception:
            pass
        return entries

    # ── Cherry-Pick ─────────────────────────────────────────────

    def cherry_pick(self, sha: str) -> Tuple[bool, str]:
        """Cherry-pick a commit."""
        try:
            self.repo.git.cherry_pick(sha)
            return True, ''
        except GitCommandError as e:
            return False, str(e)

    # ── Revert ──────────────────────────────────────────────────

    def revert_commit(self, sha: str) -> Tuple[bool, str]:
        """Revert a commit."""
        try:
            self.repo.git.revert(sha, no_edit=True)
            return True, ''
        except GitCommandError as e:
            return False, str(e)

    # ── Reset ───────────────────────────────────────────────────

    def reset(self, commit: str = 'HEAD', mode: str = '--mixed') -> bool:
        """Reset to a commit."""
        try:
            self.repo.git.reset(mode, commit)
            return True
        except GitCommandError:
            return False

    # ── Conflicts ───────────────────────────────────────────────

    def get_conflicted_files(self) -> List[ConflictFile]:
        """Get files with merge conflicts."""
        conflicts: List[ConflictFile] = []
        try:
            # Use git diff to find conflicted files
            result = subprocess.run(
                ['git', '-C', self.repo_path, 'diff', '--name-only', '--diff-filter=U'],
                capture_output=True, text=True, timeout=30
            )
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    conflicts.append(ConflictFile(path=line.strip(), status='both_modified'))
        except Exception:
            pass
        return conflicts

    def is_merging(self) -> bool:
        """Check if a merge is in progress."""
        return os.path.exists(os.path.join(self.repo_path, '.git', 'MERGE_HEAD'))

    def is_rebasing(self) -> bool:
        """Check if a rebase is in progress."""
        return os.path.exists(os.path.join(self.repo_path, '.git', 'REBASE_HEAD'))

    # ── File History & Blame ────────────────────────────────────

    def get_file_history(self, path: str, max_count: int = 50) -> List[CommitInfo]:
        """Get commit history for a specific file."""
        return self.get_commits(path=path, max_count=max_count)

    def get_blame(self, path: str) -> List[Dict[str, Any]]:
        """Get blame information for a file."""
        blame_lines: List[Dict[str, Any]] = []
        try:
            for commit, lines in self.repo.git.blame('--porcelain', path):
                for line in lines:
                    blame_lines.append({
                        'commit_sha': commit.hexsha[:7],
                        'author': commit.author.name,
                        'author_email': commit.author.email,
                        'datetime': commit.authored_datetime,
                        'line': line.strip()
                    })
        except Exception:
            pass
        return blame_lines

    # ── Patches ─────────────────────────────────────────────────

    def create_patch(self, sha1: str, sha2: str = '',
                     output_path: str = '') -> Tuple[bool, str]:
        """Create a patch file."""
        try:
            if sha2:
                patch = self.repo.git.format_patch(f'{sha1}..{sha2}', stdout=True)
            else:
                patch = self.repo.git.format_patch(f'{sha1}^..{sha1}', stdout=True)

            if output_path:
                with open(output_path, 'w') as f:
                    f.write(patch)
                return True, output_path
            return True, patch
        except GitCommandError as e:
            return False, str(e)

    def apply_patch(self, patch_path: str) -> Tuple[bool, str]:
        """Apply a patch file."""
        try:
            self.repo.git.am(patch_path)
            return True, ''
        except GitCommandError as e:
            return False, str(e)

    # ── GPG ─────────────────────────────────────────────────────

    def get_gpg_key(self) -> str:
        """Get the configured GPG signing key."""
        try:
            return self.repo.git.config('--get', 'user.signingkey')
        except GitCommandError:
            return ''

    def set_gpg_key(self, key_id: str) -> bool:
        """Set the GPG signing key."""
        try:
            self.repo.git.config('user.signingkey', key_id)
            return True
        except GitCommandError:
            return False

    # ── Config ──────────────────────────────────────────────────

    def get_config(self, key: str, global_config: bool = False) -> str:
        """Get a git config value."""
        try:
            if global_config:
                return self.repo.git.config('--global', '--get', key)
            return self.repo.git.config('--get', key)
        except GitCommandError:
            return ''

    def set_config(self, key: str, value: str, global_config: bool = False) -> bool:
        """Set a git config value."""
        try:
            if global_config:
                self.repo.git.config('--global', key, value)
            else:
                self.repo.git.config(key, value)
            return True
        except GitCommandError:
            return False

    def get_user_profiles(self) -> List[Dict[str, str]]:
        """Get git user profiles (from global config)."""
        profiles: List[Dict[str, str]] = []
        try:
            name = self.get_config('user.name', global_config=True)
            email = self.get_config('user.email', global_config=True)
            if name or email:
                profiles.append({'name': name, 'email': email, 'default': True})
        except Exception:
            pass
        return profiles

    # ── Interactive Rebase ──────────────────────────────────────

    def start_interactive_rebase(self, onto: str) -> Tuple[bool, str]:
        """Start an interactive rebase."""
        try:
            self.repo.git.rebase('-i', onto)
            return True, ''
        except GitCommandError as e:
            return False, str(e)

    def get_rebase_todo(self) -> List[Dict[str, str]]:
        """Get the current rebase todo list."""
        todo_path = os.path.join(self.repo_path, '.git', 'rebase-merge', 'git-rebase-todo')
        if not os.path.exists(todo_path):
            return []
        todos: List[Dict[str, str]] = []
        try:
            with open(todo_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split()
                        if len(parts) >= 3:
                            todos.append({
                                'command': parts[0],
                                'sha': parts[1],
                                'message': ' '.join(parts[2:])
                            })
        except Exception:
            pass
        return todos

    def write_rebase_todo(self, todos: List[Dict[str, str]]) -> bool:
        """Write the rebase todo list."""
        todo_path = os.path.join(self.repo_path, '.git', 'rebase-merge', 'git-rebase-todo')
        try:
            with open(todo_path, 'w') as f:
                for item in todos:
                    f.write(f"{item['command']} {item['sha']} {item['message']}\n")
            return True
        except Exception:
            return False

    # ── LFS ─────────────────────────────────────────────────────

    def is_lfs_enabled(self) -> bool:
        """Check if Git LFS is enabled."""
        try:
            result = subprocess.run(
                ['git', '-C', self.repo_path, 'lfs', 'env'],
                capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0
        except Exception:
            return False

    def lfs_track(self, pattern: str) -> bool:
        """Track a file pattern with Git LFS."""
        try:
            subprocess.run(
                ['git', '-C', self.repo_path, 'lfs', 'track', pattern],
                capture_output=True, timeout=30
            )
            return True
        except Exception:
            return False

    # ── Git Flow ────────────────────────────────────────────────

    def git_flow_init(self) -> bool:
        """Initialize git-flow."""
        try:
            subprocess.run(
                ['git', '-C', self.repo_path, 'flow', 'init', '-d'],
                capture_output=True, timeout=30
            )
            return True
        except Exception:
            return False

    # ── Utility ─────────────────────────────────────────────────

    def get_commit_graph(self, branch: str = '', max_count: int = 100) -> List[Dict[str, Any]]:
        """Get commit data for graph visualization."""
        nodes: List[Dict[str, Any]] = []
        try:
            kwargs: Dict[str, Any] = {
                'max_count': max_count,
                'all': True,
                'topo_order': True
            }
            if branch:
                kwargs['rev'] = branch

            for commit in self.repo.iter_commits(**kwargs):
                node = {
                    'sha': commit.hexsha[:7],
                    'full_sha': commit.hexsha,
                    'message': commit.summary,
                    'author': commit.author.name,
                    'datetime': commit.authored_datetime,
                    'parents': [p.hexsha[:7] for p in commit.parents],
                    'branches': [],
                    'tags': [],
                    'is_head': False,
                }
                # Check branches
                try:
                    for b in self.repo.branches:
                        if b.commit == commit:
                            node['branches'].append(b.name)
                except Exception:
                    pass
                # Check tags
                try:
                    for t in self.repo.tags:
                        if t.commit == commit:
                            node['tags'].append(t.name)
                except Exception:
                    pass
                # Check HEAD
                try:
                    if self.repo.head.is_valid() and commit == self.repo.head.commit:
                        node['is_head'] = True
                except Exception:
                    pass
                nodes.append(node)
        except Exception:
            pass
        return nodes

    def get_repo_statistics(self) -> Dict[str, Any]:
        """Gather repository-wide statistics including per-user breakdown.

        Returns a dict with:
          - 'total_commits', 'total_branches', 'total_tags', 'total_files'
          - 'total_added', 'total_removed', 'total_bytes'
          - 'first_commit_date', 'last_commit_date'
          - 'users': list of {name, email, commits, added, removed, files,
                              bytes, first_date, last_date}
        """
        result: Dict[str, Any] = {
            'total_commits': 0,
            'total_branches': 0,
            'total_tags': 0,
            'total_files': 0,
            'total_added': 0,
            'total_removed': 0,
            'total_bytes': 0,
            'first_commit_date': None,
            'last_commit_date': None,
            'users': [],
        }
        if not self.is_open:
            return result

        try:
            # Counts
            result['total_branches'] = len(list(self.repo.branches))
            result['total_tags'] = len(list(self.repo.tags))
            result['total_files'] = len(self.repo.git.ls_files().splitlines())

            # Per-user stats via shortlog + per-commit diffs
            users: Dict[str, Dict[str, Any]] = {}
            commits = self.get_commits(max_count=10000)
            result['total_commits'] = len(commits)

            for ci in commits:
                key = f"{ci.author_name} <{ci.author_email}>"
                if key not in users:
                    users[key] = {
                        'name': ci.author_name,
                        'email': ci.author_email,
                        'commits': 0,
                        'added': 0,
                        'removed': 0,
                        'files': 0,
                        'bytes': 0,
                        'first_date': ci.authored_datetime,
                        'last_date': ci.authored_datetime,
                    }
                u = users[key]
                u['commits'] += 1
                if ci.authored_datetime:
                    if u['first_date'] is None or ci.authored_datetime < u['first_date']:
                        u['first_date'] = ci.authored_datetime
                    if u['last_date'] is None or ci.authored_datetime > u['last_date']:
                        u['last_date'] = ci.authored_datetime

                # Per-commit diff stats
                stats = self.get_commit_stats(ci.hexsha)
                u['added'] += stats.get('total_added', 0)
                u['removed'] += stats.get('total_removed', 0)
                u['files'] += stats.get('total_files', 0)
                u['bytes'] += stats.get('total_bytes', 0)

                # Totals
                result['total_added'] += stats.get('total_added', 0)
                result['total_removed'] += stats.get('total_removed', 0)
                result['total_bytes'] += stats.get('total_bytes', 0)

                # First/last commit dates
                if ci.authored_datetime:
                    if result['first_commit_date'] is None or ci.authored_datetime < result['first_commit_date']:
                        result['first_commit_date'] = ci.authored_datetime
                    if result['last_commit_date'] is None or ci.authored_datetime > result['last_commit_date']:
                        result['last_commit_date'] = ci.authored_datetime

            result['users'] = sorted(
                users.values(),
                key=lambda u: u['commits'],
                reverse=True
            )
        except Exception:
            pass
        return result

    def get_unpushed_commits(self) -> List[CommitInfo]:
        """Get commits that haven't been pushed."""
        commits: List[CommitInfo] = []
        try:
            branch = self.current_branch
            upstream = self.repo.active_branch.tracking_branch()
            if upstream:
                for commit in self.repo.iter_commits(f'{upstream.name}..{branch}'):
                    commits.append(self._commit_to_info(commit))
        except Exception:
            pass
        return commits

    def get_unpulled_commits(self) -> List[CommitInfo]:
        """Get commits that haven't been pulled."""
        commits: List[CommitInfo] = []
        try:
            branch = self.current_branch
            upstream = self.repo.active_branch.tracking_branch()
            if upstream:
                for commit in self.repo.iter_commits(f'{branch}..{upstream.name}'):
                    commits.append(self._commit_to_info(commit))
        except Exception:
            pass
        return commits

    def compare_branches(self, branch_a: str, branch_b: str) -> Dict[str, Any]:
        """Compare two branches."""
        result: Dict[str, Any] = {
            'ahead': [],
            'behind': [],
            'common_ancestor': '',
        }
        try:
            # Commits in A not in B
            for c in self.repo.iter_commits(f'{branch_b}..{branch_a}'):
                result['ahead'].append(self._commit_to_info(c))
            # Commits in B not in A
            for c in self.repo.iter_commits(f'{branch_a}..{branch_b}'):
                result['behind'].append(self._commit_to_info(c))
            # Common ancestor
            result['common_ancestor'] = self.repo.merge_base(branch_a, branch_b)[0].hexsha[:7]
        except Exception:
            pass
        return result

    def close(self):
        """Close the repository."""
        self._repo = None
