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
        """On Windows, we can't create a virtual port. We must connect to an existing one."""
        available_ports = self.midi_out.get_ports()
        print(available_ports)
        for idx, name in enumerate(available_ports):
            if self._port_name in name:
                self.midi_out.open_port(idx)
                self._port_open = True
                print(f"Connected to MIDI port: '{name}'")
                return
        print("Error: Could not find loopMIDI port '{}'. Available ports are:".format(self._port_name))
        for idx, name in enumerate(available_ports):
            print(f"  {idx}: {name}")
        print("Please install loopMIDI and create a port with that name.")
        # We don't exit, just operate without MIDI.
        self._port_open = False

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
