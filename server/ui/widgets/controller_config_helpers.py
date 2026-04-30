import copy
from typing import Any

from PyQt5.QtWidgets import QCheckBox, QWidget
from PyQt5.QtCore import Qt


MIXED = object()
_MISSING = object()


def cc_control_width(widget: QWidget) -> int:
    return max(42, widget.fontMetrics().horizontalAdvance("888") + 20)


def deep_apply_patch(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in patch.items():
        if value is MIXED:
            continue
        if isinstance(value, dict):
            current = merged.get(key)
            merged[key] = deep_apply_patch(current if isinstance(current, dict) else {}, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def to_dialog_data(value: Any) -> Any:
    if value is MIXED:
        return None
    if isinstance(value, dict):
        return {k: to_dialog_data(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_dialog_data(v) for v in value]
    return copy.deepcopy(value)


def merge_values(values: list[Any]) -> Any:
    first = values[0]
    if all(v == first for v in values):
        return copy.deepcopy(first)
    return MIXED


def merge_dicts(dicts: list[dict[str, Any]]) -> dict[str, Any]:
    if not dicts:
        return {}

    keys = set()
    for mapping in dicts:
        keys.update(mapping.keys())

    merged: dict[str, Any] = {}
    for key in keys:
        values = [mapping.get(key, _MISSING) for mapping in dicts]
        if any(v is _MISSING for v in values):
            merged[key] = MIXED
            continue
        if all(isinstance(v, dict) for v in values):
            merged[key] = merge_dicts(values)
            continue
        merged[key] = merge_values(values)
    return merged


def mapping_index_map(mappings: list[dict[str, Any]]) -> dict[tuple[str, int], int]:
    counts: dict[str, int] = {}
    index_map: dict[tuple[str, int], int] = {}
    for idx, mapping in enumerate(mappings):
        name = str(mapping.get("name", "")).strip()
        if not name:
            continue
        occ = counts.get(name, 0)
        index_map[(name, occ)] = idx
        counts[name] = occ + 1
    return index_map


def common_mapping_rows(configs: list[dict[str, Any]]) -> list[tuple[tuple[str, int], dict[str, Any]]]:
    if not configs:
        return []

    mapping_lists = [list(cfg.get("mappings", [])) for cfg in configs]
    grouped_all: list[dict[str, list[dict[str, Any]]]] = []
    for mappings in mapping_lists:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for mapping in mappings:
            name = str(mapping.get("name", "")).strip()
            if name:
                grouped.setdefault(name, []).append(mapping)
        grouped_all.append(grouped)

    common_names = set(grouped_all[0].keys())
    for grouped in grouped_all[1:]:
        common_names &= set(grouped.keys())

    rows: list[tuple[tuple[str, int], dict[str, Any]]] = []
    seen_counts: dict[str, int] = {}
    for mapping in mapping_lists[0]:
        name = str(mapping.get("name", "")).strip()
        if not name or name not in common_names:
            continue

        occ = seen_counts.get(name, 0)
        max_common_occ = min(len(grouped[name]) for grouped in grouped_all)
        if occ >= max_common_occ:
            seen_counts[name] = occ + 1
            continue

        per_controller = [grouped[name][occ] for grouped in grouped_all]
        merged = merge_dicts(per_controller)
        merged["name"] = name
        rows.append(((name, occ), merged))
        seen_counts[name] = occ + 1

    return rows


class StrictTristateCheckbox(QCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTristate(True)

    def nextCheckState(self):
        """Overrides the default toggle behavior to skip PartChecked"""
        current = self.checkState()
        if current == Qt.CheckState.Unchecked:
            self.setCheckState(Qt.CheckState.Checked)
        else:
            # Treats Checked and PartiallyChecked as toggling to Unchecked
            self.setCheckState(Qt.CheckState.Unchecked)