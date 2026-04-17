import rtmidi
import sys
from rtmidi.midiconstants import (
    NOTE_ON, NOTE_OFF, CONTROL_CHANGE, PITCH_BEND
)

class MIDIOutput:
    def __init__(self, port_name="Handheld MIDI Controller", backend="auto"):
        self.midi_out = rtmidi.MidiOut()
        self._port_name = port_name
        self._backend = backend
        self._port_open = False
        self._connected_port_name = ""
        self._last_error = ""
        self._setup_midi()

    def _setup_midi(self):
        if self._backend != "auto":
            try:
                api = getattr(rtmidi, f"API_{self._backend.upper()}")
                self.midi_out = rtmidi.MidiOut(api)
            except AttributeError:
                print(f"Warning: Specified MIDI backend '{self._backend}' not found. Using auto.")
                self.midi_out = rtmidi.MidiOut()
        
        if sys.platform.startswith("win"):
            self._setup_windows()
        else:
            self._setup_unix()

    def _setup_windows(self):
        """On Windows, connect to preferred port when available, otherwise fall back safely."""
        available_ports = self.midi_out.get_ports()
        print(f"Available MIDI ports: {available_ports}")

        preferred = self._find_matching_port(available_ports, self._port_name)
        if preferred is not None:
            self._open_port(preferred, available_ports[preferred])
            return

        if available_ports:
            fallback_index = 0
            fallback_name = available_ports[fallback_index]
            self._open_port(fallback_index, fallback_name)
            print(
                "Warning: Preferred MIDI port '{}' not found. Falling back to '{}'".format(
                    self._port_name,
                    fallback_name,
                )
            )
            return

        self._last_error = (
            "No Windows MIDI output ports were detected. Install and configure a loopback MIDI driver "
            "(for example loopMIDI or teVirtualMIDI) or connect a hardware MIDI output."
        )
        print(f"Error: {self._last_error}")
        self._port_open = False

    def _find_matching_port(self, available_ports, target_name):
        if not target_name:
            return None

        target_lower = target_name.lower()
        for idx, name in enumerate(available_ports):
            if name.lower() == target_lower:
                return idx

        for idx, name in enumerate(available_ports):
            if target_lower in name.lower():
                return idx

        return None

    def _open_port(self, index, name):
        self.midi_out.open_port(index)
        self._port_open = True
        self._connected_port_name = name
        self._last_error = ""
        print(f"Connected to MIDI port: '{name}'")

    def _setup_unix(self):
        """On Linux/macOS, we can create a virtual port."""
        self.midi_out.open_virtual_port(self._port_name)
        self._port_open = True
        print(f"Opened virtual MIDI port: '{self._port_name}'")

    def send_note_on(self, channel, note, velocity=127):
        if not self._port_open: return
        self.midi_out.send_message([NOTE_ON | (channel - 1), note, velocity])

    def send_note_off(self, channel, note):
        if not self._port_open: return
        self.midi_out.send_message([NOTE_OFF | (channel - 1), note, 0])

    def send_cc(self, channel, cc_number, value):
        if not self._port_open: return
        self.midi_out.send_message([CONTROL_CHANGE | (channel - 1), cc_number, value])

    def send_pitch_bend(self, channel, value):
        """ value is a 14-bit integer (0-16383) """
        if not self._port_open: return
        lsb = value & 0x7F
        msb = (value >> 7) & 0x7F
        self.midi_out.send_message([PITCH_BEND | (channel - 1), lsb, msb])

    def close(self):
        if self._port_open:
            self.midi_out.close_port()
            self._port_open = False
            print("MIDI port closed.")
        del self.midi_out

    @property
    def is_connected(self):
        return self._port_open

    @property
    def connected_port_name(self):
        return self._connected_port_name

    @property
    def last_error(self):
        return self._last_error
