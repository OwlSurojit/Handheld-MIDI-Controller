import numpy as np
import time
import threading
from collections import deque
from server.quaternion_utils import Quat

class ControllerState:

    TWIST_AXIS = np.array([0,1,0])
    HISTORY_LEN = 500

    """Holds the state for a single connected controller."""
    def __init__(self, controller_mac, source_ip, midi_channel):
        self.mac = controller_mac
        self.source_ip = source_ip
        self.midi_channel = midi_channel
        self.name = ""
        self.one_way_latency_ms = None
        self.data_rate = None
        self._muted = False
        self.last_packet_time = 0.0
        self.raw_data_queue = deque(maxlen=1)
        self._lock = threading.Lock()

        # One-Euro filters for all 10 incoming signals
        # The parameters can be tuned in config.yaml for each mapping
        # self.filters = {
        #     'quat_w': OneEuroFilter(freq=55, mincutoff=1.0, beta=0.0),
        #     'quat_x': OneEuroFilter(freq=55, mincutoff=1.0, beta=0.0),
        #     'quat_y': OneEuroFilter(freq=55, mincutoff=1.0, beta=0.0),
        #     'quat_z': OneEuroFilter(freq=55, mincutoff=1.0, beta=0.0),
        #     'accel_x': OneEuroFilter(freq=55, mincutoff=2.0, beta=0.02),
        #     'accel_y': OneEuroFilter(freq=55, mincutoff=2.0, beta=0.02),
        #     'accel_z': OneEuroFilter(freq=55, mincutoff=2.0, beta=0.02),
        #     'gyro_x': OneEuroFilter(freq=55, mincutoff=3.0, beta=0.05),
        #     'gyro_y': OneEuroFilter(freq=55, mincutoff=3.0, beta=0.05),
        #     'gyro_z': OneEuroFilter(freq=55, mincutoff=3.0, beta=0.05),
        # }

        # Filtered sensor values
        self.quat = Quat.identity()
        self.accel = np.array([0.0, 0.0, 0.0])
        self.gyro = np.array([0.0, 0.0, 0.0])
        self.accel_mag = 0.0
        self.gyro_mag = 0.0

        # Relative orientation
        self.q_ref = Quat.identity()  # Reference (zero) quaternion
        self.q_delta = Quat.identity()  # Relative rotation from q_ref
        self.q_angle, self.q_axis = 0.0, np.array([1.0, 0.0, 0.0])  # Angle-axis representation of q_delta
        self.q_swing, self.q_twist = Quat.identity(), Quat.identity()  # Swing-twist decomposition
        self.swing_lr = 0.0
        self.swing_ud = 0.0
        self.twist = 0.0
        self.swing_accel = np.array([0.0, 0.0, 0.0])
        self.swing_gyro = np.array([0.0, 0.0, 0.0])
        self.swing_gyro_ud = 0.0
        self.prev_swing_gyro_ud = 0.0
        self.swing_ud_accel = 0.0
        self.swing_gyro_lr = 0.0
        
        # Hit detection state machine
        self.hit_state = "idle"  # idle, armed, refractory
        self.hit_timestamp = 0.0
        self.last_note_time = 0.0
        self.hit_max_gyro = 0.0
        self.hit_last_gyro = 0.0
        self.hit_max_accel = 0.0
        self.current_note = 60
        self.on_notes = {} # note : [timestamps]

        # History for visualisation
        self.swing_accel_x_history = deque(maxlen=ControllerState.HISTORY_LEN)
        self.swing_accel_y_history = deque(maxlen=ControllerState.HISTORY_LEN)
        self.swing_accel_z_history = deque(maxlen=ControllerState.HISTORY_LEN)
        self.swing_gyro_x_history = deque(maxlen=ControllerState.HISTORY_LEN)
        self.swing_gyro_y_history = deque(maxlen=ControllerState.HISTORY_LEN)
        self.swing_gyro_z_history = deque(maxlen=ControllerState.HISTORY_LEN)
        self.accel_mag_history = deque(maxlen=ControllerState.HISTORY_LEN)
        self.gyro_mag_history = deque(maxlen=ControllerState.HISTORY_LEN)
        self.swing_ud_accel_history = deque(maxlen=ControllerState.HISTORY_LEN)

    def add_raw_data(self, ts, quat, accel, gyro):
        """Add raw data to the queue for processing."""
        with self._lock:
            self.raw_data_queue.append((ts, quat, accel, gyro))

    def process_raw_data(self):
        """
        Main processing function for a single controller's state.
        This is called on every iteration of the processing thread.
        """
        with self._lock:
            # 1. Pop data from the queue
            try:
                ts, raw_quat, raw_accel, raw_gyro = self.raw_data_queue.popleft()
            except IndexError:
                return # No new data

            self.quat = Quat.from_array(raw_quat).normalize()
            self.accel = np.array(raw_accel)
            self.gyro = np.array(raw_gyro)

            # 2. Calculate derived values
            self.q_delta = self.q_ref.conjugate() * self.quat
            self.q_angle, self.q_axis = self.q_delta.to_angle_axis()
            self.q_swing, self.q_twist = self.q_delta.to_swing_twist(ControllerState.TWIST_AXIS)
            self.twist = self.q_twist.y
            self.twist_angle = 2 * np.atan2(self.q_twist.y, self.q_twist.w)
            self.swing_lr = self.q_swing.z
            self.swing_ud = self.q_swing.x
            self.accel_mag = np.linalg.norm(self.accel)
            self.gyro_mag = np.linalg.norm(self.gyro)
            
            # Twist-corrected vectors for hit detection
            self.swing_accel = self.q_twist.rotate_vector(self.accel)
            self.swing_gyro = self.q_twist.rotate_vector(self.gyro)
            self.prev_swing_gyro_ud = self.swing_gyro_ud
            self.swing_gyro_ud = self.swing_gyro[0]
            alpha = 0.8
            self.swing_ud_accel = alpha * (self.swing_gyro_ud - self.prev_swing_gyro_ud) + (1 - alpha) * self.swing_ud_accel
            self.swing_gyro_lr = self.swing_gyro[1]

            # 4. Update history for visualisation
            self.swing_accel_x_history.append(self.swing_accel[0])
            self.swing_accel_y_history.append(self.swing_accel[1])
            self.swing_accel_z_history.append(self.swing_accel[2])
            self.swing_gyro_x_history.append(self.swing_gyro[0])
            self.swing_gyro_y_history.append(self.swing_gyro[1])
            self.swing_gyro_z_history.append(self.swing_gyro[2])
            self.accel_mag_history.append(self.accel_mag)
            self.gyro_mag_history.append(self.gyro_mag)
            self.swing_ud_accel_history.append(self.swing_ud_accel)

    def get_angle_axis(self):
        """Returns the current angle-axis representation."""
        with self._lock:
            return self.q_angle, self.q_axis

    def get_visualiser_snapshot(self):
        """Return a thread-safe snapshot of values used by the visualiser UI."""
        with self._lock:
            return {
                "angle": self.q_angle,
                "axis": self.q_axis.copy(),
                "q_swing": self.q_swing,
                "q_twist": self.q_twist,
                "twist_angle": self.twist_angle,
                "quat": self.quat,
                "q_delta": self.q_delta,
                "accel_mag_history": np.array(self.accel_mag_history),
                "gyro_mag_history": np.array(self.gyro_mag_history),
                "swing_gyro_x_history": np.array(self.swing_gyro_x_history),
                "swing_gyro_y_history": np.array(self.swing_gyro_y_history),
                "swing_gyro_z_history": np.array(self.swing_gyro_z_history),
                "swing_accel_x_history": np.array(self.swing_accel_x_history),
                "swing_accel_y_history": np.array(self.swing_accel_y_history),
                "swing_accel_z_history": np.array(self.swing_accel_z_history),
                "swing_ud_accel_history": np.array(self.swing_ud_accel_history),
            }
        
    def re_zero(self):
        """Resets the orientation reference to the current orientation."""
        with self._lock:
            self.q_ref = self.quat

    def set_muted(self, muted: bool):
        with self._lock:
            self._muted = bool(muted)

    def is_muted(self) -> bool:
        with self._lock:
            return self._muted

    def set_name(self, name: str):
        with self._lock:
            self.name = name or ""

    def get_name(self) -> str:
        with self._lock:
            return self.name

    def set_one_way_latency_ms(self, latency_ms: float | None):
        with self._lock:
            self.one_way_latency_ms = latency_ms

    def get_one_way_latency_ms(self) -> float | None:
        with self._lock:
            return self.one_way_latency_ms
        
    def set_data_rate(self, rate_hz: int | None):
        with self._lock:
            self.data_rate = rate_hz

    def get_data_rate(self) -> int | None:
        with self._lock:
            return self.data_rate

    def add_on_note(self, note: int):
        with self._lock:
            if note not in self.on_notes:
                self.on_notes[note] = []
            self.on_notes[note].append(time.monotonic())
            
    def remove_on_note(self, note: int, timestamp: float = -1.0):
        with self._lock:
            timestamps = self.on_notes.get(note)
            if not timestamps:
                return
            if timestamp < 0:
                timestamps.pop(0)
            else:
                timestamps.remove(timestamp)
            if not timestamps:
                self.on_notes.pop(note, None)
            
    def clear_on_notes(self):
        with self._lock:
            self.on_notes.clear()
            
    def get_on_notes(self):
        with self._lock:
            return {note: timestamps.copy() for note, timestamps in self.on_notes.items()}