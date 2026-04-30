from typing import Any, cast

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)

import server.config as app_config
from server.config import get_effective_controller_config, update_controller_override
from server.scales import CUSTOM_SCALE_NAME, SCALES, get_scale
from server.ui.dialogs.hit_advanced_dialog import HitAdvancedDialog
from server.ui.widgets.controller_config_helpers import MIXED, StrictTristateCheckbox, deep_apply_patch, merge_dicts, merge_values, to_dialog_data
from server.ui.widgets.scale_selector import PianoScaleWidget


class HitMachineConfigGroup(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Hit Machine", parent)
        self.controller_macs: list[bytes] = []
        self._loading = False

        hit_layout = QGridLayout(self)
        hit_layout.setContentsMargins(8, 8, 8, 8)
        hit_layout.setHorizontalSpacing(8)
        hit_layout.setVerticalSpacing(8)

        self.hit_enabled = StrictTristateCheckbox("Enabled")
        self.hit_enabled.stateChanged.connect(self._on_hit_basic_changed)

        self.flick_release_enabled = StrictTristateCheckbox("Flick up to release")
        self.flick_release_enabled.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.flick_release_enabled.stateChanged.connect(self._on_hit_basic_changed)

        hit_toggle_row = QWidget(self)
        hit_toggle_row_layout = QHBoxLayout(hit_toggle_row)
        hit_toggle_row_layout.setContentsMargins(0, 0, 0, 0)
        hit_toggle_row_layout.setSpacing(8)
        hit_toggle_row_layout.addWidget(self.hit_enabled)
        hit_toggle_row_layout.addStretch()
        hit_toggle_row_layout.addWidget(self.flick_release_enabled)
        hit_layout.addWidget(hit_toggle_row, 0, 0, 1, 2)

        self.scale_combo = QComboBox()
        self.scale_combo.addItems(list(SCALES.keys()) + [CUSTOM_SCALE_NAME])
        self.scale_combo.currentTextChanged.connect(self._on_hit_basic_changed)
        hit_layout.addWidget(QLabel("Scale"), 1, 0)
        hit_layout.addWidget(self.scale_combo, 1, 1)

        self.root_note_spin = QSpinBox()
        self.root_note_spin.setRange(-1, 127)
        self.root_note_spin.setSpecialValueText(" ")
        self.root_note_spin.valueChanged.connect(self._on_hit_basic_changed)
        self.root_note_spin.valueChanged.connect(self._update_root_note_suffix)
        hit_layout.addWidget(QLabel("Root Note"), 2, 0)
        hit_layout.addWidget(self.root_note_spin, 2, 1)

        self.scale_keyboard = PianoScaleWidget(root_note=60, min_note=48, max_note=83, parent=self)
        self.scale_keyboard.selected_notes_changed.connect(self._on_keyboard_notes_changed)
        hit_layout.addWidget(self.scale_keyboard, 3, 0, 1, 2)

        self.advanced_hit_btn = QPushButton("Advanced Options")
        self.advanced_hit_btn.clicked.connect(self._open_hit_advanced)
        hit_layout.addWidget(self.advanced_hit_btn, 4, 0, 1, 2)

    def set_controllers(self, controller_macs: list[bytes]) -> None:
        self.controller_macs = list(controller_macs)
        self._load_from_config()

    def _load_from_config(self):
        self._loading = True

        if not self.controller_macs:
            self.hit_enabled.blockSignals(True)
            self.hit_enabled.setCheckState(Qt.CheckState.Unchecked)
            self.hit_enabled.blockSignals(False)
            self.flick_release_enabled.blockSignals(True)
            self.flick_release_enabled.setCheckState(Qt.CheckState.Unchecked)
            self.flick_release_enabled.blockSignals(False)
            self.scale_combo.blockSignals(True)
            self.scale_combo.setCurrentIndex(-1)
            self.scale_combo.blockSignals(False)
            self.root_note_spin.blockSignals(True)
            self.root_note_spin.setValue(-1)
            self.root_note_spin.blockSignals(False)
            self.scale_keyboard.set_selected_notes([], emit_signal=False)
            self._loading = False
            return

        configs = [get_effective_controller_config(mac) for mac in self.controller_macs]
        hits = [dict(cfg.get("hit", {})) for cfg in configs]
        enabled_value = merge_values([bool(hit.get("enabled", True)) for hit in hits])
        flick_release_value = merge_values([bool(hit.get("flick_up_to_release_enabled", True)) for hit in hits])
        scale_names = [
            self._normalize_scale_name(str(dict(hit.get("scale", {})).get("name", "Major (Ionian)")))
            for hit in hits
        ]
        scale_name_value = merge_values(scale_names)
        root_notes = [int(dict(hit.get("scale", {})).get("root_note", 60)) for hit in hits]
        root_note_value = merge_values(root_notes)
        custom_scales = [list(dict(hit.get("scale", {})).get("custom_scale", [])) for hit in hits]
        custom_scale_value = merge_values(custom_scales)

        self.hit_enabled.blockSignals(True)
        if enabled_value is MIXED:
            self.hit_enabled.setCheckState(Qt.CheckState.PartiallyChecked)
        else:
            self.hit_enabled.setCheckState(Qt.CheckState.Checked if enabled_value else Qt.CheckState.Unchecked)
        self.hit_enabled.blockSignals(False)

        self.flick_release_enabled.blockSignals(True)
        if flick_release_value is MIXED:
            self.flick_release_enabled.setCheckState(Qt.CheckState.PartiallyChecked)
        else:
            self.flick_release_enabled.setCheckState(
                Qt.CheckState.Checked if flick_release_value else Qt.CheckState.Unchecked
            )
        self.flick_release_enabled.blockSignals(False)

        self.scale_combo.blockSignals(True)
        if scale_name_value is MIXED:
            self.scale_combo.setCurrentIndex(-1)
        else:
            self.scale_combo.setCurrentText(str(scale_name_value))
        self.scale_combo.blockSignals(False)

        self.root_note_spin.blockSignals(True)
        if root_note_value is MIXED:
            root_value = -1
        elif isinstance(root_note_value, int):
            root_value = root_note_value
        else:
            root_value = 60
        self.root_note_spin.setValue(root_value)
        self.root_note_spin.blockSignals(False)
        self._update_root_note_suffix(self.root_note_spin.value())
        self._sync_keyboard_from_config(scale_name_value, root_note_value, custom_scale_value)

        self._loading = False

    def _on_hit_basic_changed(self, *_args: Any):
        if self._loading or not self.controller_macs:
            return

        for mac in self.controller_macs:
            mac_key = mac.hex().lower()
            updates = []

            state = self.hit_enabled.checkState()
            if state != Qt.CheckState.PartiallyChecked:
                updates.append((
                    ["controllers", mac_key, "hit", "enabled"],
                    state == Qt.CheckState.Checked,
                ))

            flick_state = self.flick_release_enabled.checkState()
            if flick_state != Qt.CheckState.PartiallyChecked:
                updates.append((
                    ["controllers", mac_key, "hit", "flick_up_to_release_enabled"],
                    flick_state == Qt.CheckState.Checked,
                ))

            if self.scale_combo.currentIndex() >= 0:
                updates.append((
                    ["controllers", mac_key, "hit", "scale", "name"],
                    self.scale_combo.currentText(),
                ))

            if self.root_note_spin.value() >= 0:
                updates.append((
                    ["controllers", mac_key, "hit", "scale", "root_note"],
                    int(self.root_note_spin.value()),
                ))

            if updates:
                app_config.update_many(updates)

        self._sync_keyboard_from_controls()

    def _open_hit_advanced(self):
        if not self.controller_macs:
            return

        hit_cfgs = [dict(get_effective_controller_config(mac).get("hit", {})) for mac in self.controller_macs]
        merged_hit_cfg = merge_dicts(hit_cfgs)
        dialog_data = cast(dict, to_dialog_data(merged_hit_cfg))
        dialog = HitAdvancedDialog(dialog_data, self)
        if not dialog.exec_():
            return

        patch = dialog.get_value()
        if not patch:
            return

        for mac in self.controller_macs:
            current_hit_cfg = dict(get_effective_controller_config(mac).get("hit", {}))
            update_controller_override(mac, ["hit"], deep_apply_patch(current_hit_cfg, patch))

    def _update_root_note_suffix(self, midi_note: int):
        if midi_note < 0:
            self.root_note_spin.setSuffix("")
            return
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        note_name = note_names[midi_note % 12]
        octave = (midi_note // 12) - 2
        self.root_note_spin.setSuffix(f" ({note_name}{octave})")

    def _normalize_scale_name(self, name: str) -> str:
        if str(name or "").strip().lower() == "custom":
            return CUSTOM_SCALE_NAME
        return str(name or "").strip()

    def _sync_keyboard_from_controls(self) -> None:
        if self.scale_combo.currentIndex() < 0:
            self.scale_keyboard.set_selected_notes([], emit_signal=False)
            return

        scale_name = self.scale_combo.currentText()
        root_value = self.root_note_spin.value()
        self.scale_keyboard.set_root_note(root_value if root_value >= 0 else -1)

        if scale_name.lower() == "custom":
            self.scale_keyboard.ensure_notes_visible(
                self._required_visible_notes(self.scale_keyboard.selected_notes(), root_value)
            )
            return

        selected = self._compute_keyboard_notes(scale_name, root_value, [])
        self.scale_keyboard.ensure_notes_visible(self._required_visible_notes(selected, root_value))
        self.scale_keyboard.set_selected_notes(
            self._filter_notes_to_keyboard_range(selected),
            emit_signal=False,
        )

    def _sync_keyboard_from_config(self, scale_name_value, root_note_value, custom_scale_value) -> None:
        if scale_name_value is MIXED:
            self.scale_keyboard.set_selected_notes([], emit_signal=False)
            return

        scale_name = self._normalize_scale_name(str(scale_name_value))
        root_value = root_note_value if isinstance(root_note_value, int) else 60
        self.scale_keyboard.set_root_note(root_value if root_value >= 0 else -1)

        if scale_name.lower() == "custom":
            if custom_scale_value is MIXED:
                self.scale_keyboard.set_selected_notes([], emit_signal=False)
                return
            custom_notes = list(custom_scale_value or [])
            custom_set = self._compute_keyboard_notes(scale_name, root_value, custom_notes)
            self.scale_keyboard.ensure_notes_visible(self._required_visible_notes(custom_set, root_value))
            self.scale_keyboard.set_selected_notes(
                self._filter_notes_to_keyboard_range(custom_set),
                emit_signal=False,
            )
            return

        selected = self._compute_keyboard_notes(scale_name, root_value, [])
        self.scale_keyboard.ensure_notes_visible(self._required_visible_notes(selected, root_value))
        self.scale_keyboard.set_selected_notes(
            self._filter_notes_to_keyboard_range(selected),
            emit_signal=False,
        )

    def _on_keyboard_notes_changed(self, notes: set[int]) -> None:
        if self._loading or not self.controller_macs:
            return

        self.scale_combo.blockSignals(True)
        self.scale_combo.setCurrentText(CUSTOM_SCALE_NAME)
        self.scale_combo.blockSignals(False)

        custom_notes = sorted({int(note) for note in notes if 0 <= int(note) <= 127})
        for mac in self.controller_macs:
            mac_key = mac.hex().lower()
            updates = [
                (["controllers", mac_key, "hit", "scale", "name"], CUSTOM_SCALE_NAME),
                (["controllers", mac_key, "hit", "scale", "custom_scale"], custom_notes),
            ]
            if self.root_note_spin.value() >= 0:
                updates.append((
                    ["controllers", mac_key, "hit", "scale", "root_note"],
                    int(self.root_note_spin.value()),
                ))
            app_config.update_many(updates)

    def _filter_notes_to_keyboard_range(self, notes: list[int] | set[int]) -> set[int]:
        min_note, max_note = self.scale_keyboard.note_range()
        return {
            int(note)
            for note in notes
            if min_note <= int(note) <= max_note
        }

    def _compute_keyboard_notes(self, scale_name: str, root_note: int, custom_scale: list[int]) -> set[int]:
        if scale_name.lower() == "custom":
            return {int(note) for note in custom_scale if 0 <= int(note) <= 127}

        root_value = 60 if root_note < 0 else int(root_note)
        offsets = get_scale(scale_name, None)
        return {
            int(root_value + int(offset))
            for offset in offsets
            if 0 <= int(root_value + int(offset)) <= 127
        }

    def _required_visible_notes(self, notes: set[int], root_note: int) -> set[int]:
        required = set(notes)
        if root_note >= 0:
            required.add(int(root_note))
        return required
