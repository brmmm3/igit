"""Integrated diff viewer with syntax highlighting and hunk staging."""

import re
from typing import Optional, List, Tuple, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPlainTextEdit, QPushButton,
    QLabel, QSplitter, QComboBox, QToolBar, QToolButton,
    QScrollBar, QFrame, QMenu, QCheckBox
)
from PySide6.QtCore import Qt, Signal, Slot, QRect, QSize
from PySide6.QtGui import (
    QFont, QColor, QTextCursor, QTextCharFormat, QSyntaxHighlighter,
    QPainter, QTextFormat, QAction, QKeySequence, QBrush, QPen,
    QFontDatabase
)


class DiffHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for unified diff output.

    Only touches text attributes (bold headers, italic commit info). The
    full-line add/remove/hunk backgrounds are painted by DiffEditor through
    extra selections so they span the entire viewport width.
    """

    def __init__(self, parent=None, dark_mode: bool = False):
        super().__init__(parent)
        self.dark_mode = dark_mode
        self._rules = self._build_rules()

    def _build_rules(self):
        rules = []
        dark = self.dark_mode

        header_fmt = QTextCharFormat()
        header_fmt.setForeground(QColor('#569cd6' if dark else '#000080'))
        header_fmt.setFontWeight(700)
        rules.append((r'^diff --git .*', header_fmt))
        rules.append((r'^--- .*', header_fmt))
        rules.append((r'^\+\+\+ .*', header_fmt))

        hunk_fmt = QTextCharFormat()
        hunk_fmt.setForeground(QColor('#9cdcfe' if dark else '#444444'))
        rules.append((r'^@@ -.*', hunk_fmt))

        info_fmt = QTextCharFormat()
        info_fmt.setForeground(QColor('#6a9955' if dark else '#1a7f37'))
        info_fmt.setFontItalic(True)
        rules.append((r'^commit .*', info_fmt))
        rules.append((r'^Author: .*', info_fmt))
        rules.append((r'^Date: .*', info_fmt))

        return rules

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


_HUNK_RE = re.compile(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@')


def compute_line_numbers(diff_text: str):
    """Return (old, new, kind) per line of a unified diff.

    kind is one of 'file', 'hunk', 'add', 'del', 'ctx', 'meta'.
    old/new are ints or None.
    """
    result = []
    old = new = 0
    in_hunk = False
    for line in diff_text.split('\n'):
        m = _HUNK_RE.match(line)
        if m:
            old, new = int(m.group(1)), int(m.group(2))
            in_hunk = True
            result.append((None, None, 'hunk'))
            continue
        if line.startswith('diff --git') or line.startswith('commit '):
            in_hunk = False
            result.append((None, None, 'file'))
            continue
        if not in_hunk:
            kind = 'file' if line.startswith(('--- ', '+++ ')) else 'meta'
            result.append((None, None, kind))
            continue
        if line.startswith('+'):
            result.append((None, new, 'add'))
            new += 1
        elif line.startswith('-'):
            result.append((old, None, 'del'))
            old += 1
        elif line.startswith('\\'):
            result.append((None, None, 'meta'))
        else:
            result.append((old, new, 'ctx'))
            old += 1
            new += 1
    return result


class LineNumberArea(QWidget):
    """Two-column (old/new) line number gutter for the diff editor."""

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.line_number_width(), 0)

    def paintEvent(self, event):
        self._editor.line_number_area_paint_event(event)


class DiffEditor(QPlainTextEdit):
    """Read-only diff view with old/new line numbers and coloured lines."""

    LIGHT = {
        'add': '#d4f5d4', 'del': '#f9d3d3', 'hunk': '#e3e3e3',
        'file': '#f0f0f0',
        'gutter': '#f0f0f0', 'gutter_add': '#b9e8b9', 'gutter_del': '#f2b8b8',
        'gutter_fg': '#808080', 'gutter_line': '#c8c8c8',
    }
    DARK = {
        'add': '#1f3d28', 'del': '#4a2326', 'hunk': '#2d2d30',
        'file': '#252526',
        'gutter': '#252526', 'gutter_add': '#2b5a38', 'gutter_del': '#6b2f33',
        'gutter_fg': '#858585', 'gutter_line': '#3c3c3c',
    }

    def __init__(self, parent=None, dark_mode: bool = False):
        super().__init__(parent)
        self._dark = dark_mode
        self._numbers = []
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        font.setPointSize(10)
        self.setFont(font)
        self.setTabStopDistance(32)
        self._line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_width)
        self.updateRequest.connect(self._update_line_number_area)
        self._update_line_number_width()

    def _colors(self):
        return self.DARK if self._dark else self.LIGHT

    def set_dark_mode(self, dark: bool):
        self._dark = dark
        self._apply_line_backgrounds()
        self._line_number_area.update()

    def set_diff_text(self, text: str):
        self._numbers = compute_line_numbers(text) if text else []
        self.setPlainText(text)
        self._update_line_number_width()
        self._apply_line_backgrounds()
        self._line_number_area.update()

    def clear_diff(self):
        self._numbers = []
        self.clear()
        self.setExtraSelections([])

    # ── backgrounds ──────────────────────────────────────────

    def _apply_line_backgrounds(self):
        colors = self._colors()
        selections = []
        doc = self.document()
        for i, (_, _, kind) in enumerate(self._numbers):
            key = {'add': 'add', 'del': 'del', 'hunk': 'hunk',
                   'file': 'file'}.get(kind)
            if key is None:
                continue
            block = doc.findBlockByNumber(i)
            if not block.isValid():
                break
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor(colors[key]))
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            cursor = QTextCursor(block)
            sel.cursor = cursor
            selections.append(sel)
        self.setExtraSelections(selections)

    # ── gutter ───────────────────────────────────────────────

    def _digits(self):
        mx = 1
        for old, new, _ in self._numbers:
            if old and old > mx:
                mx = old
            if new and new > mx:
                mx = new
        return max(3, len(str(mx)))

    def _column_width(self):
        return 12 + self.fontMetrics().horizontalAdvance('9') * self._digits()

    def line_number_width(self):
        return self._column_width() * 2 + 2

    def _update_line_number_width(self):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_width(), cr.height())
        )

    def line_number_area_paint_event(self, event):
        colors = self._colors()
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor(colors['gutter']))
        painter.setFont(self.font())

        col_w = self._column_width()
        total_w = self._line_number_area.width()

        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block)
                    .translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                if number < len(self._numbers):
                    old, new, kind = self._numbers[number]
                    h = self.fontMetrics().height()
                    if kind == 'add':
                        painter.fillRect(col_w, top, col_w, bottom - top,
                                         QColor(colors['gutter_add']))
                    elif kind == 'del':
                        painter.fillRect(0, top, col_w, bottom - top,
                                         QColor(colors['gutter_del']))
                    elif kind == 'hunk':
                        painter.fillRect(0, top, total_w, bottom - top,
                                         QColor(colors['hunk']))
                    painter.setPen(QColor(colors['gutter_fg']))
                    if old is not None:
                        painter.drawText(0, top, col_w - 6, h,
                                         Qt.AlignRight, str(old))
                    if new is not None:
                        painter.drawText(col_w, top, col_w - 6, h,
                                         Qt.AlignRight, str(new))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1

        painter.setPen(QColor(colors['gutter_line']))
        painter.drawLine(col_w, event.rect().top(), col_w, event.rect().bottom())
        painter.drawLine(total_w - 1, event.rect().top(),
                         total_w - 1, event.rect().bottom())
        painter.end()


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

        # Stats bar
        stats_bar = QHBoxLayout()
        stats_bar.setContentsMargins(8, 0, 8, 4)
        self._stats_label = QLabel("")
        self._stats_label.setObjectName("statsLabel")
        stats_bar.addWidget(self._stats_label)
        stats_bar.addStretch()
        layout.addLayout(stats_bar)

        # Diff editor
        self._editor = DiffEditor(dark_mode=self._dark_mode)
        self._highlighter = DiffHighlighter(self._editor.document(), self._dark_mode)
        layout.addWidget(self._editor)

    def set_diff(self, diff_text: str, file_path: str = ''):
        """Set the diff content to display."""
        self._current_diff = diff_text
        self._current_path = file_path
        self._file_label.setText(file_path or "Diff View")
        self._parse_hunks(diff_text)
        self._editor.set_diff_text(diff_text)
        self._editor.moveCursor(QTextCursor.Start)
        self._stage_hunk_btn.setEnabled(bool(diff_text))
        self._discard_hunk_btn.setEnabled(bool(diff_text))
        self._stats_label.setText("")

    def set_stats(self, stats: dict):
        """Display change statistics (added/removed lines, files, bytes)."""
        if not stats:
            self._stats_label.setText("")
            return
        files = stats.get('files', [])
        added = stats.get('total_added', 0)
        removed = stats.get('total_removed', 0)
        total_files = stats.get('total_files', len(files))
        total_bytes = stats.get('total_bytes', 0)

        parts = []
        parts.append(f"<b>{total_files}</b> file{'s' if total_files != 1 else ''} changed")
        parts.append(f"<span style='color:#1a7f37'>+{added}</span>")
        parts.append(f"<span style='color:#cf222e'>-{removed}</span>")
        parts.append(f"<b>{self._format_bytes(total_bytes)}</b>")
        self._stats_label.setText("  ".join(parts))

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
            self._editor.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        else:
            self._editor.setLineWrapMode(QPlainTextEdit.NoWrap)

    def clear(self):
        """Clear the diff view."""
        self._editor.clear_diff()
        self._file_label.setText("No file selected")
        self._current_path = ''
        self._current_diff = ''
        self._hunk_ranges = []
        self._stage_hunk_btn.setEnabled(False)
        self._discard_hunk_btn.setEnabled(False)
        self._stats_label.setText("")

    def set_dark_mode(self, dark: bool):
        """Update dark mode."""
        self._dark_mode = dark
        self._highlighter.setDocument(None)
        self._highlighter = DiffHighlighter(self._editor.document(), dark)
        self._highlighter.rehighlight()
        self._editor.set_dark_mode(dark)
