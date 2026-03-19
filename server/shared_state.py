from typing import Dict

from server.controller_state import ControllerState


controllers: Dict[bytes, ControllerState] = {}
_new_controller_callbacks = []
_controller_removed_callbacks = []
_free_midi_channels = list(range(16))

def get_controller(mac, source_ip=None):
    if mac not in controllers:
        add_controller(mac, source_ip)
    return controllers[mac]

def add_controller(mac, source_ip):
    print(f"Discovered new controller from {source_ip} with MAC {mac.hex()}")
    if not _free_midi_channels:
        print("Warning: Maximum number of controllers reached. Ignoring new controller.")
        return
    midi_channel = _free_midi_channels.pop(0) 
    controllers[mac] = ControllerState(mac, source_ip, midi_channel)
    for cb in _new_controller_callbacks:
        cb(controllers[mac])

def remove_controller(mac):
    if mac in controllers:
        print(f"Controller {controllers[mac].source_ip} with MAC {mac.hex()} disconnected.")
        _free_midi_channels.append(controllers[mac].midi_channel)
        _free_midi_channels.sort()
        del controllers[mac]
        for cb in _controller_removed_callbacks:
            cb(mac)

def register_new_controller_callback(callback):
    """Registers a callback function to be called when a new controller connects."""
    _new_controller_callbacks.append(callback)

def register_controller_removed_callback(callback):
    """Registers a callback function to be called when a controller disconnects."""
    _controller_removed_callbacks.append(callback)