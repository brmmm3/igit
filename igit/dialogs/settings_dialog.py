"""Settings and preferences dialog."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLineEdit, QPushButton, QLabel, QFormLayout, QGroupBox,
    QCheckBox, QComboBox, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal, Slot

from ..core.git_operations import GitOperations
from ..core.remote_service import (
    ServiceType, save_token, get_token
)


class SettingsDialog(QDialog):
    """Settings dialog with tabs for various configuration."""

    settings_changed = Signal()

    def __init__(self, git_ops: GitOperations, parent=None):
        super().__init__(parent)
        self._git = git_ops
        self.setWindowTitle("Settings")
        self.resize(550, 500)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)

        # Tabs
        tabs = QTabWidget()

        # User tab
        user_tab = self._create_user_tab()
        tabs.addTab(user_tab, "User")

        # GPG tab
        gpg_tab = self._create_gpg_tab()
        tabs.addTab(gpg_tab, "GPG Signing")

        # Services tab
        services_tab = self._create_services_tab()
        tabs.addTab(services_tab, "Services")

        # Diff tab
        diff_tab = self._create_diff_tab()
        tabs.addTab(diff_tab, "Diff / Merge")

        # Appearance tab
        appearance_tab = self._create_appearance_tab()
        tabs.addTab(appearance_tab, "Appearance")

        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _create_user_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(12)

        # User name
        self._name_edit = QLineEdit()
        self._name_edit.setText(self._git.get_config('user.name'))
        layout.addRow("Name:", self._name_edit)

        # User email
        self._email_edit = QLineEdit()
        self._email_edit.setText(self._git.get_config('user.email'))
        layout.addRow("Email:", self._email_edit)

        # Scope
        self._global_check = QCheckBox("Set globally (all repositories)")
        self._global_check.setChecked(True)
        layout.addRow("", self._global_check)

        return tab

    def _create_gpg_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(12)

        self._gpg_key_edit = QLineEdit()
        self._gpg_key_edit.setText(self._git.get_gpg_key())
        self._gpg_key_edit.setPlaceholderText("GPG Key ID")
        layout.addRow("Signing Key:", self._gpg_key_edit)

        self._gpg_sign_check = QCheckBox("Sign all commits by default")
        try:
            commit_gpgsign = self._git.get_config('commit.gpgsign')
            self._gpg_sign_check.setChecked(commit_gpgsign == 'true')
        except Exception:
            pass
        layout.addRow("", self._gpg_sign_check)

        return tab

    def _create_diff_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(12)

        # External diff tool
        self._diff_tool_edit = QLineEdit()
        self._diff_tool_edit.setPlaceholderText("e.g., meld, vimdiff, beyondcompare")
        try:
            self._diff_tool_edit.setText(self._git.get_config('diff.tool'))
        except Exception:
            pass
        layout.addRow("Diff Tool:", self._diff_tool_edit)

        diff_browse = QPushButton("Browse...")
        diff_browse.clicked.connect(
            lambda: self._browse_tool(self._diff_tool_edit)
        )
        layout.addRow("", diff_browse)

        # External merge tool
        self._merge_tool_edit = QLineEdit()
        self._merge_tool_edit.setPlaceholderText("e.g., meld, kdiff3")
        try:
            self._merge_tool_edit.setText(self._git.get_config('merge.tool'))
        except Exception:
            pass
        layout.addRow("Merge Tool:", self._merge_tool_edit)

        merge_browse = QPushButton("Browse...")
        merge_browse.clicked.connect(
            lambda: self._browse_tool(self._merge_tool_edit)
        )
        layout.addRow("", merge_browse)

        return tab

    def _create_services_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        info = QLabel(
            "Configure API tokens for remote Git hosting services. "
            "Tokens are stored locally in ~/.igit/services.json.\n\n"
            "Environment variables (GITHUB_TOKEN, GITLAB_TOKEN, BITBUCKET_TOKEN) "
            "are checked first and override stored tokens."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Service token fields
        form = QFormLayout()
        form.setSpacing(10)

        self._token_fields = {}

        services = [
            ("github", "🐙 GitHub", "GitHub Personal Access Token (repo scope)"),
            ("gitlab", "🦊 GitLab", "GitLab Personal Access Token (api scope)"),
            ("bitbucket", "🔵 Bitbucket", "Bitbucket App Password (repositories + pullrequests)"),
            ("gitea", "🏡 Gitea", "Gitea Token"),
            ("azure_devops", "🔷 Azure DevOps", "Azure DevOps PAT (Code scope)"),
            ("sourcehut", "🌅 SourceHut", "SourceHut OAuth Token"),
        ]

        for key, label, placeholder in services:
            h = QHBoxLayout()
            field = QLineEdit()
            field.setPlaceholderText(placeholder)
            field.setEchoMode(QLineEdit.Password)
            # Load existing token
            existing = get_token(key)
            if existing:
                field.setText(existing)
            self._token_fields[key] = field
            h.addWidget(QLabel(f"{label}:"))
            h.addWidget(field, 1)
            form.addRow(h)

        layout.addLayout(form)
        layout.addStretch()
        return tab

    def _create_appearance_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(12)

        self._dark_mode_check = QCheckBox("Dark Mode")
        layout.addRow("Theme:", self._dark_mode_check)

        return tab

    def _browse_tool(self, edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Tool", "/usr/bin"
        )
        if path:
            edit.setText(path)

    def _on_save(self):
        # Save user settings
        global_config = self._global_check.isChecked()
        name = self._name_edit.text().strip()
        email = self._email_edit.text().strip()

        if name:
            self._git.set_config('user.name', name, global_config)
        if email:
            self._git.set_config('user.email', email, global_config)

        # Save GPG settings
        gpg_key = self._gpg_key_edit.text().strip()
        if gpg_key:
            self._git.set_gpg_key(gpg_key)
        gpgsign = 'true' if self._gpg_sign_check.isChecked() else 'false'
        self._git.set_config('commit.gpgsign', gpgsign)

        # Save diff/merge tools
        diff_tool = self._diff_tool_edit.text().strip()
        if diff_tool:
            self._git.set_config('diff.tool', diff_tool)
        merge_tool = self._merge_tool_edit.text().strip()
        if merge_tool:
            self._git.set_config('merge.tool', merge_tool)

        # Save service tokens
        for service_key, field in self._token_fields.items():
            token = field.text().strip()
            if token:
                save_token(service_key, token)

        self.settings_changed.emit()
        self.accept()
