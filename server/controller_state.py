import numpy as np
import time
import threading
from collections import deque
from OneEuroFilter import OneEuroFilter

from server.config import get_config
import server.quaternion_utils as q_utils

class ControllerState:


    """Holds the state for a single connected controller."""
    def __init__(self, controller_mac, source_ip, midi_channel):
        self.mac = controller_mac
        self.source_ip = source_ip
        self.midi_channel = midi_channel
        self.last_packet_time = 0.0
        self.raw_data_queue = deque(maxlen=1)
        self._lock = threading.Lock()

        # Get filter params from config
        config = get_config()
        
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
        self.quat = np.array([1.0, 0.0, 0.0, 0.0])
        self.accel = np.array([0.0, 0.0, 0.0])
        self.gyro = np.array([0.0, 0.0, 0.0])
        self.accel_mag = 0.0
        self.gyro_mag = 0.0

        # Relative orientation
        self.q_ref = np.array([1.0, 0.0, 0.0, 0.0]) # Reference (zero) quaternion
        self.q_delta = np.array([1.0, 0.0, 0.0, 0.0]) # Relative rotation from q_ref
        self.q_angle, self.q_axis = 0.0, np.array([1.0, 0.0, 0.0]) # Angle-axis representation of q_delta
        # Hit detection state machine
        self.hit_state = "idle"  # idle, armed, refractory
        self.hit_timestamp = 0.0
        self.last_note_time = 0.0
        self.peak_gyro_window = deque(maxlen=5)
        self.peak_accel_window = deque(maxlen=5)

        # Note selection
        self.current_note = 60

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

            # 2. Apply One-Euro filters and assign new arrays atomically to avoid tearing
            t = time.monotonic()
            
            # new_quat = np.array([
            #     self.filters['quat_w'](raw_quat[0], t),
            #     self.filters['quat_x'](raw_quat[1], t),
            #     self.filters['quat_y'](raw_quat[2], t),
            #     self.filters['quat_z'](raw_quat[3], t)
            # ])
            self.quat = q_utils.quat_normalize(raw_quat)
            self.accel = np.array(raw_accel)
            self.gyro = np.array(raw_gyro)

            # self.accel = np.array([
            #     self.filters['accel_x'](raw_accel[0], t),
            #     self.filters['accel_y'](raw_accel[1], t),
            #     self.filters['accel_z'](raw_accel[2], t)
            # ])

            # self.gyro = np.array([
            #     self.filters['gyro_x'](raw_gyro[0], t),
            #     self.filters['gyro_y'](raw_gyro[1], t),
            #     self.filters['gyro_z'](raw_gyro[2], t)
            # ])

            # 3. Calculate derived values
            self.q_delta = q_utils.quat_mul(q_utils.quat_conjugate(self.q_ref), self.quat)
            self.q_angle, self.q_axis = q_utils.quat_to_angle_axis(self.q_delta)
            self.accel_mag = np.linalg.norm(self.accel)
            self.gyro_mag = np.linalg.norm(self.gyro)

    def get_angle_axis(self):
        """Returns the current angle-axis representation."""
        with self._lock:
            return self.q_angle, self.q_axis
        
    def re_zero(self):
        """Resets the orientation reference to the current orientation."""
        with self._lock:
            self.q_ref = self.quat.copy()

    def update_filter_params(self, mapping_name, min_cutoff, beta):
        """Update filter params for a specific source, e.g. 'euler_pitch'."""
        # This is a bit tricky since mappings use derived values (euler, mag)
        # and filters run on raw values (quat, accel, gyro).
        # For now, we assume a global filter setting per raw source.
        # A more advanced implementation could map this more dynamically.
        pass


