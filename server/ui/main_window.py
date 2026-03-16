import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
    QListWidget, QPushButton, QComboBox, QLabel, QFormLayout
)
from PyQt5.QtCore import QTimer

from server.config import get_config, load_config
from server.scales import SCALES

class MainWindow(QMainWindow):
    def __init__(self, get_controllers_func):
        super().__init__()
        self.get_controllers = get_controllers_func
        self.setWindowTitle("Handheld MIDI Controller - Settings")
        self.setGeometry(100, 100, 500, 400)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # --- Controllers Tab ---
        self.controllers_tab = QWidget()
        self.tabs.addTab(self.controllers_tab, "Controllers")
        self.controllers_layout = QVBoxLayout()
        self.controllers_tab.setLayout(self.controllers_layout)
        
        self.controller_list = QListWidget()
        self.controllers_layout.addWidget(self.controller_list)

        self.rezero_button = QPushButton("Re-zero All Controllers")
        self.rezero_button.clicked.connect(self.re_zero_all)
        self.controllers_layout.addWidget(self.rezero_button)

        # --- Scale & Zones Tab ---
        self.scale_tab = QWidget()
        self.tabs.addTab(self.scale_tab, "Scale & Zones")
        self.scale_layout = QFormLayout()
        self.scale_tab.setLayout(self.scale_layout)

        self.scale_selector = QComboBox()
        self.scale_selector.addItems(SCALES.keys())
        self.scale_layout.addRow(QLabel("Musical Scale:"), self.scale_selector)
        
        # Load initial config value
        try:
            config = get_config()
            current_scale = config.get('scale', {}).get('scale', 'pentatonic_major')
            self.scale_selector.setCurrentText(current_scale)
        except (FileNotFoundError, KeyError):
            pass # Use default if config not loaded yet

        self.scale_selector.currentTextChanged.connect(self.on_scale_change)

        # Timer to update controller list
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_controller_list)
        self.timer.start(1000) # Update every second

    def update_controller_list(self):
        controllers = self.get_controllers()
        self.controller_list.clear()
        if not controllers:
            self.controller_list.addItem("No controllers detected.")
            return

        for cid, state in sorted(controllers.items()):
            self.controller_list.addItem(f"ID: {state.id}  |  IP: {state.source_ip}  |  Channel: {state.id + 1}")

    def re_zero_all(self):
        controllers = self.get_controllers()
        for state in controllers.values():
            state.re_zero()
        print("UI: Re-zero signal sent to all controllers.")

    def on_scale_change(self, new_scale):
        # In a real implementation, this would use the config_sync mechanism
        # to update the server's running config. For now, we just print.
        # This requires a thread-safe way to modify the config.
        print(f"UI: Scale changed to {new_scale}. (Note: Hot-reload not fully implemented in this iteration)")
        # Example of how it would work:
        # from server.config_sync import update_config
        # update_config(['scale', 'scale'], new_scale)


def launch_ui(get_controllers_func):
    """Entry point for launching the PyQt application."""
    app = QApplication(sys.argv)
    # Ensure config is loaded before UI
    try:
        load_config()
    except FileNotFoundError as e:
        print(f"Could not load config for UI: {e}")

    main_win = MainWindow(get_controllers_func)
    main_win.show()
    sys.exit(app.exec_())
