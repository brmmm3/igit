"""Theme definitions for iGit - Light and Dark modes."""

LIGHT_THEME = """
QMainWindow, QDialog, QWidget {
    background-color: #ffffff;
    color: #24292e;
}

QMenuBar {
    background-color: #f6f8fa;
    border-bottom: 1px solid #d0d7de;
    padding: 2px;
}

QMenuBar::item:selected {
    background-color: #d0d7de;
    border-radius: 4px;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #0969da;
    color: #ffffff;
}

QToolBar {
    background-color: #f6f8fa;
    border-bottom: 1px solid #d0d7de;
    spacing: 4px;
    padding: 4px;
}

QToolButton {
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 8px;
    margin: 1px;
}

QToolButton:hover {
    background-color: #e8eaed;
    border-color: #d0d7de;
}

QToolButton:pressed {
    background-color: #d0d7de;
}

QTreeView, QListView, QTableWidget {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    alternate-background-color: #f6f8fa;
    selection-background-color: #ddf4ff;
    selection-color: #0969da;
    outline: none;
}

QTreeView::item, QListView::item, QTableWidget::item {
    padding: 4px 8px;
    min-height: 24px;
}

QTreeView::item:hover, QListView::item:hover {
    background-color: #f0f6fc;
}

QHeaderView::section {
    background-color: #f6f8fa;
    border: none;
    border-bottom: 1px solid #d0d7de;
    padding: 6px 8px;
    font-weight: bold;
}

QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 8px;
    font-family: "SF Mono", "Consolas", "Liberation Mono", monospace;
    font-size: 12px;
}

QLineEdit {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 6px 8px;
}

QLineEdit:focus {
    border-color: #0969da;
}

QPushButton {
    background-color: #f6f8fa;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #e8eaed;
}

QPushButton:pressed {
    background-color: #d0d7de;
}

QPushButton:disabled {
    opacity: 0.5;
}

QPushButton#primaryButton {
    background-color: #0969da;
    color: #ffffff;
    border: 1px solid #0969da;
}

QPushButton#primaryButton:hover {
    background-color: #0860ca;
}

QPushButton#dangerButton {
    background-color: #cf222e;
    color: #ffffff;
    border: 1px solid #cf222e;
}

QPushButton#dangerButton:hover {
    background-color: #b71c26;
}

QSplitter::handle {
    background-color: #d0d7de;
    width: 1px;
}

QStatusBar {
    background-color: #f6f8fa;
    border-top: 1px solid #d0d7de;
}

QTabWidget::pane {
    border: 1px solid #d0d7de;
    border-radius: 6px;
    background-color: #ffffff;
}

QTabBar::tab {
    background-color: #f6f8fa;
    border: 1px solid #d0d7de;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    border-bottom-color: #ffffff;
}

QScrollBar:vertical {
    background-color: #f6f8fa;
    width: 12px;
    border: none;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #c1c7cd;
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #a0a8b0;
}

QScrollBar:horizontal {
    background-color: #f6f8fa;
    height: 12px;
    border: none;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background-color: #c1c7cd;
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #a0a8b0;
}

QScrollBar::add-line, QScrollBar::sub-line {
    height: 0;
    width: 0;
}

QGroupBox {
    border: 1px solid #d0d7de;
    border-radius: 6px;
    margin-top: 12px;
    padding: 16px 8px 8px 8px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #57606a;
}

QLabel#sectionTitle {
    font-size: 14px;
    font-weight: bold;
    color: #24292e;
    padding: 4px 0;
}

QLabel#statusLabel {
    color: #57606a;
    font-size: 11px;
}

QComboBox {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 6px 8px;
}

QComboBox:hover {
    border-color: #0969da;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #d0d7de;
    border-radius: 3px;
}

QCheckBox::indicator:checked {
    background-color: #0969da;
    border-color: #0969da;
}
"""

DARK_THEME = """
QMainWindow, QDialog, QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
}

QMenuBar {
    background-color: #252526;
    border-bottom: 1px solid #3c3c3c;
    padding: 2px;
}

QMenuBar::item:selected {
    background-color: #37373d;
    border-radius: 4px;
}

QMenu {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #094771;
    color: #ffffff;
}

QToolBar {
    background-color: #252526;
    border-bottom: 1px solid #3c3c3c;
    spacing: 4px;
    padding: 4px;
}

QToolButton {
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 8px;
    margin: 1px;
    color: #d4d4d4;
}

QToolButton:hover {
    background-color: #37373d;
    border-color: #3c3c3c;
}

QToolButton:pressed {
    background-color: #2d2d2d;
}

QTreeView, QListView, QTableWidget {
    background-color: #1e1e1e;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    alternate-background-color: #252526;
    selection-background-color: #264f78;
    selection-color: #ffffff;
    outline: none;
    color: #d4d4d4;
}

QTreeView::item, QListView::item, QTableWidget::item {
    padding: 4px 8px;
    min-height: 24px;
}

QTreeView::item:hover, QListView::item:hover {
    background-color: #2a2d2e;
}

QHeaderView::section {
    background-color: #252526;
    border: none;
    border-bottom: 1px solid #3c3c3c;
    padding: 6px 8px;
    font-weight: bold;
    color: #d4d4d4;
}

QTextEdit, QPlainTextEdit {
    background-color: #1e1e1e;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    padding: 8px;
    font-family: "SF Mono", "Consolas", "Liberation Mono", monospace;
    font-size: 12px;
    color: #d4d4d4;
}

QLineEdit {
    background-color: #3c3c3c;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    padding: 6px 8px;
    color: #d4d4d4;
}

QLineEdit:focus {
    border-color: #007acc;
}

QPushButton {
    background-color: #3c3c3c;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 500;
    color: #d4d4d4;
}

QPushButton:hover {
    background-color: #4a4a4a;
}

QPushButton:pressed {
    background-color: #2d2d2d;
}

QPushButton:disabled {
    opacity: 0.5;
}

QPushButton#primaryButton {
    background-color: #007acc;
    color: #ffffff;
    border: 1px solid #007acc;
}

QPushButton#primaryButton:hover {
    background-color: #006bb3;
}

QPushButton#dangerButton {
    background-color: #c73e3e;
    color: #ffffff;
    border: 1px solid #c73e3e;
}

QPushButton#dangerButton:hover {
    background-color: #b03333;
}

QSplitter::handle {
    background-color: #3c3c3c;
    width: 1px;
}

QStatusBar {
    background-color: #252526;
    border-top: 1px solid #3c3c3c;
    color: #d4d4d4;
}

QTabWidget::pane {
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    background-color: #1e1e1e;
}

QTabBar::tab {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 16px;
    margin-right: 2px;
    color: #d4d4d4;
}

QTabBar::tab:selected {
    background-color: #1e1e1e;
    border-bottom-color: #1e1e1e;
}

QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 12px;
    border: none;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #424242;
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #555555;
}

QScrollBar:horizontal {
    background-color: #1e1e1e;
    height: 12px;
    border: none;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background-color: #424242;
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #555555;
}

QScrollBar::add-line, QScrollBar::sub-line {
    height: 0;
    width: 0;
}

QGroupBox {
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    margin-top: 12px;
    padding: 16px 8px 8px 8px;
    font-weight: bold;
    color: #d4d4d4;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #9d9d9d;
}

QLabel#sectionTitle {
    font-size: 14px;
    font-weight: bold;
    color: #d4d4d4;
    padding: 4px 0;
}

QLabel#statusLabel {
    color: #9d9d9d;
    font-size: 11px;
}

QComboBox {
    background-color: #3c3c3c;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    padding: 6px 8px;
    color: #d4d4d4;
}

QComboBox:hover {
    border-color: #007acc;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QCheckBox {
    spacing: 8px;
    color: #d4d4d4;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3c3c3c;
    border-radius: 3px;
}

QCheckBox::indicator:checked {
    background-color: #007acc;
    border-color: #007acc;
}
"""


def get_theme(dark_mode: bool = False) -> str:
    """Get the stylesheet for the selected theme."""
    return DARK_THEME if dark_mode else LIGHT_THEME
