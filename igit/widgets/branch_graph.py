"""Commit history graph with colored branch visualization."""

from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QHeaderView, QAbstractItemView, QMenu,
    QComboBox, QLineEdit, QStyleFactory
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QMimeData
from PySide6.QtGui import (
    QColor, QBrush, QFont, QPainter, QPen, QIcon, QAction, QDrag,
    QPixmap, QFontMetrics
)

from ..core.git_operations import GitOperations, CommitInfo


# ── Color palette for branch lanes ─────────────────────────────
BRANCH_COLORS = [
    QColor('#0969da'),  # blue
    QColor('#1a7f37'),  # green
    QColor('#9a6700'),  # yellow
    QColor('#8250df'),  # purple
    QColor('#cf222e'),  # red
    QColor('#0550ae'),  # dark blue
    QColor('#116329'),  # dark green
    QColor('#953800'),  # orange
    QColor('#622cbc'),  # dark purple
    QColor('#a40e26'),  # dark red
    QColor('#008080'),  # teal
    QColor('#6e7681'),  # gray
]

# Lighter versions for backgrounds
BRANCH_BG_COLORS = [
    QColor('#ddf4ff'),  # blue bg
    QColor('#dafbe1'),  # green bg
    QColor('#fff8c5'),  # yellow bg
    QColor('#fbefff'),  # purple bg
    QColor('#ffebe9'),  # red bg
    QColor('#ddf4ff'),  # dark blue bg
    QColor('#dafbe1'),  # dark green bg
    QColor('#fff1e5'),  # orange bg
    QColor('#fbefff'),  # dark purple bg
    QColor('#ffebe9'),  # dark red bg
    QColor('#e6f8f8'),  # teal bg
    QColor('#f0f6fc'),  # gray bg
]


class CommitGraphWidget(QWidget):
    """Custom widget that draws the commit graph with colored branch lines."""

    NODE_RADIUS = 6
    LANE_WIDTH = 22

    def __init__(self, parent=None):
        super().__init__(parent)
        self._commits: List[Dict[str, Any]] = []
        self._lanes: Dict[str, int] = {}  # sha -> lane index
        self._lane_colors: Dict[int, QColor] = {}  # lane -> color
        self.setMinimumWidth(60)
        self.setMaximumWidth(140)

    def set_commits(self, commits: List[Dict[str, Any]]):
        """Set the commits and compute lane assignments."""
        self._commits = commits
        self._compute_lanes()
        self.update()

    def _compute_lanes(self):
        """Assign each commit to a lane and pick colors."""
        self._lanes = {}
        self._lane_colors = {}
        active_lanes: Dict[int, str] = {}  # lane -> sha still active
        next_color = 0

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
                self._lane_colors[lane] = BRANCH_COLORS[next_color % len(BRANCH_COLORS)]
                next_color += 1
                active_lanes[lane] = sha

            # Clean up lanes for merged commits
            for parent in parents:
                for lane, active_sha in list(active_lanes.items()):
                    if active_sha == parent:
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
                        color = self._lane_colors.get(lane, BRANCH_COLORS[0])

                        pen = QPen(color, 2.5)
                        painter.setPen(pen)

                        # Draw connecting lines
                        mid_y = (y + parent_y) // 2
                        painter.drawLine(x, y, x, mid_y)
                        painter.drawLine(x, mid_y, px, mid_y)
                        painter.drawLine(px, mid_y, px, parent_y)

            # Draw node
            color = self._lane_colors.get(lane, BRANCH_COLORS[0])
            painter.setBrush(color)
            painter.setPen(QPen(color.darker(130), 1.5))

            if commit['is_head']:
                # HEAD commit: larger rounded rect
                r = self.NODE_RADIUS + 2
                painter.drawRoundedRect(x - r, y - r, r * 2, r * 2, 3, 3)
                # Glow effect
                painter.setBrush(Qt.NoBrush)
                glow_pen = QPen(QColor(color.red(), color.green(), color.blue(), 80), 4)
                painter.setPen(glow_pen)
                painter.drawRoundedRect(x - r - 2, y - r - 2, r * 2 + 4, r * 2 + 4, 4, 4)
            else:
                painter.drawEllipse(x - self.NODE_RADIUS, y - self.NODE_RADIUS,
                                    self.NODE_RADIUS * 2, self.NODE_RADIUS * 2)

        painter.end()

    def _row_height(self):
        return 30

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
        return QSize(max(60, min(140, width)), 0)


class BranchGraphPanel(QWidget):
    """Panel showing colored commit history with branch graph."""

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
        self._commit_tree.setHeaderLabels(["Graph", "Hash", "Author", "Message", "Date", "Branches / Tags"])
        self._commit_tree.setColumnWidth(0, 40)
        self._commit_tree.setColumnWidth(1, 100)
        self._commit_tree.setColumnWidth(2, 140)
        self._commit_tree.setColumnWidth(4, 170)
        self._commit_tree.setColumnWidth(5, 180)
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

    def _lane_color(self, sha: str) -> Optional[QColor]:
        """Get the lane color for a commit SHA."""
        lane = self._graph_widget._lanes.get(sha)
        if lane is not None:
            return self._graph_widget._lane_colors.get(lane)
        return None

    def refresh(self):
        """Refresh the commit history with colored graph."""
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
            lane_color = self._lane_color(commit['sha'])

            # Column 0: Graph indicator (colored dot)
            if lane_color:
                pix = QPixmap(16, 16)
                pix.fill(Qt.transparent)
                p = QPainter(pix)
                p.setRenderHint(QPainter.Antialiasing)
                p.setBrush(lane_color)
                p.setPen(QPen(lane_color.darker(130), 1))
                p.drawEllipse(2, 2, 12, 12)
                p.end()
                item.setIcon(0, QIcon(pix))

            # Column 1: Short hash (colored)
            item.setText(1, commit['sha'][:7])
            if lane_color:
                item.setForeground(1, QBrush(lane_color))
            font = item.font(1)
            font.setFamily("monospace")
            item.setFont(1, font)

            # Column 2: Author
            item.setText(2, commit['author'])

            # Column 3: Message
            item.setText(3, commit['message'][:80])

            # Column 4: Date/time
            if commit['datetime']:
                dt = commit['datetime']
                # Relative time for recent commits
                now = dt.now() if hasattr(dt, 'now') else None
                item.setText(4, dt.strftime('%Y-%m-%d %H:%M:%S'))
                item.setToolTip(4, dt.strftime('%A, %B %d, %Y at %H:%M:%S'))
            else:
                item.setText(4, '')

            # Column 5: Branches and tags with colored labels
            refs = []
            if commit['is_head']:
                refs.append('HEAD')
            for b in commit['branches']:
                refs.append(f"🌿 {b}")
            for t in commit['tags']:
                refs.append(f"🏷️ {t}")
            item.setText(5, '  '.join(refs))

            # Store full SHA
            item.setData(0, Qt.UserRole, commit['full_sha'])

            # Style: bold for HEAD commit
            if commit['is_head']:
                for col in range(6):
                    f = item.font(col)
                    f.setBold(True)
                    item.setFont(col, f)

            # Background tint for the commit's lane
            if lane_color:
                bg = QColor(lane_color.red(), lane_color.green(), lane_color.blue(), 25)
                for col in range(6):
                    item.setBackground(col, QBrush(bg))

            self._commit_tree.addTopLevelItem(item)

    def _on_branch_changed(self, branch: str):
        self.refresh()

    def _on_search(self, text: str):
        """Filter commits by search text."""
        for i in range(self._commit_tree.topLevelItemCount()):
            item = self._commit_tree.topLevelItem(i)
            match = not text or (
                text.lower() in item.text(1).lower() or
                text.lower() in item.text(2).lower() or
                text.lower() in item.text(3).lower() or
                text.lower() in item.text(4).lower()
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

        message = item.text(3)[:50]

        mime_data = QMimeData()
        mime_data.setText(f"commit:{sha}")
        mime_data.setData('application/x-igit-commit', sha.encode('utf-8'))

        drag = QDrag(self._commit_tree)
        drag.setMimeData(mime_data)

        # Create a simple drag pixmap
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
