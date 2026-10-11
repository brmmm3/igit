"""Working copy panel showing staged/unstaged changes."""

from typing import List, Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QSplitter, QMenu, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QBrush, QFont, QAction

from ..core.git_operations import FileStatus, GitOperations


STATUS_ICONS = {
    'M': '📝',  # Modified
    'A': '➕',  # Added
    'D': '🗑️',  # Deleted
    'R': '🔀',  # Renamed
    '?': '❓',  # Untracked
    '!!': '🚫',  # Ignored
}

STATUS_LABELS = {
    'M': 'Modified',
    'A': 'Added',
    'D': 'Deleted',
    'R': 'Renamed',
    '?': 'Untracked',
}


class WorkingCopyPanel(QWidget):
    """Panel showing working copy file status with staging/discarding."""

    file_selected = Signal(str)  # file path
    file_staged = Signal(str)
    file_unstaged = Signal(str)
    file_discarded = Signal(str)
    refresh_requested = Signal()

    def __init__(self, git_ops: GitOperations, parent=None):
        super().__init__(parent)
        self._git = git_ops
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(8, 8, 8, 0)

        title = QLabel("Working Copy")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()

        self._refresh_btn = QPushButton("🔄 Refresh")
        self._refresh_btn.clicked.connect(self.refresh_requested)
        header.addWidget(self._refresh_btn)

        layout.addLayout(header)

        # Staged section
        staged_header = QLabel("  Staged Changes")
        staged_header.setStyleSheet("font-weight: bold; color: #57606a; padding: 4px 0;")
        layout.addWidget(staged_header)

        self._staged_tree = QTreeWidget()
        self._staged_tree.setHeaderLabels(["Status", "File"])
        self._staged_tree.setColumnWidth(0, 60)
        self._staged_tree.header().setStretchLastSection(True)
        self._staged_tree.setAlternatingRowColors(True)
        self._staged_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._staged_tree.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(pos, staged=True)
        )
        self._staged_tree.itemClicked.connect(self._on_item_clicked)
        self._staged_tree.setRootIsDecorated(False)
        layout.addWidget(self._staged_tree)

        # Unstaged section
        unstaged_header = QLabel("  Unstaged Changes")
        unstaged_header.setStyleSheet("font-weight: bold; color: #57606a; padding: 4px 0;")
        layout.addWidget(unstaged_header)

        self._unstaged_tree = QTreeWidget()
        self._unstaged_tree.setHeaderLabels(["Status", "File"])
        self._unstaged_tree.setColumnWidth(0, 60)
        self._unstaged_tree.header().setStretchLastSection(True)
        self._unstaged_tree.setAlternatingRowColors(True)
        self._unstaged_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._unstaged_tree.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(pos, staged=False)
        )
        self._unstaged_tree.itemClicked.connect(self._on_item_clicked)
        self._unstaged_tree.setRootIsDecorated(False)
        layout.addWidget(self._unstaged_tree)

        # Action buttons
        actions = QHBoxLayout()
        actions.setContentsMargins(8, 4, 8, 8)

        self._stage_all_btn = QPushButton("Stage All")
        self._stage_all_btn.clicked.connect(self._on_stage_all)
        actions.addWidget(self._stage_all_btn)

        self._unstage_all_btn = QPushButton("Unstage All")
        self._unstage_all_btn.clicked.connect(self._on_unstage_all)
        actions.addWidget(self._unstage_all_btn)

        self._discard_all_btn = QPushButton("Discard All")
        self._discard_all_btn.setObjectName("dangerButton")
        self._discard_all_btn.clicked.connect(self._on_discard_all)
        actions.addWidget(self._discard_all_btn)

        actions.addStretch()
        layout.addLayout(actions)

    def refresh(self):
        """Refresh the file status display."""
        self._staged_tree.clear()
        self._unstaged_tree.clear()

        files = self._git.get_file_status()
        staged_count = 0
        unstaged_count = 0

        for fs in files:
            item = QTreeWidgetItem()
            icon = STATUS_ICONS.get(fs.status, '📄')
            label = STATUS_LABELS.get(fs.status, fs.status)
            item.setText(0, f"{icon} {label}")
            item.setText(1, fs.path)
            item.setData(0, Qt.UserRole, fs.path)
            item.setData(0, Qt.UserRole + 1, fs.status)

            # Color code
            if fs.status == 'M':
                item.setForeground(1, QColor('#9a6700'))
            elif fs.status == 'A':
                item.setForeground(1, QColor('#1a7f37'))
            elif fs.status == 'D':
                item.setForeground(1, QColor('#cf222e'))
            elif fs.status == '?':
                item.setForeground(1, QColor('#57606a'))

            if fs.staged:
                self._staged_tree.addTopLevelItem(item)
                staged_count += 1
            else:
                self._unstaged_tree.addTopLevelItem(item)
                unstaged_count += 1

        # Update headers with counts
        staged_header = self.layout().itemAt(1).widget()
        staged_header.setText(f"  Staged Changes ({staged_count})")
        unstaged_header = self.layout().itemAt(3).widget()
        unstaged_header.setText(f"  Unstaged Changes ({unstaged_count})")

    def _on_item_clicked(self, item, column):
        """Handle item click - emit file selected signal."""
        path = item.data(0, Qt.UserRole)
        if path:
            self.file_selected.emit(path)

    def _show_context_menu(self, pos, staged: bool):
        """Show context menu for a file."""
        tree = self._staged_tree if staged else self._unstaged_tree
        item = tree.itemAt(pos)
        if not item:
            return

        path = item.data(0, Qt.UserRole)
        menu = QMenu(self)

        if staged:
            unstage_action = menu.addAction("Unstage")
            unstage_action.triggered.connect(lambda: self.file_unstaged.emit(path))
        else:
            stage_action = menu.addAction("Stage")
            stage_action.triggered.connect(lambda: self.file_staged.emit(path))

            menu.addSeparator()
            discard_action = menu.addAction("Discard Changes")
            discard_action.triggered.connect(lambda: self.file_discarded.emit(path))

            menu.addSeparator()
            open_action = menu.addAction("Open File")
            open_action.triggered.connect(lambda: self._open_file(path))

        menu.exec(tree.viewport().mapToGlobal(pos))

    def _open_file(self, path: str):
        """Open file in external editor."""
        import subprocess
        import os
        full_path = os.path.join(self._git.repo_path, path)
        try:
            subprocess.Popen(['xdg-open', full_path])
        except Exception:
            pass

    def _on_stage_all(self):
        """Stage all unstaged files."""
        for i in range(self._unstaged_tree.topLevelItemCount()):
            item = self._unstaged_tree.topLevelItem(i)
            path = item.data(0, Qt.UserRole)
            if path:
                self.file_staged.emit(path)

    def _on_unstage_all(self):
        """Unstage all staged files."""
        for i in range(self._staged_tree.topLevelItemCount()):
            item = self._staged_tree.topLevelItem(i)
            path = item.data(0, Qt.UserRole)
            if path:
                self.file_unstaged.emit(path)

    def _on_discard_all(self):
        """Discard all unstaged changes."""
        for i in range(self._unstaged_tree.topLevelItemCount()):
            item = self._unstaged_tree.topLevelItem(i)
            path = item.data(0, Qt.UserRole)
            if path:
                self.file_discarded.emit(path)
