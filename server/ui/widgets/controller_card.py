from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

from server.config import set_controller_midi_channel, set_controller_muted, set_controller_name
from server.controller_state import ControllerState


class ControllerCard(QFrame):
    clicked = pyqtSignal(bytes, object, object)
    visualise_requested = pyqtSignal(bytes)

    def __init__(self, state: ControllerState, parent: QWidget | None = None):
        super().__init__(parent)
        self.state = state
        self.controller_mac = state.mac
        self._focused = False

        self.setObjectName("controllerCard")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            """
            QFrame#controllerCard {
                border: 1px solid #d5dbe2;
                border-radius: 10px;
                background: #f7f9fc;
            }
            QFrame#controllerCard[selected="true"] {
                border: 2px solid #8cb2ff;
                background: #f0f6ff;
            }
            QFrame#controllerCard[focused=\"true\"] {
                border: 2px solid #2d6cdf;
                background: #eef4ff;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 6)
        root.setSpacing(2)

        self._latency_ms: float | None = None
        self._data_rate_hz: float | None = None

        title_row = QHBoxLayout()
        title_row.setSpacing(4)

        self.selected_box = QCheckBox()
        self.selected_box.toggled.connect(self._on_selected_box_toggled)
        title_row.addWidget(self.selected_box)

        self.name_label = QLabel("Controller")
        self.name_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        title_row.addWidget(self.name_label)

        self.name_edit = QLineEdit()
        self.name_edit.setVisible(False)
        self.name_edit.editingFinished.connect(self._finish_name_edit)
        title_row.addWidget(self.name_edit)

        self.edit_name_button = QToolButton()
        self.edit_name_button.setIcon(qta.icon("fa5s.pencil-alt"))
        self.edit_name_button.setToolTip("Edit controller name")
        self.edit_name_button.clicked.connect(self._toggle_name_edit)
        title_row.addWidget(self.edit_name_button)

        self.mute_button = QPushButton("M")
        self.mute_button.setCheckable(True)
        self.mute_button.setFixedWidth(26)
        self.mute_button.toggled.connect(self._on_mute_toggled)
        title_row.addWidget(self.mute_button)

        title_row.addStretch(1)
        title_row.addWidget(QLabel("MIDI Channel"))

        self.channel_combo = QComboBox()
        for ch in range(1, 17):
            self.channel_combo.addItem(str(ch), ch)
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        self.channel_combo.setToolTip("MIDI channel")
        title_row.addWidget(self.channel_combo)

        root.addLayout(title_row)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.status_value = QLabel()
        self.status_value.setStyleSheet("color: #5a6675;")
        bottom_row.addWidget(self.status_value)
        bottom_row.addStretch(1)

        self.rezero_button = QPushButton("Re-zero")
        self.rezero_button.clicked.connect(self.state.re_zero)
        bottom_row.addWidget(self.rezero_button)

        root.addLayout(bottom_row)
        self.refresh_from_state()

    def mousePressEvent(self, a0):
        modifiers = a0.modifiers() if a0 is not None else Qt.KeyboardModifier.NoModifier
        self.clicked.emit(self.controller_mac, modifiers, None)
        super().mousePressEvent(a0)

    def _on_selected_box_toggled(self, checked: bool):
        modifiers = QApplication.keyboardModifiers()
        self.clicked.emit(self.controller_mac, modifiers, checked)

    def _toggle_name_edit(self):
        if self.name_edit.isVisible():
            self._finish_name_edit()
            return
        self.name_edit.setText(self.name_label.text())
        self.name_label.setVisible(False)
        self.name_edit.setVisible(True)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _finish_name_edit(self):
        if not self.name_edit.isVisible():
            return
        new_name = self.name_edit.text().strip() or f"Controller {self.state.midi_channel}"
        self.name_label.setVisible(True)
        self.name_edit.setVisible(False)
        if new_name != self.name_label.text():
            set_controller_name(self.controller_mac, new_name)
            self.state.set_name(new_name)
            self.name_label.setText(new_name)

    def _on_channel_changed(self):
        midi_channel = self.channel_combo.currentData()
        if isinstance(midi_channel, int):
            set_controller_midi_channel(self.controller_mac, midi_channel)
            self.state.midi_channel = midi_channel
            if not self.state.get_name().strip():
                generated = f"Controller {midi_channel}"
                set_controller_name(self.controller_mac, generated)
                self.state.set_name(generated)
                self.name_label.setText(generated)

    def _on_mute_toggled(self, checked: bool):
        set_controller_muted(self.controller_mac, checked)
        self.state.set_muted(checked)
        self.mute_button.setToolTip("Unmute controller" if checked else "Mute controller")

    def set_focused(self, focused: bool):
        self._focused = focused
        self.setProperty("focused", "true" if focused else "false")
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def set_selected(self, selected: bool):
        self.selected_box.blockSignals(True)
        self.selected_box.setChecked(selected)
        self.selected_box.blockSignals(False)
        self.setProperty("selected", "true" if selected else "false")
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def set_controller_name(self, name: str):
        self.name_label.setText(name)

    def set_midi_channel(self, midi_channel: int):
        index = self.channel_combo.findData(midi_channel)
        if index >= 0:
            self.channel_combo.blockSignals(True)
            self.channel_combo.setCurrentIndex(index)
            self.channel_combo.blockSignals(False)

    def set_ip(self, ip_addr: str):
        _ = ip_addr

    def set_latency_ms(self, latency_ms: float | None):
        self._latency_ms = latency_ms
        self._refresh_status_line()
        
    def set_data_rate(self, rate_hz: float | None):
        self._data_rate_hz = rate_hz
        self._refresh_status_line()

    def _refresh_status_line(self):
        data_rate_text = "-"
        if self._data_rate_hz is not None:
            data_rate_text = f"{self._data_rate_hz} Hz"

        latency_text = "-"
        if self._latency_ms is not None:
            latency_text = f"{self._latency_ms:.1f} ms"

        self.status_value.setText(f"Data rate: {data_rate_text}\tLatency: {latency_text}")

    def set_muted(self, muted: bool):
        self.mute_button.blockSignals(True)
        self.mute_button.setChecked(muted)
        self.mute_button.setToolTip("Unmute controller" if muted else "Mute controller")
        self.mute_button.blockSignals(False)

    def refresh_from_state(self):
        self.set_controller_name(self.state.get_name().strip() or f"Controller {self.state.midi_channel}")
        self.set_midi_channel(int(self.state.midi_channel))
        self.set_ip(self.state.source_ip)
        self.set_latency_ms(self.state.get_one_way_latency_ms())
        self.set_muted(self.state.is_muted())
        self.set_data_rate(self.state.get_data_rate())