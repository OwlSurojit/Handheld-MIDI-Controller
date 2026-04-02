from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
)

from server.config_consts import CURVE_OPTIONS, MAPPING_SOURCE_OPTIONS
from server.ui.widgets.range_invert_field import RangeInvertField


class MappingConfigDialog(QDialog):
    DIAL_RANGE = 100
    
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


        map_range = mapping.get("range")
        max_map_range = {v["name"]: v["range"] for v in MAPPING_SOURCE_OPTIONS.values()}.get(mapping.get("source"), [-1, 1])
        if not isinstance(map_range, list) or len(map_range) != 2:
            map_range = max_map_range

        if map_range[0] > map_range[1]:
            map_range = [map_range[1], map_range[0]]

        self.range_invert_field = RangeInvertField(
            slider_range=list(map(float, max_map_range)),
            value_range=list(map(float, map_range)),
            invert=bool(mapping.get("invert", False)),
            checkbox_label="Invert Source Range",
            parent=self,
        )
        self.range_invert_field.range_changed.connect(lambda _v: self._mark_touched("range"))
        self.range_invert_field.invert_changed.connect(lambda _v: self._mark_touched("invert"))
        form.addRow("Source Range", self.range_invert_field)

        # self.range_min = QDial()
        # self.range_min.setNotchesVisible(True)
        # self.range_min.setRange(-self.DIAL_RANGE, self.DIAL_RANGE)
        # #self.range_min.setSpecialValueText(" ")
        # self.range_max = QDial()
        # self.range_max.setNotchesVisible(True)
        # self.range_max.setRange(-self.DIAL_RANGE, self.DIAL_RANGE)
        # self.range_max.setSpecialValueText(" ")
        # self.range_max.setDecimals(4)
        # if isinstance(map_range, list) and len(map_range) == 2:
        #     self.range_min.setValue(int(map_range[0] / max_map_range[0] * self.DIAL_RANGE))
        #     self.range_max.setValue(int(map_range[1] / max_map_range[1] * self.DIAL_RANGE))
        # else:
        #     self.range_min.setValue(self.DIAL_RANGE)
        #     self.range_max.setValue(-self.DIAL_RANGE)
        # self.range_min.valueChanged.connect(lambda _v: self._mark_touched("range_min"))
        # self.range_max.valueChanged.connect(lambda _v: self._mark_touched("range_max"))
        # form.addRow("Range Min", self.range_min)
        # form.addRow("Range Max", self.range_max)

        self.curve_combo = QComboBox()
        self.curve_combo.addItems(CURVE_OPTIONS)
        curve_value = mapping.get("curve")
        if curve_value is None:
            self.curve_combo.setCurrentIndex(-1)
        else:
            self.curve_combo.setCurrentText(str(curve_value or "linear"))
        self.curve_combo.currentTextChanged.connect(lambda _v: self._mark_touched("curve"))
        form.addRow("Response Curve", self.curve_combo)

        self.curve_amount = QDoubleSpinBox()
        self.curve_amount.setRange(0.0, 10.0)
        self.curve_amount.setSpecialValueText(" ")
        self.curve_amount.setDecimals(2)
        self.curve_amount.setSingleStep(0.05)
        curve_amount_value = mapping.get("curve_amount")
        self.curve_amount.setValue(0.0 if curve_amount_value is None else float(curve_amount_value))
        self.curve_amount.valueChanged.connect(lambda _v: self._mark_touched("curve_amount"))
        form.addRow("Response Curve Amount", self.curve_amount)

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

        if "range" in self._touched:
            patch["range"] = self.range_invert_field.value_range()

        if "invert" in self._touched:
            patch["invert"] = self.range_invert_field.is_inverted()

        # if "range_min" in self._touched or "range_max" in self._touched:
        #     if self.range_min.value() > -10000.0 and self.range_max.value() > -10000.0:
        #         patch["range"] = [float(self.range_min.value()), float(self.range_max.value())]

        if "curve" in self._touched and self.curve_combo.currentIndex() >= 0:
            patch["curve"] = self.curve_combo.currentText()

        if "curve_amount" in self._touched and self.curve_amount.value() > 0.0:
            patch["curve_amount"] = float(self.curve_amount.value())

        return patch
