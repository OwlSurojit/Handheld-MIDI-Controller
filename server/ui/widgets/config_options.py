MAPPING_NAME_PRESETS = {
    "volume": {"name": "volume", "cc_number": 7},
    "filter cutoff": {"name": "filter_cutoff", "cc_number": 74},
    "mod wheel": {"name": "mod_wheel", "cc_number": 1},
    "pan": {"name": "pan", "cc_number": 10},
    "expression": {"name": "expression", "cc_number": 11},
    "custom": {"name": "custom", "cc_number": 0},
}

MAPPING_SOURCE_OPTIONS = [
    "swing_ud",
    "swing_lr",
    "twist",
    "twist_value",
    "q_angle",
    "q_axis_x",
    "q_axis_y",
    "q_axis_z",
    "accel_mag",
    "gyro_mag",
]

CURVE_OPTIONS = ["linear", "exp", "log", "s_curve"]

NEW_MAPPING_TEMPLATE = {
    "name": "custom",
    "enabled": True,
    "source": "swing_ud",
    "type": "cc",
    "cc_number": 0,
    "range": [1, -1],
    "curve": "linear",
    "curve_amount": 1.0,
}