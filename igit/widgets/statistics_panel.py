"""Repository statistics panel showing overall and per-user stats."""

from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QHeaderView, QFrame, QGridLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont

from ..core.git_operations import GitOperations


class StatisticsPanel(QWidget):
    """Panel showing repository-wide statistics and per-user breakdown."""

    refresh_requested = Signal()

    def __init__(self, git_ops: GitOperations, parent=None):
        super().__init__(parent)
        self._git = git_ops
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(8, 8, 8, 0)

        title = QLabel("📊 Statistics")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()

        self._refresh_btn = QPushButton("🔄")
        self._refresh_btn.setMaximumWidth(32)
        self._refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self._refresh_btn)

        layout.addLayout(header)

        # Overview summary card
        self._overview_frame = QFrame()
        self._overview_frame.setFrameShape(QFrame.StyledPanel)
        overview_layout = QGridLayout(self._overview_frame)
        overview_layout.setContentsMargins(12, 10, 12, 10)
        overview_layout.setHorizontalSpacing(24)
        overview_layout.setVerticalSpacing(6)

        self._overview_labels: Dict[str, QLabel] = {}
        overview_items = [
            ('commits', 'Commits'),
            ('branches', 'Branches'),
            ('tags', 'Tags'),
            ('files', 'Files'),
            ('contributors', 'Contributors'),
            ('added', 'Lines Added'),
            ('removed', 'Lines Removed'),
            ('bytes', 'Total Size'),
            ('first', 'First Commit'),
            ('last', 'Last Commit'),
        ]
        for i, (key, label) in enumerate(overview_items):
            col = i % 5
            row = i // 5
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #57606a; font-size: 11px;")
            val = QLabel("—")
            val.setStyleSheet("font-weight: bold; font-size: 14px;")
            overview_layout.addWidget(lbl, row * 2, col)
            overview_layout.addWidget(val, row * 2 + 1, col)
            self._overview_labels[key] = val

        layout.addWidget(self._overview_frame)

        # Per-user table
        users_header = QLabel("  Contributors")
        users_header.setStyleSheet("font-weight: bold; color: #57606a; padding: 4px 0;")
        layout.addWidget(users_header)

        self._users_tree = QTreeWidget()
        self._users_tree.setHeaderLabels([
            "User", "Commits", "Added", "Removed", "Files", "Size", "First Activity", "Last Activity"
        ])
        self._users_tree.setColumnWidth(0, 220)
        self._users_tree.setColumnWidth(1, 80)
        self._users_tree.setColumnWidth(2, 70)
        self._users_tree.setColumnWidth(3, 70)
        self._users_tree.setColumnWidth(4, 70)
        self._users_tree.setColumnWidth(5, 80)
        self._users_tree.setColumnWidth(6, 110)
        self._users_tree.setColumnWidth(7, 110)
        self._users_tree.header().setStretchLastSection(True)
        self._users_tree.setAlternatingRowColors(True)
        self._users_tree.setRootIsDecorated(False)
        layout.addWidget(self._users_tree)

    def refresh(self):
        """Refresh the statistics display."""
        if not self._git.is_open:
            self._clear_all()
            return

        stats = self._git.get_repo_statistics()

        # Overview values
        self._overview_labels['commits'].setText(str(stats.get('total_commits', 0)))
        self._overview_labels['branches'].setText(str(stats.get('total_branches', 0)))
        self._overview_labels['tags'].setText(str(stats.get('total_tags', 0)))
        self._overview_labels['files'].setText(str(stats.get('total_files', 0)))
        self._overview_labels['contributors'].setText(str(len(stats.get('users', []))))
        self._overview_labels['added'].setText(f"+{stats.get('total_added', 0)}")
        self._overview_labels['removed'].setText(f"-{stats.get('total_removed', 0)}")
        self._overview_labels['bytes'].setText(self._format_bytes(stats.get('total_bytes', 0)))

        first = stats.get('first_commit_date')
        last = stats.get('last_commit_date')
        self._overview_labels['first'].setText(
            first.strftime('%Y-%m-%d') if first else '—'
        )
        self._overview_labels['last'].setText(
            last.strftime('%Y-%m-%d') if last else '—'
        )

        # Per-user table
        self._users_tree.clear()
        for u in stats.get('users', []):
            item = QTreeWidgetItem()
            item.setText(0, f"{u['name']} <{u['email']}>")
            item.setText(1, str(u['commits']))
            item.setText(2, f"+{u['added']}")
            item.setText(3, f"-{u['removed']}")
            item.setText(4, str(u['files']))
            item.setText(5, self._format_bytes(u['bytes']))
            item.setText(6, u['first_date'].strftime('%Y-%m-%d') if u['first_date'] else '—')
            item.setText(7, u['last_date'].strftime('%Y-%m-%d') if u['last_date'] else '—')

            # Color added/removed
            item.setForeground(2, QBrush(QColor('#1a7f37')))
            item.setForeground(3, QBrush(QColor('#cf222e')))

            # Bold for the top contributor
            if u['commits'] == max((x['commits'] for x in stats.get('users', [])), default=0):
                for col in range(8):
                    f = item.font(col)
                    f.setBold(True)
                    item.setFont(col, f)

            self._users_tree.addTopLevelItem(item)

    def _clear_all(self):
        """Clear all statistics when no repo is open."""
        for key in self._overview_labels:
            self._overview_labels[key].setText('—')
        self._users_tree.clear()

    @staticmethod
    def _format_bytes(n: int) -> str:
        """Format a byte count into a human-readable string."""
        if n < 1024:
            return f"{n} B"
        for unit in ('KB', 'MB', 'GB'):
            n /= 1024.0
            if n < 1024:
                return f"{n:.1f} {unit}"
        return f"{n:.1f} TB"
