"""Theme definitions for iGit - Light and Dark modes."""

LIGHT_THEME = """
QMainWindow, QDialog, QWidget {
    background-color: #f0f0f0;
    color: #000000;
}

QMenuBar {
    background-color: #ffffff;
    border-bottom: 1px solid #dcdcdc;
    padding: 0;
}

QMenuBar::item {
    padding: 4px 8px;
    background: transparent;
}

QMenuBar::item:selected {
    background-color: #cce8ff;
}

QMenu {
    background-color: #f2f2f2;
    border: 1px solid #cccccc;
    padding: 2px;
}

QMenu::item {
    padding: 4px 24px;
}

QMenu::item:selected {
    background-color: #91c9f7;
    color: #000000;
}

QMenu::separator {
    height: 1px;
    background: #d0d0d0;
    margin: 3px 4px;
}

QToolBar {
    background-color: #f0f0f0;
    border: none;
    border-bottom: 1px solid #dcdcdc;
    spacing: 2px;
    padding: 2px;
}

QToolBar::separator {
    background-color: #c8c8c8;
    width: 1px;
    margin: 3px 4px;
}

QToolButton {
    border: 1px solid transparent;
    border-radius: 0;
    padding: 2px 6px;
    margin: 0;
    background: transparent;
}

QToolButton:hover {
    background-color: #e5f3ff;
    border-color: #99d1ff;
}

QToolButton:pressed, QToolButton:checked {
    background-color: #cce8ff;
    border-color: #66b5ff;
}

QToolButton::menu-indicator {
    image: none;
    width: 0;
}

QTreeView, QListView, QTableWidget {
    background-color: #ffffff;
    border: 1px solid #c8c8c8;
    border-radius: 0;
    alternate-background-color: #ffffff;
    selection-background-color: #0078d7;
    selection-color: #ffffff;
    outline: none;
}

QTreeView::item, QListView::item, QTableWidget::item {
    padding: 1px 2px;
    min-height: 18px;
}

QTreeView::item:hover:!selected, QListView::item:hover:!selected {
    background-color: #e5f3ff;
}

QTreeView::item:selected, QListView::item:selected {
    background-color: #0078d7;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #f0f0f0;
    border: none;
    border-right: 1px solid #d8d8d8;
    border-bottom: 1px solid #c8c8c8;
    padding: 3px 6px;
    font-weight: normal;
}

QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    border: 1px solid #c8c8c8;
    border-radius: 0;
    padding: 2px;
    font-family: "DejaVu Sans Mono", "Consolas", "Liberation Mono", monospace;
    font-size: 12px;
    selection-background-color: #0078d7;
    selection-color: #ffffff;
}

QLineEdit {
    background-color: #ffffff;
    border: 1px solid #abadb3;
    border-radius: 0;
    padding: 2px 4px;
    selection-background-color: #0078d7;
    selection-color: #ffffff;
}

QLineEdit:focus {
    border-color: #0078d7;
}

QPushButton {
    background-color: #e1e1e1;
    border: 1px solid #adadad;
    border-radius: 0;
    padding: 3px 12px;
}

QPushButton:hover {
    background-color: #e5f1fb;
    border-color: #0078d7;
}

QPushButton:pressed {
    background-color: #cce4f7;
    border-color: #005499;
}

QPushButton:disabled {
    color: #a0a0a0;
    background-color: #f0f0f0;
    border-color: #d0d0d0;
}

QPushButton#primaryButton {
    background-color: #0078d7;
    color: #ffffff;
    border: 1px solid #005a9e;
}

QPushButton#primaryButton:hover {
    background-color: #1a86dc;
}

QPushButton#dangerButton {
    background-color: #d13438;
    color: #ffffff;
    border: 1px solid #a4262c;
}

QPushButton#dangerButton:hover {
    background-color: #e04347;
}

QSplitter::handle {
    background-color: #dcdcdc;
}

QSplitter::handle:horizontal {
    width: 3px;
}

QSplitter::handle:vertical {
    height: 3px;
}

QStatusBar {
    background-color: #f0f0f0;
    border-top: 1px solid #dcdcdc;
}

QStatusBar::item {
    border: none;
}

QTabWidget::pane {
    border: 1px solid #c8c8c8;
    border-radius: 0;
    background-color: #ffffff;
    top: -1px;
}

QTabBar::tab {
    background-color: #f0f0f0;
    border: 1px solid #c8c8c8;
    border-bottom: none;
    border-radius: 0;
    padding: 3px 10px;
    margin-right: -1px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    border-top: 2px solid #0078d7;
}

QTabBar::tab:hover:!selected {
    background-color: #e5f3ff;
}

QScrollBar:vertical {
    background-color: #f0f0f0;
    width: 14px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #cdcdcd;
    min-height: 30px;
    margin: 0 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #a6a6a6;
}

QScrollBar:horizontal {
    background-color: #f0f0f0;
    height: 14px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #cdcdcd;
    min-width: 30px;
    margin: 2px 0;
}

QScrollBar::handle:horizontal:hover {
    background-color: #a6a6a6;
}

QScrollBar::add-line, QScrollBar::sub-line {
    height: 0;
    width: 0;
}

QScrollBar::add-page, QScrollBar::sub-page {
    background: none;
}

QGroupBox {
    border: 1px solid #c8c8c8;
    border-radius: 0;
    margin-top: 10px;
    padding: 10px 6px 6px 6px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #000080;
}

QLabel#sectionTitle {
    font-weight: bold;
    padding: 2px 0;
}

QLabel#statusLabel {
    color: #404040;
}

QComboBox {
    background-color: #ffffff;
    border: 1px solid #abadb3;
    border-radius: 0;
    padding: 2px 6px;
}

QComboBox:hover {
    border-color: #0078d7;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #abadb3;
    selection-background-color: #0078d7;
    selection-color: #ffffff;
}

QCheckBox {
    spacing: 6px;
}

QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #8e8f8f;
    background: #ffffff;
    border-radius: 0;
}

QCheckBox::indicator:checked {
    background-color: #0078d7;
    border-color: #005a9e;
}

QToolTip {
    background-color: #ffffe1;
    color: #000000;
    border: 1px solid #767676;
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
    border-radius: 0;
}

QMenu {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    border-radius: 0;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 0;
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
    border-radius: 0;
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
    border-radius: 0;
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
    border-radius: 0;
    padding: 8px;
    font-family: "SF Mono", "Consolas", "Liberation Mono", monospace;
    font-size: 12px;
    color: #d4d4d4;
}

QLineEdit {
    background-color: #3c3c3c;
    border: 1px solid #3c3c3c;
    border-radius: 0;
    padding: 6px 8px;
    color: #d4d4d4;
}

QLineEdit:focus {
    border-color: #007acc;
}

QPushButton {
    background-color: #3c3c3c;
    border: 1px solid #3c3c3c;
    border-radius: 0;
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
    border-radius: 0;
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
    border-radius: 0;
}

QScrollBar::handle:vertical {
    background-color: #424242;
    border-radius: 0;
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
    border-radius: 0;
}

QScrollBar::handle:horizontal {
    background-color: #424242;
    border-radius: 0;
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
    border-radius: 0;
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
    border-radius: 0;
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
    border-radius: 0;
}

QCheckBox::indicator:checked {
    background-color: #007acc;
    border-color: #007acc;
}
"""


def get_theme(dark_mode: bool = False) -> str:
    """Get the stylesheet for the selected theme."""
    return DARK_THEME if dark_mode else LIGHT_THEME
