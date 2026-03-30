import argparse
import sys
import threading
import time
from typing import Dict

from server.config import get_config, initialize
from server.midi_output import MIDIOutput
from server.controller_state import ControllerState
from server.midi_mapper import MidiMapper 
from server.receiver import receiver_thread


controllers: Dict[int, ControllerState] = {}
stop_event = threading.Event()

def main():
    parser = argparse.ArgumentParser(description="Handheld MIDI Controller Server")
    parser.add_argument("--ui", action="store_true", help="Launch the PyQt5 settings UI")
    args = parser.parse_args()

    # Load configuration
    try:
        initialize()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    config = get_config()

    # Initialize MIDI output
    midi_out = MIDIOutput(
        port_name=config['network']['midi_port_name'],
        backend=config['network']['midi_backend']
    )

    # Start the UDP receiver thread    
    recv_thread = threading.Thread(target=receiver_thread, args=(stop_event,), daemon=True)
    recv_thread.start()

    # Initialize the MIDI mapper & start the main processing loop in a separate thread
    mapper = MidiMapper(midi_out, stop_event)
    mapper.start()

    # Launch UI if requested
    if args.ui:
        print("Launching UI...")
        # Late import to avoid pulling in PyQt5 if not needed
        from server.ui.main_window import launch_ui
        # This will block until the UI is closed.
        # The UI will need access to the server state (controllers, config).
        # For this iteration, we pass the get_controllers function.
        launch_ui()
    else:
        # If no UI, just wait for Ctrl+C
        print("Server running. Press Ctrl+C to stop.")
        try:
            while not stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            print("Ctrl+C received, shutting down...")

    # Shutdown sequence
    stop_event.set()
    
    recv_thread.join(timeout=1)
    mapper.join(timeout=1)
    
    midi_out.close()
    print("Server shut down gracefully.")

if __name__ == "__main__":
    main()
