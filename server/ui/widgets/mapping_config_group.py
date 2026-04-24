import copy

from PyQt5.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from server.config import get_effective_controller_config, update_controller_override
from server.config_consts import NEW_MAPPING_TEMPLATE
from server.midi_mapper import MidiMapper
from server.shared_state import controllers
from server.ui.widgets.controller_config_helpers import (
    cc_control_width,
    common_mapping_rows,
    deep_apply_patch,
    mapping_index_map,
)
from server.ui.widgets.mapping_row import MappingRow


class MappingConfigGroup(QGroupBox):
    def __init__(self, midi_mapper: MidiMapper, parent=None):
        super().__init__("Mappings", parent)
        self.controller_macs: list[bytes] = []
        self._loaded_row_keys: set[tuple[str, int]] = set()
        self._loading = False
        self._midi_mapper = midi_mapper
        self.mapping_rows: list[MappingRow] = []

        self.mapping_layout = QVBoxLayout(self)
        self.mapping_layout.setContentsMargins(8, 8, 8, 8)
        self.mapping_layout.setSpacing(6)

        headers_row = QWidget(self)
        headers_layout = QHBoxLayout(headers_row)
        headers_layout.setContentsMargins(0, 0, 0, 0)
        headers_layout.setSpacing(6)

        cc_column_width = cc_control_width(self)

        name_header = QLabel("Name")
        name_font = name_header.font()
        name_font.setBold(True)
        name_header.setFont(name_font)
        headers_layout.addWidget(name_header, 2)

        cc_header = QLabel("CC")
        cc_font = cc_header.font()
        cc_font.setBold(True)
        cc_header.setFont(cc_font)
        cc_header.setFixedWidth(cc_column_width)
        headers_layout.addWidget(cc_header)

        source_header = QLabel("Controller source")
        source_font = source_header.font()
        source_font.setBold(True)
        source_header.setFont(source_font)
        headers_layout.addWidget(source_header, 2)

        headers_layout.addSpacing(91)
        self.mapping_layout.addWidget(headers_row)

        self.add_mapping_btn = QPushButton("Add Mapping")
        self.add_mapping_btn.clicked.connect(self._add_mapping)
        self.mapping_layout.addWidget(self.add_mapping_btn)

    def set_controllers(self, controller_macs: list[bytes]) -> None:
        self.controller_macs = list(controller_macs)
        self._load_from_config()

    def _clear_mapping_rows(self):
        for row in self.mapping_rows:
            row.setParent(None)
            row.deleteLater()
        self.mapping_rows.clear()

    def _insert_mapping_row(self, row_key: tuple[str, int], cfg: dict):
        row = MappingRow(row_key, cfg, self)
        row.changed.connect(self._persist_mappings)
        row.remove_requested.connect(self._remove_mapping_row)
        row.midi_learn_requested.connect(self._start_mapping_midi_learn)
        insert_at = max(self.mapping_layout.count() - 1, 0)
        self.mapping_layout.insertWidget(insert_at, row)
        self.mapping_rows.append(row)

    def _resolve_row_mapping_for_controller(self, mac: bytes, row_key: tuple[str, int]) -> dict:
        mappings = list(get_effective_controller_config(mac).get("mappings", []))
        mapping_idx = mapping_index_map(mappings)
        idx = mapping_idx[row_key]
        return dict(mappings[idx])

    def _start_mapping_midi_learn(self, row: MappingRow):
        if len(self.controller_macs) != 1:
            QMessageBox.information(
                self,
                "MIDI Learn",
                "Select exactly one controller to run MIDI learn for a mapping.",
            )
            return

        controller_mac = self.controller_macs[0]
        mapping_cfg = self._resolve_row_mapping_for_controller(controller_mac, row.row_key)
        midi_channel = controllers[controller_mac].midi_channel
        self._midi_mapper.set_midi_learn_mode(midi_channel, mapping_cfg)

        QMessageBox.about(
            self,
            "MIDI Learn Active",
            "The app is now sending test MIDI data on this mapping's channel.\n"
            "In your DAW or VST, enable MIDI learn and bind the target control now.\n"
            "Close this dialog to stop MIDI learn and return to normal operation.",
        )

    def _remove_mapping_row(self, row: MappingRow):
        self.mapping_rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._persist_mappings()

    def _load_from_config(self):
        self._loading = True
        self._clear_mapping_rows()

        if not self.controller_macs:
            self._loaded_row_keys = set()
            self._loading = False
            return

        configs = [get_effective_controller_config(mac) for mac in self.controller_macs]
        common_rows = common_mapping_rows(configs)
        self._loaded_row_keys = {row_key for row_key, _map_cfg in common_rows}
        for row_key, map_cfg in common_rows:
            self._insert_mapping_row(row_key, map_cfg)

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
            mapping_idx = mapping_index_map(base_mappings)
            merged_mappings = copy.deepcopy(base_mappings)

            remove_indices = sorted(
                [mapping_idx[row_key] for row_key in removed_keys if row_key in mapping_idx],
                reverse=True,
            )
            for idx in remove_indices:
                del merged_mappings[idx]

            mapping_idx = mapping_index_map(merged_mappings)

            for row_key, row_cfg in row_values:
                if row_key in mapping_idx:
                    idx = mapping_idx[row_key]
                    merged_mappings[idx] = deep_apply_patch(merged_mappings[idx], row_cfg)
                else:
                    merged_mappings.append(deep_apply_patch(copy.deepcopy(NEW_MAPPING_TEMPLATE), row_cfg))

            update_controller_override(mac, ["mappings"], merged_mappings)

        self._loaded_row_keys = visible_keys
