from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from server.config import get_controller_name
from server.midi_mapper import MidiMapper
from server.ui.widgets.hit_machine_config_group import HitMachineConfigGroup
from server.ui.widgets.mapping_config_group import MappingConfigGroup


class ControllerConfigPanel(QWidget):
    def __init__(
        self,
        midi_mapper: MidiMapper,
        parent=None,
    ):
        super().__init__(parent)
        self.controller_macs: list[bytes] = []
        self._loaded_for: tuple[bytes, ...] | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        self.title = QLabel("Select a controller")
        title_font = self.title.font()
        title_font.setBold(True)
        if title_font.pointSize() > 0:
            title_font.setPointSize(title_font.pointSize() + 4)
        self.title.setFont(title_font)
        root.addWidget(self.title)

        self.mappings_section = MappingConfigGroup(midi_mapper=midi_mapper, parent=self)
        root.addWidget(self.mappings_section)

        self.hit_section = HitMachineConfigGroup(parent=self)
        root.addWidget(self.hit_section)

        root.addStretch()

        self.setDisabled(True)

    def set_controllers(self, controller_macs: list[bytes], force_reload: bool = False):
        unique = tuple(sorted(set(controller_macs)))
        self.controller_macs = list(unique)
        if not unique:
            self.title.setText("Select one or more controllers")
            self.mappings_section.set_controllers([])
            self.hit_section.set_controllers([])
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
        selected_macs = list(unique)
        self.mappings_section.set_controllers(selected_macs)
        self.hit_section.set_controllers(selected_macs)
        self._loaded_for = unique
