from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
)

from server.ui.widgets.config_options import CURVE_OPTIONS


class MappingConfigDialog(QDialog):
    def __init__(self, mapping: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mapping Settings")
        self._loading = True
        self._touched: set[str] = set()

        form = QFormLayout(self)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["cc", "pitch_bend"])
        type_value = mapping.get("type")
        if type_value is None:
            self.type_combo.setCurrentIndex(-1)
        else:
            self.type_combo.setCurrentText(str(type_value or "cc"))
        self.type_combo.currentTextChanged.connect(lambda _v: self._mark_touched("type"))
        form.addRow("Type", self.type_combo)

        self.range_min = QDoubleSpinBox()
        self.range_min.setRange(-10000.0, 9999.0)
        self.range_min.setSpecialValueText(" ")
        self.range_min.setDecimals(4)
        self.range_max = QDoubleSpinBox()
        self.range_max.setRange(-10000.0, 9999.0)
        self.range_max.setSpecialValueText(" ")
        self.range_max.setDecimals(4)
        map_range = mapping.get("range")
        if isinstance(map_range, list) and len(map_range) == 2:
            self.range_min.setValue(float(map_range[0]))
            self.range_max.setValue(float(map_range[1]))
        else:
            self.range_min.setValue(-10000.0)
            self.range_max.setValue(-10000.0)
        self.range_min.valueChanged.connect(lambda _v: self._mark_touched("range_min"))
        self.range_max.valueChanged.connect(lambda _v: self._mark_touched("range_max"))
        form.addRow("Range Min", self.range_min)
        form.addRow("Range Max", self.range_max)

        self.curve_combo = QComboBox()
        self.curve_combo.addItems(CURVE_OPTIONS)
        curve_value = mapping.get("curve")
        if curve_value is None:
            self.curve_combo.setCurrentIndex(-1)
        else:
            self.curve_combo.setCurrentText(str(curve_value or "linear"))
        self.curve_combo.currentTextChanged.connect(lambda _v: self._mark_touched("curve"))
        form.addRow("Curve", self.curve_combo)

        self.curve_amount = QDoubleSpinBox()
        self.curve_amount.setRange(0.0, 10.0)
        self.curve_amount.setSpecialValueText(" ")
        self.curve_amount.setDecimals(3)
        self.curve_amount.setSingleStep(0.05)
        curve_amount_value = mapping.get("curve_amount")
        self.curve_amount.setValue(0.0 if curve_amount_value is None else float(curve_amount_value))
        self.curve_amount.valueChanged.connect(lambda _v: self._mark_touched("curve_amount"))
        form.addRow("Curve Amount", self.curve_amount)

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
        if "type" in self._touched and self.type_combo.currentIndex() >= 0:
            patch["type"] = self.type_combo.currentText()

        if "range_min" in self._touched or "range_max" in self._touched:
            if self.range_min.value() > -10000.0 and self.range_max.value() > -10000.0:
                patch["range"] = [float(self.range_min.value()), float(self.range_max.value())]

        if "curve" in self._touched and self.curve_combo.currentIndex() >= 0:
            patch["curve"] = self.curve_combo.currentText()

        if "curve_amount" in self._touched and self.curve_amount.value() > 0.0:
            patch["curve_amount"] = float(self.curve_amount.value())

        return patch
