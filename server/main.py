import argparse
import sys
import threading
import time
from typing import Dict

from server.config import get_config, initialize
from server.midi_output import MIDIOutput
from server.controller_state import ControllerState
from server.midi_mapper import MidiMapper 
from server.communication import CommunicationThread
from server.provisioning_service import ProvisioningService
from server.dependency_checks import collect_startup_warnings
from server.wifi_backend import WiFiBackend


controllers: Dict[int, ControllerState] = {}
stop_event = threading.Event()

def main():
    parser = argparse.ArgumentParser(description="Handheld MIDI Controller Server")
    parser.add_argument("--noui", action="store_true", help="Run the server without launching the UI")
    args = parser.parse_args()

    # Load configuration
    try:
        initialize()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    config = get_config()

    for warning in collect_startup_warnings():
        print(f"Warning: {warning}")

    # Initialize MIDI output
    midi_out = MIDIOutput(
        port_name=config['network']['midi_port_name'],
        backend=config['network']['midi_backend']
    )
    if not midi_out.is_connected:
        print(f"Warning: MIDI output is not connected. {midi_out.last_error}")

    # Start the UDP receiver thread
    provisioning_service = ProvisioningService(WiFiBackend())
    recv_thread = CommunicationThread(stop_event=stop_event, provisioning_service=provisioning_service)
    recv_thread.start()

    # Initialize the MIDI mapper & start the main processing loop in a separate thread
    mapper = MidiMapper(midi_out, stop_event, haptic_sender=recv_thread)
    mapper.start()

    # Launch UI if requested
    if not args.noui:
        print("Launching UI...")
        # Late import to avoid pulling in PyQt5 if not needed
        from server.ui.main_window import launch_ui
        # This will block until the UI is closed.
        # The UI will need access to the server state (controllers, config).
        # For this iteration, we pass the get_controllers function.
        launch_ui(
            provisioning_service=provisioning_service,
            communication_thread=recv_thread,
        )
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
