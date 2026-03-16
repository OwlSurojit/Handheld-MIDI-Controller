from collections import deque
import numpy as np
from OneEuroFilter import OneEuroFilter

from server.config import get_config

class ControllerState:
    """Holds the state for a single connected controller."""
    def __init__(self, controller_id, source_ip):
        self.id = controller_id
        self.source_ip = source_ip
        self.last_packet_time = 0.0
        self.raw_data_queue = deque(maxlen=1)

        # Get filter params from config
        config = get_config()
        
        # One-Euro filters for all 10 incoming signals
        # The parameters can be tuned in config.yaml for each mapping
        self.filters = {
            'quat_w': OneEuroFilter(freq=55, mincutoff=1.0, beta=0.0),
            'quat_x': OneEuroFilter(freq=55, mincutoff=1.0, beta=0.0),
            'quat_y': OneEuroFilter(freq=55, mincutoff=1.0, beta=0.0),
            'quat_z': OneEuroFilter(freq=55, mincutoff=1.0, beta=0.0),
            'accel_x': OneEuroFilter(freq=55, mincutoff=2.0, beta=0.02),
            'accel_y': OneEuroFilter(freq=55, mincutoff=2.0, beta=0.02),
            'accel_z': OneEuroFilter(freq=55, mincutoff=2.0, beta=0.02),
            'gyro_x': OneEuroFilter(freq=55, mincutoff=3.0, beta=0.05),
            'gyro_y': OneEuroFilter(freq=55, mincutoff=3.0, beta=0.05),
            'gyro_z': OneEuroFilter(freq=55, mincutoff=3.0, beta=0.05),
        }

        # Filtered sensor values
        self.quat = np.array([1.0, 0.0, 0.0, 0.0])
        self.accel = np.array([0.0, 0.0, 0.0])
        self.gyro = np.array([0.0, 0.0, 0.0])
        self.euler = np.array([0.0, 0.0, 0.0])
        self.accel_mag = 0.0
        self.gyro_mag = 0.0

        # Hit detection state machine
        self.hit_state = "idle"  # idle, armed, refractory
        self.hit_timestamp = 0.0
        self.last_note_time = 0.0
        self.peak_gyro_window = deque(maxlen=5)
        self.peak_accel_window = deque(maxlen=5)

        # Yaw-based note selection
        self.yaw_zero_offset = 0.0
        self.current_note = 60

    def re_zero(self):
        """Resets the yaw reference to the current orientation."""
        self.yaw_zero_offset = self.euler[2]

    def update_filter_params(self, mapping_name, min_cutoff, beta):
        """Update filter params for a specific source, e.g. 'euler_pitch'."""
        # This is a bit tricky since mappings use derived values (euler, mag)
        # and filters run on raw values (quat, accel, gyro).
        # For now, we assume a global filter setting per raw source.
        # A more advanced implementation could map this more dynamically.
        pass
