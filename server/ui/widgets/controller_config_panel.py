import copy
from typing import Any, cast

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

import server.config as app_config
from server.config import get_controller_name, get_effective_controller_config, update_controller_override
from server.scales import CUSTOM_SCALE_NAME, SCALES, get_scale
from server.ui.dialogs.hit_advanced_dialog import HitAdvancedDialog
from server.ui.dialogs.mapping_config_dialog import MappingConfigDialog
from server.ui.widgets.config_options import MAPPING_NAME_PRESETS, MAPPING_SOURCE_OPTIONS, NEW_MAPPING_TEMPLATE
from server.ui.widgets.scale_selector import PianoScaleWidget


_MIXED = object()
_MISSING = object()


def _deep_apply_patch(base: dict, patch: dict) -> dict:
    merged = copy.deepcopy(base) if isinstance(base, dict) else {}
    for key, value in (patch or {}).items():
        if value is _MIXED:
            continue
        if isinstance(value, dict):
            merged[key] = _deep_apply_patch(merged.get(key, {}), value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _to_dialog_data(value):
    if value is _MIXED:
        return None
    if isinstance(value, dict):
        return {k: _to_dialog_data(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_dialog_data(v) for v in value]
    return copy.deepcopy(value)


def _merge_values(values):
    first = values[0]
    if all(v == first for v in values):
        return copy.deepcopy(first)
    return _MIXED


def _merge_dicts(dicts: list[dict]) -> dict:
    if not dicts:
        return {}
    keys = set()
    for d in dicts:
        keys.update(d.keys())

    merged: dict = {}
    for key in keys:
        values = [d.get(key, _MISSING) for d in dicts]
        if any(v is _MISSING for v in values):
            merged[key] = _MIXED
            continue
        if all(isinstance(v, dict) for v in values):
            merged[key] = _merge_dicts(values)
            continue
        merged[key] = _merge_values(values)
    return merged


def _group_mappings_by_name(mappings: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for mapping in mappings:
        if not isinstance(mapping, dict):
            continue
        name = str(mapping.get("name", "")).strip()
        if not name:
            continue
        grouped.setdefault(name, []).append(mapping)
    return grouped


def _mapping_index_map(mappings: list[dict]) -> dict[tuple[str, int], int]:
    counts: dict[str, int] = {}
    index_map: dict[tuple[str, int], int] = {}
    for idx, mapping in enumerate(mappings):
        name = str(mapping.get("name", "")).strip()
        if not name:
            continue
        occ = counts.get(name, 0)
        index_map[(name, occ)] = idx
        counts[name] = occ + 1
    return index_map


def _common_mapping_rows(configs: list[dict]) -> list[tuple[tuple[str, int], dict]]:
    if not configs:
        return []
    mapping_lists = [list(cfg.get("mappings", [])) for cfg in configs]
    grouped_all = [_group_mappings_by_name(mappings) for mappings in mapping_lists]
    if not grouped_all:
        return []

    common_names = set(grouped_all[0].keys())
    for grouped in grouped_all[1:]:
        common_names &= set(grouped.keys())

    rows: list[tuple[tuple[str, int], dict]] = []
    seen_counts: dict[str, int] = {}
    for mapping in mapping_lists[0]:
        name = str(mapping.get("name", "")).strip()
        if not name or name not in common_names:
            continue
        occ = seen_counts.get(name, 0)
        max_common_occ = min(len(grouped[name]) for grouped in grouped_all)
        if occ >= max_common_occ:
            seen_counts[name] = occ + 1
            continue

        per_controller = [grouped[name][occ] for grouped in grouped_all]
        merged = _merge_dicts(per_controller)
        merged["name"] = name
        rows.append(((name, occ), merged))
        seen_counts[name] = occ + 1
    return rows


class MappingRow(QFrame):
    changed = pyqtSignal()
    remove_requested = pyqtSignal(object)

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
        self.cc_spin.setFixedWidth(42)
        cc_value = self.mapping_cfg.get("cc_number", 7)
        self.cc_spin.setValue(-1 if cc_value is _MIXED else int(cc_value))
        self.cc_spin.valueChanged.connect(self._on_cc_changed)
        layout.addWidget(self.cc_spin)

        self.source_combo = QComboBox()
        self.source_combo.addItems(MAPPING_SOURCE_OPTIONS)
        source_value = self.mapping_cfg.get("source", "swing_ud")
        if source_value is _MIXED:
            self.source_combo.setCurrentIndex(-1)
        else:
            self.source_combo.setCurrentText(str(source_value))
        self.source_combo.currentTextChanged.connect(self._on_source_changed)
        layout.addWidget(self.source_combo, 2)

        self.config_btn = QToolButton()
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

        if "enabled" not in self.mapping_cfg:
            self.mapping_cfg["enabled"] = True
        self._refresh_enabled_button()
        self._loading = False

    def _refresh_enabled_button(self):
        enabled = self.mapping_cfg.get("enabled", True)
        if enabled is _MIXED:
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
        self.mapping_cfg["cc_number"] = _MIXED if value < 0 else int(value)
        self.changed.emit()

    def _on_source_changed(self, value: str):
        if self._loading:
            return
        self.mapping_cfg["source"] = value
        self.changed.emit()

    def _toggle_enabled(self):
        if self._loading:
            return
        current = self.mapping_cfg.get("enabled", True)
        next_enabled = True if current is _MIXED else (not bool(current))
        self.mapping_cfg["enabled"] = next_enabled
        self._refresh_enabled_button()
        self.changed.emit()

    def _open_config(self):
        dialog_data = cast(dict, _to_dialog_data(self.mapping_cfg))
        dialog = MappingConfigDialog(dialog_data, self)
        if dialog.exec_():
            patch = dialog.get_value()
            if patch:
                self.mapping_cfg = _deep_apply_patch(self.mapping_cfg, patch)
                self.changed.emit()

    def get_value(self):
        if self.source_combo.currentIndex() >= 0:
            self.mapping_cfg["source"] = self.source_combo.currentText()
        else:
            self.mapping_cfg["source"] = _MIXED
        self.mapping_cfg["cc_number"] = _MIXED if self.cc_spin.value() < 0 else int(self.cc_spin.value())
        if "enabled" not in self.mapping_cfg:
            self.mapping_cfg["enabled"] = True
        if not str(self.mapping_cfg.get("name", "")).strip():
            self.mapping_cfg["name"] = "custom"
        return dict(self.mapping_cfg)


class ControllerConfigPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller_macs: list[bytes] = []
        self._loaded_for: tuple[bytes, ...] | None = None
        self._loaded_row_keys: set[tuple[str, int]] = set()
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        self.title = QLabel("Select a controller")
        self.title.setStyleSheet("font-size: 16px; font-weight: 600;")
        root.addWidget(self.title)

        self.mapping_group = QGroupBox("Mappings")
        self.mapping_layout = QVBoxLayout(self.mapping_group)
        self.mapping_layout.setContentsMargins(8, 8, 8, 8)
        self.mapping_layout.setSpacing(6)
        self.mapping_rows: list[MappingRow] = []

        headers_row = QWidget(self.mapping_group)
        headers_layout = QHBoxLayout(headers_row)
        headers_layout.setContentsMargins(0, 0, 0, 0)
        headers_layout.setSpacing(6)

        name_header = QLabel("Name")
        name_header.setStyleSheet("font-weight: 600;")
        headers_layout.addWidget(name_header, 2)

        cc_header = QLabel("CC")
        cc_header.setStyleSheet("font-weight: 600;")
        cc_header.setFixedWidth(42)
        headers_layout.addWidget(cc_header)

        source_header = QLabel("Controller source")
        source_header.setStyleSheet("font-weight: 600;")
        headers_layout.addWidget(source_header, 2)

        headers_layout.addSpacing(56)
        self.mapping_layout.addWidget(headers_row)

        self.add_mapping_btn = QPushButton("Add Mapping")
        self.add_mapping_btn.clicked.connect(self._add_mapping)
        self.mapping_layout.addWidget(self.add_mapping_btn)
        root.addWidget(self.mapping_group)

        self.hit_group = QGroupBox("Hit Machine")
        hit_layout = QGridLayout()
        self.hit_group.setLayout(hit_layout)
        hit_layout.setContentsMargins(8, 8, 8, 8)
        hit_layout.setHorizontalSpacing(8)
        hit_layout.setVerticalSpacing(8)

        self.hit_enabled = QCheckBox("Enabled")
        self.hit_enabled.setTristate(True)
        self.hit_enabled.stateChanged.connect(self._on_hit_basic_changed)

        self.flick_release_enabled = QCheckBox("Flick up to release")
        self.flick_release_enabled.setTristate(True)
        self.flick_release_enabled.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.flick_release_enabled.stateChanged.connect(self._on_hit_basic_changed)

        hit_toggle_row = QWidget(self.hit_group)
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

        root.addWidget(self.hit_group)
        root.addStretch()

        self.setDisabled(True)

    def set_controllers(self, controller_macs: list[bytes], force_reload: bool = False):
        unique = tuple(sorted({mac for mac in controller_macs if isinstance(mac, bytes)}))
        self.controller_macs = list(unique)
        if not unique:
            self.title.setText("Select one or more controllers")
            self.setDisabled(True)
            self._loaded_for = None
            return

        if not force_reload and self._loaded_for == unique and self.isEnabled():
            return

        self.setDisabled(False)
        if len(unique) == 1:
            self.title.setText(f"{get_controller_name(unique[0])} - Config")
        else:
            self.title.setText(f"{len(unique)} controllers - Config")
        self._load_from_config()
        self._loaded_for = unique

    def _clear_mapping_rows(self):
        for row in self.mapping_rows:
            row.setParent(None)
            row.deleteLater()
        self.mapping_rows.clear()

    def _insert_mapping_row(self, row_key: tuple[str, int], cfg: dict):
        row = MappingRow(row_key, cfg, self)
        row.changed.connect(self._persist_mappings)
        row.remove_requested.connect(self._remove_mapping_row)
        insert_at = max(self.mapping_layout.count() - 1, 0)
        self.mapping_layout.insertWidget(insert_at, row)
        self.mapping_rows.append(row)

    def _remove_mapping_row(self, row: MappingRow):
        if row not in self.mapping_rows:
            return
        self.mapping_rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._persist_mappings()

    def _load_from_config(self):
        if not self.controller_macs:
            return

        configs = [get_effective_controller_config(mac) for mac in self.controller_macs]
        self._loading = True

        self._clear_mapping_rows()
        common_rows = _common_mapping_rows(configs)
        self._loaded_row_keys = {row_key for row_key, _map_cfg in common_rows}
        for row_key, map_cfg in common_rows:
            self._insert_mapping_row(row_key, map_cfg)

        hits = [dict(cfg.get("hit", {})) for cfg in configs]
        enabled_value = _merge_values([bool(hit.get("enabled", True)) for hit in hits])
        flick_release_value = _merge_values([bool(hit.get("flick_up_to_release_enabled", True)) for hit in hits])
        scale_names = [
            self._normalize_scale_name(str(dict(hit.get("scale", {})).get("name", "Major (Ionian)")))
            for hit in hits
        ]
        scale_name_value = _merge_values(scale_names)
        root_notes = [int(dict(hit.get("scale", {})).get("root_note", 60)) for hit in hits]
        root_note_value = _merge_values(root_notes)
        custom_scales = [list(dict(hit.get("scale", {})).get("custom_scale", [])) for hit in hits]
        custom_scale_value = _merge_values(custom_scales)

        self.hit_enabled.blockSignals(True)
        if enabled_value is _MIXED:
            self.hit_enabled.setCheckState(Qt.CheckState.PartiallyChecked)
        else:
            self.hit_enabled.setCheckState(Qt.CheckState.Checked if enabled_value else Qt.CheckState.Unchecked)
        self.hit_enabled.blockSignals(False)

        self.flick_release_enabled.blockSignals(True)
        if flick_release_value is _MIXED:
            self.flick_release_enabled.setCheckState(Qt.CheckState.PartiallyChecked)
        else:
            self.flick_release_enabled.setCheckState(
                Qt.CheckState.Checked if flick_release_value else Qt.CheckState.Unchecked
            )
        self.flick_release_enabled.blockSignals(False)

        self.scale_combo.blockSignals(True)
        if scale_name_value is _MIXED:
            self.scale_combo.setCurrentIndex(-1)
        else:
            self.scale_combo.setCurrentText(str(scale_name_value))
        self.scale_combo.blockSignals(False)

        self.root_note_spin.blockSignals(True)
        if root_note_value is _MIXED:
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

    def _add_mapping(self):
        if not self.controller_macs:
            return
        existing_custom_count = sum(1 for row in self.mapping_rows if str(row.get_value().get("name", "")) == "custom")
        self._insert_mapping_row(("custom", existing_custom_count), copy.deepcopy(NEW_MAPPING_TEMPLATE))
        self._persist_mappings()

    def _persist_mappings(self):
        if self._loading or not self.controller_macs:
            return

        row_values = [(row.row_key, row.get_value()) for row in self.mapping_rows]
        visible_keys = {row_key for row_key, _row_cfg in row_values}
        removed_keys = self._loaded_row_keys - visible_keys

        for mac in self.controller_macs:
            base_mappings = list(get_effective_controller_config(mac).get("mappings", []))
            mapping_idx = _mapping_index_map(base_mappings)
            merged_mappings = copy.deepcopy(base_mappings)

            remove_indices = sorted(
                [mapping_idx[row_key] for row_key in removed_keys if row_key in mapping_idx],
                reverse=True,
            )
            for idx in remove_indices:
                del merged_mappings[idx]

            mapping_idx = _mapping_index_map(merged_mappings)

            for row_key, row_cfg in row_values:
                if row_key in mapping_idx:
                    idx = mapping_idx[row_key]
                    merged_mappings[idx] = _deep_apply_patch(merged_mappings[idx], row_cfg)
                else:
                    merged_mappings.append(_deep_apply_patch(copy.deepcopy(NEW_MAPPING_TEMPLATE), row_cfg))

            update_controller_override(mac, ["mappings"], merged_mappings)

        self._loaded_row_keys = visible_keys

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
        merged_hit_cfg = _merge_dicts(hit_cfgs)
        dialog_data = cast(dict, _to_dialog_data(merged_hit_cfg))
        dialog = HitAdvancedDialog(dialog_data, self)
        if not dialog.exec_():
            return

        patch = dialog.get_value()
        if not patch:
            return

        for mac in self.controller_macs:
            current_hit_cfg = dict(get_effective_controller_config(mac).get("hit", {}))
            update_controller_override(mac, ["hit"], _deep_apply_patch(current_hit_cfg, patch))

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
        if root_value >= 0:
            self.scale_keyboard.set_root_note(root_value)
        else:
            self.scale_keyboard.set_root_note(-1)

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
        if scale_name_value is _MIXED:
            self.scale_keyboard.set_selected_notes([], emit_signal=False)
            return

        scale_name = self._normalize_scale_name(str(scale_name_value))
        root_value = root_note_value if isinstance(root_note_value, int) else 60
        if root_value >= 0:
            self.scale_keyboard.set_root_note(root_value)
        else:
            self.scale_keyboard.set_root_note(-1)

        if scale_name.lower() == "custom":
            if custom_scale_value is _MIXED:
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
