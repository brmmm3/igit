"""Commit history with a Git Extensions-style colored graph."""

from typing import Any, Dict, List

from PySide6.QtCore import (
    Qt, Signal, QSize, QMimeData, QPointF, QRectF,
)
from PySide6.QtGui import (
    QColor, QBrush, QPainter, QPen, QDrag, QPixmap, QFont, QFontMetrics,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QApplication, QStyle,
    QStyleOptionViewItem, QHeaderView,
    QTreeWidget, QTreeWidgetItem, QStyledItemDelegate,
    QPushButton, QLabel, QAbstractItemView, QMenu,
    QComboBox, QLineEdit,
)

from ..core.git_operations import GitOperations


BRANCH_COLORS = [
    QColor("#0969da"),
    QColor("#1a7f37"),
    QColor("#9a6700"),
    QColor("#8250df"),
    QColor("#cf222e"),
    QColor("#0550ae"),
    QColor("#116329"),
    QColor("#953800"),
    QColor("#622cbc"),
    QColor("#a40e26"),
    QColor("#008080"),
    QColor("#6e7681"),
]


class CommitGraphLayout:
    """Create row-local segments from pending parent lanes.

    Each active lane stores the SHA of an unvisited parent and its color.
    Lines are generated from actual ancestry, not from lane min/max rows.

    Coordinates use fractional row positions:
        0.0 = top boundary
        0.5 = commit center
        1.0 = bottom boundary
    """

    LANE_WIDTH = 20
    PADDING = 8

    def __init__(self):
        self.rows: List[Dict[str, Any]] = []
        self.lane_count = 1

    def required_width(self) -> int:
        return max(
            40,
            self.PADDING * 2 + self.lane_count * self.LANE_WIDTH,
        )

    def lane_x(self, lane: int) -> float:
        return (
            self.PADDING
            + lane * self.LANE_WIDTH
            + self.LANE_WIDTH / 2
        )

    def set_commits(self, commits: List[Dict[str, Any]]):
        # Normalize aliases when both short and full SHAs are provided.
        aliases = {}
        for commit in commits:
            sha = commit.get("full_sha") or commit["sha"]
            aliases[commit["sha"]] = sha
            aliases[sha] = sha

        def canonical(sha):
            return aliases.get(sha, sha)

        normalized = []
        for commit in commits:
            sha = canonical(commit["sha"])
            parents = list(dict.fromkeys(
                canonical(parent)
                for parent in (commit.get("parents") or [])
            ))
            normalized.append((sha, parents))

        row_of = {
            sha: row for row, (sha, _) in enumerate(normalized)
        }

        if len(row_of) != len(normalized):
            raise ValueError("Commit graph contains duplicate commits.")

        for row, (_, parents) in enumerate(normalized):
            for parent in parents:
                if parent in row_of and row_of[parent] <= row:
                    raise ValueError(
                        "Commit graph must use newest-first topological "
                        "order. Use git log --topo-order."
                    )

        rows = []
        lane_count = 1
        active = {}  # lane -> (pending SHA, color)
        next_color = 0

        def new_color():
            nonlocal next_color
            color = BRANCH_COLORS[next_color % len(BRANCH_COLORS)]
            next_color += 1
            return color

        def free_lane(preferred=None):
            if preferred is not None and preferred not in active:
                return preferred
            lane = 0
            while lane in active:
                lane += 1
            return lane

        for row_index, (sha, parents) in enumerate(normalized):
            incoming = dict(active)
            matching = [
                lane for lane, (target, _) in incoming.items()
                if target == sha
            ]

            if matching:
                node_lane = min(matching)
                node_color = incoming[node_lane][1]
            else:
                node_lane = free_lane()
                node_color = new_color()

            # Consume all lanes reaching this commit.
            for lane in matching:
                active.pop(lane, None)

            segments = []

            # Unrelated active paths pass through this row unchanged.
            for lane, (target, color) in incoming.items():
                if target != sha:
                    segments.append(
                        (lane, 0.0, lane, 1.0, color)
                    )

            # Incoming paths converge on the commit.
            for lane in matching:
                segments.append(
                    (
                        lane, 0.0,
                        node_lane, 0.5,
                        incoming[lane][1],
                    )
                )

            # First parent continues the current path if possible.
            # Other parents either join an existing path or start one.
            for parent_index, parent in enumerate(parents):
                existing_lane = next(
                    (
                        lane
                        for lane, (target, _) in active.items()
                        if target == parent
                    ),
                    None,
                )

                if existing_lane is not None:
                    parent_lane = existing_lane
                    parent_color = active[parent_lane][1]

                    # On convergence, retain the arriving path's color
                    # until it joins the existing parent lane.
                    edge_color = (
                        node_color if parent_index == 0
                        else parent_color
                    )
                else:
                    parent_lane = free_lane(
                        node_lane if parent_index == 0 else None
                    )
                    parent_color = (
                        node_color if parent_index == 0
                        else new_color()
                    )
                    active[parent_lane] = (parent, parent_color)
                    edge_color = parent_color

                segments.append(
                    (
                        node_lane, 0.5,
                        parent_lane, 1.0,
                        edge_color,
                    )
                )

            used_lanes = [node_lane]
            used_lanes.extend(incoming.keys())
            used_lanes.extend(active.keys())
            lane_count = max(lane_count, max(used_lanes) + 1)

            rows.append({
                "lane": node_lane,
                "color": node_color,
                "segments": segments,
                "is_head": bool(commits[row_index].get("is_head")),
                "is_merge": len(parents) > 1,
            })

        self.rows = rows
        self.lane_count = lane_count


class CommitGraphDelegate(QStyledItemDelegate):
    """Paint graph lanes, ref pills and the subject in column 0."""

    ROW_ROLE = Qt.ItemDataRole.UserRole + 1
    PSEUDO_ROLE = Qt.ItemDataRole.UserRole + 2
    REFS_ROLE = Qt.ItemDataRole.UserRole + 3
    NODE_RADIUS = 4.0
    ROW_HEIGHT = 22

    # kind -> (fill, border, text)
    REF_STYLES = {
        "head": (QColor("#d9381e"), QColor("#a82a15"), QColor("#ffffff")),
        "local": (QColor("#e3f5e3"), QColor("#2e9b2e"), QColor("#1b5e1b")),
        "remote": (QColor("#e6effa"), QColor("#3b78c4"), QColor("#1f4b86")),
        "tag": (QColor("#fff4cc"), QColor("#c49a1a"), QColor("#7a5c00")),
    }

    def __init__(self, graph: CommitGraphLayout, parent=None):
        super().__init__(parent)
        self._graph = graph

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(size.width(), max(size.height(), self.ROW_HEIGHT))

    def paint(self, painter, option, index):
        if index.column() == 1:
            self._paint_author(painter, option, index)
            return
        if index.column() != 0:
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        widget = option.widget
        style = widget.style() if widget else QApplication.style()
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget
        )

        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        rect = option.rect

        painter.save()
        painter.setClipRect(rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pseudo = index.data(self.PSEUDO_ROLE)
        row_index = index.data(self.ROW_ROLE)
        if pseudo:
            self._paint_pseudo_node(painter, rect, pseudo)
        elif row_index is not None:
            self._paint_graph(painter, rect, int(row_index), opt)

        x = rect.x() + self._graph.required_width()
        painter.setFont(opt.font)
        fm = QFontMetrics(opt.font)

        # Ref pills
        for label, kind in (index.data(self.REFS_ROLE) or []):
            if x > rect.right() - 20:
                break
            fill, border, fg = self.REF_STYLES.get(
                kind, self.REF_STYLES["local"]
            )
            width = fm.horizontalAdvance(label) + 10
            pill = QRectF(x, rect.y() + 2, width, rect.height() - 5)
            painter.setPen(QPen(border, 1))
            painter.setBrush(fill)
            painter.drawRoundedRect(pill, 2, 2)
            painter.setPen(fg)
            painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, label)
            x += width + 4

        # Subject text
        avail = rect.right() - x - 4
        if avail > 0 and text:
            elided = fm.elidedText(
                text, Qt.TextElideMode.ElideRight, int(avail)
            )
            if selected:
                color = opt.palette.highlightedText().color()
            else:
                brush = index.data(Qt.ItemDataRole.ForegroundRole)
                color = (
                    brush.color()
                    if isinstance(brush, QBrush)
                    else opt.palette.text().color()
                )
            painter.setPen(color)
            painter.drawText(
                QRectF(x, rect.y(), avail, rect.height()),
                int(Qt.AlignmentFlag.AlignVCenter
                    | Qt.AlignmentFlag.AlignLeft),
                elided,
            )

        painter.restore()

    def _paint_author(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget else QApplication.style()
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget
        )
        if not text:
            return

        rect = option.rect
        diameter = 14
        x = rect.x() + 4
        y = rect.center().y() - diameter / 2
        hue = sum((i + 3) * ord(char) for i, char in enumerate(text)) % 360
        circle = QRectF(x, y, diameter, diameter)
        painter.save()
        painter.setClipRect(rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor.fromHsv(hue, 125, 185))
        painter.drawEllipse(circle)
        avatar_font = QFont(option.font)
        avatar_font.setBold(True)
        if avatar_font.pointSizeF() > 0:
            avatar_font.setPointSizeF(max(6.0, avatar_font.pointSizeF() - 3))
        painter.setFont(avatar_font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, text[0].upper())

        text_x = x + diameter + 5
        text_rect = QRectF(text_x, rect.y(), rect.right() - text_x - 2,
                           rect.height())
        painter.setFont(option.font)
        color = (
            option.palette.highlightedText().color()
            if option.state & QStyle.StateFlag.State_Selected
            else option.palette.text().color()
        )
        painter.setPen(color)
        fm = QFontMetrics(option.font)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            fm.elidedText(text, Qt.TextElideMode.ElideRight,
                          int(text_rect.width())),
        )
        painter.restore()

    def _point(self, rect, lane, fraction):
        return QPointF(
            rect.x() + self._graph.lane_x(lane),
            rect.y() + fraction * rect.height(),
        )

    def _paint_graph(self, painter, rect, row_index, opt):
        if not 0 <= row_index < len(self._graph.rows):
            return
        row = self._graph.rows[row_index]

        for lane_a, y_a, lane_b, y_b, color in row["segments"]:
            pen = QPen(color, 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(
                self._point(rect, lane_a, y_a),
                self._point(rect, lane_b, y_b),
            )

        center = self._point(rect, row["lane"], 0.5)
        color = row["color"]
        radius = self.NODE_RADIUS + (1 if row["is_head"] else 0)

        painter.setPen(QPen(color.darker(140), 1.0))
        painter.setBrush(color)
        if row.get("is_merge"):
            painter.drawRect(QRectF(
                center.x() - radius, center.y() - radius,
                radius * 2, radius * 2,
            ))
        else:
            painter.drawEllipse(center, radius, radius)

        if row["is_head"]:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(opt.palette.base())
            painter.drawEllipse(
                center, self.NODE_RADIUS - 1, self.NODE_RADIUS - 1
            )

    def _paint_pseudo_node(self, painter, rect, kind):
        head = next(
            (row for row in self._graph.rows if row.get("is_head")),
            self._graph.rows[0] if self._graph.rows else None,
        )
        lane = head["lane"] if head else 0
        color = head["color"] if head else QColor("#808080")
        pen = QPen(color, 2.0)
        pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(pen)
        top = 0.5 if kind == "workdir" else 0.0
        painter.drawLine(
            self._point(rect, lane, top), self._point(rect, lane, 1.0)
        )
        center = self._point(rect, lane, 0.5)
        r = self.NODE_RADIUS
        painter.setPen(QPen(color.darker(140), 1.0))
        painter.setBrush(color)
        if kind == "index":
            painter.drawEllipse(center, r, r)
        else:
            painter.drawRect(QRectF(center.x() - r, center.y() - r,
                                    r * 2, r * 2))


class BranchGraphPanel(QWidget):
    """Panel showing commit history with colored ancestry lanes."""

    commit_selected = Signal(str)
    commit_range_selected = Signal(str, str)
    special_row_selected = Signal(str)  # "workdir" or "index"
    branch_checkout_requested = Signal(str)
    branch_merge_requested = Signal(str)
    cherry_pick_requested = Signal(str)
    revert_requested = Signal(str)
    reset_requested = Signal(str, str)
    create_tag_requested = Signal(str, str)
    create_branch_requested = Signal(str, str)

    def __init__(self, git_ops: GitOperations, parent=None):
        super().__init__(parent)
        self._git = git_ops
        self._commits: List[Dict[str, Any]] = []
        self._graph = CommitGraphLayout()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 2, 4, 2)
        toolbar.setSpacing(4)

        toolbar.addWidget(QLabel("Branches:"))
        self._branch_combo = QComboBox()
        self._branch_combo.setMinimumWidth(180)
        self._branch_combo.currentTextChanged.connect(
            self._on_branch_changed
        )
        toolbar.addWidget(self._branch_combo)

        toolbar.addWidget(QLabel("Filter:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Highlight commits...")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setMaximumWidth(260)
        self._search_edit.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_edit)

        self._refresh_btn = QPushButton("⟳")
        self._refresh_btn.setToolTip("Refresh history")
        self._refresh_btn.setMaximumWidth(28)
        self._refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self._refresh_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._commit_tree = QTreeWidget()
        self._commit_tree.setHeaderLabels([
            "Graph / Message",
            "Author",
            "Date",
            "ID",
        ])

        self._commit_tree.setUniformRowHeights(True)
        self._commit_tree.setRootIsDecorated(False)
        self._commit_tree.setIndentation(0)
        self._commit_tree.setSortingEnabled(False)
        self._commit_tree.setAlternatingRowColors(False)
        self._commit_tree.setWordWrap(False)
        self._commit_tree.setTextElideMode(Qt.TextElideMode.ElideRight)

        self._commit_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._commit_tree.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._commit_tree.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._commit_tree.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )

        self._commit_tree.setColumnWidth(1, 160)
        self._commit_tree.setColumnWidth(2, 155)
        self._commit_tree.setColumnWidth(3, 75)
        self._commit_tree.header().setStretchLastSection(False)
        self._commit_tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._commit_tree.header().setSectionsMovable(False)

        self._graph_delegate = CommitGraphDelegate(
            self._graph, self._commit_tree
        )
        self._commit_tree.setItemDelegate(self._graph_delegate)

        self._commit_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._commit_tree.customContextMenuRequested.connect(
            self._show_context_menu
        )
        self._commit_tree.itemSelectionChanged.connect(
            self._on_selection_changed
        )

        self._commit_tree.setDragEnabled(True)
        self._commit_tree.startDrag = self._start_drag

        layout.addWidget(self._commit_tree, 1)

    @staticmethod
    def _format_bytes(n: int) -> str:
        if n < 1024:
            return f"{n} B"

        value = float(n)
        for unit in ("KB", "MB", "GB"):
            value /= 1024.0
            if value < 1024:
                return f"{value:.1f} {unit}"

        return f"{value / 1024.0:.1f} TB"

    def refresh(self):
        """Load history without reordering its topological sequence."""
        current = self._branch_combo.currentText()

        self._branch_combo.blockSignals(True)
        try:
            self._branch_combo.clear()
            self._branch_combo.addItem("All Branches")

            for branch_info in self._git.get_branches():
                if not branch_info.is_remote:
                    self._branch_combo.addItem(branch_info.name)

            if current:
                index = self._branch_combo.findText(current)
                if index >= 0:
                    self._branch_combo.setCurrentIndex(index)
        finally:
            self._branch_combo.blockSignals(False)

        branch = (
            ""
            if self._branch_combo.currentIndex() == 0
            else self._branch_combo.currentText()
        )

        commits = self._git.get_commit_graph(
            branch=branch,
            max_count=200,
        )
        # Validate and build before replacing the displayed history.
        self._graph.set_commits(commits)
        self._commits = commits

        self._commit_tree.setUpdatesEnabled(False)
        self._commit_tree.blockSignals(True)

        try:
            self._commit_tree.clear()

            try:
                current_branch = self._git.current_branch
            except Exception:
                current_branch = ""

            modified = deleted = added = staged = 0
            try:
                for file_status in self._git.get_file_status():
                    if file_status.staged_status:
                        staged += 1
                    code = file_status.unstaged_status
                    if code == "D":
                        deleted += 1
                    elif code in ("A", "?"):
                        added += 1
                    elif code:
                        modified += 1
            except Exception:
                pass

            if modified or deleted or added:
                counts = []
                if modified:
                    counts.append(f"{modified} modified")
                if deleted:
                    counts.append(f"{deleted} deleted")
                if added:
                    counts.append(f"{added} added")
                item = QTreeWidgetItem()
                item.setText(0, f"Working directory ({', '.join(counts)})")
                item.setData(0, CommitGraphDelegate.PSEUDO_ROLE, "workdir")
                self._commit_tree.addTopLevelItem(item)
            if staged:
                item = QTreeWidgetItem()
                item.setText(0, f"Commit index ({staged} staged)")
                item.setData(0, CommitGraphDelegate.PSEUDO_ROLE, "index")
                self._commit_tree.addTopLevelItem(item)

            for row, commit in enumerate(self._commits):
                item = QTreeWidgetItem()
                sha = commit.get("full_sha") or commit["sha"]
                color = self._graph.rows[row]["color"]

                item.setData(0, Qt.ItemDataRole.UserRole, sha)
                item.setData(0, CommitGraphDelegate.ROW_ROLE, row)

                author = commit.get("author") or ""
                item.setText(1, author)
                item.setToolTip(1, author)

                message = commit.get("message") or ""
                subject = message.splitlines()[0] if message else ""
                item.setText(0, subject)
                item.setToolTip(0, message)

                dt = commit.get("datetime")
                if dt is not None:
                    item.setText(2, dt.strftime("%Y-%m-%d %H:%M:%S"))
                    item.setToolTip(
                        2, dt.strftime("%A, %B %d, %Y at %H:%M:%S")
                    )

                item.setText(3, commit["sha"][:7])
                item.setToolTip(3, sha)
                item.setForeground(3, QBrush(color))
                hash_font = item.font(3)
                hash_font.setFamily("monospace")
                item.setFont(3, hash_font)

                refs = []
                for name in (commit.get("branches") or []):
                    refs.append((name, "head" if name == current_branch else "local"))
                for name in (commit.get("remote_branches") or []):
                    refs.append((name, "remote"))
                for name in (commit.get("tags") or []):
                    refs.append((name, "tag"))
                if commit.get("is_head") and not refs:
                    refs.append(("HEAD", "head"))
                item.setData(0, CommitGraphDelegate.REFS_ROLE, refs)

                ref_text = [name for name, _kind in refs]
                item.setToolTip(0, message + ("\nRefs: " + ", ".join(ref_text) if ref_text else ""))

                if commit.get("is_head"):
                    for column in range(4):
                        font = item.font(column)
                        font.setBold(True)
                        item.setFont(column, font)

                self._commit_tree.addTopLevelItem(item)

            self._on_search(self._search_edit.text())
        finally:
            self._commit_tree.blockSignals(False)
            self._commit_tree.setUpdatesEnabled(True)

        self._commit_tree.viewport().update()

    def _on_branch_changed(self, branch: str):
        self.refresh()

    def _on_search(self, text: str):
        """Highlight matches without hiding ancestry rows.

        Hiding intermediate commits would break graph continuity.
        """
        query = text.strip().casefold()
        first_match = None

        for row in range(self._commit_tree.topLevelItemCount()):
            item = self._commit_tree.topLevelItem(row)
            item.setHidden(False)

            searchable = [
                item.text(column) for column in range(4)
            ]
            searchable.extend([
                str(item.data(0, Qt.ItemDataRole.UserRole) or ""),
                item.toolTip(0),
                item.toolTip(3),
            ])

            matches = bool(query) and any(
                query in value.casefold()
                for value in searchable
            )

            background = (
                QBrush(QColor(255, 210, 70, 90))
                if matches else QBrush()
            )

            for column in range(4):
                item.setBackground(column, background)

            if matches and first_match is None:
                first_match = item

        if first_match is not None:
            self._commit_tree.scrollToItem(
                first_match,
                QAbstractItemView.ScrollHint.PositionAtCenter,
            )

    def _on_selection_changed(self):
        items = self._commit_tree.selectedItems()
        if not items:
            return

        items = sorted(
            items,
            key=self._commit_tree.indexOfTopLevelItem,
        )

        specials = [
            item.data(0, CommitGraphDelegate.PSEUDO_ROLE)
            for item in items
        ]
        specials = [kind for kind in specials if kind]
        if specials:
            self.special_row_selected.emit(str(specials[0]))
            return

        shas = [
            item.data(0, Qt.ItemDataRole.UserRole)
            for item in items
        ]
        shas = [sha for sha in shas if sha]

        if len(shas) == 1:
            self.commit_selected.emit(shas[0])
        elif len(shas) > 1:
            self.commit_range_selected.emit(shas[0], shas[-1])

    def _start_drag(self, actions):
        item = self._commit_tree.currentItem()
        if item is None:
            return

        sha = item.data(0, Qt.ItemDataRole.UserRole)
        if not sha:
            return

        message = item.text(0)[:50]

        mime_data = QMimeData()
        mime_data.setText(f"commit:{sha}")
        mime_data.setData(
            "application/x-igit-commit",
            sha.encode("utf-8"),
        )

        drag = QDrag(self._commit_tree)
        drag.setMimeData(mime_data)

        pixmap = QPixmap(300, 24)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setPen(QColor("#0969da"))
        painter.drawText(4, 17, f"{sha[:7]} {message}")
        painter.end()

        drag.setPixmap(pixmap)
        drag.exec(actions)

    def _show_context_menu(self, pos):
        item = self._commit_tree.itemAt(pos)
        if item is None:
            return

        sha = item.data(0, Qt.ItemDataRole.UserRole)
        if not sha:
            return

        menu = QMenu(self)

        action = menu.addAction("Checkout")
        action.triggered.connect(
            lambda checked=False: self._git.checkout_commit(sha)
        )

        menu.addSeparator()

        action = menu.addAction("Cherry-Pick")
        action.triggered.connect(
            lambda checked=False: self.cherry_pick_requested.emit(sha)
        )

        action = menu.addAction("Revert")
        action.triggered.connect(
            lambda checked=False: self.revert_requested.emit(sha)
        )

        menu.addSeparator()

        action = menu.addAction("Create Branch Here...")
        action.triggered.connect(
            lambda checked=False:
            self.create_branch_requested.emit(sha, "")
        )

        action = menu.addAction("Create Tag Here...")
        action.triggered.connect(
            lambda checked=False:
            self.create_tag_requested.emit(sha, "")
        )

        menu.addSeparator()

        reset_menu = menu.addMenu("Reset to Here")

        action = reset_menu.addAction("Soft (keep changes staged)")
        action.triggered.connect(
            lambda checked=False:
            self.reset_requested.emit(sha, "--soft")
        )

        action = reset_menu.addAction("Mixed (keep changes unstaged)")
        action.triggered.connect(
            lambda checked=False:
            self.reset_requested.emit(sha, "--mixed")
        )

        action = reset_menu.addAction("Hard (discard all changes)")
        action.triggered.connect(
            lambda checked=False:
            self.reset_requested.emit(sha, "--hard")
        )

        menu.exec(self._commit_tree.viewport().mapToGlobal(pos))
