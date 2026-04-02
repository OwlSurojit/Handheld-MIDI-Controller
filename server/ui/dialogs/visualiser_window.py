import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont, QKeyEvent
from server.shared_state import get_controller

class VisualiserWindow(QWidget):
    UPDATE_INTERVAL_MS = 33
    PLOT_UPDATE_EVERY_N_FRAMES = 3
    TEXT_UPDATE_EVERY_N_FRAMES = 1
    HISTORY_SIZE = 150

    def __init__(self, controller_mac):
        super().__init__()
        # Keep widget lifecycle simple; OpenGL context sharing is configured at app startup.
        self.controller_mac = controller_mac
        self.is_paused = False
        self._frame_count = 0
        self.setWindowTitle(f"Visualiser - Controller {controller_mac.hex()}")
        #self.resize(1000, 600)
        #self.showFullScreen()
        
        main_layout = QVBoxLayout(self)
        visuals_layout = QHBoxLayout()

        self.info_text = QLabel("Swing: 0.0 | Twist: 0.0")
        self.info_text.setFont(QFont("Courier", 7))
        main_layout.addWidget(self.info_text)
        main_layout.addLayout(visuals_layout)

        # --- 3D View (OpenGL) ---
        self.view_3d = gl.GLViewWidget()
        self.view_3d.setCameraPosition(distance=10.0)
        visuals_layout.addWidget(self.view_3d, stretch=1)

        # Add grid and dummy 3D axis/box
        grid = gl.GLGridItem(antialias=False)
        self.view_3d.addItem(grid)
        self.box_mesh = gl.GLBoxItem(size=pg.Vector(2, 4, 1), color=(0, 255, 0, 100), glOptions='translucent')
        self.view_3d.addItem(self.box_mesh)
        # self.accel_vector = gl.GLLinePlotItem(pos=np.array([[0,0,0], [0,0,1]]), color=(1, 0, 0, 255), width=3)
        # self.view_3d.addItem(self.accel_vector)
        # self.gyro_vector = gl.GLLinePlotItem(pos=np.array([[0,0,0], [0,1,0]]), color=(0, 0, 1, 255), width=3)
        # self.view_3d.addItem(self.gyro_vector)

        # --- 2D Graphs Layout ---
        graphs_layout = QVBoxLayout()
        visuals_layout.addLayout(graphs_layout, stretch=1)




        # 2D Plot for Acceleration Magnitude
        self.accel_plot = pg.PlotWidget(title="Acceleration")
        self.accel_plot.addLegend()
        self.accel_plot.setYRange(-5, 6)
        self.accel_plot.setLabel('left', 'Magnitude (g)')
        self.accel_plot.setLabel('bottom', 'Samples')
        self.curve_accel = self.accel_plot.plot(pen='r', name='Accel Mag')
        graphs_layout.addWidget(self.accel_plot)
        
        # 2D Plot for Gyro Magnitude
        self.gyro_plot = pg.PlotWidget(title="Angular Velocity")
        self.gyro_plot.addLegend()
        self.gyro_plot.setYRange(-1500, 1500)
        self.gyro_plot.setLabel('left', 'Magnitude (deg/s)')
        self.gyro_plot.setLabel('bottom', 'Samples')
        self.curve_gyro = self.gyro_plot.plot(pen='g', name='Gyro Mag')
        graphs_layout.addWidget(self.gyro_plot)

        self.curve_gyro_x = self.gyro_plot.plot(pen='b', name='Gyro X')
        self.curve_gyro_y = self.gyro_plot.plot(pen='m', name='Gyro Y')
        self.curve_gyro_z = self.gyro_plot.plot(pen='c', name='Gyro Z')

        self.curve_accel_x = self.accel_plot.plot(pen='b', name='Accel X')
        self.curve_accel_y = self.accel_plot.plot(pen='m', name='Accel Y')
        self.curve_accel_z = self.accel_plot.plot(pen='c', name='Accel Z')

        self.swing_plot = pg.PlotWidget(title="Up/Down Swing Acceleration")
        self.swing_plot.addLegend()
        self.swing_plot.setYRange(-200, 200)
        self.swing_plot.setLabel('left', 'Swing Acceleration')
        self.swing_plot.setLabel('bottom', 'Samples')
        self.curve_swing_ud_accel = self.swing_plot.plot(pen='y', name='Swing Acceleration')
        graphs_layout.addWidget(self.swing_plot)

        for curve in (
            self.curve_accel,
            self.curve_gyro,
            self.curve_gyro_x,
            self.curve_gyro_y,
            self.curve_gyro_z,
            self.curve_accel_x,
            self.curve_accel_y,
            self.curve_accel_z,
            self.curve_swing_ud_accel,
        ):
            curve.setClipToView(True)
            curve.setDownsampling(ds=2, auto=False, method='subsample')
            curve.setSkipFiniteCheck(True)

        # Timer to read active controller state and update plots
        self.timer = QTimer(self) # Parented to self so it cleans up properly
        coarse_timer = getattr(Qt, "CoarseTimer", None)
        if coarse_timer is not None:
            self.timer.setTimerType(coarse_timer)
        self.timer.timeout.connect(self.update_views)
        self.timer.start(self.UPDATE_INTERVAL_MS)

        #self.showMaximized()

    def hideEvent(self, a0):
        """Pause drawing when window is hidden to save CPU/GPU."""
        self.timer.stop()
        super().hideEvent(a0)

    def showEvent(self, a0):
        """Resume drawing when window is shown."""
        if self.timer and not self.timer.isActive():
            self.timer.start(self.UPDATE_INTERVAL_MS)
        super().showEvent(a0)

    def keyPressEvent(self, a0: QKeyEvent | None):
        """Handle spacebar to pause/resume updates."""
        if a0 and a0.key() == Qt.Key.Key_Space and not a0.isAutoRepeat():
            self.is_paused = not self.is_paused
            if self.is_paused:
                self.timer.stop()
            else:
                self.timer.start(self.UPDATE_INTERVAL_MS)
            a0.accept()
        else:
            super().keyPressEvent(a0)

    def update_views(self):
        state = get_controller(self.controller_mac)
        if not state:
            return

        snapshot = state.get_visualiser_snapshot()
        self._frame_count += 1
        
        angle = snapshot["angle"]
        axis = snapshot["axis"]

        # Reset transform and apply new
        self.box_mesh.resetTransform()
        # Note: For GLBoxItem, the center is at (width/2, depth/2, height/2).
        # To rotate around origin, we shift it, rotate, and shift back, or just rotate.
        self.box_mesh.translate(-1, -2, -0.5)
        self.box_mesh.rotate(np.degrees(angle), axis[0], axis[1], axis[2])
        # self.accel_vector.setData(pos=np.array([[0,0,0], state.swing_accel]))
        # self.gyro_vector.setData(pos=np.array([[0,0,0], state.swing_gyro / 100]))

        if self._frame_count % self.TEXT_UPDATE_EVERY_N_FRAMES == 0:
            self.info_text.setText(
                f'Swing: {snapshot["q_swing"]} | Twist: {snapshot["q_twist"]} | Twist Angle: {np.degrees(snapshot["twist_angle"]):.1f}°\n'
                f'Orig. Quat: {snapshot["quat"]}\n'
                f'Delta Quat: {snapshot["q_delta"]} | Angle: {np.degrees(angle):.1f}° Axis: ({axis[0]:.2f}, {axis[1]:.2f}, {axis[2]:.2f})'
            )

        if self._frame_count % self.PLOT_UPDATE_EVERY_N_FRAMES != 0:
            return

        self.curve_accel.setData(snapshot["accel_mag_history"])
        self.curve_gyro.setData(snapshot["gyro_mag_history"])
        self.curve_gyro_x.setData(snapshot["swing_gyro_x_history"])
        self.curve_gyro_y.setData(snapshot["swing_gyro_y_history"])
        self.curve_gyro_z.setData(snapshot["swing_gyro_z_history"])
        self.curve_accel_x.setData(snapshot["swing_accel_x_history"])
        self.curve_accel_y.setData(snapshot["swing_accel_y_history"])
        self.curve_accel_z.setData(snapshot["swing_accel_z_history"])
        self.curve_swing_ud_accel.setData(snapshot["swing_ud_accel_history"])
