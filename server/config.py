import copy
import os
import threading
import yaml
from typing import Any, Callable, Dict, List, Tuple

from server.config_consts import DEFAULT_CONFIG, DEFAULT_APP_SETTINGS




_config: Dict[str, Any] = {}
_config_path = "config.yaml"
_app_settings: Dict[str, Any] = {}
_app_settings_path = os.path.join("server", "app_settings.yaml")
_lock = threading.RLock()
_version = 0
_subscribers: List[Callable[[int], None]] = []


def _resolve_config_path(path: str) -> str:
    if os.path.exists(path):
        return path
    fallback = os.path.join("server", path)
    if os.path.exists(fallback):
        return fallback
    raise FileNotFoundError(f"Configuration file not found at {path} or {fallback}")


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _normalize_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    merged = _deep_merge(
        {
            "name": "custom",
            "enabled": True,
            "source": "swing_ud",
            "type": "cc",
            "cc_number": 7,
            "range": [-1, 1],
            "invert": False,
            "curve": "linear",
            "curve_amount": 1.0,
        },
        mapping or {},
    )
    merged.pop("filter", None)
    merged["name"] = str(merged.get("name", "custom")).strip() or "custom"
    merged["enabled"] = bool(merged.get("enabled", True))
    merged["range"] = list(merged.get("range", [-1, 1]))
    if len(merged["range"]) != 2:
        merged["range"] = [-1, 1]
    merged["invert"] = bool(merged.get("invert", False))
    if merged["range"][0] > merged["range"][1]:
        merged["range"] = [merged["range"][1], merged["range"][0]]
        merged["invert"] = not merged["invert"]
    merged["curve"] = str(merged.get("curve", "linear"))
    merged["curve_amount"] = float(merged.get("curve_amount", 1.0))
    return merged


def _normalize_mappings(mappings: List[Dict[str, Any]] | Any) -> List[Dict[str, Any]]:
    if not isinstance(mappings, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for mapping in mappings:
        if isinstance(mapping, dict):
            normalized.append(_normalize_mapping(mapping))
    return normalized


def _normalize_hit_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
    default_params = DEFAULT_CONFIG["defaults"]["hit"]["parameters"]
    merged = _deep_merge(default_params, params or {})
    return merged


def _normalize_hit_config(hit_cfg: Dict[str, Any]) -> Dict[str, Any]:
    hit_cfg = dict(hit_cfg or {})
    scale = dict(hit_cfg.get("scale", {}))
    haptic = dict(hit_cfg.get("haptic", {}))
    normalized = {
        "enabled": bool(hit_cfg.get("enabled", True)),
        "flick_up_to_release_enabled": bool(hit_cfg.get("flick_up_to_release_enabled", True)),
        "note_source": str(hit_cfg.get("note_source", "swing_lr")),
        "note_range": list(hit_cfg.get("note_range", [-1, 1])),
        "note_invert": bool(hit_cfg.get("note_invert", False)),
        "note_curve": str(hit_cfg.get("note_curve", "linear")),
        "note_curve_amount": float(hit_cfg.get("note_curve_amount", 1.0)),
        "scale": {
            "name": str(scale.get("name", "Major (Ionian)")),
            "root_note": int(scale.get("root_note", 60)),
            "custom_scale": list(scale.get("custom_scale", []) or []),
        },
        "haptic": {
            "enabled": bool(haptic.get("enabled", True)),
            "command": int(haptic.get("command", 1)) & 0xFF,
            "duration_ms": max(0, int(haptic.get("duration_ms", 35))),
        },
        "parameters": _normalize_hit_parameters(hit_cfg.get("parameters", {})),
    }
    if len(normalized["note_range"]) != 2:
        normalized["note_range"] = [-1, 1]
    if normalized["note_range"][0] > normalized["note_range"][1]:
        normalized["note_range"] = [normalized["note_range"][1], normalized["note_range"][0]]
        normalized["note_invert"] = not normalized["note_invert"]
    return normalized


def _normalize_controller_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(entry or {})
    channel = merged.get("midi_channel")
    if isinstance(channel, int) and 1 <= channel <= 16:
        merged["midi_channel"] = channel
    else:
        merged["midi_channel"] = None

    name_value = str(merged.get("name", "")).strip()
    if not name_value and merged["midi_channel"] is not None:
        name_value = _default_controller_name(merged["midi_channel"])
    merged["name"] = name_value

    merged["muted"] = bool(merged.get("muted", False))

    merged["mappings"] = _normalize_mappings(merged.get("mappings", []))

    if "hit" in merged and isinstance(merged.get("hit"), dict):
        hit = dict(merged.get("hit", {}))
        if "note_range" in hit:
            hit["note_range"] = list(hit.get("note_range", [-1, 1]))
            if len(hit["note_range"]) != 2:
                hit["note_range"] = [-1, 1]
            hit["note_invert"] = bool(hit.get("note_invert", False))
            if hit["note_range"][0] > hit["note_range"][1]:
                hit["note_range"] = [hit["note_range"][1], hit["note_range"][0]]
                hit["note_invert"] = not hit["note_invert"]
        if "scale" in hit and isinstance(hit.get("scale"), dict):
            scale = dict(hit.get("scale", {}))
            hit["scale"] = {
                "name": str(scale.get("name", "Major (Ionian)")),
                "root_note": int(scale.get("root_note", 60)),
                "custom_scale": list(scale.get("custom_scale", []) or []),
            }
        if "parameters" in hit and isinstance(hit.get("parameters"), dict):
            hit["parameters"] = _normalize_hit_parameters(hit.get("parameters", {}))
        merged["hit"] = hit

    if "source_ip" in entry:
        merged["source_ip"] = str(entry["source_ip"])

    return merged


def _mac_key(controller_mac: bytes | str) -> str:
    if isinstance(controller_mac, bytes):
        return controller_mac.hex().lower()
    return str(controller_mac).replace(":", "").lower()


def _default_controller_name(midi_channel: int | None) -> str:
    if isinstance(midi_channel, int) and 1 <= midi_channel <= 16:
        return f"Controller {midi_channel}"
    return ""


def _notify_subscribers(new_version: int) -> None:
    for callback in list(_subscribers):
        try:
            callback(new_version)
        except Exception as exc:
            print(f"Config subscriber callback failed: {exc}")


def _bump_version_locked() -> int:
    global _version
    _version += 1
    return _version


def _load_app_settings() -> Dict[str, Any]:
    global _app_settings
    if _app_settings:
        return _app_settings

    if os.path.exists(_app_settings_path):
        with open(_app_settings_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    _app_settings = _deep_merge(DEFAULT_APP_SETTINGS, raw)
    return _app_settings


def _save_app_settings() -> None:
    os.makedirs(os.path.dirname(_app_settings_path) or ".", exist_ok=True)
    with open(_app_settings_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(_app_settings, f, sort_keys=False)


def normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    merged = _deep_merge(DEFAULT_CONFIG, config or {})

    controllers_raw = dict(merged.get("controllers", {}))
    normalized_controllers: Dict[str, Any] = {}
    for mac, entry in controllers_raw.items():
        if not isinstance(entry, dict):
            continue
        normalized_controllers[str(mac).lower()] = _normalize_controller_entry(entry)
    merged["controllers"] = normalized_controllers

    defaults_cfg = dict(merged.get("defaults", {}))
    defaults_cfg["mappings"] = _normalize_mappings(defaults_cfg.get("mappings", []))
    defaults_cfg["hit"] = _normalize_hit_config(defaults_cfg.get("hit", {}))
    merged["defaults"] = defaults_cfg

    return merged


def load_config(path: str = "config.yaml") -> None:
    global _config, _config_path
    resolved_path = _resolve_config_path(path)
    with open(resolved_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    _config = normalize_config(data)
    _config_path = resolved_path


def initialize(path: str = "config.yaml") -> None:
    with _lock:
        load_config(path)
        _load_app_settings()
        version = _bump_version_locked()
    _notify_subscribers(version)


def save_config(path: str | None = None) -> str:
    global _config_path
    if not _config:
        load_config(path or _config_path)
    target = path or _config_path
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        yaml.safe_dump(_config, f, sort_keys=False)
    _config_path = target
    return target


def get_config() -> Dict[str, Any]:
    if not _config:
        load_config()
    return _config


def get_config_path() -> str:
    if not _config:
        load_config()
    return _config_path


def subscribe(callback: Callable[[int], None]) -> Callable[[], None]:
    with _lock:
        _subscribers.append(callback)

    def _unsubscribe() -> None:
        with _lock:
            if callback in _subscribers:
                _subscribers.remove(callback)

    return _unsubscribe


def get_version() -> int:
    with _lock:
        return _version


def get_config_snapshot() -> Tuple[int, Dict[str, Any]]:
    with _lock:
        return _version, copy.deepcopy(get_config())


def update_config(path: List[str], value: Any) -> int:
    if not path:
        raise ValueError("Config update path cannot be empty")

    with _lock:
        config = get_config()
        node = config
        for key in path[:-1]:
            if key not in node or not isinstance(node[key], dict):
                node[key] = {}
            node = node[key]
        node[path[-1]] = value
        version = _bump_version_locked()

    _notify_subscribers(version)
    return version


def update_many(updates: List[Tuple[List[str], Any]]) -> int:
    with _lock:
        config = get_config()
        for path, value in updates:
            if not path:
                continue
            node = config
            for key in path[:-1]:
                if key not in node or not isinstance(node[key], dict):
                    node[key] = {}
                node = node[key]
            node[path[-1]] = value
        version = _bump_version_locked()
    _notify_subscribers(version)
    return version


def save_current_config(path: str | None = None) -> str:
    with _lock:
        return save_config(path)


def save_to_default_path() -> str:
    return save_current_config(get_config_path())


def import_config_from_file(path: str, replace: bool = True) -> int:
    with open(path, "r", encoding="utf-8") as f:
        imported = yaml.safe_load(f) or {}
    imported = normalize_config(imported)

    with _lock:
        config = get_config()
        if replace:
            config.clear()
            config.update(imported)
        else:
            config.update(imported)
        version = _bump_version_locked()
    _notify_subscribers(version)
    return version


def set_presets_directory(path: str) -> int:
    normalized = os.path.normpath(path)
    os.makedirs(normalized, exist_ok=True)
    with _lock:
        settings = _load_app_settings()
        settings["presets_directory"] = normalized
        _save_app_settings()
        version = _bump_version_locked()
    _notify_subscribers(version)
    return version


def get_presets_directory() -> str:
    with _lock:
        directory = _load_app_settings().get("presets_directory", DEFAULT_APP_SETTINGS["presets_directory"])
    os.makedirs(directory, exist_ok=True)
    return directory


def list_presets() -> List[str]:
    directory = get_presets_directory()
    preset_names: List[str] = []
    for entry in os.listdir(directory):
        if entry.endswith(".yaml"):
            preset_names.append(entry[:-5])
    preset_names.sort()
    return preset_names


def save_preset(name: str) -> str:
    safe_name = name.strip().replace(" ", "_")
    if not safe_name:
        raise ValueError("Preset name cannot be empty")
    directory = get_presets_directory()
    path = os.path.join(directory, f"{safe_name}.yaml")
    with _lock:
        snapshot = copy.deepcopy(get_config())
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(snapshot, f, sort_keys=False)
    return path


def preset_exists(name: str) -> bool:
    safe_name = name.strip().replace(" ", "_")
    if not safe_name:
        return False
    directory = get_presets_directory()
    path = os.path.join(directory, f"{safe_name}.yaml")
    return os.path.isfile(path)


def load_preset(name: str) -> int:
    safe_name = name.strip().replace(" ", "_")
    directory = get_presets_directory()
    path = os.path.join(directory, f"{safe_name}.yaml")
    return import_config_from_file(path, replace=True)


def load_default_config() -> int:
    default_path = _resolve_config_path("config.yaml")
    return import_config_from_file(default_path, replace=True)


def delete_preset(name: str) -> str:
    safe_name = name.strip().replace(" ", "_")
    if not safe_name:
        raise ValueError("Preset name cannot be empty")
    directory = get_presets_directory()
    path = os.path.join(directory, f"{safe_name}.yaml")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Preset not found: {safe_name}")
    os.remove(path)
    return path


def _controller_path(mac_key: str) -> List[str]:
    return ["controllers", mac_key]


def upsert_controller(controller_mac: bytes | str, midi_channel: int | None = None, source_ip: str | None = None) -> int:
    mac_key = _mac_key(controller_mac)
    with _lock:
        config = get_config()
        controllers_cfg = config.setdefault("controllers", {})
        entry = _normalize_controller_entry(controllers_cfg.get(mac_key, {}))
        if midi_channel is not None:
            entry["midi_channel"] = midi_channel
            if not str(entry.get("name", "")).strip():
                entry["name"] = _default_controller_name(midi_channel)
        if source_ip:
            entry["source_ip"] = source_ip
        controllers_cfg[mac_key] = entry
        version = _bump_version_locked()
    _notify_subscribers(version)
    return version


def get_controller_entry(controller_mac: bytes | str) -> Dict[str, Any]:
    with _lock:
        config = get_config()
        return copy.deepcopy(config.get("controllers", {}).get(_mac_key(controller_mac), {}))


def get_saved_controller_channel(controller_mac: bytes | str) -> int | None:
    entry = get_controller_entry(controller_mac)
    channel = entry.get("midi_channel")
    if isinstance(channel, int) and 1 <= channel <= 16:
        return channel
    return None


def get_controller_name(controller_mac: bytes | str) -> str:
    entry = get_controller_entry(controller_mac)
    value = str(entry.get("name", "")).strip()
    if value:
        return value
    return _default_controller_name(get_saved_controller_channel(controller_mac))


def set_controller_name(controller_mac: bytes | str, name: str) -> int:
    mac_key = _mac_key(controller_mac)
    normalized_name = str(name).strip()
    if not normalized_name:
        normalized_name = _default_controller_name(get_saved_controller_channel(controller_mac))
    return update_config(_controller_path(mac_key) + ["name"], normalized_name)


def is_controller_muted(controller_mac: bytes | str) -> bool:
    return bool(get_controller_entry(controller_mac).get("muted", False))


def set_controller_muted(controller_mac: bytes | str, muted: bool) -> int:
    mac_key = _mac_key(controller_mac)
    return update_config(_controller_path(mac_key) + ["muted"], bool(muted))


def set_controller_midi_channel(controller_mac: bytes | str, midi_channel: int) -> int:
    mac_key = _mac_key(controller_mac)
    return update_config(_controller_path(mac_key) + ["midi_channel"], midi_channel)


def remove_controller_entry(controller_mac: bytes | str) -> int:
    mac_key = _mac_key(controller_mac)
    with _lock:
        config = get_config()
        controllers_cfg = config.setdefault("controllers", {})
        controllers_cfg.pop(mac_key, None)
        version = _bump_version_locked()
    _notify_subscribers(version)
    return version


def update_controller_override(controller_mac: bytes | str, path: List[str], value: Any) -> int:
    mac_key = _mac_key(controller_mac)
    return update_config(_controller_path(mac_key) + path, value)


def get_effective_controller_config(controller_mac: bytes | str) -> Dict[str, Any]:
    with _lock:
        config = get_config()
        defaults = copy.deepcopy(config.get("defaults", {}))
        controller_cfg = copy.deepcopy(config.get("controllers", {}).get(_mac_key(controller_mac), {}))

    effective = {
        "mappings": _normalize_mappings(defaults.get("mappings", [])),
        "hit": _normalize_hit_config(defaults.get("hit", {})),
        "muted": bool(controller_cfg.get("muted", False)),
    }

    controller_mappings = _normalize_mappings(controller_cfg.get("mappings", []))
    if controller_mappings:
        effective["mappings"] = controller_mappings

    controller_hit = controller_cfg.get("hit", {})
    if isinstance(controller_hit, dict):
        effective["hit"] = _deep_merge(effective["hit"], controller_hit)

    effective["hit"] = _normalize_hit_config(effective["hit"])

    return effective
