"""Conflict resolution wizard dialog."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QLabel, QTextEdit, QSplitter, QMessageBox, QWidget
)
from PySide6.QtCore import Qt, Signal, Slot

from ..core.git_operations import GitOperations


class ConflictDialog(QDialog):
    """Dialog for resolving merge conflicts."""

    def __init__(self, git_ops: GitOperations, parent=None):
        super().__init__(parent)
        self._git = git_ops
        self.setWindowTitle("Resolve Conflicts")
        self.resize(800, 600)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Conflicted Files - Use external merge tool or edit manually")
        header.setObjectName("sectionTitle")
        layout.addWidget(header)

        # File list
        self._file_list = QListWidget()
        self._file_list.itemClicked.connect(self._on_file_selected)
        layout.addWidget(self._file_list)

        # Conflict preview
        self._conflict_preview = QTextEdit()
        self._conflict_preview.setReadOnly(True)
        self._conflict_preview.setFont(
            self._conflict_preview.font().family()
        )
        layout.addWidget(self._conflict_preview)

        # Buttons
        btn_layout = QHBoxLayout()

        self._mark_resolved_btn = QPushButton("✅ Mark as Resolved")
        self._mark_resolved_btn.clicked.connect(self._on_mark_resolved)
        btn_layout.addWidget(self._mark_resolved_btn)

        self._open_mergetool_btn = QPushButton("🔧 Open Merge Tool")
        self._open_mergetool_btn.clicked.connect(self._on_open_mergetool)
        btn_layout.addWidget(self._open_mergetool_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        self.refresh()

    def refresh(self):
        """Refresh the conflict list."""
        self._file_list.clear()
        conflicts = self._git.get_conflicted_files()
        for cf in conflicts:
            self._file_list.addItem(cf.path)

        if not conflicts:
            self._conflict_preview.setText("No conflicts detected!")
            self._mark_resolved_btn.setEnabled(False)
            self._open_mergetool_btn.setEnabled(False)

    def _on_file_selected(self, item):
        """Show conflict markers for the selected file."""
        path = item.text()
        try:
            import os
            full_path = os.path.join(self._git.repo_path, path)
            with open(full_path) as f:
                content = f.read()

            # Extract conflict regions
            lines = content.split('\n')
            conflict_lines = []
            in_conflict = False
            for i, line in enumerate(lines):
                if line.startswith('<<<<<<<'):
                    in_conflict = True
                    conflict_lines.append(f'--- Conflict at line {i + 1} ---')
                if in_conflict:
                    conflict_lines.append(line)
                if line.startswith('>>>>>>>'):
                    in_conflict = False
                    conflict_lines.append('')

            if conflict_lines:
                self._conflict_preview.setText('\n'.join(conflict_lines))
            else:
                self._conflict_preview.setText(
                    f"File '{path}' has no conflict markers (may already be resolved)"
                )
        except Exception as e:
            self._conflict_preview.setText(f"Error reading file: {e}")

    def _on_mark_resolved(self):
        """Mark the selected file as resolved."""
        item = self._file_list.currentItem()
        if not item:
            return

        path = item.text()
        try:
            self._git.stage_file(path)
            self._file_list.takeItem(self._file_list.row(item))
            self._conflict_preview.clear()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to mark as resolved: {e}")

    def _on_open_mergetool(self):
        """Open the external merge tool."""
        item = self._file_list.currentItem()
        if not item:
            return

        path = item.text()
        try:
            import subprocess
            subprocess.run(
                ['git', '-C', self._git.repo_path, 'mergetool', path],
                cwd=self._git.repo_path
            )
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open merge tool: {e}")
