"""Stash management panel."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QHeaderView, QMenu, QInputDialog, QMessageBox,
    QCheckBox
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QAction

from ..core.git_operations import GitOperations


class StashPanel(QWidget):
    """Panel for managing stashes."""

    refresh_requested = Signal()
    stash_saved = Signal(str)  # message
    stash_dropped = Signal(int, str)  # index, message

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

        title = QLabel("Stashes")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()

        self._stash_btn = QPushButton("📦 Stash")
        self._stash_btn.clicked.connect(self._on_stash)
        header.addWidget(self._stash_btn)

        self._refresh_btn = QPushButton("🔄")
        self._refresh_btn.setMaximumWidth(32)
        self._refresh_btn.clicked.connect(self.refresh_requested)
        header.addWidget(self._refresh_btn)

        layout.addLayout(header)

        # Stash tree
        self._stash_tree = QTreeWidget()
        self._stash_tree.setHeaderLabels(["#", "Message", "Branch"])
        self._stash_tree.setColumnWidth(0, 40)
        self._stash_tree.setColumnWidth(1, 300)
        self._stash_tree.header().setStretchLastSection(True)
        self._stash_tree.setAlternatingRowColors(True)
        self._stash_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._stash_tree.customContextMenuRequested.connect(self._show_context_menu)
        self._stash_tree.setRootIsDecorated(False)
        layout.addWidget(self._stash_tree)

    def refresh(self):
        """Refresh the stash list."""
        self._stash_tree.clear()
        stashes = self._git.get_stashes()
        for stash in stashes:
            item = QTreeWidgetItem()
            item.setText(0, str(stash.index))
            item.setText(1, stash.message)
            item.setText(2, stash.branch)
            item.setData(0, Qt.UserRole, stash.index)
            self._stash_tree.addTopLevelItem(item)

    def _show_context_menu(self, pos):
        item = self._stash_tree.itemAt(pos)
        if not item:
            return

        index = item.data(0, Qt.UserRole)
        menu = QMenu(self)

        apply_action = menu.addAction("Apply (keep stash)")
        apply_action.triggered.connect(lambda: self._apply_stash(index))

        pop_action = menu.addAction("Pop (remove stash)")
        pop_action.triggered.connect(lambda: self._pop_stash(index))

        menu.addSeparator()

        show_action = menu.addAction("Show Diff")
        show_action.triggered.connect(lambda: self._show_stash_diff(index))

        menu.addSeparator()

        drop_action = menu.addAction("Drop")
        drop_action.triggered.connect(lambda: self._drop_stash(index))

        menu.exec(self._stash_tree.viewport().mapToGlobal(pos))

    def _on_stash(self):
        """Save a new stash."""
        message, ok = QInputDialog.getText(self, "Stash Changes", "Stash message:")
        if ok:
            if self._git.stash_save(message):
                self.stash_saved.emit(message)
                self.refresh_requested.emit()
            else:
                QMessageBox.warning(self, "Error", "Failed to stash changes")

    def _apply_stash(self, index: int):
        if self._git.stash_apply(index):
            self.refresh_requested.emit()
        else:
            QMessageBox.warning(self, "Error", "Failed to apply stash")

    def _pop_stash(self, index: int):
        if self._git.stash_pop(index):
            self.refresh_requested.emit()
        else:
            QMessageBox.warning(self, "Error", "Failed to pop stash")

    def _drop_stash(self, index: int):
        reply = QMessageBox.question(
            self, "Drop Stash", "Are you sure you want to drop this stash?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Get stash message before dropping
            message = ''
            for i in range(self._stash_tree.topLevelItemCount()):
                item = self._stash_tree.topLevelItem(i)
                if item.data(0, Qt.UserRole) == index:
                    message = item.text(1)
                    break
            if self._git.stash_drop(index):
                self.stash_dropped.emit(index, message)
                self.refresh_requested.emit()
            else:
                QMessageBox.warning(self, "Error", "Failed to drop stash")

    def _show_stash_diff(self, index: int):
        diff = self._git.stash_show_diff(index)
        from ..dialogs.diff_dialog import DiffDialog
        dialog = DiffDialog(diff, f"Stash @{{{index}}}", self)
        dialog.exec()
