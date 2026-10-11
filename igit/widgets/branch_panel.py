"""Branch management panel."""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QHeaderView, QMenu, QInputDialog, QMessageBox,
    QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QMimeData, QPoint
from PySide6.QtGui import QColor, QBrush, QFont, QAction, QDrag, QPainter, QPixmap

from ..core.git_operations import GitOperations, BranchInfo


class BranchPanel(QWidget):
    """Panel for managing branches."""

    branch_checkout_requested = Signal(str)
    branch_merge_requested = Signal(str)
    branch_delete_requested = Signal(str)
    refresh_requested = Signal()
    # Drag & drop signals
    branch_dropped_for_merge = Signal(str, str)  # source_branch, target_branch
    branch_dropped_for_rebase = Signal(str, str)  # source_branch, target_branch
    commit_dropped_for_branch = Signal(str, str)  # commit_sha, branch_name (empty = prompt)
    branch_dropped_for_push = Signal(str, str)  # branch_name, remote_name
    branch_dropped_for_pull = Signal(str, str)  # branch_name, remote_name

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

        title = QLabel("Branches")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()

        self._new_branch_btn = QPushButton("➕ New Branch")
        self._new_branch_btn.clicked.connect(self._on_new_branch)
        header.addWidget(self._new_branch_btn)

        self._refresh_btn = QPushButton("🔄")
        self._refresh_btn.setMaximumWidth(32)
        self._refresh_btn.clicked.connect(self.refresh_requested)
        header.addWidget(self._refresh_btn)

        layout.addLayout(header)

        # Branch tree
        self._branch_tree = QTreeWidget()
        self._branch_tree.setHeaderLabels(["Branch", "Status", "Upstream", "Ahead/Behind"])
        self._branch_tree.setColumnWidth(0, 200)
        self._branch_tree.setColumnWidth(1, 80)
        self._branch_tree.setColumnWidth(2, 200)
        self._branch_tree.header().setStretchLastSection(True)
        self._branch_tree.setAlternatingRowColors(True)
        self._branch_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._branch_tree.customContextMenuRequested.connect(self._show_context_menu)
        self._branch_tree.itemDoubleClicked.connect(self._on_double_click)
        self._branch_tree.setRootIsDecorated(False)
        self._branch_tree.setDragEnabled(True)
        self._branch_tree.setAcceptDrops(True)
        self._branch_tree.setDragDropMode(QAbstractItemView.DragDrop)
        self._branch_tree.startDrag = self._start_drag
        self._branch_tree.dragEnterEvent = self._drag_enter_event
        self._branch_tree.dragMoveEvent = self._drag_move_event
        self._branch_tree.dropEvent = self._drop_event
        layout.addWidget(self._branch_tree)

    def refresh(self):
        """Refresh the branch list."""
        self._branch_tree.clear()

        branches = self._git.get_branches()
        for branch in branches:
            item = QTreeWidgetItem()

            # Branch name
            name = branch.name
            if branch.is_remote:
                name = f"☁️ {name}"
            elif branch.is_head:
                name = f"🌿 {name} (current)"
            else:
                name = f"🌿 {name}"
            item.setText(0, name)
            item.setData(0, Qt.UserRole, branch.name)

            # Status
            if branch.is_head:
                item.setText(1, "✅ Active")
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)
            elif branch.is_remote:
                item.setText(1, "Remote")
            else:
                item.setText(1, "Local")

            # Upstream
            item.setText(2, branch.upstream)

            # Ahead/Behind
            if branch.ahead > 0 or branch.behind > 0:
                status = ""
                if branch.ahead > 0:
                    status += f"↑{branch.ahead} "
                if branch.behind > 0:
                    status += f"↓{branch.behind}"
                item.setText(3, status.strip())
                if branch.ahead > 0:
                    item.setForeground(3, QColor('#1a7f37'))
                if branch.behind > 0:
                    item.setForeground(3, QColor('#cf222e'))

            self._branch_tree.addTopLevelItem(item)

    def _on_double_click(self, item, column):
        """Checkout or rename branch on double click."""
        name = item.data(0, Qt.UserRole)
        if not name:
            return
        is_remote = item.text(0).startswith('☁️')

        if column == 0 and not is_remote:
            # Double-click on the name column renames the local branch
            new_name, ok = QInputDialog.getText(
                self, "Rename Branch", "New branch name:", text=name
            )
            if ok and new_name.strip() and new_name.strip() != name:
                new_name = new_name.strip()
                if self._git.rename_branch(name, new_name):
                    self.refresh_requested.emit()
                else:
                    QMessageBox.warning(self, "Error", f"Failed to rename branch '{name}'")
        elif not is_remote:
            self.branch_checkout_requested.emit(name)

    def _show_context_menu(self, pos):
        item = self._branch_tree.itemAt(pos)
        if not item:
            return

        name = item.data(0, Qt.UserRole)
        is_remote = item.text(0).startswith('☁️')
        is_current = item.text(0).endswith('(current)')

        menu = QMenu(self)

        if not is_current and not is_remote:
            checkout_action = menu.addAction("Checkout")
            checkout_action.triggered.connect(
                lambda: self.branch_checkout_requested.emit(name)
            )

            merge_action = menu.addAction("Merge into Current Branch")
            merge_action.triggered.connect(
                lambda: self.branch_merge_requested.emit(name)
            )

            menu.addSeparator()

            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(
                lambda: self.branch_delete_requested.emit(name)
            )

        elif is_remote:
            checkout_action = menu.addAction("Checkout as Local Branch")
            checkout_action.triggered.connect(
                lambda: self.branch_checkout_requested.emit(name)
            )

        menu.exec(self._branch_tree.viewport().mapToGlobal(pos))

    def _on_new_branch(self):
        """Create a new branch."""
        name, ok = QInputDialog.getText(self, "New Branch", "Branch name:")
        if ok and name:
            base, ok2 = QInputDialog.getText(
                self, "New Branch", "Base branch/commit (empty for current):"
            )
            if ok2:
                if self._git.create_branch(name, base):
                    self.refresh_requested.emit()
                else:
                    QMessageBox.warning(self, "Error", f"Failed to create branch '{name}'")

    # ── Drag & Drop ──────────────────────────────────────────────────────────

    def _start_drag(self, actions):
        """Start a drag operation for a branch item."""
        item = self._branch_tree.currentItem()
        if not item:
            return

        branch_name = item.data(0, Qt.UserRole)
        if not branch_name:
            return

        mime_data = QMimeData()
        mime_data.setText(f"branch:{branch_name}")
        mime_data.setData('application/x-igit-branch', branch_name.encode('utf-8'))

        drag = QDrag(self._branch_tree)
        drag.setMimeData(mime_data)

        # Create a drag pixmap
        pixmap = QPixmap(200, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QColor('#0969da'))
        painter.drawText(4, 17, f"🌿 {branch_name}")
        painter.end()
        drag.setPixmap(pixmap)

        drag.exec(Qt.MoveAction | Qt.CopyAction)

    def _drag_enter_event(self, event):
        """Accept drag enter if it carries our MIME types."""
        mime = event.mimeData()
        if mime.hasFormat('application/x-igit-branch') or mime.hasFormat('application/x-igit-commit'):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _drag_move_event(self, event):
        """Accept drag move if it carries our MIME types."""
        mime = event.mimeData()
        if mime.hasFormat('application/x-igit-branch') or mime.hasFormat('application/x-igit-commit'):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _drop_event(self, event):
        """Handle drop on the branch tree."""
        mime = event.mimeData()
        pos = event.position().toPoint()
        item = self._branch_tree.itemAt(pos)

        if mime.hasFormat('application/x-igit-branch'):
            source_branch = mime.data('application/x-igit-branch').data().decode('utf-8')
            if item:
                target_branch = item.data(0, Qt.UserRole)
                if target_branch and target_branch != source_branch:
                    # Dropped on a branch item → merge/rebase
                    from PySide6.QtCore import Qt as QtCore
                    modifiers = self._branch_tree.window().windowHandle()
                    # Check keyboard modifiers
                    from PySide6.QtWidgets import QApplication
                    mods = QApplication.keyboardModifiers()
                    if mods == Qt.AltModifier:
                        self.branch_dropped_for_rebase.emit(source_branch, target_branch)
                    else:
                        self.branch_dropped_for_merge.emit(source_branch, target_branch)
                    event.acceptProposedAction()
                    return
            else:
                # Dropped on empty area / header → create new branch from this branch
                self.commit_dropped_for_branch.emit('', source_branch)
                event.acceptProposedAction()
                return

        elif mime.hasFormat('application/x-igit-commit'):
            commit_sha = mime.data('application/x-igit-commit').data().decode('utf-8')
            if item:
                # Dropped on a branch → create new branch from commit
                self.commit_dropped_for_branch.emit(commit_sha, '')
            else:
                # Dropped on empty area → create new branch from commit
                self.commit_dropped_for_branch.emit(commit_sha, '')
            event.acceptProposedAction()
            return

        event.ignore()
