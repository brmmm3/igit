"""Commit history graph with branch visualization."""

from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QHeaderView, QAbstractItemView, QMenu,
    QComboBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QMimeData
from PySide6.QtGui import (
    QColor, QBrush, QFont, QPainter, QPen, QIcon, QAction, QDrag
)

from ..core.git_operations import GitOperations, CommitInfo


class CommitGraphWidget(QWidget):
    """Custom widget that draws the commit graph with branch lines."""

    NODE_RADIUS = 5
    LANE_WIDTH = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._commits: List[Dict[str, Any]] = []
        self._lanes: Dict[str, int] = {}  # sha -> lane index
        self._colors = [
            QColor('#0969da'), QColor('#1a7f37'), QColor('#9a6700'),
            QColor('#8250df'), QColor('#cf222e'), QColor('#0550ae'),
            QColor('#116329'), QColor('#953800'), QColor('#622cbc'),
            QColor('#a40e26'),
        ]
        self.setMinimumWidth(60)
        self.setMaximumWidth(120)

    def set_commits(self, commits: List[Dict[str, Any]]):
        """Set the commits and compute lane assignments."""
        self._commits = commits
        self._compute_lanes()
        self.update()

    def _compute_lanes(self):
        """Assign each commit to a lane for graph drawing."""
        self._lanes = {}
        active_lanes: Dict[int, str] = {}  # lane -> sha still active

        for i, commit in enumerate(self._commits):
            sha = commit['sha']
            parents = commit['parents']

            # Try to reuse a parent's lane
            assigned = False
            for lane, active_sha in list(active_lanes.items()):
                if active_sha in parents:
                    self._lanes[sha] = lane
                    active_lanes[lane] = sha
                    assigned = True
                    break

            if not assigned:
                # Find first free lane
                used = set(self._lanes.values())
                lane = 0
                while lane in used:
                    lane += 1
                self._lanes[sha] = lane
                active_lanes[lane] = sha

            # Clean up lanes for merged commits
            for parent in parents:
                for lane, active_sha in list(active_lanes.items()):
                    if active_sha == parent:
                        # Check if any later commit has this parent
                        still_needed = any(
                            parent in c['parents']
                            for c in self._commits[i + 1:]
                        )
                        if not still_needed:
                            del active_lanes[lane]
                        break

    def paintEvent(self, event):
        if not self._commits:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        height = self._row_height()
        padding = 10

        for i, commit in enumerate(self._commits):
            y = padding + i * height + height // 2
            sha = commit['sha']
            lane = self._lanes.get(sha, 0)
            x = padding + lane * self.LANE_WIDTH + self.LANE_WIDTH // 2

            # Draw lines to parents
            for parent in commit['parents']:
                parent_lane = self._lanes.get(parent)
                if parent_lane is not None:
                    parent_y = self._find_parent_y(parent)
                    if parent_y > y:
                        px = padding + parent_lane * self.LANE_WIDTH + self.LANE_WIDTH // 2
                        color = self._colors[(lane + parent_lane) % len(self._colors)]

                        pen = QPen(color, 2)
                        painter.setPen(pen)

                        # Draw bezier curve
                        mid_y = (y + parent_y) // 2
                        path = painter.pen()
                        painter.drawLine(x, y, x, mid_y)
                        painter.drawLine(x, mid_y, px, mid_y)
                        painter.drawLine(px, mid_y, px, parent_y)

            # Draw node
            color = self._colors[lane % len(self._colors)]
            painter.setBrush(color)
            painter.setPen(QPen(color.darker(120), 1))

            if commit['is_head']:
                # Draw head as a larger square
                painter.drawRect(x - self.NODE_RADIUS - 2, y - self.NODE_RADIUS - 2,
                                 (self.NODE_RADIUS + 2) * 2, (self.NODE_RADIUS + 2) * 2)
            else:
                painter.drawEllipse(x - self.NODE_RADIUS, y - self.NODE_RADIUS,
                                    self.NODE_RADIUS * 2, self.NODE_RADIUS * 2)

        painter.end()

    def _row_height(self):
        return 28

    def _find_parent_y(self, sha: str) -> int:
        """Find the y position of a parent commit."""
        height = self._row_height()
        padding = 10
        for i, commit in enumerate(self._commits):
            if commit['sha'] == sha:
                return padding + i * height + height // 2
        return 0

    def sizeHint(self):
        num_lanes = max(self._lanes.values()) + 1 if self._lanes else 1
        width = 20 + num_lanes * self.LANE_WIDTH
        return QSize(max(60, min(120, width)), 0)


class BranchGraphPanel(QWidget):
    """Panel showing commit history with branch graph."""

    commit_selected = Signal(str)  # commit SHA
    branch_checkout_requested = Signal(str)
    branch_merge_requested = Signal(str)
    cherry_pick_requested = Signal(str)
    revert_requested = Signal(str)
    reset_requested = Signal(str, str)  # sha, mode
    create_tag_requested = Signal(str, str)  # sha, name
    create_branch_requested = Signal(str, str)  # sha, name

    def __init__(self, git_ops: GitOperations, parent=None):
        super().__init__(parent)
        self._git = git_ops
        self._commits: List[Dict[str, Any]] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 8, 8, 0)

        title = QLabel("History")
        title.setObjectName("sectionTitle")
        toolbar.addWidget(title)

        self._branch_combo = QComboBox()
        self._branch_combo.setMinimumWidth(200)
        self._branch_combo.currentTextChanged.connect(self._on_branch_changed)
        toolbar.addWidget(self._branch_combo)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search commits...")
        self._search_edit.setMaximumWidth(200)
        self._search_edit.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_edit)

        self._refresh_btn = QPushButton("🔄")
        self._refresh_btn.setMaximumWidth(32)
        self._refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self._refresh_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Commit list with graph
        list_layout = QHBoxLayout()
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)

        self._graph_widget = CommitGraphWidget()
        list_layout.addWidget(self._graph_widget)

        self._commit_tree = QTreeWidget()
        self._commit_tree.setHeaderLabels(["SHA", "Author", "Message", "Date", "Tags/Branches"])
        self._commit_tree.setColumnWidth(0, 80)
        self._commit_tree.setColumnWidth(1, 150)
        self._commit_tree.setColumnWidth(3, 160)
        self._commit_tree.setColumnWidth(4, 150)
        self._commit_tree.header().setStretchLastSection(True)
        self._commit_tree.setAlternatingRowColors(True)
        self._commit_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._commit_tree.customContextMenuRequested.connect(self._show_context_menu)
        self._commit_tree.itemClicked.connect(self._on_item_clicked)
        self._commit_tree.setRootIsDecorated(False)
        self._commit_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self._commit_tree.setDragEnabled(True)
        self._commit_tree.startDrag = self._start_drag
        list_layout.addWidget(self._commit_tree)

        layout.addLayout(list_layout)

    def refresh(self):
        """Refresh the commit history."""
        self._commit_tree.clear()

        # Update branch combo
        current = self._branch_combo.currentText()
        self._branch_combo.blockSignals(True)
        self._branch_combo.clear()
        self._branch_combo.addItem("All Branches")
        for b in self._git.get_branches():
            if not b.is_remote:
                self._branch_combo.addItem(b.name)
        if current:
            idx = self._branch_combo.findText(current)
            if idx >= 0:
                self._branch_combo.setCurrentIndex(idx)
        self._branch_combo.blockSignals(False)

        # Get commits
        branch = '' if self._branch_combo.currentIndex() == 0 else self._branch_combo.currentText()
        self._commits = self._git.get_commit_graph(branch=branch, max_count=200)

        self._graph_widget.set_commits(self._commits)

        for commit in self._commits:
            item = QTreeWidgetItem()
            item.setText(0, commit['sha'])
            item.setText(1, commit['author'])
            item.setText(2, commit['message'][:80])
            item.setText(3, commit['datetime'].strftime('%Y-%m-%d %H:%M') if commit['datetime'] else '')
            item.setData(0, Qt.UserRole, commit['full_sha'])

            # Tags and branches
            refs = []
            if commit['is_head']:
                refs.append('HEAD')
            for b in commit['branches']:
                refs.append(f"🌿 {b}")
            for t in commit['tags']:
                refs.append(f"🏷️ {t}")
            item.setText(4, ', '.join(refs))

            # Style
            if commit['is_head']:
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)

            self._commit_tree.addTopLevelItem(item)

    def _on_branch_changed(self, branch: str):
        self.refresh()

    def _on_search(self, text: str):
        """Filter commits by search text."""
        for i in range(self._commit_tree.topLevelItemCount()):
            item = self._commit_tree.topLevelItem(i)
            match = not text or (
                text.lower() in item.text(0).lower() or
                text.lower() in item.text(1).lower() or
                text.lower() in item.text(2).lower()
            )
            item.setHidden(not match)

    def _on_item_clicked(self, item, column):
        sha = item.data(0, Qt.UserRole)
        if sha:
            self.commit_selected.emit(sha)

    def _start_drag(self, actions):
        """Start a drag operation for a commit item."""
        item = self._commit_tree.currentItem()
        if not item:
            return

        sha = item.data(0, Qt.UserRole)
        if not sha:
            return

        message = item.text(2)[:50]

        mime_data = QMimeData()
        mime_data.setText(f"commit:{sha}")
        mime_data.setData('application/x-igit-commit', sha.encode('utf-8'))

        drag = QDrag(self._commit_tree)
        drag.setMimeData(mime_data)

        # Create a simple drag pixmap
        from PySide6.QtGui import QPixmap
        pixmap = QPixmap(200, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QColor('#0969da'))
        painter.drawText(4, 17, f"📝 {sha[:7]} {message}")
        painter.end()
        drag.setPixmap(pixmap)

        drag.exec(Qt.MoveAction | Qt.CopyAction)

    def _show_context_menu(self, pos):
        item = self._commit_tree.itemAt(pos)
        if not item:
            return

        sha = item.data(0, Qt.UserRole)
        menu = QMenu(self)

        checkout_action = menu.addAction("Checkout")
        checkout_action.triggered.connect(lambda: self._git.checkout_commit(sha))

        menu.addSeparator()

        cherry_pick_action = menu.addAction("Cherry-Pick")
        cherry_pick_action.triggered.connect(lambda: self.cherry_pick_requested.emit(sha))

        revert_action = menu.addAction("Revert")
        revert_action.triggered.connect(lambda: self.revert_requested.emit(sha))

        menu.addSeparator()

        create_branch_action = menu.addAction("Create Branch Here...")
        create_branch_action.triggered.connect(
            lambda: self.create_branch_requested.emit(sha, '')
        )

        create_tag_action = menu.addAction("Create Tag Here...")
        create_tag_action.triggered.connect(
            lambda: self.create_tag_requested.emit(sha, '')
        )

        menu.addSeparator()

        reset_menu = menu.addMenu("Reset to Here")
        soft_action = reset_menu.addAction("Soft (keep changes staged)")
        soft_action.triggered.connect(lambda: self.reset_requested.emit(sha, '--soft'))
        mixed_action = reset_menu.addAction("Mixed (keep changes unstaged)")
        mixed_action.triggered.connect(lambda: self.reset_requested.emit(sha, '--mixed'))
        hard_action = reset_menu.addAction("Hard (discard all changes)")
        hard_action.triggered.connect(lambda: self.reset_requested.emit(sha, '--hard'))

        menu.exec(self._commit_tree.viewport().mapToGlobal(pos))
