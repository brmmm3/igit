"""Commit message panel with author selection and commit options."""

from typing import Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton,
    QLabel, QComboBox, QCheckBox, QFrame, QLineEdit
)
from PySide6.QtCore import Qt, Signal, Slot

from ..core.git_operations import GitOperations


class CommitPanel(QWidget):
    """Panel for writing commit messages and committing."""

    commit_requested = Signal(str, str, bool, bool)  # message, author, signoff, gpg_sign

    def __init__(self, git_ops: GitOperations, parent=None):
        super().__init__(parent)
        self._git = git_ops
        self._has_staged_changes = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Title
        title = QLabel("Commit")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        # Commit message area
        self._message_edit = QPlainTextEdit()
        self._message_edit.setPlaceholderText("Commit message...")
        self._message_edit.setMinimumHeight(100)
        self._message_edit.setMaximumHeight(200)
        self._message_edit.textChanged.connect(self._update_commit_button)
        layout.addWidget(self._message_edit)

        # Description
        self._description_edit = QPlainTextEdit()
        self._description_edit.setPlaceholderText("Description (optional)...")
        self._description_edit.setMinimumHeight(60)
        self._description_edit.setMaximumHeight(120)
        layout.addWidget(self._description_edit)

        # Author selection
        author_layout = QHBoxLayout()
        author_layout.addWidget(QLabel("Author:"))

        self._author_combo = QComboBox()
        self._author_combo.setEditable(True)
        self._author_combo.setMinimumWidth(250)
        author_layout.addWidget(self._author_combo)
        author_layout.addStretch()
        layout.addLayout(author_layout)

        # Options
        options_layout = QHBoxLayout()

        self._signoff_check = QCheckBox("Sign-off")
        options_layout.addWidget(self._signoff_check)

        self._gpg_check = QCheckBox("GPG Sign")
        options_layout.addWidget(self._gpg_check)

        self._amend_check = QCheckBox("Amend")
        self._amend_check.toggled.connect(self._update_commit_button)
        options_layout.addWidget(self._amend_check)

        options_layout.addStretch()
        layout.addLayout(options_layout)

        # Commit button
        btn_layout = QHBoxLayout()

        self._commit_btn = QPushButton("Commit")
        self._commit_btn.setObjectName("primaryButton")
        self._commit_btn.clicked.connect(self._on_commit)
        self._commit_btn.setMinimumHeight(36)
        btn_layout.addWidget(self._commit_btn)

        self._status_label = QLabel("")
        self._status_label.setObjectName("statusLabel")
        btn_layout.addWidget(self._status_label)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()

    def refresh(self):
        """Refresh author list and state."""
        self._author_combo.clear()
        profiles = self._git.get_user_profiles()
        for p in profiles:
            self._author_combo.addItem(f"{p['name']} <{p['email']}>")

        # Also add current repo config
        name = self._git.get_config('user.name')
        email = self._git.get_config('user.email')
        if name and email:
            entry = f"{name} <{email}>"
            if self._author_combo.findText(entry) == -1:
                self._author_combo.insertItem(0, entry)
                self._author_combo.setCurrentIndex(0)

    def set_has_staged_changes(self, has_staged: bool):
        """Set whether there are staged changes available to commit."""
        self._has_staged_changes = has_staged
        self._update_commit_button()

    def _update_commit_button(self):
        """Enable the commit button only when there is something to commit
        and a commit message has been entered."""
        has_message = bool(self._message_edit.toPlainText().strip())
        can_commit = (self._has_staged_changes or self._amend_check.isChecked()) and has_message
        self._commit_btn.setEnabled(can_commit)

    def _on_commit(self):
        """Handle commit button click."""
        message = self._message_edit.toPlainText().strip()
        if not message:
            self._status_label.setText("⚠️ Please enter a commit message")
            return

        # Append description if provided
        description = self._description_edit.toPlainText().strip()
        if description:
            message = f"{message}\n\n{description}"

        author = self._author_combo.currentText().strip()
        signoff = self._signoff_check.isChecked()
        gpg_sign = self._gpg_check.isChecked()

        self.commit_requested.emit(message, author, signoff, gpg_sign)

    def clear(self):
        """Clear the commit form."""
        self._message_edit.clear()
        self._description_edit.clear()
        self._status_label.setText("")
        self._update_commit_button()

    def set_status(self, status: str):
        """Set the status label."""
        self._status_label.setText(status)

    def set_amend_mode(self, amend: bool):
        """Toggle amend mode."""
        self._amend_check.setChecked(amend)
        self._update_commit_button()
