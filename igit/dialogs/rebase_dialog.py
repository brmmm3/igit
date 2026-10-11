"""Interactive rebase dialog with drag-and-drop reordering."""

from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox, QComboBox, QWidget
)
from PySide6.QtCore import Qt, Signal, Slot

from ..core.git_operations import GitOperations


class RebaseDialog(QDialog):
    """Dialog for interactive rebase with commit reordering."""

    def __init__(self, git_ops: GitOperations, parent=None):
        super().__init__(parent)
        self._git = git_ops
        self.setWindowTitle("Interactive Rebase")
        self.resize(600, 500)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            "Drag commits to reorder. Use buttons to change actions.\n"
            "pick = use commit, reword = edit message, squash = combine with previous\n"
            "edit = stop to amend, drop = remove commit"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #57606a; padding: 8px;")
        layout.addWidget(instructions)

        # Branch selection
        branch_layout = QHBoxLayout()
        branch_layout.addWidget(QLabel("Rebase onto:"))

        self._branch_combo = QComboBox()
        branches = [b.name for b in self._git.get_branches()
                    if not b.is_remote and b.name != self._git.current_branch]
        for b in branches:
            self._branch_combo.addItem(b)
        branch_layout.addWidget(self._branch_combo)
        branch_layout.addStretch()

        self._load_btn = QPushButton("Load Commits")
        self._load_btn.clicked.connect(self._load_commits)
        branch_layout.addWidget(self._load_btn)

        layout.addLayout(branch_layout)

        # Commit list
        self._commit_list = QListWidget()
        self._commit_list.setDragDropMode(QListWidget.InternalMove)
        self._commit_list.setAlternatingRowColors(True)
        layout.addWidget(self._commit_list)

        # Action buttons for selected commit
        actions = QHBoxLayout()

        self._pick_btn = QPushButton("Pick")
        self._pick_btn.clicked.connect(lambda: self._change_action('pick'))
        actions.addWidget(self._pick_btn)

        self._reword_btn = QPushButton("Reword")
        self._reword_btn.clicked.connect(lambda: self._change_action('reword'))
        actions.addWidget(self._reword_btn)

        self._squash_btn = QPushButton("Squash")
        self._squash_btn.clicked.connect(lambda: self._change_action('squash'))
        actions.addWidget(self._squash_btn)

        self._edit_btn = QPushButton("Edit")
        self._edit_btn.clicked.connect(lambda: self._change_action('edit'))
        actions.addWidget(self._edit_btn)

        self._drop_btn = QPushButton("Drop")
        self._drop_btn.setObjectName("dangerButton")
        self._drop_btn.clicked.connect(lambda: self._change_action('drop'))
        actions.addWidget(self._drop_btn)

        actions.addStretch()
        layout.addLayout(actions)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._start_btn = QPushButton("Start Rebase")
        self._start_btn.setObjectName("primaryButton")
        self._start_btn.clicked.connect(self._on_start_rebase)
        btn_layout.addWidget(self._start_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _load_commits(self):
        """Load commits that will be rebased."""
        onto = self._branch_combo.currentText()
        if not onto:
            return

        self._commit_list.clear()
        commits = self._git.get_commits(branch=self._git.current_branch, max_count=50)

        # Only show commits that are not in the target branch
        try:
            comparison = self._git.compare_branches(self._git.current_branch, onto)
            for commit in comparison['ahead']:
                item = QListWidgetItem(f"pick {commit.short_sha} {commit.summary[:60]}")
                item.setData(Qt.UserRole, commit.hexsha)
                item.setData(Qt.UserRole + 1, 'pick')
                self._commit_list.addItem(item)
        except Exception:
            # Fallback: show recent commits
            for commit in commits[:10]:
                item = QListWidgetItem(f"pick {commit.short_sha} {commit.summary[:60]}")
                item.setData(Qt.UserRole, commit.hexsha)
                item.setData(Qt.UserRole + 1, 'pick')
                self._commit_list.addItem(item)

    def _change_action(self, action: str):
        """Change the action for the selected commit."""
        item = self._commit_list.currentItem()
        if not item:
            return

        text = item.text()
        parts = text.split(' ', 1)
        if len(parts) >= 2:
            item.setText(f"{action} {parts[1]}")
            item.setData(Qt.UserRole + 1, action)

            # Color code
            colors = {
                'pick': '#1a7f37',
                'reword': '#9a6700',
                'squash': '#8250df',
                'edit': '#0550ae',
                'drop': '#cf222e',
            }
            from PySide6.QtGui import QColor
            item.setForeground(QColor(colors.get(action, '#24292e')))

    def _on_start_rebase(self):
        """Start the interactive rebase."""
        onto = self._branch_combo.currentText()
        if not onto:
            QMessageBox.warning(self, "Error", "Please select a target branch")
            return

        if self._commit_list.count() == 0:
            QMessageBox.warning(self, "Error", "No commits to rebase")
            return

        # Build todo list
        todos = []
        for i in range(self._commit_list.count()):
            item = self._commit_list.item(i)
            action = item.data(Qt.UserRole + 1) or 'pick'
            sha = item.data(Qt.UserRole)
            text = item.text()
            message = ' '.join(text.split(' ', 2)[2:]) if len(text.split(' ', 2)) > 2 else ''
            todos.append({
                'command': action,
                'sha': sha,
                'message': message
            })

        # Write todo and start rebase
        if self._git.write_rebase_todo(todos):
            success, error = self._git.rebase_branch(onto)
            if success:
                QMessageBox.information(self, "Rebase", "Rebase completed successfully!")
                self.accept()
            else:
                QMessageBox.warning(self, "Rebase Error", error)
        else:
            QMessageBox.warning(self, "Error", "Failed to write rebase todo")
