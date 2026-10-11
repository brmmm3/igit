"""Pull Request management dialog.

Provides a UI for viewing, creating, and managing pull requests
across GitHub, GitLab, and Bitbucket.
"""

from typing import Optional, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLineEdit, QPushButton, QLabel, QFormLayout, QGroupBox,
    QCheckBox, QComboBox, QMessageBox, QTextEdit, QListWidget,
    QListWidgetItem, QSplitter, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QAbstractItemView, QMenu, QProgressDialog,
    QApplication
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer
from PySide6.QtGui import QAction, QFont, QDesktopServices, QPixmap
from PySide6.QtCore import QUrl

from ..core.remote_service import (
    ServiceClient, ServiceInfo, PullRequest, ServiceType,
    detect_service, save_token, get_token
)
from ..core.git_operations import GitOperations


class PullRequestDialog(QDialog):
    """Dialog for managing pull requests across remote services."""

    def __init__(self, git_ops: GitOperations, parent=None):
        super().__init__(parent)
        self._git = git_ops
        self._service_client: Optional[ServiceClient] = None
        self._service_info: Optional[ServiceInfo] = None
        self._current_prs: List[PullRequest] = []
        self.setWindowTitle("Pull Requests")
        self.resize(800, 600)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._setup_ui()
        self._detect_service()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Service info header
        self._service_header = QLabel("No remote service detected")
        self._service_header.setObjectName("sectionTitle")
        layout.addWidget(self._service_header)

        # Token status
        token_layout = QHBoxLayout()
        self._token_status = QLabel("")
        self._token_status.setStyleSheet("color: #888;")
        token_layout.addWidget(self._token_status)
        token_layout.addStretch()
        self._configure_token_btn = QPushButton("Configure Token...")
        self._configure_token_btn.clicked.connect(self._on_configure_token)
        self._configure_token_btn.setVisible(False)
        token_layout.addWidget(self._configure_token_btn)
        layout.addLayout(token_layout)

        # Tabs
        tabs = QTabWidget()

        # Browse PRs tab
        browse_tab = self._create_browse_tab()
        tabs.addTab(browse_tab, "Browse")

        # Create PR tab
        create_tab = self._create_create_tab()
        tabs.addTab(create_tab, "Create")

        # Search tab
        search_tab = self._create_search_tab()
        tabs.addTab(search_tab, "Search")

        layout.addWidget(tabs)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _create_browse_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("State:"))

        self._state_combo = QComboBox()
        self._state_combo.addItems(["Open", "Closed", "All"])
        self._state_combo.currentTextChanged.connect(self._on_refresh_prs)
        filter_layout.addWidget(self._state_combo)

        filter_layout.addStretch()

        self._refresh_btn = QPushButton("🔄 Refresh")
        self._refresh_btn.clicked.connect(self._on_refresh_prs)
        filter_layout.addWidget(self._refresh_btn)

        layout.addLayout(filter_layout)

        # PR list
        self._pr_tree = QTreeWidget()
        self._pr_tree.setHeaderLabels(["#", "Title", "Author", "Source → Target", "Status", "Updated"])
        self._pr_tree.setColumnWidth(0, 60)
        self._pr_tree.setColumnWidth(1, 300)
        self._pr_tree.setColumnWidth(2, 120)
        self._pr_tree.setColumnWidth(3, 200)
        self._pr_tree.setColumnWidth(4, 80)
        self._pr_tree.header().setStretchLastSection(True)
        self._pr_tree.setAlternatingRowColors(True)
        self._pr_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._pr_tree.customContextMenuRequested.connect(self._show_pr_context_menu)
        self._pr_tree.itemDoubleClicked.connect(self._on_pr_double_clicked)
        self._pr_tree.setRootIsDecorated(False)
        layout.addWidget(self._pr_tree)

        # PR detail area
        self._pr_detail = QLabel("Select a pull request to view details")
        self._pr_detail.setWordWrap(True)
        self._pr_detail.setStyleSheet("padding: 8px; background: palette(window); border: 1px solid palette(mid);")
        self._pr_detail.setMaximumHeight(120)
        layout.addWidget(self._pr_detail)

        return tab

    def _create_create_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form = QFormLayout()
        form.setSpacing(8)

        # Source branch
        self._source_branch_combo = QComboBox()
        self._source_branch_combo.setEditable(True)
        form.addRow("Source branch:", self._source_branch_combo)

        # Target branch
        self._target_branch_combo = QComboBox()
        self._target_branch_combo.setEditable(True)
        self._target_branch_combo.setCurrentText('main')
        form.addRow("Target branch:", self._target_branch_combo)

        # Title
        self._pr_title_edit = QLineEdit()
        self._pr_title_edit.setPlaceholderText("Pull request title")
        form.addRow("Title:", self._pr_title_edit)

        # Description
        self._pr_desc_edit = QTextEdit()
        self._pr_desc_edit.setPlaceholderText("Pull request description (supports Markdown)")
        self._pr_desc_edit.setMaximumHeight(200)
        form.addRow("Description:", self._pr_desc_edit)

        # Draft checkbox
        self._draft_check = QCheckBox("Create as Draft PR")
        form.addRow("", self._draft_check)

        layout.addLayout(form)

        layout.addStretch()

        # Create button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._create_pr_btn = QPushButton("🚀 Create Pull Request")
        self._create_pr_btn.setObjectName("primaryButton")
        self._create_pr_btn.clicked.connect(self._on_create_pr)
        self._create_pr_btn.setEnabled(False)
        btn_layout.addWidget(self._create_pr_btn)
        layout.addLayout(btn_layout)

        return tab

    def _create_search_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Search bar
        search_layout = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search by title, author, branch...")
        self._search_edit.returnPressed.connect(self._on_search_prs)
        search_layout.addWidget(self._search_edit)

        self._search_btn = QPushButton("🔍 Search")
        self._search_btn.clicked.connect(self._on_search_prs)
        search_layout.addWidget(self._search_btn)

        layout.addLayout(search_layout)

        # Search results
        self._search_results = QTreeWidget()
        self._search_results.setHeaderLabels(["#", "Title", "Author", "Source → Target", "Status"])
        self._search_results.setColumnWidth(0, 60)
        self._search_results.setColumnWidth(1, 300)
        self._search_results.setColumnWidth(2, 120)
        self._search_results.setColumnWidth(3, 200)
        self._search_results.header().setStretchLastSection(True)
        self._search_results.setAlternatingRowColors(True)
        self._search_results.setRootIsDecorated(False)
        self._search_results.itemDoubleClicked.connect(self._on_pr_double_clicked)
        layout.addWidget(self._search_results)

        return tab

    # ── Service Detection ───────────────────────────────────────

    def _detect_service(self):
        """Detect the remote service from the repository's remotes."""
        if not self._git.is_open:
            self._service_header.setText("⚠️ No repository open")
            return

        remotes = self._git.get_remotes()
        if not remotes:
            self._service_header.setText("⚠️ No remotes configured")
            return

        # Use the first remote (typically 'origin')
        remote_url = remotes[0].url
        self._service_info = detect_service(remote_url)

        if self._service_info.service_type == ServiceType.UNKNOWN:
            self._service_header.setText(
                f"🌐 Remote: {remotes[0].name} — {remote_url}\n"
                f"⚠️ Unknown hosting service"
            )
            return

        # Create service client
        self._service_client = ServiceClient(self._service_info)

        # Update header
        service_icons = {
            ServiceType.GITHUB: '🐙',
            ServiceType.GITLAB: '🦊',
            ServiceType.BITBUCKET: '🔵',
            ServiceType.GITEA: '🔶',
            ServiceType.AZURE_DEVOPS: '🔷',
            ServiceType.SOURCEHUT: '🌱',
        }
        icon = service_icons.get(self._service_info.service_type, '🌐')
        self._service_header.setText(
            f"{icon} {self._service_info.service_name}: "
            f"{self._service_info.owner}/{self._service_info.repo}"
        )

        # Token status
        if self._service_client.has_token:
            self._token_status.setText("✅ API token configured")
            self._configure_token_btn.setVisible(False)
            self._create_pr_btn.setEnabled(True)
            self._populate_branches()
            self._on_refresh_prs()
        else:
            self._token_status.setText(
                "⚠️ No API token configured — set one to manage pull requests"
            )
            self._configure_token_btn.setVisible(True)

    def _populate_branches(self):
        """Populate branch combos in the Create tab."""
        try:
            branches = self._git.get_branches()
            local_branches = [b.name for b in branches if not b.is_remote]
            all_branches = [b.name for b in branches]

            self._source_branch_combo.clear()
            self._source_branch_combo.addItems(local_branches)

            self._target_branch_combo.clear()
            self._target_branch_combo.addItems(all_branches)

            # Set current branch as source
            current = self._git.current_branch
            idx = self._source_branch_combo.findText(current)
            if idx >= 0:
                self._source_branch_combo.setCurrentIndex(idx)

            # Default target to main/master
            for default in ('main', 'master', 'develop'):
                idx = self._target_branch_combo.findText(default)
                if idx >= 0:
                    self._target_branch_combo.setCurrentIndex(idx)
                    break
        except Exception:
            pass

    # ── PR Listing ──────────────────────────────────────────────

    def _on_refresh_prs(self):
        """Refresh the pull request list."""
        if not self._service_client or not self._service_client.has_token:
            return

        state = self._state_combo.currentText().lower()
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("⏳ Loading...")
        QApplication.processEvents()

        success, prs, error = self._service_client.list_pull_requests(state)

        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("🔄 Refresh")

        if not success:
            QMessageBox.warning(self, "Error", f"Failed to load pull requests:\n{error}")
            return

        self._current_prs = prs
        self._pr_tree.clear()

        for pr in prs:
            item = QTreeWidgetItem()
            item.setText(0, str(pr.id))
            item.setText(1, pr.title)
            item.setText(2, pr.author)
            item.setText(3, f"{pr.source_branch} → {pr.target_branch}")

            # Status with visual indicator
            if pr.state == 'open':
                status_text = '✅ Open' if not pr.is_draft else '📝 Draft'
            elif pr.state == 'merged':
                status_text = '✅ Merged'
            elif pr.state == 'closed':
                status_text = '❌ Closed'
            else:
                status_text = pr.state
            item.setText(4, status_text)

            # Format date
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(pr.updated_at.replace('Z', '+00:00'))
                item.setText(5, dt.strftime('%Y-%m-%d %H:%M'))
            except Exception:
                item.setText(5, pr.updated_at[:10] if pr.updated_at else '')

            item.setData(0, Qt.UserRole, pr.id)
            self._pr_tree.addTopLevelItem(item)

        # Update detail
        self._pr_detail.setText(f"📊 {len(prs)} pull request(s) loaded")

    def _show_pr_context_menu(self, pos):
        """Show context menu for a PR item."""
        item = self._pr_tree.itemAt(pos)
        if not item:
            return

        pr_id = item.data(0, Qt.UserRole)
        pr = next((p for p in self._current_prs if p.id == pr_id), None)
        if not pr:
            return

        menu = QMenu(self)

        view_action = menu.addAction("🌐 Open in Browser")
        view_action.triggered.connect(lambda: self._open_in_browser(pr.web_url))

        menu.addSeparator()

        if pr.state == 'open':
            merge_action = menu.addAction("✅ Merge")
            merge_action.triggered.connect(lambda: self._on_merge_pr(pr))

            close_action = menu.addAction("❌ Close")
            close_action.triggered.connect(lambda: self._on_close_pr(pr))

        checkout_action = menu.addAction("📥 Checkout Source Branch")
        checkout_action.triggered.connect(lambda: self._checkout_branch(pr.source_branch))

        menu.exec(self._pr_tree.viewport().mapToGlobal(pos))

    def _on_pr_double_clicked(self, item, column):
        """Open PR in browser on double-click."""
        pr_id = item.data(0, Qt.UserRole)
        pr = next((p for p in self._current_prs if p.id == pr_id), None)
        if pr:
            self._open_in_browser(pr.web_url)

    # ── PR Creation ─────────────────────────────────────────────

    def _on_create_pr(self):
        """Create a new pull request."""
        if not self._service_client or not self._service_client.has_token:
            QMessageBox.warning(self, "Error", "API token not configured")
            return

        title = self._pr_title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Error", "Please enter a title")
            return

        description = self._pr_desc_edit.toPlainText().strip()
        source = self._source_branch_combo.currentText()
        target = self._target_branch_combo.currentText()
        draft = self._draft_check.isChecked()

        if not source:
            QMessageBox.warning(self, "Error", "Please select a source branch")
            return

        self._create_pr_btn.setEnabled(False)
        self._create_pr_btn.setText("⏳ Creating...")
        QApplication.processEvents()

        success, pr, error = self._service_client.create_pull_request(
            title, description, source, target, draft
        )

        self._create_pr_btn.setEnabled(True)
        self._create_pr_btn.setText("🚀 Create Pull Request")

        if success and pr:
            reply = QMessageBox.question(
                self, "PR Created",
                f"Pull request #{pr.id} created successfully!\n\n"
                f"Title: {pr.title}\n"
                f"URL: {pr.web_url}\n\n"
                "Open in browser?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._open_in_browser(pr.web_url)

            # Clear form
            self._pr_title_edit.clear()
            self._pr_desc_edit.clear()
            self._draft_check.setChecked(False)

            # Refresh list
            self._on_refresh_prs()
        else:
            QMessageBox.warning(self, "Error", f"Failed to create PR:\n{error}")

    # ── PR Actions ──────────────────────────────────────────────

    def _on_merge_pr(self, pr: PullRequest):
        """Merge a pull request."""
        if not self._service_client:
            return

        # Ask for merge method
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QDialogButtonBox

        method_dialog = QDialog(self)
        method_dialog.setWindowTitle("Merge Pull Request")
        method_dialog.setMinimumWidth(350)
        layout = QVBoxLayout(method_dialog)

        layout.addWidget(QLabel(f"Merge #{pr.id}: {pr.title}"))
        layout.addWidget(QLabel("Merge method:"))

        merge_rb = QRadioButton("Create merge commit")
        merge_rb.setChecked(True)
        layout.addWidget(merge_rb)

        squash_rb = QRadioButton("Squash and merge")
        layout.addWidget(squash_rb)

        rebase_rb = QRadioButton("Rebase and merge")
        layout.addWidget(rebase_rb)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(method_dialog.accept)
        buttons.rejected.connect(method_dialog.reject)
        layout.addWidget(buttons)

        if method_dialog.exec() != QDialog.Accepted:
            return

        method = 'merge'
        if squash_rb.isChecked():
            method = 'squash'
        elif rebase_rb.isChecked():
            method = 'rebase'

        success, message = self._service_client.merge_pull_request(pr.id, method)
        if success:
            QMessageBox.information(self, "Merged", message)
            self._on_refresh_prs()
        else:
            QMessageBox.warning(self, "Merge Failed", message)

    def _on_close_pr(self, pr: PullRequest):
        """Close a pull request without merging."""
        reply = QMessageBox.question(
            self, "Close PR",
            f"Close #{pr.id}: {pr.title} without merging?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        success, message = self._service_client.close_pull_request(pr.id)
        if success:
            self._on_refresh_prs()
        else:
            QMessageBox.warning(self, "Error", message)

    # ── Search ──────────────────────────────────────────────────

    def _on_search_prs(self):
        """Search pull requests."""
        query = self._search_edit.text().strip().lower()
        if not query:
            return

        self._search_results.clear()

        # Search locally in loaded PRs
        results = []
        for pr in self._current_prs:
            if (query in pr.title.lower() or
                    query in pr.author.lower() or
                    query in pr.source_branch.lower() or
                    query in pr.target_branch.lower() or
                    query in str(pr.id)):
                results.append(pr)

        for pr in results:
            item = QTreeWidgetItem()
            item.setText(0, str(pr.id))
            item.setText(1, pr.title)
            item.setText(2, pr.author)
            item.setText(3, f"{pr.source_branch} → {pr.target_branch}")
            item.setText(4, pr.state)
            item.setData(0, Qt.UserRole, pr.id)
            self._search_results.addTopLevelItem(item)

    # ── Token Configuration ─────────────────────────────────────

    def _on_configure_token(self):
        """Open token configuration dialog."""
        if not self._service_info:
            return

        dialog = TokenConfigDialog(self._service_info, self)
        if dialog.exec():
            # Reload client with new token
            token = get_token(self._service_info.service_type)
            self._service_client = ServiceClient(self._service_info, token)

            if self._service_client.has_token:
                self._token_status.setText("✅ API token configured")
                self._configure_token_btn.setVisible(False)
                self._create_pr_btn.setEnabled(True)
                self._populate_branches()
                self._on_refresh_prs()
            else:
                self._token_status.setText("⚠️ No API token configured")

    # ── Helpers ─────────────────────────────────────────────────

    def _open_in_browser(self, url: str):
        """Open a URL in the default browser."""
        QDesktopServices.openUrl(QUrl(url))

    def _checkout_branch(self, branch: str):
        """Checkout a branch."""
        if self._git.checkout_branch(branch):
            self._git.checkout_branch(branch)


class TokenConfigDialog(QDialog):
    """Dialog for configuring API tokens for remote services."""

    def __init__(self, service_info: ServiceInfo, parent=None):
        super().__init__(parent)
        self._service_info = service_info
        self.setWindowTitle(f"Configure {service_info.service_name} Token")
        self.resize(500, 300)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Service info
        info_text = (
            f"<h3>{self._service_info.service_name}</h3>"
            f"<p>Repository: {self._service_info.owner}/{self._service_info.repo}</p>"
            f"<p>Remote URL: {self._service_info.web_url}</p>"
        )
        layout.addWidget(QLabel(info_text))

        # Token instructions
        instructions = self._get_token_instructions()
        layout.addWidget(QLabel(instructions))
        layout.addSpacing(8)

        # Token input
        form = QFormLayout()
        self._token_edit = QLineEdit()
        self._token_edit.setEchoMode(QLineEdit.Password)
        self._token_edit.setPlaceholderText("Paste your personal access token here")
        # Show existing token if any
        existing = get_token(self._service_info.service_type)
        if existing:
            self._token_edit.setText(existing)
        form.addRow("Token:", self._token_edit)

        self._show_token_check = QCheckBox("Show token")
        self._show_token_check.toggled.connect(
            lambda checked: self._token_edit.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        form.addRow("", self._show_token_check)

        layout.addLayout(form)
        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("Save Token")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _get_token_instructions(self) -> str:
        """Get instructions for creating a token for the service."""
        instructions = {
            ServiceType.GITHUB: (
                "To create a GitHub Personal Access Token:\n"
                "1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)\n"
                "2. Click 'Generate new token (classic)'\n"
                "3. Select scopes: 'repo' (full control) and optionally 'workflow'\n"
                "4. Copy the token and paste it below"
            ),
            ServiceType.GITLAB: (
                "To create a GitLab Personal Access Token:\n"
                "1. Go to GitLab Settings → Access Tokens\n"
                "2. Add a token name and select 'api' scope\n"
                "3. Click 'Create personal access token'\n"
                "4. Copy the token and paste it below"
            ),
            ServiceType.BITBUCKET: (
                "To create a Bitbucket App Password:\n"
                "1. Go to Bitbucket Settings → App passwords\n"
                "2. Click 'Create app password'\n"
                "3. Select permissions: 'Pull requests: Read & Write'\n"
                "4. Copy the password and paste it below"
            ),
            ServiceType.GITEA: (
                "To create a Gitea Access Token:\n"
                "1. Go to your Gitea Settings → Applications\n"
                "2. Under 'Manage Access Tokens', enter a token name\n"
                "3. Click 'Generate Token'\n"
                "4. Copy the token and paste it below"
            ),
            ServiceType.AZURE_DEVOPS: (
                "To create an Azure DevOps PAT:\n"
                "1. Go to Azure DevOps → User settings → Personal access tokens\n"
                "2. Click '+ New Token'\n"
                "3. Select 'Code (Read & Write)' scope\n"
                "4. Copy the token and paste it below"
            ),
        }
        return instructions.get(
            self._service_info.service_type,
            "Enter your API token for this service:"
        )

    def _on_save(self):
        token = self._token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, "Error", "Please enter a token")
            return

        if save_token(self._service_info.service_type, token):
            QMessageBox.information(
                self, "Saved",
                f"Token saved for {self._service_info.service_name}.\n"
                "You can now manage pull requests."
            )
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Failed to save token")
