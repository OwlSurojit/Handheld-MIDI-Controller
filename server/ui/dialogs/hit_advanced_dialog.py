from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
)

from server.ui.widgets.config_options import CURVE_OPTIONS, MAPPING_SOURCE_OPTIONS


class HitAdvancedDialog(QDialog):
    def __init__(self, hit_cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hit Machine Advanced")
        self._loading = True
        self._touched: set[str] = set()

        params = dict(hit_cfg.get("parameters", {}))
        form = QFormLayout(self)

        self.note_source = QComboBox()
        self.note_source.addItems(MAPPING_SOURCE_OPTIONS)
        note_source_value = hit_cfg.get("note_source")
        if note_source_value is None:
            self.note_source.setCurrentIndex(-1)
        else:
            self.note_source.setCurrentText(str(note_source_value))
        self.note_source.currentTextChanged.connect(lambda _v: self._mark_touched("note_source"))
        form.addRow("Note Source", self.note_source)

        self.note_range_min = QDoubleSpinBox()
        self.note_range_min.setRange(-10000.0, 9999.0)
        self.note_range_min.setSpecialValueText(" ")
        self.note_range_min.setDecimals(4)
        self.note_range_max = QDoubleSpinBox()
        self.note_range_max.setRange(-10000.0, 9999.0)
        self.note_range_max.setSpecialValueText(" ")
        self.note_range_max.setDecimals(4)
        note_range = hit_cfg.get("note_range")
        if isinstance(note_range, list) and len(note_range) == 2:
            self.note_range_min.setValue(float(note_range[0]))
            self.note_range_max.setValue(float(note_range[1]))
        else:
            self.note_range_min.setValue(-10000.0)
            self.note_range_max.setValue(-10000.0)
        self.note_range_min.valueChanged.connect(lambda _v: self._mark_touched("note_range_min"))
        self.note_range_max.valueChanged.connect(lambda _v: self._mark_touched("note_range_max"))
        form.addRow("Note Range Min", self.note_range_min)
        form.addRow("Note Range Max", self.note_range_max)

        self.note_curve = QComboBox()
        self.note_curve.addItems(CURVE_OPTIONS)
        note_curve_value = hit_cfg.get("note_curve")
        if note_curve_value is None:
            self.note_curve.setCurrentIndex(-1)
        else:
            self.note_curve.setCurrentText(str(note_curve_value))
        self.note_curve.currentTextChanged.connect(lambda _v: self._mark_touched("note_curve"))
        form.addRow("Note Curve", self.note_curve)

        self.note_curve_amount = QDoubleSpinBox()
        self.note_curve_amount.setRange(0.0, 10.0)
        self.note_curve_amount.setSpecialValueText(" ")
        self.note_curve_amount.setDecimals(3)
        note_curve_amount_value = hit_cfg.get("note_curve_amount")
        self.note_curve_amount.setValue(0.0 if note_curve_amount_value is None else float(note_curve_amount_value))
        self.note_curve_amount.valueChanged.connect(lambda _v: self._mark_touched("note_curve_amount"))
        form.addRow("Note Curve Amount", self.note_curve_amount)

        self.gyro_onset = QDoubleSpinBox()
        self.gyro_onset.setRange(-1.0, 10000.0)
        self.gyro_onset.setSpecialValueText(" ")
        gyro_onset_val = params.get("gyro_onset_threshold")
        self.gyro_onset.setValue(-1.0 if gyro_onset_val is None else float(gyro_onset_val))
        self.gyro_onset.valueChanged.connect(lambda _v: self._mark_touched("gyro_onset_threshold"))
        form.addRow("Gyro Onset", self.gyro_onset)

        self.gyro_release = QDoubleSpinBox()
        self.gyro_release.setRange(-10000.0, 10000.0)
        self.gyro_release.setSpecialValueText(" ")
        gyro_release_val = params.get("gyro_release_threshold")
        self.gyro_release.setValue(-10000.0 if gyro_release_val is None else float(gyro_release_val))
        self.gyro_release.valueChanged.connect(lambda _v: self._mark_touched("gyro_release_threshold"))
        form.addRow("Gyro Release", self.gyro_release)

        self.max_velocity_gyro = QDoubleSpinBox()
        self.max_velocity_gyro.setRange(-1.0, 20000.0)
        self.max_velocity_gyro.setSpecialValueText(" ")
        max_vel_val = params.get("max_velocity_gyro")
        self.max_velocity_gyro.setValue(-1.0 if max_vel_val is None else float(max_vel_val))
        self.max_velocity_gyro.valueChanged.connect(lambda _v: self._mark_touched("max_velocity_gyro"))
        form.addRow("Max Velocity Gyro", self.max_velocity_gyro)

        self.accel_onset = QDoubleSpinBox()
        self.accel_onset.setRange(-1.0, 50.0)
        self.accel_onset.setSpecialValueText(" ")
        self.accel_onset.setDecimals(4)
        accel_onset_val = params.get("accel_onset_threshold")
        self.accel_onset.setValue(-1.0 if accel_onset_val is None else float(accel_onset_val))
        self.accel_onset.valueChanged.connect(lambda _v: self._mark_touched("accel_onset_threshold"))
        form.addRow("Accel Onset", self.accel_onset)

        self.velocity_weight = QDoubleSpinBox()
        self.velocity_weight.setRange(-1.0, 1.0)
        self.velocity_weight.setSpecialValueText(" ")
        self.velocity_weight.setDecimals(4)
        vel_weight_val = params.get("velocity_gyro_weight")
        self.velocity_weight.setValue(-1.0 if vel_weight_val is None else float(vel_weight_val))
        self.velocity_weight.valueChanged.connect(lambda _v: self._mark_touched("velocity_gyro_weight"))
        form.addRow("Velocity Gyro Weight", self.velocity_weight)

        self.velocity_min = QSpinBox()
        self.velocity_min.setRange(0, 127)
        self.velocity_min.setSpecialValueText(" ")
        velocity_min_val = params.get("velocity_min")
        self.velocity_min.setValue(0 if velocity_min_val is None else int(velocity_min_val))
        self.velocity_min.valueChanged.connect(lambda _v: self._mark_touched("velocity_min"))
        form.addRow("Velocity Min", self.velocity_min)

        self.velocity_max = QSpinBox()
        self.velocity_max.setRange(0, 127)
        self.velocity_max.setSpecialValueText(" ")
        velocity_max_val = params.get("velocity_max")
        self.velocity_max.setValue(0 if velocity_max_val is None else int(velocity_max_val))
        self.velocity_max.valueChanged.connect(lambda _v: self._mark_touched("velocity_max"))
        form.addRow("Velocity Max", self.velocity_max)

        self.hit_window_ms = QSpinBox()
        self.hit_window_ms.setRange(0, 10000)
        self.hit_window_ms.setSpecialValueText(" ")
        hit_window_val = params.get("hit_window_ms")
        self.hit_window_ms.setValue(0 if hit_window_val is None else int(hit_window_val))
        self.hit_window_ms.valueChanged.connect(lambda _v: self._mark_touched("hit_window_ms"))
        form.addRow("Hit Window (ms)", self.hit_window_ms)

        self.refractory_ms = QSpinBox()
        self.refractory_ms.setRange(0, 10000)
        self.refractory_ms.setSpecialValueText(" ")
        refractory_val = params.get("refractory_ms")
        self.refractory_ms.setValue(0 if refractory_val is None else int(refractory_val))
        self.refractory_ms.valueChanged.connect(lambda _v: self._mark_touched("refractory_ms"))
        form.addRow("Refractory (ms)", self.refractory_ms)

        self.note_duration_ms = QSpinBox()
        self.note_duration_ms.setRange(0, 10000)
        self.note_duration_ms.setSpecialValueText(" ")
        note_duration_val = params.get("note_duration_ms")
        self.note_duration_ms.setValue(0 if note_duration_val is None else int(note_duration_val))
        self.note_duration_ms.valueChanged.connect(lambda _v: self._mark_touched("note_duration_ms"))
        form.addRow("Note Duration (ms)", self.note_duration_ms)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._loading = False

    def _mark_touched(self, key: str):
        if not self._loading:
            self._touched.add(key)

    def get_value(self) -> dict:
        patch: dict = {}

        if "note_source" in self._touched and self.note_source.currentIndex() >= 0:
            patch["note_source"] = self.note_source.currentText()

        if "note_range_min" in self._touched or "note_range_max" in self._touched:
            if self.note_range_min.value() > -10000.0 and self.note_range_max.value() > -10000.0:
                patch["note_range"] = [float(self.note_range_min.value()), float(self.note_range_max.value())]

        if "note_curve" in self._touched and self.note_curve.currentIndex() >= 0:
            patch["note_curve"] = self.note_curve.currentText()

        if "note_curve_amount" in self._touched and self.note_curve_amount.value() > 0.0:
            patch["note_curve_amount"] = float(self.note_curve_amount.value())

        params_patch = {}
        if "gyro_onset_threshold" in self._touched and self.gyro_onset.value() >= 0.0:
            params_patch["gyro_onset_threshold"] = float(self.gyro_onset.value())
        if "gyro_release_threshold" in self._touched and self.gyro_release.value() > -10000.0:
            params_patch["gyro_release_threshold"] = float(self.gyro_release.value())
        if "max_velocity_gyro" in self._touched and self.max_velocity_gyro.value() >= 0.0:
            params_patch["max_velocity_gyro"] = float(self.max_velocity_gyro.value())
        if "accel_onset_threshold" in self._touched and self.accel_onset.value() >= 0.0:
            params_patch["accel_onset_threshold"] = float(self.accel_onset.value())
        if "velocity_gyro_weight" in self._touched and self.velocity_weight.value() >= 0.0:
            params_patch["velocity_gyro_weight"] = float(self.velocity_weight.value())
        if "velocity_min" in self._touched and self.velocity_min.value() > 0:
            params_patch["velocity_min"] = int(self.velocity_min.value())
        if "velocity_max" in self._touched and self.velocity_max.value() > 0:
            params_patch["velocity_max"] = int(self.velocity_max.value())
        if "hit_window_ms" in self._touched and self.hit_window_ms.value() > 0:
            params_patch["hit_window_ms"] = int(self.hit_window_ms.value())
        if "refractory_ms" in self._touched and self.refractory_ms.value() > 0:
            params_patch["refractory_ms"] = int(self.refractory_ms.value())
        if "note_duration_ms" in self._touched and self.note_duration_ms.value() > 0:
            params_patch["note_duration_ms"] = int(self.note_duration_ms.value())
        if params_patch:
            patch["parameters"] = params_patch

        return patch
