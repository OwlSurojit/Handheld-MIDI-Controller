from typing import cast

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QComboBox, QFrame, QHBoxLayout, QSpinBox, QToolButton
import qtawesome as qta

from server.config_consts import MAPPING_NAME_PRESETS, MAPPING_SOURCE_OPTIONS
from server.ui.dialogs.mapping_config_dialog import MappingConfigDialog
from server.ui.widgets.controller_config_helpers import MIXED, cc_control_width, deep_apply_patch, to_dialog_data


class MappingRow(QFrame):
    changed = pyqtSignal()
    remove_requested = pyqtSignal(object)
    midi_learn_requested = pyqtSignal(object)

    def __init__(self, row_key: tuple[str, int], mapping_cfg: dict, parent=None):
        super().__init__(parent)
        self.row_key = row_key
        self.mapping_cfg = dict(mapping_cfg)
        self._loading = True
        self._internal_to_display = {
            values["name"]: display
            for display, values in MAPPING_NAME_PRESETS.items()
        }

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.name_combo = QComboBox()
        self.name_combo.setEditable(True)
        self.name_combo.addItems(list(MAPPING_NAME_PRESETS.keys()))
        mapping_name = str(self.mapping_cfg.get("name", "custom"))
        self.name_combo.setCurrentText(
            self._internal_to_display.get(mapping_name, mapping_name.replace("_", " "))
        )
        self.name_combo.currentTextChanged.connect(self._on_name_changed)
        layout.addWidget(self.name_combo, 2)

        self.cc_spin = QSpinBox()
        self.cc_spin.setRange(-1, 127)
        self.cc_spin.setSpecialValueText(" ")
        self.cc_spin.setFixedWidth(cc_control_width(self.cc_spin))
        cc_value = self.mapping_cfg.get("cc_number", 7)
        self.cc_spin.setValue(-1 if cc_value is MIXED else int(cc_value))
        self.cc_spin.valueChanged.connect(self._on_cc_changed)
        layout.addWidget(self.cc_spin)

        self.source_combo = QComboBox()
        self.source_combo.addItems(list(MAPPING_SOURCE_OPTIONS.keys()))
        source_value = self.mapping_cfg.get("source", "swing_ud")
        if source_value is MIXED:
            self.source_combo.setCurrentIndex(-1)
        else:
            display_value = {v["name"]: k for k, v in MAPPING_SOURCE_OPTIONS.items()}.get(source_value, source_value)
            self.source_combo.setCurrentText(str(display_value))
        self.source_combo.currentTextChanged.connect(self._on_source_changed)
        layout.addWidget(self.source_combo, 2)

        self.learn_btn = QToolButton()
        self.learn_btn.setIcon(qta.icon("fa5s.graduation-cap", color="#2d7d46"))
        self.learn_btn.setToolTip("MIDI learn: send test pulses for this mapping")
        self.learn_btn.clicked.connect(lambda: self.midi_learn_requested.emit(self))
        layout.addWidget(self.learn_btn)

        self.toggle_enabled_btn = QToolButton()
        self.toggle_enabled_btn.clicked.connect(self._toggle_enabled)
        layout.addWidget(self.toggle_enabled_btn)

        self.config_btn = QToolButton()
        self.config_btn.setIcon(qta.icon("fa5s.sliders-h"))
        self.config_btn.setToolTip("Mapping advanced settings")
        self.config_btn.clicked.connect(self._open_config)
        layout.addWidget(self.config_btn)

        self.remove_btn = QToolButton()
        self.remove_btn.setIcon(qta.icon("fa5s.trash-alt", color="#c22121"))
        self.remove_btn.setToolTip("Remove mapping")
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        layout.addWidget(self.remove_btn)

        self.mapping_cfg.setdefault("enabled", True)
        self._refresh_enabled_button()
        self._loading = False

    def _refresh_enabled_button(self):
        enabled = self.mapping_cfg.get("enabled", True)
        if enabled is MIXED:
            self.toggle_enabled_btn.setIcon(qta.icon("fa5s.adjust", color="#999999"))
            self.toggle_enabled_btn.setToolTip("Mapping active state differs across selected controllers")
        elif bool(enabled):
            self.toggle_enabled_btn.setIcon(qta.icon("mdi6.knob", color="#c22121"))
            self.toggle_enabled_btn.setToolTip("Mapping is active. Click to deactivate.")
        else:
            self.toggle_enabled_btn.setIcon(qta.icon("mdi6.knob", color="#999999"))
            self.toggle_enabled_btn.setToolTip("Mapping is inactive. Click to activate.")

    def _on_name_changed(self, value: str):
        if self._loading:
            return
        display_name = value.strip().lower() or "custom"
        if display_name in MAPPING_NAME_PRESETS:
            preset = MAPPING_NAME_PRESETS[display_name]
            self.mapping_cfg["name"] = preset["name"]
            mapped_cc = preset["cc_number"]
            if mapped_cc is not None:
                self.mapping_cfg["cc_number"] = int(mapped_cc)
                self.cc_spin.blockSignals(True)
                self.cc_spin.setValue(int(mapped_cc))
                self.cc_spin.blockSignals(False)
        else:
            self.mapping_cfg["name"] = display_name.replace(" ", "_")
        self.changed.emit()

    def _on_cc_changed(self, value: int):
        if self._loading:
            return
        self.mapping_cfg["cc_number"] = MIXED if value < 0 else int(value)
        self.changed.emit()

    def _on_source_changed(self, value: str):
        if self._loading:
            return
        mapping = MAPPING_SOURCE_OPTIONS.get(value, {})
        self.mapping_cfg["source"] = mapping.get("name", value) if value else MIXED
        self.mapping_cfg["range"] = mapping.get("range", [-1, 1])
        self.mapping_cfg["invert"] = False
        self.changed.emit()

    def _toggle_enabled(self):
        if self._loading:
            return
        current = self.mapping_cfg.get("enabled", True)
        next_enabled = True if current is MIXED else (not bool(current))
        self.mapping_cfg["enabled"] = next_enabled
        self._refresh_enabled_button()
        self.changed.emit()

    def _open_config(self):
        dialog_data = cast(dict, to_dialog_data(self.mapping_cfg))
        dialog = MappingConfigDialog(dialog_data, self)
        if dialog.exec_():
            patch = dialog.get_value()
            if patch:
                self.mapping_cfg = deep_apply_patch(self.mapping_cfg, patch)
                self.changed.emit()

    def get_value(self):
        if self.source_combo.currentIndex() >= 0:
            self.mapping_cfg["source"] = MAPPING_SOURCE_OPTIONS.get(self.source_combo.currentText(), {}).get("name", self.source_combo.currentText())
        else:
            self.mapping_cfg["source"] = MIXED
        self.mapping_cfg["cc_number"] = MIXED if self.cc_spin.value() < 0 else int(self.cc_spin.value())
        self.mapping_cfg.setdefault("enabled", True)
        if not str(self.mapping_cfg.get("name", "")).strip():
            self.mapping_cfg["name"] = "custom"
        return dict(self.mapping_cfg)
