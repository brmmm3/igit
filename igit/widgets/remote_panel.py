"""Remote operations panel with service integration."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QHeaderView, QMenu, QInputDialog, QMessageBox,
    QCheckBox, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, Slot, QMimeData, QPoint
from PySide6.QtGui import QAction, QDrag, QPainter, QPixmap, QDesktopServices
from PySide6.QtCore import QUrl

from ..core.git_operations import GitOperations
from ..core.remote_service import detect_service, ServiceType, ServiceClient
from ..dialogs.pr_dialog import PullRequestDialog


class RemotePanel(QWidget):
    """Panel for managing remotes and remote operations."""

    refresh_requested = Signal()
    remote_removed = Signal(str, str)  # name, url
    # Drag & drop signals
    branch_dropped_for_push = Signal(str, str)  # branch_name, remote_name
    branch_dropped_for_pull = Signal(str, str)  # branch_name, remote_name

    def __init__(self, git_ops: GitOperations, parent=None):
        super().__init__(parent)
        self._git = git_ops
        self._detected_services = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(8, 8, 8, 0)

        title = QLabel("Remotes")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()

        self._service_label = QLabel("")
        self._service_label.setStyleSheet("color: #888; font-size: 11px; padding: 0 8px;")
        header.addWidget(self._service_label)

        self._pr_btn = QPushButton("🔀 Pull Requests")
        self._pr_btn.setVisible(False)
        self._pr_btn.clicked.connect(self._on_open_prs)
        header.addWidget(self._pr_btn)

        self._fetch_btn = QPushButton("⬇️ Fetch")
        self._fetch_btn.clicked.connect(self._on_fetch)
        header.addWidget(self._fetch_btn)

        self._pull_btn = QPushButton("⬇️ Pull")
        self._pull_btn.clicked.connect(self._on_pull)
        header.addWidget(self._pull_btn)

        self._push_btn = QPushButton("⬆️ Push")
        self._push_btn.clicked.connect(self._on_push)
        header.addWidget(self._push_btn)

        layout.addLayout(header)

        # Remote tree
        self._remote_tree = QTreeWidget()
        self._remote_tree.setHeaderLabels(["Remote", "URL"])
        self._remote_tree.setColumnWidth(0, 150)
        self._remote_tree.header().setStretchLastSection(True)
        self._remote_tree.setAlternatingRowColors(True)
        self._remote_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._remote_tree.customContextMenuRequested.connect(self._show_context_menu)
        self._remote_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._remote_tree.setRootIsDecorated(False)
        self._remote_tree.setAcceptDrops(True)
        self._remote_tree.setDragDropMode(QAbstractItemView.DropOnly)
        self._remote_tree.dragEnterEvent = self._drag_enter_event
        self._remote_tree.dragMoveEvent = self._drag_move_event
        self._remote_tree.dropEvent = self._drop_event
        layout.addWidget(self._remote_tree)

        # Action buttons
        actions = QHBoxLayout()
        actions.setContentsMargins(8, 4, 8, 8)

        self._add_remote_btn = QPushButton("➕ Add Remote")
        self._add_remote_btn.clicked.connect(self._on_add_remote)
        actions.addWidget(self._add_remote_btn)

        self._refresh_btn = QPushButton("🔄")
        self._refresh_btn.setMaximumWidth(32)
        self._refresh_btn.clicked.connect(self.refresh_requested)
        actions.addWidget(self._refresh_btn)

        actions.addStretch()
        layout.addLayout(actions)

    def refresh(self):
        """Refresh the remote list and detect services."""
        self._remote_tree.clear()
        remotes = self._git.get_remotes()

        # Detect service from first remote
        self._detected_services = {}
        for remote in remotes:
            item = QTreeWidgetItem()
            item.setText(0, remote.name)
            item.setText(1, remote.url)
            item.setData(0, Qt.UserRole, remote.name)

            # Detect service
            service_info = detect_service(remote.url)
            self._detected_services[remote.name] = service_info

            # Show service icon in remote name
            service_icons = {
                ServiceType.GITHUB: '🐙',
                ServiceType.GITLAB: '🦊',
                ServiceType.BITBUCKET: '🔵',
                ServiceType.GITEA: '🔶',
                ServiceType.AZURE_DEVOPS: '🔷',
                ServiceType.SOURCEHUT: '🌱',
            }
            icon = service_icons.get(service_info.service_type, '')
            if icon:
                item.setText(0, f"{icon} {remote.name}")

            self._remote_tree.addTopLevelItem(item)

        # Show service label and PR button
        if remotes:
            service_info = self._detected_services.get(remotes[0].name)
            if service_info and service_info.service_type != ServiceType.UNKNOWN:
                self._service_label.setText(
                    f"{service_info.service_name}: {service_info.owner}/{service_info.repo}"
                )
                self._pr_btn.setVisible(True)
            else:
                self._service_label.setText("")
                self._pr_btn.setVisible(False)
        else:
            self._service_label.setText("")
            self._pr_btn.setVisible(False)

    def _show_context_menu(self, pos):
        item = self._remote_tree.itemAt(pos)
        if not item:
            return

        name = item.data(0, Qt.UserRole)
        menu = QMenu(self)

        fetch_action = menu.addAction("Fetch")
        fetch_action.triggered.connect(lambda: self._fetch(name))

        pull_action = menu.addAction("Pull")
        pull_action.triggered.connect(lambda: self._pull(name))

        push_action = menu.addAction("Push")
        push_action.triggered.connect(lambda: self._push(name))

        menu.addSeparator()

        # Service-specific actions
        service_info = self._detected_services.get(name)
        if service_info and service_info.service_type != ServiceType.UNKNOWN:
            open_browser_action = menu.addAction(f"🌐 Open on {service_info.service_name}")
            open_browser_action.triggered.connect(
                lambda: QDesktopServices.openUrl(QUrl(service_info.web_url))
            )

            open_prs_action = menu.addAction("🔀 Pull Requests")
            open_prs_action.triggered.connect(self._on_open_prs)

            menu.addSeparator()

        remove_action = menu.addAction("Remove Remote")
        remove_action.triggered.connect(lambda: self._remove_remote(name))

        menu.exec(self._remote_tree.viewport().mapToGlobal(pos))

    def _on_item_double_clicked(self, item, column):
        """Handle double-click on a remote row to edit name or URL."""
        name = item.data(0, Qt.UserRole)
        if not name:
            return

        if column == 0:
            # Edit remote name
            new_name, ok = QInputDialog.getText(
                self, "Rename Remote",
                "New remote name:",
                text=name
            )
            if ok and new_name.strip() and new_name.strip() != name:
                new_name = new_name.strip()
                if self._git.rename_remote(name, new_name):
                    self.refresh_requested.emit()
                else:
                    QMessageBox.warning(self, "Error", f"Failed to rename remote '{name}'")
        elif column == 1:
            # Edit remote URL
            current_url = item.text(1)
            new_url, ok = QInputDialog.getText(
                self, "Edit Remote URL",
                "New URL:",
                text=current_url
            )
            if ok and new_url.strip() and new_url.strip() != current_url:
                new_url = new_url.strip()
                if self._git.set_remote_url(name, new_url):
                    self.refresh_requested.emit()
                else:
                    QMessageBox.warning(self, "Error", f"Failed to update URL for remote '{name}'")

    def _on_fetch(self):
        success, error = self._git.fetch()
        if success:
            self.refresh_requested.emit()
        else:
            QMessageBox.warning(self, "Fetch Error", error)

    def _on_pull(self):
        success, error = self._git.pull()
        if success:
            self.refresh_requested.emit()
        else:
            QMessageBox.warning(self, "Pull Error", error)

    def _on_push(self):
        success, error = self._git.push()
        if success:
            self.refresh_requested.emit()
        else:
            QMessageBox.warning(self, "Push Error", error)

    def _fetch(self, remote: str):
        success, error = self._git.fetch(remote)
        if success:
            self.refresh_requested.emit()
        else:
            QMessageBox.warning(self, "Fetch Error", error)

    def _pull(self, remote: str):
        success, error = self._git.pull(remote)
        if success:
            self.refresh_requested.emit()
        else:
            QMessageBox.warning(self, "Pull Error", error)

    def _push(self, remote: str):
        success, error = self._git.push(remote)
        if success:
            self.refresh_requested.emit()
        else:
            QMessageBox.warning(self, "Push Error", error)

    def _on_add_remote(self):
        name, ok = QInputDialog.getText(self, "Add Remote", "Remote name:")
        if ok and name:
            url, ok2 = QInputDialog.getText(self, "Add Remote", "Remote URL:")
            if ok2 and url:
                if self._git.add_remote(name, url):
                    self.refresh_requested.emit()
                else:
                    QMessageBox.warning(self, "Error", f"Failed to add remote '{name}'")

    def _on_open_prs(self):
        """Open the Pull Request management dialog."""
        dialog = PullRequestDialog(self._git, self)
        dialog.exec()

    def _remove_remote(self, name: str):
        reply = QMessageBox.question(
            self, "Remove Remote",
            f"Are you sure you want to remove remote '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Get URL before removing
            url = ''
            for i in range(self._remote_tree.topLevelItemCount()):
                item = self._remote_tree.topLevelItem(i)
                if item.data(0, Qt.UserRole) == name:
                    url = item.text(1)
                    break
            if self._git.remove_remote(name):
                self.remote_removed.emit(name, url)
                self.refresh_requested.emit()
            else:
                QMessageBox.warning(self, "Error", f"Failed to remove remote '{name}'")

    # ── Drag & Drop ──────────────────────────────────────────────────────────

    def _drag_enter_event(self, event):
        """Accept drag enter for branch drops."""
        mime = event.mimeData()
        if mime.hasFormat('application/x-igit-branch'):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _drag_move_event(self, event):
        """Accept drag move for branch drops."""
        mime = event.mimeData()
        if mime.hasFormat('application/x-igit-branch'):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _drop_event(self, event):
        """Handle dropping a branch on a remote."""
        mime = event.mimeData()
        if not mime.hasFormat('application/x-igit-branch'):
            event.ignore()
            return

        branch_name = mime.data('application/x-igit-branch').data().decode('utf-8')
        pos = event.position().toPoint()
        item = self._remote_tree.itemAt(pos)

        if not item:
            event.ignore()
            return

        remote_name = item.data(0, Qt.UserRole)
        if not remote_name:
            event.ignore()
            return

        # Show context menu: Push or Pull
        from PySide6.QtWidgets import QApplication
        mods = QApplication.keyboardModifiers()

        if mods == Qt.AltModifier:
            # Alt+drag → pull
            self.branch_dropped_for_pull.emit(branch_name, remote_name)
        else:
            # Default → push
            self.branch_dropped_for_push.emit(branch_name, remote_name)

        event.acceptProposedAction()
