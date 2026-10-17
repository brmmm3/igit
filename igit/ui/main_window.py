"""Main application window for iGit."""

import os
import shlex
import sys
from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel, QStatusBar,
    QMenuBar, QMenu, QToolBar, QToolButton, QFileDialog, QMessageBox,
    QTabWidget, QInputDialog, QApplication, QDockWidget, QListWidget,
    QFrame, QLineEdit, QComboBox, QPlainTextEdit
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer, QSettings, QProcess
from PySide6.QtGui import QAction, QKeySequence, QIcon, QFont, QColor
from PySide6.QtWidgets import QSizePolicy

from ..core.git_operations import GitOperations
from ..core.undo_manager import UndoManager
from ..resources.themes import get_theme
from ..resources import app_icon_path
from ..widgets.working_copy import WorkingCopyPanel
from ..widgets.diff_viewer import DiffViewer
from ..widgets.commit_panel import CommitPanel
from ..widgets.branch_graph import BranchGraphPanel
from ..widgets.branch_panel import BranchPanel
from ..widgets.stash_panel import StashPanel
from ..widgets.remote_panel import RemotePanel
from ..widgets.statistics_panel import StatisticsPanel
from ..dialogs.clone_dialog import CloneDialog
from ..dialogs.settings_dialog import SettingsDialog
from ..dialogs.conflict_dialog import ConflictDialog
from ..dialogs.diff_dialog import DiffDialog
from ..dialogs.rebase_dialog import RebaseDialog
from ..dialogs.pr_dialog import PullRequestDialog


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self._git = GitOperations()
        self._undo_manager = UndoManager(self._git)
        self._dark_mode = False
        self._recent_repos: list[str] = []
        self._recent_repo_actions: list[QAction] = []
        self._setup_window()
        self._create_menu_bar()
        self._create_toolbar()
        self._create_central_widget()
        self._create_status_bar()
        self._connect_signals()
        self._load_recent_repos()
        self._update_title()

    def _setup_window(self):
        self.setWindowTitle("iGit")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        # Apply application icon
        if app_icon_path:
            icon = QIcon(app_icon_path)
            self.setWindowIcon(icon)
            app = QApplication.instance()
            if app is not None:
                app.setWindowIcon(icon)

    def _create_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&Start")

        open_action = QAction("&Open Repository...", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._on_open_repo)
        file_menu.addAction(open_action)

        init_action = QAction("&Initialize Repository...", self)
        init_action.triggered.connect(self._on_init_repo)
        file_menu.addAction(init_action)

        clone_action = QAction("&Clone Repository...", self)
        clone_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        clone_action.triggered.connect(self._on_clone_repo)
        file_menu.addAction(clone_action)

        file_menu.addSeparator()

        close_action = QAction("&Close Repository", self)
        close_action.triggered.connect(self._on_close_repo)
        file_menu.addAction(close_action)

        file_menu.addSeparator()

        # Recent repositories submenu
        self._recent_menu = file_menu.addMenu("&Recent Repositories")
        self._recent_menu.setEnabled(False)

        file_menu.addSeparator()

        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self._on_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Commands")

        self._undo_action = QAction("&Undo", self)
        self._undo_action.setShortcut(QKeySequence.Undo)
        self._undo_action.setEnabled(False)
        self._undo_action.triggered.connect(self._on_undo)
        edit_menu.addAction(self._undo_action)

        edit_menu.addSeparator()

        self._undo_history_action = QAction("Undo &History...", self)
        self._undo_history_action.triggered.connect(self._on_undo_history)
        edit_menu.addAction(self._undo_history_action)

        # Repository menu
        repo_menu = menubar.addMenu("&Repository")

        fetch_action = QAction("&Fetch", self)
        fetch_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        fetch_action.triggered.connect(self._on_fetch)
        repo_menu.addAction(fetch_action)

        pull_action = QAction("&Pull", self)
        pull_action.setShortcut(QKeySequence("Ctrl+Shift+P"))
        pull_action.triggered.connect(self._on_pull)
        repo_menu.addAction(pull_action)

        push_action = QAction("&Push", self)
        push_action.setShortcut(QKeySequence("Ctrl+Shift+U"))
        push_action.triggered.connect(self._on_push)
        repo_menu.addAction(push_action)

        repo_menu.addSeparator()

        pr_action = QAction("🔀 &Pull Requests...", self)
        pr_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        pr_action.triggered.connect(self._on_open_prs)
        repo_menu.addAction(pr_action)

        repo_menu.addSeparator()

        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self._refresh_all)
        repo_menu.addAction(refresh_action)

        # Branch menu
        branch_menu = menubar.addMenu("&Navigate")

        new_branch_action = QAction("&New Branch...", self)
        new_branch_action.triggered.connect(self._on_new_branch)
        branch_menu.addAction(new_branch_action)

        merge_action = QAction("&Merge...", self)
        merge_action.triggered.connect(self._on_merge)
        branch_menu.addAction(merge_action)

        rebase_action = QAction("&Rebase...", self)
        rebase_action.triggered.connect(self._on_rebase)
        branch_menu.addAction(rebase_action)

        interactive_rebase_action = QAction("&Interactive Rebase...", self)
        interactive_rebase_action.triggered.connect(self._on_interactive_rebase)
        branch_menu.addAction(interactive_rebase_action)

        # Commit and stash commands share the Commands menu.
        commit_menu = edit_menu
        commit_menu.addSeparator()

        commit_action = QAction("&Commit...", self)
        commit_action.setShortcut(QKeySequence("Ctrl+Return"))
        commit_action.triggered.connect(self._on_commit)
        commit_menu.addAction(commit_action)

        amend_action = QAction("&Amend Last Commit", self)
        amend_action.triggered.connect(self._on_amend)
        commit_menu.addAction(amend_action)

        commit_menu.addSeparator()

        stash_action = QAction("&Stash...", self)
        stash_action.triggered.connect(self._on_stash)
        commit_menu.addAction(stash_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        toggle_dark_action = QAction("Toggle &Dark Mode", self)
        toggle_dark_action.setShortcut(QKeySequence("Ctrl+D"))
        toggle_dark_action.triggered.connect(self._toggle_dark_mode)
        view_menu.addAction(toggle_dark_action)

        view_menu.addSeparator()

        show_conflicts_action = QAction("Show &Conflicts", self)
        show_conflicts_action.triggered.connect(self._on_show_conflicts)
        view_menu.addAction(show_conflicts_action)

        show_reflog_action = QAction("Show &Reflog", self)
        show_reflog_action.triggered.connect(self._on_show_reflog)
        view_menu.addAction(show_reflog_action)

        console_action = QAction("Git &Console", self)
        console_action.setShortcut(QKeySequence("Ctrl+Shift+G"))
        console_action.triggered.connect(self._show_git_console)
        view_menu.addAction(console_action)

        # Screenshot-aligned service/plugin/tool menu placeholders.
        github_menu = menubar.addMenu("&GitHub")
        plugins_menu = menubar.addMenu("&Plugins")
        tools_menu = menubar.addMenu("&Tools")
        dark_action = QAction("Toggle Dark Mode", self)
        dark_action.triggered.connect(self._toggle_dark_mode)
        tools_menu.addAction(dark_action)
        tools_menu.addAction("Settings...").triggered.connect(self._on_settings)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About iGit", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

        # Present the same top-level menu sequence as Git Extensions.
        ordered_menus = (
            repo_menu, branch_menu, view_menu, edit_menu,
            github_menu, plugins_menu, tools_menu,
        )
        for menu in ordered_menus:
            menubar.removeAction(menu.menuAction())
        for menu in ordered_menus:
            menubar.insertMenu(help_menu.menuAction(), menu)

    def _create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        # Repository actions
        open_btn = QToolButton()
        open_btn.setText("📂 Open")
        open_btn.clicked.connect(self._on_open_repo)
        toolbar.addWidget(open_btn)

        clone_btn = QToolButton()
        clone_btn.setText("📥 Clone")
        clone_btn.clicked.connect(self._on_clone_repo)
        toolbar.addWidget(clone_btn)

        toolbar.addSeparator()

        fetch_btn = QToolButton()
        fetch_btn.setText("⬇️ Fetch")
        fetch_btn.clicked.connect(self._on_fetch)
        toolbar.addWidget(fetch_btn)

        pull_btn = QToolButton()
        pull_btn.setText("⬇️ Pull")
        pull_btn.clicked.connect(self._on_pull)
        toolbar.addWidget(pull_btn)

        push_btn = QToolButton()
        push_btn.setText("⬆️ Push")
        push_btn.clicked.connect(self._on_push)
        toolbar.addWidget(push_btn)

        toolbar.addSeparator()

        pr_btn = QToolButton()
        pr_btn.setText("🔀 PR")
        pr_btn.setToolTip("Pull Requests (Ctrl+Shift+R)")
        pr_btn.clicked.connect(self._on_open_prs)
        toolbar.addWidget(pr_btn)

        toolbar.addSeparator()

        self._commit_btn = QToolButton()
        self._commit_btn.setText("Commit")
        self._commit_btn.setObjectName("primaryButton")
        self._commit_btn.setToolTip("Commit staged changes (Ctrl+Enter)")
        self._commit_btn.clicked.connect(self._on_commit)
        toolbar.addWidget(self._commit_btn)

        self._stash_count_label = QLabel("Stash: 0")
        self._stash_count_label.setObjectName("statusLabel")
        toolbar.addWidget(self._stash_count_label)

        toolbar.addSeparator()

        self._undo_btn = QToolButton()
        self._undo_btn.setText("↩️ Undo")
        self._undo_btn.setToolTip("Undo last action (Ctrl+Z)")
        self._undo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self._on_undo)
        toolbar.addWidget(self._undo_btn)

        toolbar.addSeparator()

        refresh_btn = QToolButton()
        refresh_btn.setText("🔄 Refresh")
        refresh_btn.clicked.connect(self._refresh_all)
        toolbar.addWidget(refresh_btn)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred
        )
        toolbar.addWidget(spacer)

        # Branch indicator
        self._repo_path_label = QLabel("No repository")
        self._repo_path_label.setObjectName("statusLabel")
        self._repo_path_label.setMaximumWidth(280)
        self._repo_path_label.setToolTip("Repository path")
        toolbar.addWidget(self._repo_path_label)

        self._branch_label = QLabel("No repo")
        self._branch_label.setObjectName("statusLabel")
        self._branch_label.setStyleSheet("padding: 0 8px;")
        toolbar.addWidget(self._branch_label)

        self._toolbar_branch_combo = QComboBox()
        self._toolbar_branch_combo.setMinimumWidth(150)
        self._toolbar_branch_combo.setMaximumWidth(220)
        self._toolbar_branch_combo.setToolTip("Checkout branch")
        self._toolbar_branch_combo.activated.connect(
            self._on_toolbar_branch_selected
        )
        toolbar.addWidget(self._toolbar_branch_combo)

        # Dark mode toggle
        dark_btn = QToolButton()
        dark_btn.setText("🌙")
        dark_btn.setToolTip("Toggle Dark Mode")
        dark_btn.clicked.connect(self._toggle_dark_mode)
        toolbar.addWidget(dark_btn)

    def _create_central_widget(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar retains the existing Changes / Branches / Stashes / Remotes
        # panels and their signal-facing private widget attributes.
        self._main_splitter = QSplitter(Qt.Horizontal)
        self._main_splitter.setChildrenCollapsible(False)

        self._sidebar_tabs = QTabWidget()
        branch_sidebar = QWidget()
        branch_layout = QVBoxLayout(branch_sidebar)
        branch_layout.setContentsMargins(4, 4, 4, 4)
        branch_layout.setSpacing(4)
        self._branch_search = QLineEdit()
        self._branch_search.setPlaceholderText("Search branches...")
        self._branch_search.textChanged.connect(self._filter_branch_sidebar)
        branch_layout.addWidget(self._branch_search)
        self._branch_sidebar_tree = QTreeWidget()
        self._branch_sidebar_tree.setHeaderHidden(True)
        self._branch_sidebar_tree.setRootIsDecorated(True)
        self._branch_sidebar_tree.setUniformRowHeights(True)
        self._branch_sidebar_tree.itemDoubleClicked.connect(
            self._on_branch_sidebar_activated
        )
        branch_layout.addWidget(self._branch_sidebar_tree, 1)
        self._sidebar_tabs.addTab(branch_sidebar, "Branches")

        self._working_copy = WorkingCopyPanel(self._git)
        self._sidebar_tabs.addTab(self._working_copy, "Changes")
        self._branch_panel = BranchPanel(self._git)
        self._sidebar_tabs.addTab(self._branch_panel, "Manage")
        self._stash_panel = StashPanel(self._git)
        self._sidebar_tabs.addTab(self._stash_panel, "Stashes")
        self._remote_panel = RemotePanel(self._git)
        self._sidebar_tabs.addTab(self._remote_panel, "Remotes")
        self._sidebar_tabs.setMinimumWidth(220)
        self._main_splitter.addWidget(self._sidebar_tabs)

        # Right side: history above the tabbed commit/diff/detail workspace.
        self._right_splitter = QSplitter(Qt.Vertical)
        self._right_splitter.setChildrenCollapsible(False)

        self._branch_graph = BranchGraphPanel(self._git)
        self._right_splitter.addWidget(self._branch_graph)

        self._bottom_tabs = QTabWidget()
        self._commit_panel = CommitPanel(self._git)
        self._bottom_tabs.addTab(self._commit_panel, "Commit")

        self._diff_viewer = DiffViewer(self, self._dark_mode)
        diff_tab = QWidget()
        diff_layout = QVBoxLayout(diff_tab)
        diff_layout.setContentsMargins(2, 2, 2, 2)
        diff_layout.setSpacing(2)
        diff_controls = QHBoxLayout()
        self._diff_file_filter = QLineEdit()
        self._diff_file_filter.setPlaceholderText("Filter files...")
        self._diff_file_filter.textChanged.connect(self._filter_diff_files)
        diff_controls.addWidget(self._diff_file_filter, 1)
        self._diff_with_combo = QComboBox()
        self._diff_with_combo.setMinimumWidth(180)
        self._diff_with_combo.setToolTip("Diff with selected revision")
        diff_controls.addWidget(self._diff_with_combo)
        diff_layout.addLayout(diff_controls)
        diff_splitter = QSplitter(Qt.Horizontal)
        self._diff_file_list = QListWidget()
        self._diff_file_list.setMinimumWidth(160)
        self._diff_file_list.currentTextChanged.connect(
            self._on_diff_file_list_selected
        )
        diff_splitter.addWidget(self._diff_file_list)
        diff_splitter.addWidget(self._diff_viewer)
        diff_splitter.setSizes([220, 780])
        diff_layout.addWidget(diff_splitter, 1)
        self._bottom_tabs.addTab(diff_tab, "Diff")

        self._file_tree = QTreeWidget()
        self._file_tree.setHeaderLabels(["File", "Added", "Removed"])
        self._file_tree.setRootIsDecorated(False)
        self._file_tree.setAlternatingRowColors(False)
        self._bottom_tabs.addTab(self._file_tree, "File tree")

        self._gpg_panel = QLabel("GPG signature information appears for signed commits.")
        self._gpg_panel.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._bottom_tabs.addTab(self._gpg_panel, "GPG")

        console_panel = QWidget()
        console_layout = QVBoxLayout(console_panel)
        console_layout.setContentsMargins(4, 4, 4, 4)
        console_layout.setSpacing(4)
        self._console_view = QPlainTextEdit()
        self._console_view.setReadOnly(True)
        self._console_view.setPlaceholderText(
            "Run Git commands here. Commands execute in the open repository; shell syntax is not evaluated."
        )
        console_layout.addWidget(self._console_view, 1)
        console_controls = QHBoxLayout()
        self._console_input = QLineEdit()
        self._console_input.setPlaceholderText("git status --short")
        self._console_input.returnPressed.connect(self._run_git_console_command)
        console_controls.addWidget(self._console_input, 1)
        self._console_run_button = QPushButton("Run")
        self._console_run_button.clicked.connect(self._run_git_console_command)
        console_controls.addWidget(self._console_run_button)
        self._console_stop_button = QPushButton("Stop")
        self._console_stop_button.setEnabled(False)
        self._console_stop_button.clicked.connect(self._stop_git_console_command)
        console_controls.addWidget(self._console_stop_button)
        console_layout.addLayout(console_controls)
        self._console_process = QProcess(self)
        self._console_process.readyReadStandardOutput.connect(
            self._read_git_console_stdout
        )
        self._console_process.readyReadStandardError.connect(
            self._read_git_console_stderr
        )
        self._console_process.finished.connect(self._git_console_finished)
        self._console_process.errorOccurred.connect(self._git_console_error)
        self._bottom_tabs.addTab(console_panel, "Console")

        self._build_report_view = QPlainTextEdit()
        self._build_report_view.setReadOnly(True)
        self._build_report_view.setPlaceholderText("No build report available")
        self._bottom_tabs.addTab(self._build_report_view, "Build Report")

        self._statistics_panel = StatisticsPanel(self._git)
        self._bottom_tabs.addTab(self._statistics_panel, "Statistics")

        self._right_splitter.addWidget(self._bottom_tabs)
        self._right_splitter.setSizes([520, 280])
        self._right_splitter.setStretchFactor(0, 3)
        self._right_splitter.setStretchFactor(1, 2)

        self._main_splitter.addWidget(self._right_splitter)
        self._main_splitter.setSizes([270, 1010])
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        main_layout.addWidget(self._main_splitter)

    def _create_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._repo_status = QLabel("No repository open")
        self._repo_status.setObjectName("statusLabel")
        self._status_bar.addWidget(self._repo_status)

        self._branch_status = QLabel("")
        self._branch_status.setObjectName("statusLabel")
        self._status_bar.addPermanentWidget(self._branch_status)

        self._commit_count = QLabel("")
        self._commit_count.setObjectName("statusLabel")
        self._status_bar.addPermanentWidget(self._commit_count)

    def _connect_signals(self):
        # Working copy signals
        self._working_copy.file_selected.connect(self._on_file_selected)
        self._working_copy.file_staged.connect(self._on_stage_file)
        self._working_copy.file_unstaged.connect(self._on_unstage_file)
        self._working_copy.file_discarded.connect(self._on_discard_file)
        self._working_copy.refresh_requested.connect(self._refresh_all)

        # Diff viewer signals
        self._diff_viewer.stage_hunk_requested.connect(self._on_stage_hunk)
        self._diff_viewer.discard_hunk_requested.connect(self._on_discard_hunk)

        # Commit panel signals
        self._commit_panel.commit_requested.connect(self._on_commit_action)

        # Branch graph signals
        self._branch_graph.commit_selected.connect(self._on_commit_selected)
        self._branch_graph.commit_range_selected.connect(self._on_commit_range_selected)
        self._branch_graph.special_row_selected.connect(self._on_special_history_row)
        self._branch_graph.cherry_pick_requested.connect(self._on_cherry_pick)
        self._branch_graph.revert_requested.connect(self._on_revert)
        self._branch_graph.reset_requested.connect(self._on_reset)
        self._branch_graph.create_tag_requested.connect(self._on_create_tag)
        self._branch_graph.create_branch_requested.connect(self._on_create_branch_from_sha)

        # Branch panel signals
        self._branch_panel.branch_checkout_requested.connect(self._on_checkout_branch)
        self._branch_panel.branch_merge_requested.connect(self._on_merge_branch)
        self._branch_panel.branch_delete_requested.connect(self._on_delete_branch)
        self._branch_panel.refresh_requested.connect(self._refresh_all)

        # Stash panel signals
        self._stash_panel.refresh_requested.connect(self._refresh_all)
        self._stash_panel.stash_saved.connect(self._undo_manager.record_stash_save)
        self._stash_panel.stash_saved.connect(lambda _: self._update_undo_state())
        self._stash_panel.stash_dropped.connect(self._undo_manager.record_stash_drop)
        self._stash_panel.stash_dropped.connect(lambda *_: self._update_undo_state())

        # Remote panel signals
        self._remote_panel.refresh_requested.connect(self._refresh_all)
        self._remote_panel.remote_removed.connect(self._undo_manager.record_remote_remove)
        self._remote_panel.remote_removed.connect(lambda *_: self._update_undo_state())

        # Drag & drop signals
        self._branch_panel.branch_dropped_for_merge.connect(self._on_branch_dropped_for_merge)
        self._branch_panel.branch_dropped_for_rebase.connect(self._on_branch_dropped_for_rebase)
        self._branch_panel.commit_dropped_for_branch.connect(self._on_commit_dropped_for_branch)
        self._branch_panel.branch_dropped_for_push.connect(self._on_branch_dropped_on_remote)
        self._branch_panel.branch_dropped_for_pull.connect(self._on_branch_dropped_on_remote_pull)
        self._remote_panel.branch_dropped_for_push.connect(self._on_branch_dropped_on_remote)
        self._remote_panel.branch_dropped_for_pull.connect(self._on_branch_dropped_on_remote_pull)

    def _update_title(self):
        if self._git.is_open:
            branch = self._git.current_branch
            self.setWindowTitle(f"iGit - {self._git.repo_name} ({branch})")
            self._branch_label.setText(f"{branch}")
            self._repo_path_label.setText(os.path.basename(self._git.repo_path) or self._git.repo_path)
            self._toolbar_branch_combo.blockSignals(True)
            try:
                self._toolbar_branch_combo.clear()
                for info in self._git.get_branches():
                    if not info.is_remote:
                        self._toolbar_branch_combo.addItem(info.name)
                selected = self._toolbar_branch_combo.findText(branch)
                if selected >= 0:
                    self._toolbar_branch_combo.setCurrentIndex(selected)
            finally:
                self._toolbar_branch_combo.blockSignals(False)
            self._repo_path_label.setToolTip(self._git.repo_path)
            self._branch_status.setText(f"Branch: {branch}")
            self._repo_status.setText(f"{self._git.repo_path}")
        else:
            self.setWindowTitle("iGit")
            self._branch_label.setText("No repo")
            self._repo_path_label.setText("No repository")
            self._repo_path_label.setToolTip("")
            self._toolbar_branch_combo.clear()
            self._branch_status.setText("")
            self._repo_status.setText("No repository open")
        self._update_undo_state()

    def _on_toolbar_branch_selected(self, _index: int):
        branch = self._toolbar_branch_combo.currentText()
        if branch and branch != self._git.current_branch:
            self._on_checkout_branch(branch)

    def _update_undo_state(self):
        """Update undo button and menu state."""
        can_undo = self._undo_manager.can_undo
        self._undo_action.setEnabled(can_undo)
        self._undo_btn.setEnabled(can_undo)
        if can_undo:
            desc = self._undo_manager.undo_description
            self._undo_action.setText(f"Undo {desc}")
            self._undo_btn.setToolTip(f"Undo {desc} (Ctrl+Z)")
        else:
            self._undo_action.setText("&Undo")
            self._undo_btn.setToolTip("Undo last action (Ctrl+Z)")

    def _refresh_all(self):
        """Refresh all panels."""
        if not self._git.is_open:
            return

        self._working_copy.refresh()
        self._commit_panel.refresh()
        try:
            status_files = self._git.get_file_status()
            staged_count = sum(
                1 for fs in status_files
                if fs.staged_status or fs.staged
            )
            self._commit_btn.setText(
                f"Commit ({staged_count})" if staged_count else "Commit"
            )
            self._stash_count_label.setText(
                f"Stash: {len(self._git.get_stashes())}"
            )
        except Exception:
            self._commit_btn.setText("Commit")
            self._stash_count_label.setText("Stash: 0")
        # Determine if there are staged changes to commit
        has_staged = any(
            fs.staged_status or fs.staged
            for fs in self._git.get_file_status()
        )
        self._commit_panel.set_has_staged_changes(has_staged)
        self._branch_graph.refresh()
        self._refresh_branch_sidebar()
        self._branch_panel.refresh()
        self._stash_panel.refresh()
        self._remote_panel.refresh()
        self._statistics_panel.refresh()
        self._update_title()

        # Update commit count
        try:
            commits = self._git.get_commits(max_count=1)
            self._commit_count.setText(f"Total commits: {len(commits)}+")
        except Exception:
            pass

    # ── Slots ──────────────────────────────────────────────────

    def _refresh_branch_sidebar(self):
        """Build a slash-separated branch tree with tag/remote sections."""
        tree = self._branch_sidebar_tree
        tree.clear()
        branches = self._git.get_branches()
        local = [b for b in branches if not b.is_remote]
        remotes = [b for b in branches if b.is_remote]
        root = QTreeWidgetItem([f"Branches ({len(local)})"])
        root.setExpanded(True)
        tree.addTopLevelItem(root)

        try:
            current_branch = self._git.current_branch
        except Exception:
            current_branch = ""

        folders = {}
        for branch in sorted(local, key=lambda b: b.name.casefold()):
            parent = root
            parts = branch.name.split("/")
            accumulated = []
            for part in parts[:-1]:
                accumulated.append(part)
                key = (tuple(accumulated))
                if key not in folders:
                    folder = QTreeWidgetItem([part])
                    folder.setData(0, Qt.ItemDataRole.UserRole, None)
                    parent.addChild(folder)
                    folders[key] = folder
                parent = folders[key]
            leaf = QTreeWidgetItem([parts[-1]])
            leaf.setData(0, Qt.ItemDataRole.UserRole, branch.name)
            leaf.setToolTip(0, branch.name)
            if branch.name == current_branch:
                font = leaf.font(0)
                font.setBold(True)
                leaf.setFont(0, font)
                leaf.setForeground(0, QColor("#d9534f"))
            parent.addChild(leaf)

        if remotes:
            remote_root = QTreeWidgetItem([f"Remote branches ({len(remotes)})"])
            tree.addTopLevelItem(remote_root)
            for branch in sorted(remotes, key=lambda b: b.name.casefold()):
                item = QTreeWidgetItem([branch.name])
                item.setData(0, Qt.ItemDataRole.UserRole, None)
                remote_root.addChild(item)

        try:
            tags = self._git.get_tags()
        except Exception:
            tags = []
        tag_root = QTreeWidgetItem([f"Tags ({len(tags)})"])
        tree.addTopLevelItem(tag_root)
        for tag in tags:
            item = QTreeWidgetItem([tag.name])
            tag_root.addChild(item)

        try:
            stashes = self._git.get_stashes()
        except Exception:
            stashes = []
        stash_root = QTreeWidgetItem([f"Stashes ({len(stashes)})"])
        tree.addTopLevelItem(stash_root)
        for stash in stashes:
            stash_root.addChild(QTreeWidgetItem([stash.message]))

        root.setExpanded(True)
        self._filter_branch_sidebar(self._branch_search.text())

    def _filter_branch_sidebar(self, text: str):
        """Filter branch-tree leaves while retaining matching parents."""
        query = text.strip().casefold()
        tree = getattr(self, "_branch_sidebar_tree", None)
        if tree is None:
            return

        def visit(item):
            child_match = False
            for i in range(item.childCount()):
                child_match = visit(item.child(i)) or child_match
            value = item.text(0).casefold()
            own_match = not query or query in value
            item.setHidden(not (own_match or child_match))
            return own_match or child_match

        for i in range(tree.topLevelItemCount()):
            visit(tree.topLevelItem(i))

    def _on_branch_sidebar_activated(self, item, _column):
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if name and self._git.is_open:
            self._on_checkout_branch(str(name))

    def _show_git_console(self):
        """Select the integrated Git command console."""
        self._bottom_tabs.setCurrentWidget(self._console_input.parentWidget())
        self._console_input.setFocus()

    def _run_git_console_command(self):
        """Run a Git CLI command without passing it through a shell."""
        if not self._git.is_open:
            QMessageBox.information(self, "Git Console", "Open a repository first.")
            return
        command = self._console_input.text().strip()
        if not command:
            return
        try:
            arguments = shlex.split(command)
        except ValueError as exc:
            self._console_view.appendPlainText(f"Invalid command: {exc}")
            return
        if arguments and arguments[0] == "git":
            arguments = arguments[1:]
        if not arguments:
            self._console_view.appendPlainText("Enter a Git subcommand, for example: git status")
            return
        if self._console_process.state() != QProcess.NotRunning:
            return

        self._console_input.clear()
        self._console_view.appendPlainText(
            f"$ git {' '.join(shlex.quote(arg) for arg in arguments)}"
        )
        self._console_run_button.setEnabled(False)
        self._console_stop_button.setEnabled(True)
        self._console_process.setWorkingDirectory(self._git.repo_path)
        environment = self._console_process.processEnvironment()
        environment.insert("GIT_TERMINAL_PROMPT", "0")
        environment.insert("GCM_INTERACTIVE", "Never")
        self._console_process.setProcessEnvironment(environment)
        self._console_process.start("git", arguments)

    def _read_git_console_stdout(self):
        output = bytes(self._console_process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        if output:
            self._console_view.insertPlainText(output)
            self._console_view.ensureCursorVisible()

    def _read_git_console_stderr(self):
        output = bytes(self._console_process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        if output:
            self._console_view.insertPlainText(output)
            self._console_view.ensureCursorVisible()

    def _git_console_finished(self, exit_code, _exit_status):
        self._read_git_console_stdout()
        self._read_git_console_stderr()
        self._console_view.appendPlainText(f"[Git exited with status {exit_code}]\n")
        self._console_run_button.setEnabled(True)
        self._console_stop_button.setEnabled(False)
        if self._git.is_open:
            self._refresh_all()

    def _git_console_error(self, error):
        if error == QProcess.FailedToStart:
            self._console_view.appendPlainText(
                f"Unable to start Git: {self._console_process.errorString()}"
            )
            self._console_run_button.setEnabled(True)
            self._console_stop_button.setEnabled(False)

    def _stop_git_console_command(self):
        if self._console_process.state() != QProcess.NotRunning:
            self._console_process.terminate()
            QTimer.singleShot(1500, self._kill_git_console_if_running)

    def _kill_git_console_if_running(self):
        if self._console_process.state() != QProcess.NotRunning:
            self._console_process.kill()

    def closeEvent(self, event):
        """Clean up on close."""
        if self._console_process.state() != QProcess.NotRunning:
            self._console_process.kill()
        self._undo_manager.close()
        super().closeEvent(event)

    def _on_open_repo(self):
        start_dir = self._git.repo_path if self._git.is_open and self._git.repo_path else ''
        path = QFileDialog.getExistingDirectory(self, "Open Repository", start_dir)
        if path:
            if self._git.open(path):
                self._add_to_recent_repos(path)
                self._refresh_all()
            else:
                QMessageBox.warning(self, "Error", "Not a git repository")

    def _on_init_repo(self):
        path = QFileDialog.getExistingDirectory(self, "Initialize Repository")
        if path:
            if self._git.init_repo(path):
                self._git.open(path)
                self._add_to_recent_repos(path)
                self._refresh_all()
            else:
                QMessageBox.warning(self, "Error", "Failed to initialize repository")

    def _on_clone_repo(self):
        dialog = CloneDialog(self)
        if dialog.exec():
            path = dialog.result_path
            if path and self._git.open(path):
                self._add_to_recent_repos(path)
                self._refresh_all()

    def _on_close_repo(self):
        self._git.close()
        self._undo_manager.clear()
        self._update_undo_state()
        self._working_copy._staged_tree.clear()
        self._working_copy._unstaged_tree.clear()
        self._diff_viewer.clear()
        self._commit_panel.clear()
        self._commit_panel.set_has_staged_changes(False)
        self._branch_graph._commit_tree.clear()
        self._branch_sidebar_tree.clear()
        self._branch_panel._branch_tree.clear()
        self._stash_panel._stash_tree.clear()
        self._remote_panel._remote_tree.clear()
        self._statistics_panel.refresh()
        self._update_title()

    # ── Recent Repositories ────────────────────────────────────

    def _load_recent_repos(self):
        """Load recent repositories from QSettings."""
        settings = QSettings("iGit", "iGit")
        size = settings.beginReadArray("recent_repos")
        self._recent_repos.clear()
        for i in range(size):
            settings.setArrayIndex(i)
            path = settings.value("path", "")
            if path and os.path.isdir(path):
                self._recent_repos.append(path)
        settings.endArray()
        self._update_recent_repos_menu()

    def _save_recent_repos(self):
        """Save recent repositories to QSettings."""
        settings = QSettings("iGit", "iGit")
        settings.beginWriteArray("recent_repos")
        for i, path in enumerate(self._recent_repos):
            settings.setArrayIndex(i)
            settings.setValue("path", path)
        settings.endArray()

    def _add_to_recent_repos(self, path: str):
        """Add a repository path to the recent list (deduped, max 10)."""
        if path in self._recent_repos:
            self._recent_repos.remove(path)
        self._recent_repos.insert(0, path)
        self._recent_repos = self._recent_repos[:10]
        self._save_recent_repos()
        self._update_recent_repos_menu()

    def _update_recent_repos_menu(self):
        """Rebuild the recent repositories submenu."""
        self._recent_menu.clear()
        if not self._recent_repos:
            self._recent_menu.setEnabled(False)
            action = self._recent_menu.addAction("(No recent repositories)")
            action.setEnabled(False)
            return

        self._recent_menu.setEnabled(True)
        for path in self._recent_repos:
            # Show just the folder name, with full path as tooltip
            name = os.path.basename(path) or path
            action = self._recent_menu.addAction(name)
            action.setToolTip(path)
            action.setData(path)
            action.triggered.connect(self._on_open_recent_repo)

        self._recent_menu.addSeparator()
        clear_action = self._recent_menu.addAction("Clear Recent Repositories")
        clear_action.triggered.connect(self._on_clear_recent_repos)

    def _on_open_recent_repo(self):
        """Open a repository from the recent list."""
        action = self.sender()
        if not action:
            return
        path = action.data()
        if not path or not os.path.isdir(path):
            QMessageBox.warning(self, "Error", f"Repository not found:\n{path}")
            self._recent_repos = [p for p in self._recent_repos if p != path]
            self._save_recent_repos()
            self._update_recent_repos_menu()
            return
        if self._git.open(path):
            self._add_to_recent_repos(path)
            self._refresh_all()
        else:
            QMessageBox.warning(self, "Error", "Not a git repository")

    def _on_clear_recent_repos(self):
        """Clear the recent repositories list."""
        self._recent_repos.clear()
        self._save_recent_repos()
        self._update_recent_repos_menu()

    def _on_settings(self):
        dialog = SettingsDialog(self._git, self)
        dialog.settings_changed.connect(self._refresh_all)
        dialog.exec()

    def _on_file_selected(self, path: str):
        self._selected_commit_sha = None
        self._selected_commit_range = None
        diff = self._git.get_diff(path)
        self._diff_viewer.set_diff(diff, path)
        self._bottom_tabs.setCurrentWidget(self._bottom_tabs.widget(1))

    def _populate_diff_files(self, stats):
        self._diff_file_list.blockSignals(True)
        self._diff_file_list.clear()
        self._file_tree.clear()
        for file_info in (stats or {}).get("files", []):
            path = file_info.get("path", "")
            if path:
                self._diff_file_list.addItem(path)
                row = QTreeWidgetItem([
                    path,
                    str(file_info.get("added", 0)),
                    str(file_info.get("removed", 0)),
                ])
                self._file_tree.addTopLevelItem(row)
        self._diff_file_list.blockSignals(False)
        self._filter_diff_files(self._diff_file_filter.text())

    def _filter_diff_files(self, text: str):
        query = text.strip().casefold()
        for row in range(self._diff_file_list.count()):
            item = self._diff_file_list.item(row)
            item.setHidden(bool(query) and query not in item.text().casefold())

    def _on_diff_file_list_selected(self, path: str):
        if not path or not self._git.is_open:
            return
        try:
            if self._selected_commit_range:
                newest, oldest = self._selected_commit_range
                diff = self._git.get_diff_for_commit_range_file(
                    newest, oldest, path
                )
            elif self._selected_commit_sha:
                diff = self._git.get_diff_for_commit_file(
                    self._selected_commit_sha, path
                )
            else:
                diff = self._git.get_diff(path)
            self._diff_viewer.set_diff(diff, path)
        except Exception as exc:
            self._diff_viewer.set_diff(f"Unable to load diff: {exc}", path)

    def _on_stage_file(self, path: str):
        if self._git.stage_file(path):
            self._undo_manager.record_stage(path)
            self._update_undo_state()
            self._refresh_all()

    def _on_unstage_file(self, path: str):
        if self._git.unstage_file(path):
            self._undo_manager.record_unstage(path)
            self._update_undo_state()
            self._refresh_all()

    def _on_discard_file(self, path: str):
        reply = QMessageBox.question(
            self, "Discard Changes",
            f"Discard all changes in '{path}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Backup before discarding
            self._undo_manager.record_discard_file(path)
            if self._git.discard_changes(path):
                self._update_undo_state()
                self._refresh_all()

    def _on_stage_hunk(self, path: str, start: int, end: int):
        if self._git.stage_hunk(path, start, end):
            self._undo_manager.record_stage(path)
            self._update_undo_state()
            self._refresh_all()

    def _on_discard_hunk(self, path: str, start: int, end: int):
        reply = QMessageBox.question(
            self, "Discard Hunk",
            "Discard this hunk?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._undo_manager.record_discard_hunk(path, start, end)
            if self._git.discard_hunk(path, start, end):
                self._update_undo_state()
                self._refresh_all()

    def _on_commit(self):
        """Trigger commit from toolbar/menu."""
        self._commit_panel._on_commit()

    def _on_commit_action(self, message: str, author: str, signoff: bool, gpg_sign: bool):
        success, result = self._git.commit(message, author, signoff, gpg_sign)
        if success:
            self._undo_manager.record_commit(result, message)
            self._update_undo_state()
            self._commit_panel.clear()
            self._commit_panel.set_status("✅ Commit successful")
            self._refresh_all()
        else:
            self._commit_panel.set_status(f"❌ Commit failed: {result}")

    def _on_amend(self):
        # Record the current HEAD before amending
        old_sha = ''
        try:
            old_sha = self._git.repo.head.commit.hexsha
        except Exception:
            pass
        message = self._commit_panel._message_edit.toPlainText().strip()
        author = self._commit_panel._author_combo.currentText().strip()
        if self._git.amend_commit(message if message else None, author if author else None):
            new_sha = ''
            try:
                new_sha = self._git.repo.head.commit.hexsha
            except Exception:
                pass
            if old_sha and new_sha and old_sha != new_sha:
                self._undo_manager.record_amend_commit(old_sha, new_sha, message)
                self._update_undo_state()
            self._commit_panel.clear()
            self._commit_panel.set_status("✅ Amended successfully")
            self._refresh_all()
        else:
            self._commit_panel.set_status("❌ Amend failed")

    def _on_fetch(self):
        if not self._git.is_open:
            return
        success, error = self._git.fetch()
        if success:
            self._refresh_all()
        else:
            QMessageBox.warning(self, "Fetch Error", error)

    def _on_pull(self):
        if not self._git.is_open:
            return
        success, error = self._git.pull()
        if success:
            self._refresh_all()
        else:
            QMessageBox.warning(self, "Pull Error", error)

    def _on_push(self):
        if not self._git.is_open:
            return
        success, error = self._git.push()
        if success:
            self._refresh_all()
        else:
            QMessageBox.warning(self, "Push Error", error)

    def _on_open_prs(self):
        """Open the Pull Request management dialog."""
        if not self._git.is_open:
            QMessageBox.information(self, "Pull Requests", "Open a repository first")
            return
        dialog = PullRequestDialog(self._git, self)
        dialog.exec()

    def _on_new_branch(self):
        name, ok = QInputDialog.getText(self, "New Branch", "Branch name:")
        if ok and name:
            if self._git.create_branch(name):
                self._refresh_all()
            else:
                QMessageBox.warning(self, "Error", f"Failed to create branch '{name}'")

    def _on_merge(self):
        branches = [b.name for b in self._git.get_branches() if not b.is_remote and not b.is_head]
        if not branches:
            QMessageBox.information(self, "Merge", "No other branches to merge")
            return

        branch, ok = QInputDialog.getItem(self, "Merge Branch", "Select branch to merge:", branches, False)
        if ok and branch:
            self._on_merge_branch(branch)

    def _on_rebase(self):
        branches = [b.name for b in self._git.get_branches() if not b.is_remote and not b.is_head]
        if not branches:
            QMessageBox.information(self, "Rebase", "No other branches to rebase onto")
            return

        onto, ok = QInputDialog.getItem(self, "Rebase", "Rebase current branch onto:", branches, False)
        if ok and onto:
            success, error = self._git.rebase_branch(onto)
            if success:
                self._refresh_all()
            else:
                QMessageBox.warning(self, "Rebase Error", error)

    def _on_checkout_branch(self, name: str):
        if self._git.checkout_branch(name):
            self._refresh_all()
        else:
            QMessageBox.warning(self, "Error", f"Failed to checkout '{name}'")

    def _on_merge_branch(self, name: str):
        success, error = self._git.merge_branch(name)
        if success:
            self._refresh_all()
        else:
            # Check for conflicts
            if self._git.is_merging():
                reply = QMessageBox.question(
                    self, "Merge Conflicts",
                    "Merge has conflicts. Open conflict resolver?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self._on_show_conflicts()
            else:
                QMessageBox.warning(self, "Merge Error", error)

    def _on_delete_branch(self, name: str):
        reply = QMessageBox.question(
            self, "Delete Branch",
            f"Delete branch '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Get the commit SHA before deleting
            commit_sha = ''
            try:
                branches = self._git.get_branches()
                for b in branches:
                    if b.name == name:
                        commit_sha = b.commit_sha
                        break
            except Exception:
                pass
            if self._git.delete_branch(name):
                if commit_sha:
                    self._undo_manager.record_branch_delete(name, commit_sha)
                    self._update_undo_state()
                self._refresh_all()
            else:
                QMessageBox.warning(self, "Error", f"Failed to delete branch '{name}'")

    def _on_stash(self):
        message, ok = QInputDialog.getText(self, "Stash Changes", "Stash message:")
        if ok:
            if self._git.stash_save(message):
                self._undo_manager.record_stash_save(message)
                self._update_undo_state()
                self._refresh_all()
            else:
                QMessageBox.warning(self, "Error", "Failed to stash changes")

    def _on_special_history_row(self, kind: str):
        """Show the working-copy panel for history pseudo-row selections."""
        self._selected_commit_sha = None
        self._selected_commit_range = None
        if kind == "workdir":
            self._sidebar_tabs.setCurrentWidget(self._working_copy)
            statuses = self._git.get_file_status()
            selected = next((fs.path for fs in statuses if fs.unstaged_status), "")
            if selected:
                diff = self._git.get_diff(selected)
                self._diff_viewer.set_diff(diff, selected)
                self._bottom_tabs.setCurrentWidget(self._diff_viewer)
        elif kind == "index":
            self._sidebar_tabs.setCurrentWidget(self._working_copy)
            statuses = self._git.get_file_status()
            selected = next((fs.path for fs in statuses if fs.staged_status), "")
            if selected:
                diff = self._git.get_diff(selected, staged=True)
                self._diff_viewer.set_diff(diff, selected)
                self._bottom_tabs.setCurrentWidget(self._diff_viewer)

    def _on_commit_selected(self, sha: str):
        self._selected_commit_sha = sha
        self._selected_commit_range = None
        diff = self._git.get_diff_for_commit(sha)
        self._diff_viewer.set_diff(diff, f"Commit {sha}")
        stats = self._git.get_commit_stats(sha)
        self._diff_viewer.set_stats(stats)
        self._populate_diff_files(stats)
        self._bottom_tabs.setCurrentIndex(1)

    def _on_commit_range_selected(self, newest_sha: str, oldest_sha: str):
        self._selected_commit_sha = None
        self._selected_commit_range = (newest_sha, oldest_sha)
        diff = self._git.get_diff_for_commit_range(newest_sha, oldest_sha)
        self._diff_viewer.set_diff(diff, f"Commits {oldest_sha[:7]}..{newest_sha[:7]}")
        stats = self._git.get_commit_range_stats(newest_sha, oldest_sha)
        self._diff_viewer.set_stats(stats)
        self._populate_diff_files(stats)
        self._bottom_tabs.setCurrentIndex(1)
        # Show statistics in the status bar
        files = stats.get('total_files', 0)
        added = stats.get('total_added', 0)
        removed = stats.get('total_removed', 0)
        bytes_total = stats.get('total_bytes', 0)
        self._status_bar.showMessage(
            f"📊 {files} file{'s' if files != 1 else ''} changed, "
            f"+{added} added, -{removed} removed, "
            f"{self._format_bytes(bytes_total)}",
            8000
        )

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

    def _on_cherry_pick(self, sha: str):
        old_head = ''
        try:
            old_head = self._git.repo.head.commit.hexsha
        except Exception:
            pass
        success, error = self._git.cherry_pick(sha)
        if success:
            new_sha = ''
            try:
                new_sha = self._git.repo.head.commit.hexsha
            except Exception:
                pass
            if new_sha and new_sha != old_head:
                self._undo_manager.record_cherry_pick(sha, new_sha)
                self._update_undo_state()
            self._refresh_all()
        else:
            QMessageBox.warning(self, "Cherry-Pick Error", error)

    def _on_revert(self, sha: str):
        reply = QMessageBox.question(
            self, "Revert Commit",
            f"Revert commit {sha}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, error = self._git.revert_commit(sha)
            if success:
                new_sha = ''
                try:
                    new_sha = self._git.repo.head.commit.hexsha
                except Exception:
                    pass
                if new_sha:
                    self._undo_manager.record_revert(sha, new_sha)
                    self._update_undo_state()
                self._refresh_all()
            else:
                QMessageBox.warning(self, "Revert Error", error)

    def _on_reset(self, sha: str, mode: str):
        mode_names = {'--soft': 'Soft (keep changes staged)',
                      '--mixed': 'Mixed (keep changes unstaged)',
                      '--hard': 'Hard (discard all changes)'}
        mode_name = mode_names.get(mode, mode)

        reply = QMessageBox.question(
            self, "Reset",
            f"Reset to {sha} ({mode_name})?\n\n"
            "This action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            old_head = ''
            try:
                old_head = self._git.repo.head.commit.hexsha
            except Exception:
                pass
            if self._git.reset(sha, mode):
                if mode == '--hard' and old_head:
                    self._undo_manager.record_reset_hard(sha, old_head)
                    self._update_undo_state()
                self._refresh_all()
            else:
                QMessageBox.warning(self, "Error", "Reset failed")

    def _on_create_tag(self, sha: str, name: str = ''):
        if not name:
            name, ok = QInputDialog.getText(self, "Create Tag", "Tag name:")
            if not (ok and name):
                return
        message, ok2 = QInputDialog.getText(self, "Create Tag", "Tag message (optional):")
        if ok2:
            if self._git.create_tag(name, message, annotated=bool(message), ref=sha):
                self._refresh_all()
            else:
                QMessageBox.warning(self, "Error", f"Failed to create tag '{name}'")

    def _on_create_branch_from_sha(self, sha: str, name: str = ''):
        if not name:
            name, ok = QInputDialog.getText(self, "Create Branch", "Branch name:")
            if not (ok and name):
                return
        if self._git.create_branch(name, sha):
            self._refresh_all()
        else:
            QMessageBox.warning(self, "Error", f"Failed to create branch '{name}'")

    def _on_interactive_rebase(self):
        dialog = RebaseDialog(self._git, self)
        if dialog.exec():
            self._refresh_all()

    def _on_show_conflicts(self):
        dialog = ConflictDialog(self._git, self)
        dialog.exec()
        self._refresh_all()

    def _on_show_reflog(self):
        entries = self._git.get_reflog()
        if not entries:
            QMessageBox.information(self, "Reflog", "No reflog entries found")
            return

        text = "Reflog:\n\n"
        for entry in entries:
            text += f"{entry['index']}: {entry['old_sha']}..{entry['new_sha']} "
            text += f"{entry['committer']} - {entry['message']}\n"

        dialog = DiffDialog(text, "Reflog", self)
        dialog.exec()

    def _on_undo(self):
        """Undo the last recorded action."""
        if not self._undo_manager.can_undo:
            return

        success, message = self._undo_manager.undo()
        if success:
            self._status_bar.showMessage(f"↩️ {message}", 5000)
            self._update_undo_state()
            self._refresh_all()
        else:
            QMessageBox.warning(self, "Undo Failed", message)

    def _on_undo_history(self):
        """Show undo history dialog."""
        from ..dialogs.diff_dialog import DiffDialog

        if not self._undo_manager.can_undo:
            QMessageBox.information(self, "Undo History", "No undo history available")
            return

        # Build a list of undo entries
        lines = ["Undo History:\n"]
        # We need access to the history list - use a simple approach
        lines.append(f"Next undo: {self._undo_manager.undo_description}\n")
        lines.append("\nPress Ctrl+Z to undo the last action.")

        dialog = DiffDialog('\n'.join(lines), "Undo History", self)
        dialog.exec()

    # ── Drag & Drop Slots ──────────────────────────────────────

    def _on_branch_dropped_for_merge(self, source_branch: str, target_branch: str):
        """Merge source_branch into target_branch (drag & drop)."""
        # Checkout target branch first
        if not self._git.checkout_branch(target_branch):
            QMessageBox.warning(self, "Merge Error", f"Failed to checkout '{target_branch}'")
            return

        success, error = self._git.merge_branch(source_branch)
        if success:
            self._undo_manager.record_merge(source_branch, target_branch)
            self._update_undo_state()
            self._status_bar.showMessage(f"✅ Merged '{source_branch}' into '{target_branch}'", 5000)
            self._refresh_all()
        else:
            if self._git.is_merging():
                reply = QMessageBox.question(
                    self, "Merge Conflicts",
                    f"Merge of '{source_branch}' into '{target_branch}' has conflicts. Open conflict resolver?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self._on_show_conflicts()
            else:
                QMessageBox.warning(self, "Merge Error", error)

    def _on_branch_dropped_for_rebase(self, source_branch: str, target_branch: str):
        """Rebase source_branch onto target_branch (drag & drop with Alt)."""
        # Checkout source branch first
        if not self._git.checkout_branch(source_branch):
            QMessageBox.warning(self, "Rebase Error", f"Failed to checkout '{source_branch}'")
            return

        success, error = self._git.rebase_branch(target_branch)
        if success:
            self._undo_manager.record_rebase(source_branch, target_branch)
            self._update_undo_state()
            self._status_bar.showMessage(f"✅ Rebased '{source_branch}' onto '{target_branch}'", 5000)
            self._refresh_all()
        else:
            QMessageBox.warning(self, "Rebase Error", error)

    def _on_commit_dropped_for_branch(self, commit_sha: str, branch_name: str):
        """Create a new branch from a dropped commit or branch."""
        if not branch_name:
            name, ok = QInputDialog.getText(self, "Create Branch", "New branch name:")
            if not (ok and name):
                return
            branch_name = name

        base = commit_sha if commit_sha else branch_name
        if self._git.create_branch(branch_name, base):
            self._undo_manager.record_branch_create(branch_name, base)
            self._update_undo_state()
            self._status_bar.showMessage(f"✅ Created branch '{branch_name}' from {base[:7] if base else 'HEAD'}", 5000)
            self._refresh_all()
        else:
            QMessageBox.warning(self, "Error", f"Failed to create branch '{branch_name}'")

    def _on_branch_dropped_on_remote(self, branch_name: str, remote_name: str):
        """Push a branch to a remote (drag & drop)."""
        success, error = self._git.push(remote_name, branch_name)
        if success:
            self._undo_manager.record_push(branch_name, remote_name)
            self._update_undo_state()
            self._status_bar.showMessage(f"✅ Pushed '{branch_name}' to '{remote_name}'", 5000)
            self._refresh_all()
        else:
            QMessageBox.warning(self, "Push Error", error)

    def _on_branch_dropped_on_remote_pull(self, branch_name: str, remote_name: str):
        """Pull a branch from a remote (drag & drop with Alt)."""
        success, error = self._git.pull(remote_name, branch_name)
        if success:
            self._undo_manager.record_pull(branch_name, remote_name)
            self._update_undo_state()
            self._status_bar.showMessage(f"✅ Pulled '{branch_name}' from '{remote_name}'", 5000)
            self._refresh_all()
        else:
            QMessageBox.warning(self, "Pull Error", error)

    def _toggle_dark_mode(self):
        self._dark_mode = not self._dark_mode
        self.setStyleSheet(get_theme(self._dark_mode))
        self._diff_viewer.set_dark_mode(self._dark_mode)
        self._refresh_all()

    def _on_about(self):
        QMessageBox.about(
            self, "About iGit",
            "<h2>iGit 1.0</h2>"
            "<p>An easy-to-use Git GUI built with PySide6.</p>"
            "<p>Features include:</p>"
            "<ul>"
            "<li>Working copy management (stage/unstage/discard)</li>"
            "<li>Integrated diff viewer with hunk staging</li>"
            "<li>Commit history graph with branch visualization</li>"
            "<li>Branch management (create/delete/merge/rebase)</li>"
            "<li>Stash management</li>"
            "<li>Remote operations (fetch/pull/push)</li>"
            "<li>Conflict resolution wizard</li>"
            "<li>Interactive rebase</li>"
            "<li>Submodule support</li>"
            "<li>File history and blame</li>"
            "<li>Reflog recovery</li>"
            "<li>Patch creation and application</li>"
            "<li>Tag management</li>"
            "<li>GPG signing</li>"
            "<li>Dark mode</li>"
            "</ul>"
        )
