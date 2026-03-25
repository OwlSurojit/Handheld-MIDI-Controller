import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QComboBox, QLabel, QFormLayout
)
from PyQt5.QtCore import QTimer, pyqtSignal, Qt

from server.shared_state import controllers, register_new_controller_callback
from server.config import get_config, load_config
from server.scales import SCALES
from server.ui.dialogs.visualiser_window import VisualiserWindow


class MainWindow(QMainWindow):
    new_controller_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Handheld MIDI Controller - Settings")
        self.setGeometry(100, 100, 500, 400)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        self.visualiser_windows: dict[bytes, VisualiserWindow] = {}

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
        
        # Connect the signal up
        self.new_controller_signal.connect(self.on_new_controller)
        register_new_controller_callback(self.new_controller_signal.emit)

        # Do an initial populate
        self.update_controller_list()

    def on_new_controller(self, state):
        self.update_controller_list()

    def update_controller_list(self):
        self.controller_list.clear()
        if not controllers:
            self.controller_list.addItem("No controllers detected.")
            return

        for mac, state in sorted(controllers.items()):
            item = QListWidgetItem(self.controller_list)
            
            widget = QWidget()
            layout = QHBoxLayout()
            layout.setContentsMargins(5, 5, 5, 5)
            
            info_label = QLabel(f"MAC: {state.mac.hex()}  |  IP: {state.source_ip}  |  Channel: {state.midi_channel}")
            viz_button = QPushButton("Visualise")
            
            layout.addWidget(info_label)
            layout.addStretch()
            layout.addWidget(viz_button)
            widget.setLayout(layout)
            
            viz_button.clicked.connect(lambda checked, idx=mac: self.open_visualiser(idx))
            
            item.setSizeHint(widget.sizeHint())
            self.controller_list.setItemWidget(item, widget)

    def open_visualiser(self, controller_id):
        if controller_id in self.visualiser_windows:
            try:
                print(f"Visualiser for controller {controller_id.hex()} opening/bringing to front.")
                self.visualiser_windows[controller_id].show()
                self.visualiser_windows[controller_id].raise_()
                self.visualiser_windows[controller_id].activateWindow()
                return
            except RuntimeError:
                pass
            
        viz_win = VisualiserWindow(controller_id)
        
        self.visualiser_windows[controller_id] = viz_win
        viz_win.show()

    def re_zero_all(self):
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


def launch_ui():
    """Entry point for launching the PyQt application."""
    # pyqtgraph OpenGL items cache shader programs at class scope.
    # Sharing contexts keeps those programs valid across multiple GLViewWidget windows.
    aa_share_gl = getattr(Qt, "AA_ShareOpenGLContexts", None)
    if aa_share_gl is not None:
        QApplication.setAttribute(aa_share_gl, True)
    app = QApplication(sys.argv)
    # Ensure config is loaded before UI
    try:
        load_config()
    except FileNotFoundError as e:
        print(f"Could not load config for UI: {e}")

    main_win = MainWindow()
    main_win.show()
    return app.exec_()
