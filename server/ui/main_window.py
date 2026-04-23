import sys
import os
from typing import Any
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
    QSplitter,
    QLabel,
)
from PyQt5.QtGui import QKeySequence, QPixmap

from server.config import (
    import_config_from_file,
    set_controller_muted,
)
from server.communication import CommunicationThread
from server.provisioning_service import ProvisioningService
from server.shared_state import controllers
from server.runtime_paths import get_resource_path
from server.ui.dialogs.provisioning_wizard import ProvisioningWizard
import server.ui.widgets.controller_config_panel as controller_config_panel
from server.ui.widgets.controller_list import ControllerListWidget
from server.ui.widgets.preset_manager import PresetBar


class MainWindow(QMainWindow):
    def __init__(
        self,
        provisioning_service: ProvisioningService | None = None,
        communication_thread: CommunicationThread | None = None,
    ):
        super().__init__()
        self.setWindowTitle("Handheld MIDI Controller")
        self.setGeometry(100, 100, 980, 620)
        self.provisioning_service = provisioning_service
        self.communication_thread = communication_thread

        self.visualiser_windows: dict[bytes, Any] = {}

        root = QWidget(self)
        self.setCentralWidget(root)
        self.root_layout = QVBoxLayout(root)
        self.root_layout.setContentsMargins(12, 12, 12, 12)
        self.root_layout.setSpacing(10)

        self._build_top_bar()
        self._build_controller_list()
        self._build_menu_bar()

        self._refresh_panel_selection()

    def _build_top_bar(self):
        from PyQt5.QtWidgets import QHBoxLayout

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        
        logo = QLabel()
        logo_path = get_resource_path(os.path.join("server", "ui", "img", "yy_logo.jpg"))
        logo.setPixmap(QPixmap(logo_path).scaledToHeight(32, Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel(text="Handheld MIDI Controllers")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        top_bar.addWidget(logo)
        top_bar.addWidget(title)

        top_bar.addStretch()  # Pushes the preset bar to the right

        self.preset_bar = PresetBar()
        self.preset_bar.config_reloaded.connect(self._on_preset_config_reloaded)
        top_bar.addWidget(self.preset_bar, 0, Qt.AlignmentFlag.AlignRight)

        self.root_layout.addLayout(top_bar)

    def _build_controller_list(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.controller_list = ControllerListWidget()
        self.controller_list.setMinimumWidth(420)
        self.controller_list.focused_controller_changed.connect(self.on_focused_controller_changed)
        self.controller_list.selection_changed.connect(self.on_selection_changed)
        self.controller_list.visualise_requested.connect(self.open_visualiser)
        self.controller_list.mute_selected_requested.connect(self.on_mute_selected)
        self.controller_list.unmute_selected_requested.connect(self.on_unmute_selected)
        self.controller_list.rezero_selected_requested.connect(self.on_rezero_selected)
        self.controller_list.identify_requested.connect(self.on_identify_requested)
        self.controller_list.setup_wizard_requested.connect(self.open_provisioning_wizard)

        self.config_panel = controller_config_panel.ControllerConfigPanel()
        self.config_panel.setMinimumWidth(360)
        splitter.addWidget(self.controller_list)
        splitter.addWidget(self.config_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        self.root_layout.addWidget(splitter, stretch=1)

    def _build_menu_bar(self):
        menu_bar = self.menuBar()
        if menu_bar is None:
            return

        file_menu = menu_bar.addMenu("File")
        if file_menu is None:
            return
        file_menu.addAction("Import Config YAML...", self.on_import_config, QKeySequence("Ctrl+O"))
        file_menu.addAction("Save Config", self.on_save_config, QKeySequence("Ctrl+S"))
        file_menu.addSeparator()
        file_menu.addAction("Set Preset Folder...", self.preset_bar.open_set_presets_folder_dialog)
        file_menu.addAction("Quit", self.close)

        controllers_menu = menu_bar.addMenu("Controllers")
        if controllers_menu is not None:
            controllers_menu.addAction("Controller Setup Wizard", self.open_provisioning_wizard)

    def closeEvent(self, a0):
        super().closeEvent(a0)

    def on_focused_controller_changed(self, _controller_mac):
        self._refresh_panel_selection()

    def on_selection_changed(self):
        self._refresh_panel_selection()

    def _on_preset_config_reloaded(self):
        self.controller_list.sync_runtime_settings()
        self.controller_list.rebuild()
        self._refresh_panel_selection(force_reload=True)

    def _refresh_panel_selection(self, force_reload: bool = False):
        selected = [mac for mac in self.controller_list.selected_controller_ids() if mac in controllers]
        if not selected:
            self.config_panel.set_controllers([])
            return
        self.config_panel.set_controllers(selected, force_reload=force_reload)

    def _selected_states(self):
        return self.controller_list.selected_states()

    def on_rezero_selected(self):
        for state in self._selected_states():
            state.re_zero()

    def on_mute_selected(self):
        for state in self._selected_states():
            set_controller_muted(state.mac, True)
            state.set_muted(True)
        self.controller_list.refresh_visible_cards()

    def on_unmute_selected(self):
        for state in self._selected_states():
            set_controller_muted(state.mac, False)
            state.set_muted(False)
        self.controller_list.refresh_visible_cards()

    def on_identify_requested(self, controller_mac: bytes):
        if self.communication_thread is None:
            QMessageBox.warning(self, "Identify Unavailable", "Communication thread is not ready.")
            return
        ok = self.communication_thread.send_identify(controller_mac)
        if not ok:
            QMessageBox.warning(self, "Identify Failed", "Unable to queue identify request.")

    def on_import_config(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Config", "", "YAML Files (*.yaml *.yml)")
        if not file_path:
            return
        try:
            import_config_from_file(file_path, replace=True)
            self.controller_list.sync_runtime_settings()
            self.controller_list.rebuild()
            self._refresh_panel_selection(force_reload=True)
            self.preset_bar.handle_external_config_replaced()
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", str(exc))

    def on_save_config(self):
        if (self.preset_bar._save_to_current_or_save_as()):
            QMessageBox.information(self, "Config Saved", f"Config saved as {self.preset_bar._current_preset_name}")
        else:
            QMessageBox.critical(self, "Save Failed", "Failed to save config.")

    def open_visualiser(self, controller_id: bytes):
        try:
            from server.ui.dialogs.visualiser_window import VisualiserWindow
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Visualiser Unavailable",
                "Unable to open the visualiser window.\n\n"
                f"Details: {exc}",
            )
            return

        if controller_id in self.visualiser_windows:
            try:
                self.visualiser_windows[controller_id].show()
                self.visualiser_windows[controller_id].raise_()
                self.visualiser_windows[controller_id].activateWindow()
                return
            except RuntimeError:
                pass

        viz_win = VisualiserWindow(controller_id)
        self.visualiser_windows[controller_id] = viz_win
        viz_win.show()

    def open_provisioning_wizard(self):
        provisioning_service = self.provisioning_service
        if provisioning_service is None:
            QMessageBox.warning(self, "Setup Unavailable", "Provisioning is unavailable: communication thread not ready.")
            return

        wizard = ProvisioningWizard(
            provisioning_service=provisioning_service,
            parent=self,
        )
        wizard.exec_()


def launch_ui(
    provisioning_service: ProvisioningService | None = None,
    communication_thread: CommunicationThread | None = None,
):
    aa_share_gl = getattr(Qt, "AA_ShareOpenGLContexts", None)
    if aa_share_gl is not None:
        QApplication.setAttribute(aa_share_gl, True)
    app = QApplication(sys.argv)

    main_win = MainWindow(
        provisioning_service=provisioning_service,
        communication_thread=communication_thread,
    )
    main_win.show()
    return app.exec_()
