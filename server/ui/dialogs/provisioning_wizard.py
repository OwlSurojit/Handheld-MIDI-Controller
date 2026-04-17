from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

from server.provisioning_service import ProvisioningService


INTRO_TEXT = "This wizard will guide you through setting up your handheld MIDI controllers on your Wi-Fi network for the first time." \
"Make sure your controllers are powered on and in provisioning mode (LED rapidly blinking) before starting the setup." \
"As part of the setup, the server will connect to each controller's temporary AP one at a time, so Wi-Fi will disconnect briefly during the process."

TITLE_STYLE = "font-weight: 600; font-size: 16px;"

class ProvisioningWizard(QDialog):
    def __init__(self, provisioning_service: ProvisioningService, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Controller Setup Wizard")
        self.resize(500, 300)

        self._provisioning = provisioning_service
        self._started = False

        self._stack = QStackedWidget()
        self._device_list = QListWidget()
        self._ssid_combo = QComboBox()
        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.Password)

        self._back_btn = QPushButton("< Back")
        self._next_btn = QPushButton("Next >")
        self._cancel_btn = QPushButton("Cancel")
        self._finish_btn = QPushButton("Finish")
        self._finish_btn.setAutoDefault(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)
        root.addWidget(self._stack, 1)
        root.addLayout(self._build_nav_row())

        self._stack.addWidget(self._build_intro_step())
        self._stack.addWidget(self._build_device_step())
        self._stack.addWidget(self._build_network_step())

        self._back_btn.clicked.connect(self._go_back)
        self._next_btn.clicked.connect(self._go_next)
        self._cancel_btn.clicked.connect(self.reject)        
        self._finish_btn.clicked.connect(self._apply)
        self._password_input.returnPressed.connect(self._apply)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(5000)
        self._refresh_timer.timeout.connect(self._refresh_devices)

        self._set_controls_enabled(False)
        self._update_nav_buttons()
        
        self.finished.connect(self._reconnect_previous_wifi)

    def _build_intro_step(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        
        title = QLabel("Controller Setup Wizard")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        intro = QLabel(INTRO_TEXT)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        
        layout.addStretch(1)
        
        start_btn = QPushButton("Start")
        start_btn.setStyleSheet("font-size: 11pt")
        start_btn.setMinimumSize(120, 36)
        start_btn.clicked.connect(self._start_session)

        start_row = QHBoxLayout()
        start_row.addStretch()
        start_row.addWidget(start_btn)
        start_row.addStretch()
        layout.addLayout(start_row)

        layout.addStretch(1)
        return page

    def _build_device_step(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setSpacing(8)

        title = QLabel("Step 1: Select Controllers")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        description = QLabel("Choose the controllers to configure. If your controller doesn't show up, make sure it's turned on and in provisioning mode. You might need to reset it to factory settings by holding the reset button for 10s (will delete all stored credentials)")
        description.setWordWrap(True)
        layout.addWidget(description)

        self._device_list.itemChanged.connect(self._update_nav_buttons)
        layout.addWidget(self._device_list, 1)

        controls = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_devices)
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all_devices)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_device_selection)
        
        controls.addWidget(refresh_btn)
        controls.addWidget(select_all_btn)
        controls.addWidget(clear_btn)
        controls.addStretch()

        layout.addLayout(controls)
        return page

    def _build_network_step(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setSpacing(8)

        title = QLabel("Step 2: Wi-Fi Credentials")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        description = QLabel("Select the WiFi network which the controllers should connect to and enter its password. Your computer should be connected to the same network (either wired or wirelessly).")
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QFormLayout()
        self._ssid_combo.setEditable(True)
        self._ssid_combo.setInsertPolicy(QComboBox.NoInsert)
        refresh_btn = QPushButton("Refresh Networks")
        refresh_btn.clicked.connect(self._load_ssids)
        
        view_password_btn = QToolButton()
        view_password_btn.setIcon(qta.icon("fa5s.eye"))
        view_password_btn.setToolTip("Show/Hide Password")
        view_password_btn.setCheckable(True)
        view_password_btn.toggled.connect(lambda checked: self._password_input.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password))

        ssid_row = QHBoxLayout()
        ssid_row.setContentsMargins(0, 0, 0, 0)
        ssid_row.addWidget(self._ssid_combo, 1)
        ssid_row.addWidget(refresh_btn)
        password_row = QHBoxLayout()
        password_row.setContentsMargins(0,0,0,0)
        password_row.addWidget(self._password_input)
        password_row.addWidget(view_password_btn)
        form.addRow("SSID", ssid_row)
        form.addRow("Password", password_row)
        layout.addLayout(form)

        line_edit = self._ssid_combo.lineEdit()
        if line_edit is not None:
            line_edit.returnPressed.connect(self._apply)

        layout.addStretch(1)
        return page

    def _build_nav_row(self) -> QHBoxLayout:
        nav = QHBoxLayout()
        nav.addStretch()
        nav.addWidget(self._back_btn)
        nav.addWidget(self._next_btn)
        nav.addWidget(self._finish_btn)
        nav.addWidget(self._cancel_btn)
        return nav
    
    def _selected_aps_as_dict(self) -> dict[str, bool]:
        selected: dict[str, bool] = {}
        for index in range(self._device_list.count()):
            item = self._device_list.item(index)
            if item is None:
                continue
            ssid = item.data(Qt.ItemDataRole.UserRole)
            selected[ssid] = item.checkState() == Qt.CheckState.Checked
        return selected

    def _selected_aps(self) -> list[str]:
        return [ssid for ssid, sel in self._selected_aps_as_dict().items() if sel]

    def _refresh_devices(self):
        previous = self._selected_aps_as_dict()
        ap_ssids = self._provisioning.list_controller_aps()

        self._device_list.blockSignals(True)
        self._device_list.clear()

        if not ap_ssids:
            placeholder = QListWidgetItem("No controller AP SSIDs found yet.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._device_list.addItem(placeholder)
            self._device_list.blockSignals(False)
            self._update_nav_buttons()
            return

        for ap_ssid in ap_ssids:
            item = QListWidgetItem(ap_ssid)
            item.setData(Qt.ItemDataRole.UserRole, ap_ssid)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(Qt.CheckState.Checked if previous.get(ap_ssid, True) else Qt.CheckState.Unchecked)
            self._device_list.addItem(item)

        self._device_list.blockSignals(False)
        self._update_nav_buttons()

    def _select_all_devices(self):
        for index in range(self._device_list.count()):
            item = self._device_list.item(index)
            if item is not None and isinstance(item.data(Qt.ItemDataRole.UserRole), str):
                item.setCheckState(Qt.CheckState.Checked)
        self._update_nav_buttons()

    def _clear_device_selection(self):
        for index in range(self._device_list.count()):
            item = self._device_list.item(index)
            if item is not None and isinstance(item.data(Qt.ItemDataRole.UserRole), str):
                item.setCheckState(Qt.CheckState.Unchecked)
        self._update_nav_buttons()

    def _load_ssids(self):
        current = self._provisioning.current_wifi()
        values = self._provisioning.list_target_ssids()

        previous = self._ssid_combo.currentText().strip()
        self._ssid_combo.clear()
        self._ssid_combo.addItems(values)

        preferred = previous or current
        if preferred:
            idx = self._ssid_combo.findText(preferred)
            if idx >= 0:
                self._ssid_combo.setCurrentIndex(idx)
            else:
                self._ssid_combo.setEditText(preferred)

    def _go_next(self):
        if self._stack.currentIndex() == 1 and not self._selected_aps():
            QMessageBox.warning(self, "No Devices Selected", "Select at least one device to continue.")
            return
        self._stack.setCurrentIndex(min(self._stack.currentIndex() + 1, self._stack.count() - 1))
        self._update_nav_buttons()

    def _go_back(self):
        self._stack.setCurrentIndex(max(self._stack.currentIndex() - 1, 0))
        self._update_nav_buttons()

    def _apply(self):
        if not self._started:
            QMessageBox.warning(self, "Setup Not Started", "Click Start before configuring devices.")
            return

        selected_aps = self._selected_aps()
        if not selected_aps:
            QMessageBox.warning(self, "No Devices Selected", "Select at least one device to configure.")
            return

        ssid = self._ssid_combo.currentText().strip()
        password = self._password_input.text()

        if not ssid:
            QMessageBox.warning(self, "SSID Required", "Select or enter an SSID.")
            return

        results = self._provisioning.provision_access_points(selected_aps, ssid, password)
        ok_count = sum(1 for status in results.values() if status == "ok")

        QMessageBox.information(
            self,
            "Setup Finished",
            f"Successfully provisioned {ok_count} of {len(selected_aps)} device(s).\nIf your computer is connected to the same network as the devices, they should be registered within a few seconds. Otherwise you might need to double-check the credentials you entered.",
        )
        self.accept()

    def _set_controls_enabled(self, enabled: bool):
        self._device_list.setEnabled(enabled)
        self._ssid_combo.setEnabled(enabled)
        self._password_input.setEnabled(enabled)

    def _start_session(self):
        if self._started:
            return

        user_ok = QMessageBox.question(
            self,
            "Start Setup",
            "Starting setup may temporarily disconnect Wi-Fi while scanning and provisioning. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if user_ok != QMessageBox.Yes:
            return

        self._provisioning.start_setup_session()
        self._started = True
        self._set_controls_enabled(True)
        self._refresh_timer.start()
        self._load_ssids()
        self._refresh_devices()
        self._stack.setCurrentIndex(1)
        self._update_nav_buttons()

    def _update_nav_buttons(self):
        step = self._stack.currentIndex()
        on_intro = step == 0
        on_devices = step == 1
        on_network = step == 2

        self._back_btn.setEnabled(on_network)
        self._next_btn.setEnabled(on_devices)
        self._finish_btn.setEnabled(on_network)
        
    def _reconnect_previous_wifi(self):
        reconnected = self._provisioning.end_setup_session()
        if not reconnected:
            QMessageBox.warning(
                self,
                "Reconnect Failed",
                "Could not automatically restore the previous Wi-Fi network. You may need to reconnect manually.",
            )

    def closeEvent(self, a0):
        self._refresh_timer.stop()
        # if self._started:
        #     self._reconnect_previous_wifi()
        super().closeEvent(a0)
        
    
