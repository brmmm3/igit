"""Undo manager for tracking and reversing Git operations.

Supports undoing:
- File deletion (restore deleted file)
- Staging/unstaging a file
- Discarding a chunk or file
- The last commit (bring changes back to working copy)
"""

import os
import shutil
import tempfile
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

from .git_operations import GitOperations


class UndoActionType(Enum):
    """Types of undoable actions."""
    STAGE_FILE = auto()
    UNSTAGE_FILE = auto()
    DISCARD_FILE = auto()
    DISCARD_HUNK = auto()
    DELETE_FILE = auto()
    COMMIT = auto()
    AMEND_COMMIT = auto()
    STASH_SAVE = auto()
    STASH_DROP = auto()
    RESET_HARD = auto()
    REVERT_COMMIT = auto()
    CHERRY_PICK = auto()
    BRANCH_DELETE = auto()
    TAG_DELETE = auto()
    REMOTE_REMOVE = auto()


@dataclass
class UndoEntry:
    """An undoable action with its reversal data."""
    action_type: UndoActionType
    timestamp: datetime = field(default_factory=datetime.now)
    description: str = ''
    # Reversal data - varies by action type
    data: Dict[str, Any] = field(default_factory=dict)


class UndoManager:
    """Manages undo history for Git operations.

    Stores a stack of actions with enough context to reverse each one.
    Some reversals require file backups (e.g., discarded changes, deleted files)
    which are stored in a temporary directory.
    """

    def __init__(self, git_ops: GitOperations, max_history: int = 100):
        self._git = git_ops
        self._max_history = max_history
        self._history: List[UndoEntry] = []
        self._backup_dir = tempfile.mkdtemp(prefix='igit_undo_')

    def close(self):
        """Clean up backup directory."""
        if os.path.exists(self._backup_dir):
            shutil.rmtree(self._backup_dir, ignore_errors=True)

    @property
    def can_undo(self) -> bool:
        return len(self._history) > 0

    @property
    def undo_description(self) -> str:
        if not self._history:
            return ''
        return self._history[-1].description

    def clear(self):
        """Clear undo history."""
        self._history.clear()

    def _backup_file(self, repo_path: str, file_path: str) -> Optional[str]:
        """Backup a file's content before destructive operations."""
        full_path = os.path.join(repo_path, file_path)
        if not os.path.isfile(full_path):
            return None
        try:
            backup = os.path.join(self._backup_dir, f"{len(self._history)}_{file_path.replace('/', '_')}")
            shutil.copy2(full_path, backup)
            return backup
        except Exception:
            return None

    def _backup_file_content(self, repo_path: str, file_path: str) -> Optional[str]:
        """Backup file content, returning the backup path."""
        return self._backup_file(repo_path, file_path)

    def _get_backup_content(self, backup_path: Optional[str]) -> Optional[str]:
        """Read content from a backup file."""
        if not backup_path or not os.path.isfile(backup_path):
            return None
        try:
            with open(backup_path, 'r', errors='replace') as f:
                return f.read()
        except Exception:
            return None

    def _push(self, entry: UndoEntry):
        """Add an entry to the undo stack."""
        self._history.append(entry)
        if len(self._history) > self._max_history:
            removed = self._history.pop(0)
            # Clean up any backup files for the removed entry
            self._cleanup_entry(removed)

    def _cleanup_entry(self, entry: UndoEntry):
        """Remove backup files for an entry."""
        backup = entry.data.get('backup_path')
        if backup and os.path.isfile(backup):
            try:
                os.remove(backup)
            except Exception:
                pass

    # ── Recording actions ──────────────────────────────────────

    def record_stage(self, file_path: str):
        """Record a file staging action."""
        self._push(UndoEntry(
            action_type=UndoActionType.STAGE_FILE,
            description=f"Stage '{file_path}'",
            data={'file_path': file_path}
        ))

    def record_unstage(self, file_path: str):
        """Record a file unstaging action."""
        self._push(UndoEntry(
            action_type=UndoActionType.UNSTAGE_FILE,
            description=f"Unstage '{file_path}'",
            data={'file_path': file_path}
        ))

    def record_discard_file(self, file_path: str):
        """Record a file discard action, backing up the original content."""
        backup = None
        try:
            backup = self._backup_file_content(self._git.repo_path, file_path)
        except Exception:
            pass
        self._push(UndoEntry(
            action_type=UndoActionType.DISCARD_FILE,
            description=f"Discard changes in '{file_path}'",
            data={
                'file_path': file_path,
                'backup_path': backup,
            }
        ))

    def record_discard_hunk(self, file_path: str, start_line: int, end_line: int):
        """Record a hunk discard action, backing up the file."""
        backup = None
        try:
            backup = self._backup_file_content(self._git.repo_path, file_path)
        except Exception:
            pass
        self._push(UndoEntry(
            action_type=UndoActionType.DISCARD_HUNK,
            description=f"Discard hunk in '{file_path}' ({start_line}-{end_line})",
            data={
                'file_path': file_path,
                'start_line': start_line,
                'end_line': end_line,
                'backup_path': backup,
            }
        ))

    def record_delete_file(self, file_path: str):
        """Record a file deletion, backing up the file."""
        backup = None
        try:
            backup = self._backup_file_content(self._git.repo_path, file_path)
        except Exception:
            pass
        self._push(UndoEntry(
            action_type=UndoActionType.DELETE_FILE,
            description=f"Delete '{file_path}'",
            data={
                'file_path': file_path,
                'backup_path': backup,
            }
        ))

    def record_commit(self, commit_sha: str, message: str):
        """Record a commit action."""
        # Get the diff for this commit so we can reverse it
        diff = ''
        try:
            diff = self._git.get_diff_for_commit(commit_sha)
        except Exception:
            pass
        self._push(UndoEntry(
            action_type=UndoActionType.COMMIT,
            description=f"Commit '{message.split(chr(10))[0]}'",
            data={
                'commit_sha': commit_sha,
                'message': message,
                'diff': diff,
            }
        ))

    def record_amend_commit(self, old_sha: str, new_sha: str, message: str):
        """Record an amend commit action."""
        self._push(UndoEntry(
            action_type=UndoActionType.AMEND_COMMIT,
            description=f"Amend commit",
            data={
                'old_sha': old_sha,
                'new_sha': new_sha,
                'message': message,
            }
        ))

    def record_stash_save(self, message: str):
        """Record a stash save action."""
        self._push(UndoEntry(
            action_type=UndoActionType.STASH_SAVE,
            description=f"Stash '{message}'",
            data={'message': message}
        ))

    def record_stash_drop(self, index: int, message: str):
        """Record a stash drop action."""
        self._push(UndoEntry(
            action_type=UndoActionType.STASH_DROP,
            description=f"Drop stash @{{{index}}}",
            data={
                'index': index,
                'message': message,
            }
        ))

    def record_reset_hard(self, target_sha: str, old_head_sha: str):
        """Record a hard reset action."""
        self._push(UndoEntry(
            action_type=UndoActionType.RESET_HARD,
            description=f"Hard reset to {target_sha[:7]}",
            data={
                'target_sha': target_sha,
                'old_head_sha': old_head_sha,
            }
        ))

    def record_revert(self, reverted_sha: str, revert_sha: str):
        """Record a revert action."""
        self._push(UndoEntry(
            action_type=UndoActionType.REVERT_COMMIT,
            description=f"Revert {reverted_sha[:7]}",
            data={
                'reverted_sha': reverted_sha,
                'revert_sha': revert_sha,
            }
        ))

    def record_cherry_pick(self, cherry_sha: str, new_sha: str):
        """Record a cherry-pick action."""
        self._push(UndoEntry(
            action_type=UndoActionType.CHERRY_PICK,
            description=f"Cherry-pick {cherry_sha[:7]}",
            data={
                'cherry_sha': cherry_sha,
                'new_sha': new_sha,
            }
        ))

    def record_branch_delete(self, branch_name: str, commit_sha: str):
        """Record a branch deletion."""
        self._push(UndoEntry(
            action_type=UndoActionType.BRANCH_DELETE,
            description=f"Delete branch '{branch_name}'",
            data={
                'branch_name': branch_name,
                'commit_sha': commit_sha,
            }
        ))

    def record_tag_delete(self, tag_name: str, commit_sha: str):
        """Record a tag deletion."""
        self._push(UndoEntry(
            action_type=UndoActionType.TAG_DELETE,
            description=f"Delete tag '{tag_name}'",
            data={
                'tag_name': tag_name,
                'commit_sha': commit_sha,
            }
        ))

    def record_remote_remove(self, remote_name: str, remote_url: str):
        """Record a remote removal."""
        self._push(UndoEntry(
            action_type=UndoActionType.REMOTE_REMOVE,
            description=f"Remove remote '{remote_name}'",
            data={
                'remote_name': remote_name,
                'remote_url': remote_url,
            }
        ))

    # ── Undoing actions ────────────────────────────────────────

    def undo(self) -> Tuple[bool, str]:
        """Undo the last recorded action.

        Returns:
            Tuple of (success, description_or_error_message)
        """
        if not self._history:
            return False, "Nothing to undo"

        entry = self._history.pop()
        try:
            return self._execute_undo(entry)
        except Exception as e:
            return False, f"Undo failed: {e}"

    def _execute_undo(self, entry: UndoEntry) -> Tuple[bool, str]:
        """Execute the undo for a specific entry."""
        action_type = entry.action_type
        data = entry.data

        if action_type == UndoActionType.STAGE_FILE:
            return self._undo_stage(data)

        elif action_type == UndoActionType.UNSTAGE_FILE:
            return self._undo_unstage(data)

        elif action_type == UndoActionType.DISCARD_FILE:
            return self._undo_discard_file(data)

        elif action_type == UndoActionType.DISCARD_HUNK:
            return self._undo_discard_hunk(data)

        elif action_type == UndoActionType.DELETE_FILE:
            return self._undo_delete_file(data)

        elif action_type == UndoActionType.COMMIT:
            return self._undo_commit(data)

        elif action_type == UndoActionType.AMEND_COMMIT:
            return self._undo_amend(data)

        elif action_type == UndoActionType.STASH_SAVE:
            return self._undo_stash_save(data)

        elif action_type == UndoActionType.STASH_DROP:
            return self._undo_stash_drop(data)

        elif action_type == UndoActionType.RESET_HARD:
            return self._undo_reset_hard(data)

        elif action_type == UndoActionType.REVERT_COMMIT:
            return self._undo_revert(data)

        elif action_type == UndoActionType.CHERRY_PICK:
            return self._undo_cherry_pick(data)

        elif action_type == UndoActionType.BRANCH_DELETE:
            return self._undo_branch_delete(data)

        elif action_type == UndoActionType.TAG_DELETE:
            return self._undo_tag_delete(data)

        elif action_type == UndoActionType.REMOTE_REMOVE:
            return self._undo_remote_remove(data)

        return False, f"Unknown action type: {action_type}"

    def _undo_stage(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo staging a file → unstage it."""
        file_path = data['file_path']
        if self._git.unstage_file(file_path):
            return True, f"Undid stage of '{file_path}'"
        return False, f"Failed to unstage '{file_path}'"

    def _undo_unstage(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo unstaging a file → stage it again."""
        file_path = data['file_path']
        if self._git.stage_file(file_path):
            return True, f"Undid unstage of '{file_path}'"
        return False, f"Failed to stage '{file_path}'"

    def _undo_discard_file(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo discarding a file → restore from backup."""
        file_path = data['file_path']
        backup_path = data.get('backup_path')
        content = self._get_backup_content(backup_path)
        if content is None:
            return False, f"Cannot restore '{file_path}': no backup available"

        full_path = os.path.join(self._git.repo_path, file_path)
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(content)
            return True, f"Restored changes in '{file_path}'"
        except Exception as e:
            return False, f"Failed to restore '{file_path}': {e}"

    def _undo_discard_hunk(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo discarding a hunk → restore the whole file from backup."""
        # Since we can't easily reconstruct a single hunk, restore the full file
        return self._undo_discard_file(data)

    def _undo_delete_file(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo deleting a file → restore from backup."""
        file_path = data['file_path']
        backup_path = data.get('backup_path')
        content = self._get_backup_content(backup_path)
        if content is None:
            return False, f"Cannot restore '{file_path}': no backup available"

        full_path = os.path.join(self._git.repo_path, file_path)
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(content)
            # Stage the restored file
            self._git.stage_file(file_path)
            return True, f"Restored deleted file '{file_path}'"
        except Exception as e:
            return False, f"Failed to restore '{file_path}': {e}"

    def _undo_commit(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo the last commit → reset to parent, keeping changes in working copy.

        This is equivalent to: git reset --soft HEAD~1
        """
        commit_sha = data.get('commit_sha', '')
        try:
            # Use git reset --soft HEAD~1 to undo the commit but keep changes staged
            import subprocess
            proc = subprocess.run(
                ['git', '-C', self._git.repo_path, 'reset', '--soft', 'HEAD~1'],
                capture_output=True, text=True, timeout=30
            )
            if proc.returncode == 0:
                return True, f"Undid commit (changes are now staged)"
            else:
                return False, f"Failed to undo commit: {proc.stderr.strip()}"
        except Exception as e:
            return False, f"Failed to undo commit: {e}"

    def _undo_amend(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo an amend → restore the original commit via reflog."""
        old_sha = data.get('old_sha', '')
        try:
            # Use reflog to find the old commit and reset to it
            import subprocess
            proc = subprocess.run(
                ['git', '-C', self._git.repo_path, 'reset', '--soft', old_sha],
                capture_output=True, text=True, timeout=30
            )
            if proc.returncode == 0:
                return True, f"Undid amend (restored original commit)"
            else:
                return False, f"Failed to undo amend: {proc.stderr.strip()}"
        except Exception as e:
            return False, f"Failed to undo amend: {e}"

    def _undo_stash_save(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo a stash save → drop the most recent stash."""
        try:
            import subprocess
            proc = subprocess.run(
                ['git', '-C', self._git.repo_path, 'stash', 'drop'],
                capture_output=True, text=True, timeout=30
            )
            if proc.returncode == 0:
                return True, "Undid stash save (dropped stash)"
            return False, f"Failed to drop stash: {proc.stderr.strip()}"
        except Exception as e:
            return False, f"Failed to undo stash: {e}"

    def _undo_stash_drop(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo a stash drop → can't easily restore without stash reflog."""
        return False, "Cannot undo stash drop (stash reflog not available)"

    def _undo_reset_hard(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo a hard reset → reset back to the old HEAD."""
        old_head = data.get('old_head_sha', '')
        if not old_head:
            return False, "Cannot undo reset: no previous HEAD recorded"
        try:
            import subprocess
            proc = subprocess.run(
                ['git', '-C', self._git.repo_path, 'reset', '--hard', old_head],
                capture_output=True, text=True, timeout=30
            )
            if proc.returncode == 0:
                return True, f"Undid reset (restored to {old_head[:7]})"
            return False, f"Failed to undo reset: {proc.stderr.strip()}"
        except Exception as e:
            return False, f"Failed to undo reset: {e}"

    def _undo_revert(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo a revert → revert the revert commit."""
        revert_sha = data.get('revert_sha', '')
        if not revert_sha:
            return False, "Cannot undo revert: no revert commit SHA"
        try:
            import subprocess
            proc = subprocess.run(
                ['git', '-C', self._git.repo_path, 'revert', '--no-edit', revert_sha],
                capture_output=True, text=True, timeout=30
            )
            if proc.returncode == 0:
                return True, f"Undid revert of {data.get('reverted_sha', '')[:7]}"
            return False, f"Failed to undo revert: {proc.stderr.strip()}"
        except Exception as e:
            return False, f"Failed to undo revert: {e}"

    def _undo_cherry_pick(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo a cherry-pick → revert the new commit."""
        new_sha = data.get('new_sha', '')
        if not new_sha:
            return False, "Cannot undo cherry-pick: no new commit SHA"
        try:
            import subprocess
            proc = subprocess.run(
                ['git', '-C', self._git.repo_path, 'revert', '--no-edit', new_sha],
                capture_output=True, text=True, timeout=30
            )
            if proc.returncode == 0:
                return True, f"Undid cherry-pick of {data.get('cherry_sha', '')[:7]}"
            return False, f"Failed to undo cherry-pick: {proc.stderr.strip()}"
        except Exception as e:
            return False, f"Failed to undo cherry-pick: {e}"

    def _undo_branch_delete(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo a branch deletion → recreate the branch at the old commit."""
        branch_name = data.get('branch_name', '')
        commit_sha = data.get('commit_sha', '')
        if not branch_name or not commit_sha:
            return False, "Cannot restore branch: missing data"
        try:
            self._git.create_branch(branch_name, commit_sha)
            return True, f"Restored branch '{branch_name}'"
        except Exception as e:
            return False, f"Failed to restore branch: {e}"

    def _undo_tag_delete(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo a tag deletion → recreate the tag at the old commit."""
        tag_name = data.get('tag_name', '')
        commit_sha = data.get('commit_sha', '')
        if not tag_name or not commit_sha:
            return False, "Cannot restore tag: missing data"
        try:
            self._git.create_tag(tag_name, ref=commit_sha)
            return True, f"Restored tag '{tag_name}'"
        except Exception as e:
            return False, f"Failed to restore tag: {e}"

    def _undo_remote_remove(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Undo a remote removal → re-add the remote."""
        remote_name = data.get('remote_name', '')
        remote_url = data.get('remote_url', '')
        if not remote_name or not remote_url:
            return False, "Cannot restore remote: missing data"
        try:
            self._git.add_remote(remote_name, remote_url)
            return True, f"Restored remote '{remote_name}'"
        except Exception as e:
            return False, f"Failed to restore remote: {e}"
