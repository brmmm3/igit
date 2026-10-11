"""Clone repository dialog."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QFileDialog, QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot
from git import RemoteProgress


class CloneProgress(RemoteProgress):
    """Progress callback for cloning."""

    def __init__(self, progress_bar: QProgressBar):
        super().__init__()
        self._progress_bar = progress_bar

    def update(self, op_code, cur_count, max_count=None, message=''):
        if max_count:
            pct = int(cur_count / max_count * 100)
            self._progress_bar.setValue(pct)
        self._progress_bar.setFormat(f"{message} ({cur_count}/{max_count})")


class CloneDialog(QDialog):
    """Dialog for cloning a repository."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clone Repository")
        self.resize(500, 200)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)

        # URL
        layout.addWidget(QLabel("Repository URL:"))
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://github.com/user/repo.git")
        layout.addWidget(self._url_edit)

        # Quick clone buttons
        quick_layout = QHBoxLayout()
        quick_layout.addWidget(QLabel("Quick clone:"))
        for provider, url in [
            ("GitHub", "https://github.com/"),
            ("GitLab", "https://gitlab.com/"),
            ("Bitbucket", "https://bitbucket.org/"),
        ]:
            btn = QPushButton(provider)
            btn.clicked.connect(lambda checked, u=url: self._url_edit.setText(u))
            quick_layout.addWidget(btn)
        quick_layout.addStretch()
        layout.addLayout(quick_layout)

        # Target path
        layout.addWidget(QLabel("Target directory:"))
        path_layout = QHBoxLayout()
        self._path_edit = QLineEdit()
        path_layout.addWidget(self._path_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        # Progress
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._clone_btn = QPushButton("Clone")
        self._clone_btn.setObjectName("primaryButton")
        self._clone_btn.clicked.connect(self._on_clone)
        btn_layout.addWidget(self._clone_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self._result_path: str = ''

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select Target Directory")
        if path:
            self._path_edit.setText(path)

    def _on_clone(self):
        url = self._url_edit.text().strip()
        path = self._path_edit.text().strip()

        if not url:
            QMessageBox.warning(self, "Error", "Please enter a repository URL")
            return
        if not path:
            QMessageBox.warning(self, "Error", "Please select a target directory")
            return

        self._clone_btn.setEnabled(False)
        self._progress_bar.setVisible(True)

        from ..core.git_operations import GitOperations
        git = GitOperations()
        progress = CloneProgress(self._progress_bar)

        # Clone in a non-blocking way
        from PySide6.QtCore import QTimer
        self._progress_bar.setFormat("Cloning...")

        def do_clone():
            success = git.clone_repo(url, path, progress)
            if success:
                self._result_path = path
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Failed to clone repository")
                self._clone_btn.setEnabled(True)
                self._progress_bar.setVisible(False)

        QTimer.singleShot(100, do_clone)

    @property
    def result_path(self) -> str:
        return self._result_path
