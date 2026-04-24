import threading
import time

from server.shared_state import controllers
from server.midi_output import MIDIOutput


class MidiLearnEngine:
    def __init__(self):
        self.wave_hz = 0.7
        self.emit_hz = 120.0

        self._lock = threading.Lock()
        self._active = False
        self._midi_channel = 1
        self._mapping_type = "cc"
        self._cc_number = 1
        self._midi_range = [0, 127]
        self._phase = 0.0
        self._last_update_ts = 0.0
        self._last_emit_ts = 0.0

    def activate(self, midi_channel: int, mapping_cfg: dict) -> None:
        mapping_type = str(mapping_cfg.get("type", "cc")).strip().lower()
        if mapping_type not in ("cc", "pitch_bend"):
            mapping_type = "cc"

        try:
            cc_number = int(mapping_cfg.get("cc_number", 1))
        except (TypeError, ValueError):
            cc_number = 1
            
        midi_range = mapping_cfg.get("midi_range", [0, 127])
        

        now = time.monotonic()
        with self._lock:
            self._midi_channel = max(1, min(16, int(midi_channel)))
            self._mapping_type = mapping_type
            self._cc_number = max(0, min(127, cc_number))
            self._midi_range = midi_range
            self._phase = 0.0
            self._last_update_ts = now
            self._last_emit_ts = 0.0
            self._active = True

    def deactivate(self) -> None:
        with self._lock:
            self._active = False
            self._phase = 0.0
            self._last_update_ts = 0.0
            self._last_emit_ts = 0.0

    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def tick(self, midi_out: MIDIOutput) -> None:
        now = time.monotonic()
        with self._lock:
            if not self._active:
                return

            dt = now - self._last_update_ts
            self._last_update_ts = now
            self._phase = (self._phase + (dt * float(self.wave_hz))) % 1.0

            emit_interval = 1.0 / max(1.0, float(self.emit_hz))
            if now - self._last_emit_ts < emit_interval:
                return

            self._last_emit_ts = now

            norm = (2.0 * self._phase) if self._phase < 0.5 else (2.0 * (1.0 - self._phase))
            if self._mapping_type == "pitch_bend":
                midi_out.send_pitch_bend(self._midi_channel, int(round(16383.0 * norm)))
                return
            midi_val = int(self._midi_range[0] + norm * (self._midi_range[1] - self._midi_range[0]))
            midi_out.send_cc(self._midi_channel, self._cc_number, midi_val)
        
