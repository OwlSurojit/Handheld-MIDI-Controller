import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QMdiSubWindow
from PyQt5.QtCore import QTimer, Qt

from server.shared_state import get_controller

class VisualiserWindow(QWidget):
    def __init__(self, controller_mac):
        super().__init__()
        # Removed WA_DeleteOnClose to avoid PyQtGraph OpenGL shader caching issues 
        # when recreating the GL context. Instead, we hide/show and pause the timer.
        self.controller_mac = controller_mac
        self.setWindowTitle(f"Visualiser - Controller {controller_mac}")
        self.resize(1000, 600)
        
        main_layout = QHBoxLayout(self)

        # --- 3D View (OpenGL) ---
        self.view_3d = gl.GLViewWidget()
        self.view_3d.opts['distance'] = 10
        main_layout.addWidget(self.view_3d, stretch=1)

        # Add grid and dummy 3D axis/box
        grid = gl.GLGridItem()
        self.view_3d.addItem(grid)
        self.box_mesh = gl.GLBoxItem(size=pg.Vector(2, 4, 1), color=(0, 255, 0, 100), glOptions='translucent')
        self.view_3d.addItem(self.box_mesh)

        # --- 2D Graphs Layout ---
        graphs_layout = QVBoxLayout()
        main_layout.addLayout(graphs_layout, stretch=1)

        # 2D Plot for Acceleration Magnitude
        self.accel_plot = pg.PlotWidget(title="Acceleration Magnitude")
        self.accel_plot.setLabel('left', 'Magnitude (g)')
        self.accel_plot.setLabel('bottom', 'Samples')
        self.curve_accel = self.accel_plot.plot(pen='r', name='Accel Mag')
        graphs_layout.addWidget(self.accel_plot)
        
        # 2D Plot for Gyro Magnitude
        self.gyro_plot = pg.PlotWidget(title="Angular Velocity Magnitude")
        self.gyro_plot.setLabel('left', 'Magnitude (deg/s)')
        self.gyro_plot.setLabel('bottom', 'Samples')
        self.curve_gyro = self.gyro_plot.plot(pen='g', name='Gyro Mag')
        graphs_layout.addWidget(self.gyro_plot)

        # History buffers for 2D graphing
        self.history_size = 150
        self.data_accel = []
        self.data_gyro = []

        # Timer to read active controller state and update plots
        self.timer = QTimer(self) # Parented to self so it cleans up properly
        self.timer.timeout.connect(self.update_views)
        self.timer.start(33) # ~30fps

    def hideEvent(self, event):
        """Pause drawing when window is hidden to save CPU/GPU."""
        self.timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        """Resume drawing when window is shown."""
        self.timer.start(33)
        super().showEvent(event)

    def update_views(self):
        # TODO !!!!! only extract the values we need
        state = get_controller(self.controller_mac)
        if not state:
            return
        
        angle, axis = state.get_angle_axis()
        self.setWindowTitle(f"Visualiser - Controller {self.controller_mac} | Angle: {np.degrees(angle):.1f}° Axis: ({axis[0]:.2f}, {axis[1]:.2f}, {axis[2]:.2f})")
        # Reset transform and apply new
        self.box_mesh.resetTransform()
        # Note: For GLBoxItem, the center is at (width/2, depth/2, height/2).
        # To rotate around origin, we shift it, rotate, and shift back, or just rotate.
        self.box_mesh.translate(-1, -2, -0.5)
        self.box_mesh.rotate(np.degrees(angle), axis[0], axis[1], axis[2])

        # 2. Update 2D Plot data
        # Use existing pre-calculated magnitudes from ControllerState
        self.data_accel.append(state.accel_mag)
        self.data_gyro.append(state.gyro_mag)
        
        if len(self.data_accel) > self.history_size:
            self.data_accel.pop(0)
            self.data_gyro.pop(0)

        self.curve_accel.setData(self.data_accel)
        self.curve_gyro.setData(self.data_gyro)
