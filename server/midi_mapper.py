import time
import threading
import numpy as np

from server.shared_state import controllers
from server.controller_state import ControllerState
from server.midi_output import MIDIOutput
from server.config import get_effective_controller_config
from server.scales import get_scale
import server.quaternion_utils as q_utils

class MidiMapper(threading.Thread):
    def __init__(self, midi_out: MIDIOutput, stop_event: threading.Event):
        super().__init__()
        self.midi_out = midi_out
        self.stop_event = stop_event
        self.last_cc_values = {} # (controller_id, cc_number) -> value

    def run(self):
        """The main processing loop of the server."""        
        print("Starting processing loop...")
        
        while not self.stop_event.is_set():
            active_controllers = list(controllers.values())
            if not active_controllers:
                time.sleep(0.01)
                continue

            for state in active_controllers:
                self.process(state)
            
            # Handle note-offs in a simple way for this iteration
            self.send_scheduled_note_offs(controllers)

            # Sleep briefly to yield CPU
            time.sleep(0.0005) # 0.5ms sleep as per plan

        print("Processing loop stopped.")


    def process(self, state: ControllerState):
        state.process_raw_data()
        cfg = get_effective_controller_config(state.mac)
        if cfg.get("muted", False):
            return
        self._update_hit_detector(state, cfg)
        self._process_mappings(state, cfg)

    def _update_hit_detector(self, state: ControllerState, cfg):
        hit_cfg = cfg['hit']
        if not hit_cfg.get('enabled', True):
            state.hit_state = "idle"
            return
        params = hit_cfg['parameters']
        now = time.monotonic()

        # Refractory period check
        if state.hit_state == "refractory" and (now - state.last_note_time) * 1000 > params['refractory_ms']:
            state.hit_state = "idle"

        # "Drumstick Algorithm"
        vertical_accel = state.swing_accel[2]
        downward_gyro = state.swing_gyro[0]

        # State: idle -> armed
        if state.hit_state == "idle" and downward_gyro > params['gyro_onset_threshold']:
            #and vertical_accel < 1 - params['accel_onset_threshold']:
            state.hit_state = "armed"
            state.hit_timestamp = now
            state.hit_max_gyro = downward_gyro
            state.hit_max_accel = vertical_accel

        # State: armed -> check for confirmation
        if state.hit_state == "armed":

            # Timeout if no confirmation
            if (now - state.hit_timestamp) * 1000 > params['hit_window_ms']:
                state.hit_state = "idle"
                return

            if downward_gyro > state.hit_max_gyro:
                state.hit_max_gyro = downward_gyro
            if vertical_accel < state.hit_max_accel:
                state.hit_max_accel = vertical_accel

            if downward_gyro < 0:
                self._trigger_note(state, cfg)
                
        elif hit_cfg['flick_up_to_release_enabled']:
            if downward_gyro < params['gyro_release_threshold']:
                self.send_all_notes_off(state)
                state.hit_state = "idle"
            

    def _trigger_note(self, state: ControllerState, cfg):
        hit_cfg = cfg['hit']
        params = hit_cfg['parameters']
        
        # Calculate velocity

        # norm_gyro = min(peak_gyro / (params['gyro_onset_threshold'] * 2), 1.0)
        # norm_accel = min(peak_accel / (params['accel_confirm_threshold'] * 2), 1.0)
        
        # alpha = params['velocity_gyro_weight']
        # v = alpha * norm_gyro + (1 - alpha) * norm_accel

        v = min(state.hit_max_gyro / (params['max_velocity_gyro'] - params['gyro_onset_threshold']), 1.0)
        
        velocity = int(params['velocity_min'] + v * (params['velocity_max'] - params['velocity_min']))
        # velocity = max(0, min(127, velocity))

        # Select note based on source
        scale_cfg = hit_cfg.get('scale', {})
        scale = get_scale(scale_cfg.get('name', 'Major (Ionian)'), scale_cfg.get('custom_scale'))
        note_source_val = self._get_source_value(state, hit_cfg['note_source'])
        if note_source_val is None or scale is None:
            return
        num_notes = len(scale)
        range = hit_cfg['note_range']
        norm_note = (note_source_val - range[0]) / (range[1] - range[0])
        norm_note = max(0.0, min(1.0, norm_note))
        norm_note = self._apply_curve(norm_note, hit_cfg.get('note_curve', 'linear'), hit_cfg.get('note_curve_amount', 1.0))
        note_index = min(num_notes - 1, max(0, int(norm_note * num_notes)))
        state.current_note = scale_cfg.get('root_note', 60) + scale[note_index]

        
        # Send MIDI
        print(f"Triggering note {state.current_note} with velocity {velocity} on channel {state.midi_channel}")
        self.midi_out.send_note_on(state.midi_channel, state.current_note, velocity)
        state.add_on_note(state.current_note)
        
        state.hit_state = "refractory"
        state.last_note_time = time.monotonic()

    def _process_mappings(self, state: ControllerState, cfg):
        mappings = cfg.get('mappings', [])
        for m in mappings:
            if not isinstance(m, dict):
                continue
            if not bool(m.get('enabled', True)):
                continue
            source_val = self._get_source_value(state, m['source'])
            if source_val is None: continue

            # Map source value from its range to 0-127 for CC
            in_min, in_max = m['range']
            
            # Clamp and normalize
            norm_val = (source_val - in_min) / (in_max - in_min)
            norm_val = max(0.0, min(1.0, norm_val))
            norm_val = self._apply_curve(norm_val, m.get('curve', 'linear'), m.get('curve_amount', 1.0))
            
            if m['type'] == 'cc':
                cc_val = int(norm_val * 127)
                key = (state.midi_channel, m['cc_number'])
                
                # Delta gate: only send if value changed
                if self.last_cc_values.get(key) != cc_val:
                    self.midi_out.send_cc(state.midi_channel, m['cc_number'], cc_val)
                    self.last_cc_values[key] = cc_val
            
            elif m['type'] == 'pitch_bend':
                # Pitch bend is 14-bit
                pb_val = int(norm_val * 16383)
                self.midi_out.send_pitch_bend(state.midi_channel, pb_val)

    def _get_source_value(self, state: ControllerState, source_name: str):
        # Use the delta quaternion's components for mapping.
        # For small rotations, x, y, z are roughly roll, pitch, yaw.
        match source_name:
            case 'q_angle': return state.q_angle
            case 'q_axis_x': return state.q_axis[0]
            case 'q_axis_y': return state.q_axis[1]
            case 'q_axis_z': return state.q_axis[2]
            case 'twist_value' | 'twist': return state.twist_value
            case 'swing_lr' | 'lr' | 'swing_z': return state.swing_lr
            case 'swing_ud' | 'ud' | 'swing_x': return state.swing_ud
            case 'accel_mag': return state.accel_mag
            case 'gyro_mag': return state.gyro_mag
            case _: return None

    def _apply_curve(self, x: float, curve: str, amount: float) -> float:
        x = max(0.0, min(1.0, float(x)))
        amount = max(0.05, float(amount))

        if curve == 'exp':
            return x ** amount
        if curve == 'log':
            return 1.0 - ((1.0 - x) ** amount)
        if curve == 's_curve':
            if x < 0.5:
                return 0.5 * ((2.0 * x) ** amount)
            return 1.0 - 0.5 * ((2.0 * (1.0 - x)) ** amount)
        return x

    def send_scheduled_note_offs(self, controllers: dict):
        """A simple way to handle note offs for this implementation."""
        now = time.monotonic()
        for _, state in controllers.items():
            cfg = get_effective_controller_config(state.mac)
            note_duration_ms = cfg['hit']['parameters']['note_duration_ms']
            for note, timestamp in list(state.get_on_notes().items()):
                if (now - timestamp) * 1000 >= note_duration_ms:
                    self.midi_out.send_note_off(state.midi_channel, note)
                    state.remove_on_note(note)

    def send_all_notes_off(self, state: ControllerState):
        for note in state.get_on_notes().keys():
            self.midi_out.send_note_off(state.midi_channel, note)
        state.clear_on_notes()