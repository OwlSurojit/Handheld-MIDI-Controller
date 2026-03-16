import argparse
import sys
import time
import threading

from server.config import load_config, get_config
from server.receiver import receiver_thread, stop_receiver, get_controllers
from server.midi_output import MIDIOutput
from server.midi_mapper import MidiMapper

def main_loop(mapper: MidiMapper):
    """The main processing loop of the server."""
    print("Starting processing loop...")
    controllers = get_controllers()
    
    while not stop_event.is_set():
        active_controllers = list(controllers.values())
        if not active_controllers:
            time.sleep(0.01)
            continue

        for state in active_controllers:
            mapper.process(state)
        
        # Handle note-offs in a simple way for this iteration
        mapper.send_scheduled_note_offs(controllers)

        # Sleep briefly to yield CPU
        time.sleep(0.0005) # 0.5ms sleep as per plan

    print("Processing loop stopped.")

def main():
    parser = argparse.ArgumentParser(description="Handheld MIDI Controller Server")
    parser.add_argument("--ui", action="store_true", help="Launch the PyQt5 settings UI")
    args = parser.parse_args()

    # Load configuration
    try:
        load_config()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    config = get_config()

    # Initialize MIDI output
    midi_out = MIDIOutput(
        port_name=config['network']['midi_port_name'],
        backend=config['network']['midi_backend']
    )

    # Initialize the MIDI mapper
    mapper = MidiMapper(midi_out)

    # Start the UDP receiver thread
    global stop_event
    stop_event = threading.Event()
    
    recv_thread = threading.Thread(target=receiver_thread, daemon=True)
    recv_thread.start()

    # Start the main processing loop in a separate thread
    proc_thread = threading.Thread(target=main_loop, args=(mapper,), daemon=True)
    proc_thread.start()

    # Launch UI if requested
    if args.ui:
        print("Launching UI...")
        # Late import to avoid pulling in PyQt5 if not needed
        from server.ui.main_window import launch_ui
        # This will block until the UI is closed.
        # The UI will need access to the server state (controllers, config).
        # For this iteration, we pass the get_controllers function.
        launch_ui(get_controllers)
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
    stop_receiver()
    
    recv_thread.join(timeout=1)
    proc_thread.join(timeout=1)
    
    midi_out.close()
    print("Server shut down gracefully.")

if __name__ == "__main__":
    main()
