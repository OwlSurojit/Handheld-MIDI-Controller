from typing import Any, Dict, List


MAPPING_NAME_PRESETS: Dict[str, Dict[str, Any]] = {
    "volume": {"name": "volume", "cc_number": 7},
    "filter cutoff": {"name": "filter_cutoff", "cc_number": 74},
    "mod wheel": {"name": "mod_wheel", "cc_number": 1},
    "pan": {"name": "pan", "cc_number": 10},
    "expression": {"name": "expression", "cc_number": 11},
    "custom": {"name": "custom", "cc_number": 0},
}

MAPPING_SOURCE_OPTIONS: Dict[str, Dict[str, Any]] = {
    "Up/Down Swing" : {"name" : "swing_ud", "range": [-1, 1]},
    "Left/Right Swing" : {"name" : "swing_lr", "range": [-1, 1]},
    "Twist" : {"name" : "twist", "range": [-1, 1]},
    "Twist Angle" : {"name" : "twist_angle", "range": [-180, 180]},
    "Quaternion Angle" : {"name" : "q_angle", "range": [0, 360]},
    "Up/Down Swing Velocity" : {"name" : "swing_gyro_ud", "range": [-2000, 2000]},
    "Left/Right Swing Velocity" : {"name" : "swing_gyro_lr", "range": [-2000, 2000]},
    "Acceleration Magnitude" : {"name" : "accel_mag", "range": [0, 8]},
    "Gyroscope Magnitude" : {"name" : "gyro_mag", "range": [0, 2000]},
}

CURVE_OPTIONS: List[str] = ["linear", "exp", "log", "s_curve"]

NEW_MAPPING_TEMPLATE: Dict[str, Any] = {
    "name": "custom",
    "enabled": True,
    "source": "swing_ud",
    "type": "cc",
    "cc_number": 0,
    "range": [-1, 1],
    "midi_range": [0, 127],
    "invert": False,
    "curve": "linear",
    "curve_amount": 1.0,
}

DEFAULT_CONTROLLER_CONFIG: Dict[str, Any] = {
    "name": "",
    "midi_channel": None,
    "muted": False,
    "mappings": [],
    "hit": {},
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "network": {
        "udp_port": 9367,
        "midi_port_name": "Handheld MIDI Controller",
        "midi_backend": "auto",
    },
    "controllers": {},
    "defaults": {
        "mappings": [
            {
                "name": "volume",
                "enabled": True,
                "source": "swing_ud",
                "type": "cc",
                "cc_number": 7,
                "range": [-1, 1],
                "midi_range": [0, 127],
                "invert": True,
                "curve": "linear",
                "curve_amount": 1.0,
            },
            {
                "name": "filter_cutoff",
                "enabled": True,
                "source": "twist",
                "type": "cc",
                "cc_number": 74,
                "range": [-1, 1],
                "midi_range": [0, 127],
                "invert": False,
                "curve": "linear",
                "curve_amount": 1.0,
            },
        ],
        "hit": {
            "enabled": True,
            "flick_up_to_release_enabled": True,
            "note_source": "swing_lr",
            "note_range": [-1, 1],
            "note_invert": True,
            "note_curve": "linear",
            "note_curve_amount": 1.0,
            "scale": {
                "name": "Major (Ionian)",
                "root_note": 60,
                "custom_scale": [],
            },
            "haptic": {
                "enabled": True,
                "command": 1,
                "duration_ms": 100,
            },
            "parameters": {
                "gyro_onset_threshold": 300,
                "gyro_release_threshold": -1000,
                "max_velocity_gyro": 2000,
                "accel_onset_threshold": 0.5,
                "velocity_min": 20,
                "velocity_max": 127,
                "hit_window_ms": 100,
                "refractory_ms": 50,
                "note_duration_ms": 500,
            },
        },
    },
}

DEFAULT_APP_SETTINGS: Dict[str, Any] = {
    "presets_directory": "server/presets",
}