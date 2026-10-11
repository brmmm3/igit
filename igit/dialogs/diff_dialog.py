"""Dialog for displaying diffs."""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt

from ..widgets.diff_viewer import DiffViewer


class DiffDialog(QDialog):
    """Dialog for displaying a diff."""

    def __init__(self, diff_text: str, title: str = "Diff", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 600)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)

        self._diff_viewer = DiffViewer(self)
        self._diff_viewer.set_diff(diff_text, title)
        layout.addWidget(self._diff_viewer)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
