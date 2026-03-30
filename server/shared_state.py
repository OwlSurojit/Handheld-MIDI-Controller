from typing import Dict

from server.controller_state import ControllerState
import server.config as app_config


controllers: Dict[bytes, ControllerState] = {}
_new_controller_callbacks = []
_controller_removed_callbacks = []
_free_midi_channels = list(range(1,17))

def has_controller(mac):
    return mac in controllers

def get_controller(mac, ip_addr = None):
    if mac not in controllers and ip_addr is not None:
        add_controller(mac, ip_addr)
    return controllers[mac]

def add_controller(mac, source_ip):
    print(f"Discovered new controller from {source_ip} with MAC {mac.hex()}")
    if not _free_midi_channels:
        print("Warning: Maximum number of controllers reached. Ignoring new controller.")
        return

    preferred_channel = app_config.get_saved_controller_channel(mac)
    if preferred_channel in _free_midi_channels:
        _free_midi_channels.remove(preferred_channel)
        midi_channel = preferred_channel
    else:
        midi_channel = _free_midi_channels.pop(0)

    controllers[mac] = ControllerState(mac, source_ip, midi_channel)
    app_config.upsert_controller(mac, midi_channel=midi_channel, source_ip=source_ip)
    controllers[mac].set_name(app_config.get_controller_name(mac))
    controllers[mac].set_muted(app_config.is_controller_muted(mac))
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