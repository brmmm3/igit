"""Integrated diff viewer with syntax highlighting and hunk staging."""

import re
from typing import Optional, List, Tuple, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QSplitter, QComboBox, QToolBar, QToolButton,
    QScrollBar, QFrame, QMenu, QCheckBox
)
from PySide6.QtCore import Qt, Signal, Slot, QRect, QSize
from PySide6.QtGui import (
    QFont, QColor, QTextCursor, QTextCharFormat, QSyntaxHighlighter,
    QPainter, QTextFormat, QAction, QKeySequence, QBrush, QPen
)


class DiffHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for unified diff output."""

    def __init__(self, parent=None, dark_mode: bool = False):
        super().__init__(parent)
        self.dark_mode = dark_mode
        self._rules = self._build_rules()

    def _build_rules(self):
        rules = []
        bg = self.dark_mode

        # Header lines (---, +++, @@)
        header_fmt = QTextCharFormat()
        header_fmt.setForeground(QColor('#569cd6' if bg else '#0550ae'))
        header_fmt.setFontWeight(700)
        rules.append((r'^--- .*', header_fmt))
        rules.append((r'^\+\+\+ .*', header_fmt))
        rules.append((r'^@@ -.*', header_fmt))

        # Added lines
        add_fmt = QTextCharFormat()
        add_fmt.setForeground(QColor('#4ec9b0' if bg else '#116329'))
        rules.append((r'^\+.*', add_fmt))

        # Removed lines
        rem_fmt = QTextCharFormat()
        rem_fmt.setForeground(QColor('#f14c4c' if bg else '#cf222e'))
        rules.append((r'^-.*', rem_fmt))

        # Commit info
        info_fmt = QTextCharFormat()
        info_fmt.setForeground(QColor('#6a9955' if bg else '#1a7f37'))
        info_fmt.setFontItalic(True)
        rules.append((r'^commit .*', info_fmt))
        rules.append((r'^Author: .*', info_fmt))
        rules.append((r'^Date: .*', info_fmt))

        return rules

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class LineNumberArea(QWidget):
    """Line number area for the diff viewer."""

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.line_number_width(), 0)

    def paintEvent(self, event):
        self._editor.line_number_area_paint_event(event)


class DiffEditor(QTextEdit):
    """Custom QTextEdit for diff display with line numbers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("SF Mono", 10))
        self.setTabStopDistance(32)
        self._line_number_area = LineNumberArea(self)
        self.document().blockCountChanged.connect(self._update_line_number_width)
        self.verticalScrollBar().valueChanged.connect(
            self._line_number_area.update
        )
        self._update_line_number_width()

    def line_number_width(self):
        digits = len(str(max(1, self.document().blockCount())))
        return 10 + 8 * digits

    def _update_line_number_width(self):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_width(), cr.height())
        )

    def line_number_area_paint_event(self, event):
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor('#f6f8fa'))

        block = self.document().begin()
        block_number = 1
        top = self.document().documentLayout().blockBoundingRect(block).top()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor('#8b949e'))

        while block.isValid():
            if block.isVisible():
                pos = self.document().documentLayout().blockBoundingRect(block).top()
                if pos >= event.rect().top() - 100 and pos <= event.rect().bottom() + 100:
                    painter.setPen(QColor('#8b949e'))
                    painter.drawText(
                        0, round(pos), self.line_number_width() - 5,
                        self.fontMetrics().height(),
                        Qt.AlignRight, str(block_number)
                    )
                block_number += 1
            block = block.next()

        painter.end()

    def wheelEvent(self, event):
        super().wheelEvent(event)
        self._line_number_area.update()


class DiffViewer(QWidget):
    """Integrated diff viewer with syntax highlighting."""

    stage_hunk_requested = Signal(str, int, int)  # path, start_line, end_line
    discard_hunk_requested = Signal(str, int, int)

    def __init__(self, parent=None, dark_mode: bool = False):
        super().__init__(parent)
        self._dark_mode = dark_mode
        self._current_path: str = ''
        self._current_diff: str = ''
        self._hunk_ranges: List[Tuple[int, int, int, int]] = []  # (start_line, end_line, old_start, old_end)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)

        self._file_label = QLabel("No file selected")
        self._file_label.setObjectName("sectionTitle")
        toolbar.addWidget(self._file_label)
        toolbar.addStretch()

        self._stage_hunk_btn = QPushButton("Stage Hunk")
        self._stage_hunk_btn.setEnabled(False)
        self._stage_hunk_btn.clicked.connect(self._on_stage_hunk)
        toolbar.addWidget(self._stage_hunk_btn)

        self._discard_hunk_btn = QPushButton("Discard Hunk")
        self._discard_hunk_btn.setObjectName("dangerButton")
        self._discard_hunk_btn.setEnabled(False)
        self._discard_hunk_btn.clicked.connect(self._on_discard_hunk)
        toolbar.addWidget(self._discard_hunk_btn)

        self._wrap_check = QCheckBox("Word Wrap")
        self._wrap_check.toggled.connect(self._on_toggle_wrap)
        toolbar.addWidget(self._wrap_check)

        layout.addLayout(toolbar)

        # Diff editor
        self._editor = DiffEditor()
        self._highlighter = DiffHighlighter(self._editor.document(), self._dark_mode)
        layout.addWidget(self._editor)

    def set_diff(self, diff_text: str, file_path: str = ''):
        """Set the diff content to display."""
        self._current_diff = diff_text
        self._current_path = file_path
        self._file_label.setText(file_path or "Diff View")
        self._parse_hunks(diff_text)
        self._editor.setPlainText(diff_text)
        self._editor.moveCursor(QTextCursor.Start)
        self._stage_hunk_btn.setEnabled(bool(diff_text))
        self._discard_hunk_btn.setEnabled(bool(diff_text))

    def _parse_hunks(self, diff_text: str):
        """Parse hunk headers from diff text."""
        self._hunk_ranges = []
        lines = diff_text.split('\n')
        for i, line in enumerate(lines):
            m = re.match(r'^@@ -(\d+),?\d* \+(\d+),?\d* @@', line)
            if m:
                old_start = int(m.group(1))
                new_start = int(m.group(2))
                # Find the end of this hunk
                end = i + 1
                while end < len(lines):
                    if re.match(r'^@@ -', lines[end]):
                        break
                    end += 1
                self._hunk_ranges.append((i, end - 1, old_start, new_start))

    def _on_stage_hunk(self):
        cursor = self._editor.textCursor()
        line = cursor.blockNumber()
        for start, end, old_start, old_end in self._hunk_ranges:
            if start <= line <= end:
                self.stage_hunk_requested.emit(self._current_path, old_start, old_end)
                break

    def _on_discard_hunk(self):
        cursor = self._editor.textCursor()
        line = cursor.blockNumber()
        for start, end, old_start, old_end in self._hunk_ranges:
            if start <= line <= end:
                self.discard_hunk_requested.emit(self._current_path, old_start, old_end)
                break

    def _on_toggle_wrap(self, checked: bool):
        if checked:
            self._editor.setLineWrapMode(QTextEdit.WidgetWidth)
        else:
            self._editor.setLineWrapMode(QTextEdit.NoWrap)

    def clear(self):
        """Clear the diff view."""
        self._editor.clear()
        self._file_label.setText("No file selected")
        self._current_path = ''
        self._current_diff = ''
        self._hunk_ranges = []
        self._stage_hunk_btn.setEnabled(False)
        self._discard_hunk_btn.setEnabled(False)

    def set_dark_mode(self, dark: bool):
        """Update dark mode."""
        self._dark_mode = dark
        self._highlighter = DiffHighlighter(self._editor.document(), dark)
        self._highlighter.rehighlight()
