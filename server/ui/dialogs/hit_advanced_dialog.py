from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QLabel,
    QSpacerItem,
    QFrame,
)

from server.config_consts import CURVE_OPTIONS, MAPPING_SOURCE_OPTIONS
from server.ui.widgets.range_invert_field import RangeInvertField


def _make_section_label(text: str) -> QLabel:
    label = QLabel(text)
    label_font = label.font()
    label_font.setBold(True)
    if label_font.pointSize() > 0:
        label_font.setPointSize(label_font.pointSize() + 1)
    label.setFont(label_font)
    return label


class HitAdvancedDialog(QDialog):
    def __init__(self, hit_cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hit Machine Advanced")
        self._loading = True
        self._touched: set[str] = set()

        params = dict(hit_cfg.get("parameters", {}))
        form = QFormLayout(self)
        
        ### NOTE SOURCE, RANGE, INVERT, CURVE ###
        note_source_label = _make_section_label("Note Mapping")
        form.addRow(note_source_label)

        self.note_source = QComboBox()
        self.note_source.addItems(list(MAPPING_SOURCE_OPTIONS.keys()))
        note_source_value = hit_cfg.get("note_source")
        if note_source_value is None:
            self.note_source.setCurrentIndex(-1)
        else:
            display_value = {v["name"]: k for k, v in MAPPING_SOURCE_OPTIONS.items()}.get(note_source_value, note_source_value)
            self.note_source.setCurrentText(str(display_value))
        self.note_source.currentTextChanged.connect(self._on_note_source_changed)
        form.addRow("Note Source", self.note_source)

        note_range = hit_cfg.get("note_range")
        max_note_range = {v["name"]: v["range"] for v in MAPPING_SOURCE_OPTIONS.values()}.get(hit_cfg.get("note_source"), [-1, 1])
        if not isinstance(note_range, list) or len(note_range) != 2:
            note_range = max_note_range
        if note_range[0] > note_range[1]:
            note_range = [note_range[1], note_range[0]]

        self.note_range_field = RangeInvertField(
            slider_range=list(map(float, max_note_range)),
            value_range=list(map(float, note_range)),
            invert=bool(hit_cfg.get("note_invert", False)),
            checkbox_label="Invert Source Range",
            parent=self,
        )
        self.note_range_field.range_changed.connect(lambda _v: self._mark_touched("note_range"))
        self.note_range_field.invert_changed.connect(lambda _v: self._mark_touched("note_invert"))
        form.addRow("Source Range", self.note_range_field)

        self.note_curve = QComboBox()
        self.note_curve.addItems(CURVE_OPTIONS)
        note_curve_value = hit_cfg.get("note_curve")
        if note_curve_value is None:
            self.note_curve.setCurrentIndex(-1)
        else:
            self.note_curve.setCurrentText(str(note_curve_value))
        self.note_curve.currentTextChanged.connect(lambda _v: self._mark_touched("note_curve"))
        form.addRow("Response Curve", self.note_curve)

        self.note_curve_amount = QDoubleSpinBox()
        self.note_curve_amount.setRange(0.0, 10.0)
        self.note_curve_amount.setSingleStep(0.05)
        self.note_curve_amount.setSpecialValueText(" ")
        self.note_curve_amount.setDecimals(2)
        note_curve_amount_value = hit_cfg.get("note_curve_amount")
        self.note_curve_amount.setValue(0.0 if note_curve_amount_value is None else float(note_curve_amount_value))
        self.note_curve_amount.valueChanged.connect(lambda _v: self._mark_touched("note_curve_amount"))
        form.addRow("Response Curve Amount", self.note_curve_amount)


        # separator = QSpacerItem(0, 20)
        
        form.addRow(Separator())

        ### TIMING & VELOCITY ###
        timing_label = _make_section_label("Timing & Velocity")
        form.addRow(timing_label)
        
        self.hit_window_ms = QSpinBox()
        self.hit_window_ms.setRange(-1, 10000)
        self.hit_window_ms.setSpecialValueText(" ")
        hit_window_val = params.get("hit_window_ms")
        self.hit_window_ms.setValue(-1 if hit_window_val is None else int(hit_window_val))
        self.hit_window_ms.valueChanged.connect(lambda _v: self._mark_touched("hit_window_ms"))
        form.addRow("Hit Window (ms)", self.hit_window_ms)

        self.refractory_ms = QSpinBox()
        self.refractory_ms.setRange(-1, 10000)
        self.refractory_ms.setSpecialValueText(" ")
        refractory_val = params.get("refractory_ms")
        self.refractory_ms.setValue(-1 if refractory_val is None else int(refractory_val))
        self.refractory_ms.valueChanged.connect(lambda _v: self._mark_touched("refractory_ms"))
        form.addRow("Refractory (ms)", self.refractory_ms)

        self.note_duration_ms = QSpinBox()
        self.note_duration_ms.setRange(-1, 1000000)
        self.note_duration_ms.setSpecialValueText(" ")
        note_duration_val = params.get("note_duration_ms")
        self.note_duration_ms.setValue(-1 if note_duration_val is None else int(note_duration_val))
        self.note_duration_ms.valueChanged.connect(lambda _v: self._mark_touched("note_duration_ms"))
        form.addRow("Note Duration (ms)", self.note_duration_ms)


        self.velocity_min = QSpinBox()
        self.velocity_min.setRange(-1, 127)
        self.velocity_min.setSpecialValueText(" ")
        velocity_min_val = params.get("velocity_min")
        self.velocity_min.setValue(-1 if velocity_min_val is None else int(velocity_min_val))
        self.velocity_min.valueChanged.connect(lambda _v: self._mark_touched("velocity_min"))
        form.addRow("Min Velocity", self.velocity_min)

        self.velocity_max = QSpinBox()
        self.velocity_max.setRange(-1, 127)
        self.velocity_max.setSpecialValueText(" ")
        velocity_max_val = params.get("velocity_max")
        self.velocity_max.setValue(-1 if velocity_max_val is None else int(velocity_max_val))
        self.velocity_max.valueChanged.connect(lambda _v: self._mark_touched("velocity_max"))
        form.addRow("Max Velocity", self.velocity_max)

        form.addRow(Separator())


        ### HIT DETECTION THRESHOLDS ###
        threshold_label = _make_section_label("Hit Detection Thresholds")
        form.addRow(threshold_label)

        self.gyro_onset = QSpinBox()
        self.gyro_onset.setRange(-1, 2000)
        self.gyro_onset.setSpecialValueText(" ")
        gyro_onset_val = params.get("gyro_onset_threshold")
        self.gyro_onset.setValue(-1 if gyro_onset_val is None else int(gyro_onset_val))
        self.gyro_onset.valueChanged.connect(lambda _v: self._mark_touched("gyro_onset_threshold"))
        form.addRow("Hit gyro threshold (°/s)", self.gyro_onset)

        self.gyro_release = QSpinBox()
        self.gyro_release.setRange(-2001, 2000)
        self.gyro_release.setSpecialValueText(" ")
        gyro_release_val = params.get("gyro_release_threshold")
        self.gyro_release.setValue(-2001 if gyro_release_val is None else int(gyro_release_val))
        self.gyro_release.valueChanged.connect(lambda _v: self._mark_touched("gyro_release_threshold"))
        form.addRow("Release gyro threshold (°/s)", self.gyro_release)

        self.max_velocity_gyro = QSpinBox()
        self.max_velocity_gyro.setRange(-1, 2000)
        self.max_velocity_gyro.setSpecialValueText(" ")
        max_vel_val = params.get("max_velocity_gyro")
        self.max_velocity_gyro.setValue(-1 if max_vel_val is None else int(max_vel_val))
        self.max_velocity_gyro.valueChanged.connect(lambda _v: self._mark_touched("max_velocity_gyro"))
        form.addRow("Max velocity gyro (°/s)", self.max_velocity_gyro)

        self.accel_onset = QSpinBox()
        self.accel_onset.setRange(-1, 500)
        self.accel_onset.setSpecialValueText(" ")
        accel_onset_val = params.get("accel_onset_threshold")
        self.accel_onset.setValue(-1 if accel_onset_val is None else int(accel_onset_val))
        self.accel_onset.valueChanged.connect(lambda _v: self._mark_touched("accel_onset_threshold"))
        form.addRow("Accel Onset (g)", self.accel_onset)


        ### DIALOG BUTTONS ###

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._loading = False
        
    def _on_note_source_changed(self, text: str):
        #source_name = MAPPING_SOURCE_OPTIONS.get(text, {}).get("name", text)
        max_note_range = MAPPING_SOURCE_OPTIONS.get(text, {}).get("range", [-1, 1])
        self.note_range_field.set_slider_range(max_note_range)
        self._mark_touched("note_source")

    def _mark_touched(self, key: str):
        if not self._loading:
            self._touched.add(key)

    def get_value(self) -> dict:
        patch: dict = {}

        if "note_source" in self._touched and self.note_source.currentIndex() >= 0:
            patch["note_source"] = MAPPING_SOURCE_OPTIONS.get(self.note_source.currentText(), {}).get("name", self.note_source.currentText())

        if "note_range" in self._touched:
            patch["note_range"] = self.note_range_field.value_range()

        if "note_invert" in self._touched:
            patch["note_invert"] = self.note_range_field.is_inverted()

        if "note_curve" in self._touched and self.note_curve.currentIndex() >= 0:
            patch["note_curve"] = self.note_curve.currentText()

        if "note_curve_amount" in self._touched and self.note_curve_amount.value() > 0.0:
            patch["note_curve_amount"] = float(self.note_curve_amount.value())

        params_patch = {}
        if "gyro_onset_threshold" in self._touched and self.gyro_onset.value() >= 0.0:
            params_patch["gyro_onset_threshold"] = float(self.gyro_onset.value())
        if "gyro_release_threshold" in self._touched and self.gyro_release.value() > -2001:
            params_patch["gyro_release_threshold"] = float(self.gyro_release.value())
        if "max_velocity_gyro" in self._touched and self.max_velocity_gyro.value() >= 0.0:
            params_patch["max_velocity_gyro"] = float(self.max_velocity_gyro.value())
        if "accel_onset_threshold" in self._touched and self.accel_onset.value() >= 0.0:
            params_patch["accel_onset_threshold"] = float(self.accel_onset.value())
        if "velocity_min" in self._touched and self.velocity_min.value() >= 0:
            params_patch["velocity_min"] = int(self.velocity_min.value())
        if "velocity_max" in self._touched and self.velocity_max.value() >= 0:
            params_patch["velocity_max"] = int(self.velocity_max.value())
        if "hit_window_ms" in self._touched and self.hit_window_ms.value() >= 0:
            params_patch["hit_window_ms"] = int(self.hit_window_ms.value())
        if "refractory_ms" in self._touched and self.refractory_ms.value() >= 0:
            params_patch["refractory_ms"] = int(self.refractory_ms.value())
        if "note_duration_ms" in self._touched and self.note_duration_ms.value() >= 0:
            params_patch["note_duration_ms"] = int(self.note_duration_ms.value())
        if params_patch:
            patch["parameters"] = params_patch

        return patch


class Separator(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
        self.setFixedHeight(max(12, self.fontMetrics().height() + 4))