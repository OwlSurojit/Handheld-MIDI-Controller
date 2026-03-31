from __future__ import annotations

from typing import Iterable

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtCore import QRect, QSize
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QSizePolicy, QToolButton, QWidget
import qtawesome as qta


_BLACK_KEYS = {1, 3, 6, 8, 10}
_WHITE_PCS = {0, 2, 4, 5, 7, 9, 11}
_WHITE_INDEX = {0: 0, 2: 1, 4: 2, 5: 3, 7: 4, 9: 5, 11: 6}
_BLACK_OFFSETS = {1: 0.7, 3: 1.7, 6: 3.7, 8: 4.7, 10: 5.7}


class PianoScaleKeyboard(QWidget):
    selected_notes_changed = pyqtSignal(set)
    
    _MIN_KEY_WIDTH = 18
    _MAX_KEY_WIDTH = 40
    _MIN_KEY_HEIGHT = 72
    _MAX_KEY_HEIGHT = 96
    _BLACK_KEY_WIDTH_RATIO = 2/3

    def __init__(self, root_note: int = 60, min_note: int | None = None, max_note: int | None = None, parent=None):
        super().__init__(parent)
        self._root_note = int(root_note)
        if min_note is None:
            min_note = self._root_note
        if max_note is None:
            max_note = self._root_note + 11
        self._min_note = max(0, min(127, int(min_note)))
        self._max_note = max(0, min(127, int(max_note)))
        if self._min_note > self._max_note:
            self._min_note, self._max_note = self._max_note, self._min_note

        self._selected_notes: set[int] = set()
        self._read_only = False
        self._note_rects: dict[int, QRect] = {}
        self._black_notes: list[int] = []
        self._white_notes: list[int] = []
        
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(self._MIN_KEY_HEIGHT)
        self.setMaximumHeight(self._MAX_KEY_HEIGHT)
        self._rebuild_notes()

    def set_note_range(self, min_note: int, max_note: int) -> None:
        min_value = max(0, min(127, int(min_note)))
        max_value = max(0, min(127, int(max_note)))
        if min_value > max_value:
            min_value, max_value = max_value, min_value
        if min_value == self._min_note and max_value == self._max_note:
            return
        self._min_note = min_value
        self._max_note = max_value
        self._rebuild_notes()
        self.updateGeometry()
        self.update()

    def note_range(self) -> tuple[int, int]:
        return self._min_note, self._max_note

    def set_root_note(self, root_note: int) -> None:
        root_value = int(root_note)
        if root_value == self._root_note:
            return
        previous = self._root_note
        self._root_note = root_value
        self._update_note(previous)
        self._update_note(self._root_note)

    def set_selected_notes(self, notes: Iterable[int], emit_signal: bool = False) -> None:
        new_notes = {int(note) for note in notes if 0 <= int(note) <= 127}
        if new_notes == self._selected_notes:
            return
        removed = self._selected_notes - new_notes
        added = new_notes - self._selected_notes
        self._selected_notes = set(new_notes)
        for note in removed:
            self._update_note(note)
        for note in added:
            self._update_note(note)
        if emit_signal:
            self.selected_notes_changed.emit(set(self._selected_notes))

    def selected_notes(self) -> set[int]:
        return set(self._selected_notes)

    def set_read_only(self, enabled: bool) -> None:
        self._read_only = bool(enabled)

    def sizeHint(self) -> QSize:
        white_count = self._count_white_keys()
        return QSize(max(1, white_count * 28), self._MAX_KEY_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        white_count = self._count_white_keys()
        return QSize(max(1, white_count * self._MIN_KEY_WIDTH), self._MIN_KEY_HEIGHT)

    def resizeEvent(self, a0) -> None:
        super().resizeEvent(a0)
        self._recompute_geometry()

    def showEvent(self, a0) -> None:
        super().showEvent(a0)
        self._recompute_geometry()

    def mousePressEvent(self, a0) -> None:
        if self._read_only:
            return
        if a0 is None:
            return
        pos = a0.pos()
        for note in self._black_notes:
            rect = self._note_rects.get(note)
            if rect is not None and rect.contains(pos):
                self._toggle_note(note)
                return
        for note in self._white_notes:
            rect = self._note_rects.get(note)
            if rect is not None and rect.contains(pos):
                self._toggle_note(note)
                return

    def paintEvent(self, a0) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        white_fill = QColor("#f7f7f7")
        white_on = QColor("#ffe29a")
        black_fill = QColor("#1a1a1a")
        black_on = QColor("#f1a05e")
        border = QColor("#2b2b2b")
        root_border = QColor("#2a9d8f")

        for note in self._white_notes:
            rect = self._note_rects.get(note)
            if rect is None:
                continue
            is_on = note in self._selected_notes
            painter.fillRect(rect, white_on if is_on else white_fill)
            pen = QPen(root_border if note == self._root_note else border)
            pen.setWidth(2 if note == self._root_note else 1)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
            
            if note % 12 == 0:
                # Draw octave number
                octave = note // 12 - 1
                painter.setPen(QPen(border))
                painter.setFont(self.font())
                painter.drawText(rect.adjusted(0, 0, 0, -10), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, f"C{octave}")

        for note in self._black_notes:
            rect = self._note_rects.get(note)
            if rect is None:
                continue
            is_on = note in self._selected_notes
            painter.fillRect(rect, black_on if is_on else black_fill)
            pen = QPen(root_border if note == self._root_note else QColor("#0f0f0f"))
            pen.setWidth(2 if note == self._root_note else 1)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
        painter.end()

    def _toggle_note(self, note: int) -> None:
        if note in self._selected_notes:
            self._selected_notes.discard(note)
        else:
            self._selected_notes.add(note)
        self._update_note(note)
        self.selected_notes_changed.emit(set(self._selected_notes))

    def _update_note(self, note: int) -> None:
        rect = self._note_rects.get(note)
        if rect is not None:
            self.update(rect)

    def _rebuild_notes(self) -> None:
        notes = list(range(self._min_note, self._max_note + 1))
        self._white_notes = [note for note in notes if (note % 12) in _WHITE_PCS]
        self._black_notes = [note for note in notes if (note % 12) in _BLACK_KEYS]
        self.setMinimumWidth(max(1, len(self._white_notes) * self._MIN_KEY_WIDTH))
        self._recompute_geometry()

    def _recompute_geometry(self) -> None:
        if self._min_note > self._max_note:
            self._note_rects.clear()
            return

        rect = self.contentsRect()
        if rect.width() <= 0 or rect.height() <= 0:
            self._note_rects.clear()
            return

        white_count = max(1, self._count_white_keys())
        ideal_width = float(rect.width()) / white_count
        white_key_width = min(self._MAX_KEY_WIDTH, max(self._MIN_KEY_WIDTH, ideal_width))
        if (white_key_width * white_count) > rect.width():
            white_key_width = rect.width() / white_count
        black_key_width = white_key_width * self._BLACK_KEY_WIDTH_RATIO
        black_key_height = rect.height() * 0.6

        note_units = {note: self._note_unit(note) for note in range(self._min_note, self._max_note + 1)}
        min_unit = min(note_units.values()) if note_units else 0.0
        left_padding = rect.left() + max(0.0, (rect.width() - (white_key_width * white_count)) / 2)

        self._note_rects.clear()
        for note in self._white_notes:
            x = left_padding + (note_units[note] - min_unit) * white_key_width
            self._note_rects[note] = QRect(int(x), rect.top(), int(white_key_width), rect.height())

        for note in self._black_notes:
            x = left_padding + (note_units[note] - min_unit) * white_key_width
            self._note_rects[note] = QRect(int(x), rect.top(), int(black_key_width), int(black_key_height))

        self.update()

    def _note_unit(self, note: int) -> float:
        octave = note // 12
        pc = note % 12
        base = octave * 7
        if pc in _WHITE_INDEX:
            return base + _WHITE_INDEX[pc]
        return base + _BLACK_OFFSETS.get(pc, 0.0)

    def _count_white_keys(self) -> int:
        return sum(1 for note in range(self._min_note, self._max_note + 1) if (note % 12) in _WHITE_PCS)


class _HorizontalScrollArea(QScrollArea):
    def wheelEvent(self, a0) -> None:
        if a0 is None:
            return
        delta = a0.angleDelta()
        steps = delta.y() if delta.y() != 0 else delta.x()
        if steps != 0:
            bar = self.horizontalScrollBar()
            if bar is not None:
                bar.setValue(bar.value() - int(steps / 2))
            return
        super().wheelEvent(a0)


class PianoScaleWidget(QWidget):
    selected_notes_changed = pyqtSignal(set)

    def __init__(
        self,
        root_note: int = 60,
        min_note: int = 48,
        max_note: int = 83,
        parent=None,
    ):
        super().__init__(parent)
        self._keyboard = PianoScaleKeyboard(root_note=root_note, min_note=min_note, max_note=max_note, parent=self)
        self._keyboard.selected_notes_changed.connect(self.selected_notes_changed.emit)

        self._expand_left_btn = QToolButton(self)
        self._expand_left_btn.setIcon(qta.icon("mdi.arrow-expand-left"))
        self._expand_left_btn.setToolTip("Show one octave lower")
        self._expand_left_btn.clicked.connect(self.expand_left_octave)

        self._expand_right_btn = QToolButton(self)
        self._expand_right_btn.setIcon(qta.icon("mdi.arrow-expand-right"))
        self._expand_right_btn.setToolTip("Show one octave higher")
        self._expand_right_btn.clicked.connect(self.expand_right_octave)

        self._scroll_area = _HorizontalScrollArea(self)
        self._scroll_area.setWidget(self._keyboard)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scrollbar = self._scroll_area.horizontalScrollBar()
        self._scroll_area.setMinimumHeight(self._keyboard.sizeHint().height() + (scrollbar.sizeHint().height() if scrollbar is not None else 20))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._expand_left_btn)
        layout.addWidget(self._scroll_area, 1)
        layout.addWidget(self._expand_right_btn)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_note_range(self, min_note: int, max_note: int) -> None:
        self._keyboard.set_note_range(min_note, max_note)

    def note_range(self) -> tuple[int, int]:
        return self._keyboard.note_range()

    def set_root_note(self, root_note: int) -> None:
        self._keyboard.set_root_note(root_note)

    def set_selected_notes(self, notes: Iterable[int], emit_signal: bool = False) -> None:
        self._keyboard.set_selected_notes(notes, emit_signal=emit_signal)

    def selected_notes(self) -> set[int]:
        return self._keyboard.selected_notes()

    def set_read_only(self, enabled: bool) -> None:
        self._keyboard.set_read_only(enabled)
        self._expand_left_btn.setEnabled(not enabled)
        self._expand_right_btn.setEnabled(not enabled)

    def ensure_notes_visible(self, notes: Iterable[int]) -> None:
        visible = {int(note) for note in notes if 0 <= int(note) <= 127}
        if not visible:
            return
        min_note, max_note = self._keyboard.note_range()
        required_min = min(visible)
        required_max = max(visible)
        if required_min >= min_note and required_max <= max_note:
            return
        new_min = min(min_note, required_min)
        new_max = max(max_note, required_max)
        new_min = self._snap_down_to_c(new_min)
        new_max = self._snap_up_to_b(new_max)
        self._keyboard.set_note_range(new_min, new_max)

    def expand_left_octave(self) -> None:
        min_note, max_note = self._keyboard.note_range()
        new_min = max(0, min_note - 12)
        self._keyboard.set_note_range(self._snap_down_to_c(new_min), max_note)

    def expand_right_octave(self) -> None:
        min_note, max_note = self._keyboard.note_range()
        new_max = min(127, max_note + 12)
        self._keyboard.set_note_range(min_note, self._snap_up_to_b(new_max))

    def _snap_down_to_c(self, note: int) -> int:
        return max(0, int(note) - (int(note) % 12))

    def _snap_up_to_b(self, note: int) -> int:
        return min(127, int(note) + (11 - (int(note) % 12)))
