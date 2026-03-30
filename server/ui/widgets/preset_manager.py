from typing import cast

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QSizePolicy, QToolButton, QWidget
import qtawesome as qta

from server.config import (
    delete_preset,
    get_version,
    list_presets,
    load_default_config,
    load_preset,
    preset_exists,
    save_preset,
    set_presets_directory,
)


class PresetBar(QWidget):
    DEFAULT_PRESET_NAME = "Default"

    config_reloaded = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_preset_name: str | None = None
        self._preset_base_version = get_version()
        self._selection_guard = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Preset:"))

        self.preset_selector = QComboBox()
        self.preset_selector.setMinimumContentsLength(14)
        self.preset_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.preset_selector.setToolTip("Choose preset")
        self.preset_selector.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.preset_selector.currentTextChanged.connect(self._on_preset_changed)
        layout.addWidget(self.preset_selector)

        self.save_button = QToolButton()
        self.save_button.setIcon(qta.icon("fa5s.save"))
        self.save_button.setToolTip("Save to current preset")
        self.save_button.clicked.connect(self._on_save_clicked)
        layout.addWidget(self.save_button)

        self.save_as_button = QToolButton()
        self.save_as_button.setIcon(qta.icon("fa5s.file-medical"))
        self.save_as_button.setToolTip("Save as new preset")
        self.save_as_button.clicked.connect(self._on_save_as_clicked)
        layout.addWidget(self.save_as_button)

        self.delete_button = QToolButton()
        self.delete_button.setIcon(qta.icon("fa5s.trash-alt"))
        self.delete_button.setToolTip("Delete selected preset")
        self.delete_button.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.delete_button)

        self.folder_button = QToolButton()
        self.folder_button.setIcon(qta.icon("fa5s.folder"))
        self.folder_button.setToolTip("Set preset folder")
        self.folder_button.clicked.connect(self.open_set_presets_folder_dialog)
        layout.addWidget(self.folder_button)

        self.refresh_presets(select_name=PresetBar.DEFAULT_PRESET_NAME)
        self._current_preset_name = PresetBar.DEFAULT_PRESET_NAME
        self._capture_baseline()

    def _capture_baseline(self):
        self._preset_base_version = get_version()

    def _is_dirty(self) -> bool:
        return self._current_preset_name is not None and get_version() != self._preset_base_version

    def _is_default_selected(self) -> bool:
        return self._current_preset_name == PresetBar.DEFAULT_PRESET_NAME

    def refresh_presets(self, select_name: str | None = None):
        names = [name for name in list_presets() if name != PresetBar.DEFAULT_PRESET_NAME]
        current = select_name if select_name is not None else self.preset_selector.currentText().strip()

        self._selection_guard = True
        self.preset_selector.blockSignals(True)
        self.preset_selector.clear()
        self.preset_selector.addItem(PresetBar.DEFAULT_PRESET_NAME)
        self.preset_selector.addItems(names)

        target = current if current else PresetBar.DEFAULT_PRESET_NAME
        idx = self.preset_selector.findText(target)
        if idx < 0:
            idx = self.preset_selector.findText(PresetBar.DEFAULT_PRESET_NAME)
        self.preset_selector.setCurrentIndex(idx)
        self.preset_selector.blockSignals(False)
        self._selection_guard = False

        selected = self.preset_selector.currentText().strip()
        self._current_preset_name = selected or None
        self.delete_button.setEnabled(bool(selected) and selected != PresetBar.DEFAULT_PRESET_NAME)

    def handle_external_config_replaced(self):
        self._current_preset_name = None
        self._capture_baseline()
        self._selection_guard = True
        self.preset_selector.blockSignals(True)
        self.preset_selector.setCurrentIndex(-1)
        self.preset_selector.blockSignals(False)
        self._selection_guard = False
        self.delete_button.setEnabled(False)

    def open_set_presets_folder_dialog(self):
        selected = QFileDialog.getExistingDirectory(self, "Select Preset Folder")
        if not selected:
            return
        try:
            set_presets_directory(selected)
            keep = self._current_preset_name or PresetBar.DEFAULT_PRESET_NAME
            self.refresh_presets(select_name=keep)
        except Exception as exc:
            QMessageBox.critical(self, "Folder Error", str(exc))

    def _prompt_save_before_switch(self) -> bool:
        if not self._is_dirty():
            return True

        answer = QMessageBox.question(
            self,
            "Save Changes",
            f"Preset '{self._current_preset_name}' has unsaved changes. Save before switching?",
            cast(
                QMessageBox.StandardButtons,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            ),
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Yes:
            if not self._save_to_current_or_save_as():
                return False
        return True

    def _save_as_dialog(self) -> str | None:
        name, ok = QInputDialog.getText(self, "Save As New Preset", "Preset name:")
        if not ok:
            return None

        safe_name = name.strip().replace(" ", "_")
        if not safe_name:
            QMessageBox.warning(self, "Preset Missing", "Preset name cannot be empty.")
            return None
        if safe_name == PresetBar.DEFAULT_PRESET_NAME:
            QMessageBox.warning(self, "Reserved Name", "'Default' is reserved and cannot be overwritten.")
            return None

        if preset_exists(safe_name):
            answer = QMessageBox.question(
                self,
                "Overwrite Preset",
                f"Preset '{safe_name}' already exists. Overwrite it?",
                cast(
                    QMessageBox.StandardButtons,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                ),
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return None
        return safe_name

    def _save_to_current_or_save_as(self) -> bool:
        current = self._current_preset_name
        if current and current != PresetBar.DEFAULT_PRESET_NAME:
            try:
                save_preset(current)
                self.refresh_presets(select_name=current)
                self._capture_baseline()
                return True
            except Exception as exc:
                QMessageBox.critical(self, "Preset Save Failed", str(exc))
                return False

        safe_name = self._save_as_dialog()
        if not safe_name:
            return False
        try:
            save_preset(safe_name)
            self.refresh_presets(select_name=safe_name)
            self._current_preset_name = safe_name
            self._capture_baseline()
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Preset Save Failed", str(exc))
            return False

    def _load_selected(self, preset_name: str) -> bool:
        try:
            if preset_name == PresetBar.DEFAULT_PRESET_NAME:
                load_default_config()
            else:
                load_preset(preset_name)
            self._current_preset_name = preset_name
            self._capture_baseline()
            self.delete_button.setEnabled(preset_name != PresetBar.DEFAULT_PRESET_NAME)
            self.config_reloaded.emit()
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Preset Load Failed", str(exc))
            return False

    def _on_preset_changed(self, preset_name: str):
        if self._selection_guard:
            return
        if not preset_name:
            return

        previous = self._current_preset_name
        if preset_name == previous:
            return

        if not self._prompt_save_before_switch():
            self._selection_guard = True
            self.preset_selector.blockSignals(True)
            if previous:
                idx = self.preset_selector.findText(previous)
                self.preset_selector.setCurrentIndex(idx if idx >= 0 else -1)
            else:
                self.preset_selector.setCurrentIndex(-1)
            self.preset_selector.blockSignals(False)
            self._selection_guard = False
            return

        if self._load_selected(preset_name):
            return

        # Restore old selection on load failure
        self._selection_guard = True
        self.preset_selector.blockSignals(True)
        if previous:
            idx = self.preset_selector.findText(previous)
            self.preset_selector.setCurrentIndex(idx if idx >= 0 else -1)
        else:
            self.preset_selector.setCurrentIndex(-1)
        self.preset_selector.blockSignals(False)
        self._selection_guard = False

    def _on_save_clicked(self):
        self._save_to_current_or_save_as()

    def _on_save_as_clicked(self):
        safe_name = self._save_as_dialog()
        if not safe_name:
            return
        try:
            save_preset(safe_name)
            self.refresh_presets(select_name=safe_name)
            self._current_preset_name = safe_name
            self._capture_baseline()
        except Exception as exc:
            QMessageBox.critical(self, "Preset Save Failed", str(exc))

    def _on_delete_clicked(self):
        preset_name = self.preset_selector.currentText().strip()
        if not preset_name:
            QMessageBox.information(self, "No Preset", "Select a preset to delete.")
            return
        if preset_name == PresetBar.DEFAULT_PRESET_NAME:
            QMessageBox.information(self, "Protected Preset", "The Default preset cannot be deleted.")
            return

        answer = QMessageBox.question(
            self,
            "Delete Preset",
            f"Delete preset '{preset_name}'?",
            cast(
                QMessageBox.StandardButtons,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ),
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_preset(preset_name)
            # After deleting currently selected preset, fall back to Default.
            self.refresh_presets(select_name=PresetBar.DEFAULT_PRESET_NAME)
            if self._current_preset_name == preset_name:
                self._load_selected(PresetBar.DEFAULT_PRESET_NAME)
        except Exception as exc:
            QMessageBox.critical(self, "Preset Delete Failed", str(exc))
