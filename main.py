#!/usr/bin/env python3
"""iGit - An easy-to-use Git GUI built with PySide6.

Usage:
    python main.py              # Launch iGit
    python main.py /path/to/repo  # Open a repository
"""

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from igit.ui.main_window import MainWindow
from igit import __app_name__, __version__


def main():
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("iGit")

    # Set application-wide font
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)

    # Create and show main window
    window = MainWindow()

    # Open repository from command line argument if provided
    if len(sys.argv) > 1:
        repo_path = sys.argv[1]
        if os.path.isdir(repo_path):
            from igit.core.git_operations import GitOperations
            git = GitOperations()
            if git.open(repo_path):
                window._git = git
                # Update all panels with the new git instance
                window._working_copy._git = git
                window._commit_panel._git = git
                window._branch_panel._git = git
                window._stash_panel._git = git
                window._remote_panel._git = git
                window._statistics_panel._git = git
                window._branch_graph._git = git
                window._connect_signals()
                window._refresh_all()

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
