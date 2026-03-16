import time
import numpy as np

from server.controller_state import ControllerState
from server.midi_output import MIDIOutput
from server.config import get_config
from server.scales import get_scale
import server.quaternion_utils as q_utils

class MidiMapper:
    def __init__(self, midi_out: MIDIOutput):
        self.midi_out = midi_out
        self.config = get_config()
        self.last_cc_values = {} # (controller_id, cc_number) -> value

    def process(self, state: ControllerState):
        """
        Main processing function for a single controller's state.
        This is called on every iteration of the processing thread.
        """
        # 1. Pop data from the queue
        try:
            ts, raw_quat, raw_accel, raw_gyro = state.raw_data_queue.popleft()
        except IndexError:
            return # No new data

        # 2. Apply One-Euro filters
        t = time.monotonic()
        state.quat[0] = state.filters['quat_w'](raw_quat[0], t)
        state.quat[1] = state.filters['quat_x'](raw_quat[1], t)
        state.quat[2] = state.filters['quat_y'](raw_quat[2], t)
        state.quat[3] = state.filters['quat_z'](raw_quat[3], t)
        state.quat = q_utils.quat_normalize(state.quat)

        state.accel[0] = state.filters['accel_x'](raw_accel[0], t)
        state.accel[1] = state.filters['accel_y'](raw_accel[1], t)
        state.accel[2] = state.filters['accel_z'](raw_accel[2], t)

        state.gyro[0] = state.filters['gyro_x'](raw_gyro[0], t)
        state.gyro[1] = state.filters['gyro_y'](raw_gyro[1], t)
        state.gyro[2] = state.filters['gyro_z'](raw_gyro[2], t)

        # 3. Calculate derived values (Euler angles, magnitudes)
        state.euler = q_utils.quat_to_euler(state.quat)
        state.accel_mag = np.linalg.norm(state.accel)
        state.gyro_mag = np.linalg.norm(state.gyro)

        # 4. Run hit detector and note selection
        self._update_hit_detector(state)

        # 5. Process continuous MIDI mappings
        self._process_mappings(state)

    def _update_hit_detector(self, state: ControllerState):
        hit_cfg = self.config['hit_detector']
        now = time.monotonic()

        # Refractory period check
        if state.hit_state == "refractory" and (now - state.last_note_time) * 1000 > hit_cfg['refractory_ms']:
            state.hit_state = "idle"

        # State: idle -> armed
        if state.hit_state == "idle" and state.gyro_mag > hit_cfg['gyro_onset_threshold']:
            state.hit_state = "armed"
            state.hit_timestamp = now
            state.peak_gyro_window.clear()
            state.peak_accel_window.clear()

        # State: armed -> check for confirmation
        if state.hit_state == "armed":
            state.peak_gyro_window.append(state.gyro_mag)
            state.peak_accel_window.append(state.accel_mag)

            # Timeout if no confirmation
            if (now - state.hit_timestamp) > 0.1: # 100ms window
                state.hit_state = "idle"
                return

            if state.accel_mag > hit_cfg['accel_confirm_threshold']:
                self._trigger_note(state)

    def _trigger_note(self, state: ControllerState):
        hit_cfg = self.config['hit_detector']
        
        # Calculate velocity
        peak_gyro = max(state.peak_gyro_window) if state.peak_gyro_window else 0
        peak_accel = max(state.peak_accel_window) if state.peak_accel_window else 0
        
        norm_gyro = min(peak_gyro / (hit_cfg['gyro_onset_threshold'] * 2), 1.0)
        norm_accel = min(peak_accel / (hit_cfg['accel_confirm_threshold'] * 2), 1.0)
        
        alpha = hit_cfg['velocity_gyro_weight']
        v = alpha * norm_gyro + (1 - alpha) * norm_accel
        
        velocity = int(hit_cfg['velocity_min'] + v * (hit_cfg['velocity_max'] - hit_cfg['velocity_min']))
        velocity = max(0, min(127, velocity))

        # Select note based on yaw
        self._select_note_from_yaw(state)
        
        # Send MIDI
        channel = state.id + 1
        self.midi_out.send_note_on(channel, state.current_note, velocity)
        
        # Schedule Note Off (in a real implementation, this should be handled more robustly)
        # For now, we'll rely on a simple state check in the main loop or a separate thread.
        # A better way is a priority queue of note-off events.
        # For this implementation, we'll just send a note-off after a fixed duration in a simple way.
        # This is a simplification from the plan.
        
        state.hit_state = "refractory"
        state.last_note_time = time.monotonic()

    def _select_note_from_yaw(self, state: ControllerState):
        scale_cfg = self.config['scale']
        scale = get_scale(scale_cfg['scale'], scale_cfg.get('custom_scale'))
        if not scale: return

        # Relative yaw from zero reference, wrapped to 0-360
        relative_yaw = (state.euler[2] - state.yaw_zero_offset + 360) % 360
        
        num_notes = len(scale)
        zone_width = 360 / num_notes
        
        # Hysteresis to prevent chatter at boundaries
        hysteresis = self.config['yaw_zone_hysteresis']
        
        # Find the current zone
        current_zone = int(relative_yaw / zone_width)
        
        # Check if we are in a hysteresis deadband
        zone_boundary = (current_zone + 1) * zone_width
        if abs(relative_yaw - zone_boundary) < hysteresis:
            # We are in a deadband, don't change the note
            return

        note_index = current_zone
        midi_note = scale_cfg['root_note'] + scale[note_index]
        state.current_note = max(0, min(127, midi_note))

    def _process_mappings(self, state: ControllerState):
        mappings = self.config.get('mappings', {})
        for name, m in mappings.items():
            source_val = self._get_source_value(state, m['source'])
            if source_val is None: continue

            # Map source value from its range to 0-127 for CC
            in_min, in_max = m['range']
            
            # Clamp and normalize
            norm_val = (source_val - in_min) / (in_max - in_min)
            norm_val = max(0.0, min(1.0, norm_val))
            
            if m['type'] == 'cc':
                cc_val = int(norm_val * 127)
                key = (state.id, m['cc_number'])
                
                # Delta gate: only send if value changed
                if self.last_cc_values.get(key) != cc_val:
                    self.midi_out.send_cc(state.id + 1, m['cc_number'], cc_val)
                    self.last_cc_values[key] = cc_val
            
            elif m['type'] == 'pitch_bend':
                # Pitch bend is 14-bit
                pb_val = int(norm_val * 16383)
                self.midi_out.send_pitch_bend(state.id + 1, pb_val)

    def _get_source_value(self, state: ControllerState, source_name: str):
        if source_name == 'euler_roll': return state.euler[0]
        if source_name == 'euler_pitch': return state.euler[1]
        if source_name == 'euler_yaw': return state.euler[2]
        if source_name == 'accel_mag': return state.accel_mag
        if source_name == 'gyro_mag': return state.gyro_mag
        return None

    def send_scheduled_note_offs(self, controllers: dict):
        """A simple way to handle note offs for this implementation."""
        now = time.monotonic()
        note_duration_ms = self.config['hit_detector']['note_duration_ms']
        for cid, state in controllers.items():
            if state.hit_state == "refractory" and (now - state.last_note_time) * 1000 >= note_duration_ms:
                 if (now - state.last_note_time) * 1000 < note_duration_ms + 50: # Send only once
                    self.midi_out.send_note_off(state.id + 1, state.current_note)
