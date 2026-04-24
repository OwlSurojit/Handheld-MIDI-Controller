from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QVBoxLayout, QWidget
from superqt import QLabeledDoubleRangeSlider
from numpy import interp


class RangeInvertField(QWidget):
    range_changed = pyqtSignal(object)
    invert_changed = pyqtSignal(bool)

    def __init__(self, slider_range: list[float], value_range: list[float], invert: bool, checkbox_label: str, parent=None):
        super().__init__(parent)

        self.range_slider = QLabeledDoubleRangeSlider(Qt.Orientation.Horizontal)
        self.range_slider.setRange(float(slider_range[0]), float(slider_range[1])) # type: ignore
        self.range_slider.setDecimals(2 if abs(float(slider_range[0])) < 10 else 0)
        self.range_slider.setValue((float(value_range[0]), float(value_range[1])))
        value_label_width = max(30, self.fontMetrics().horizontalAdvance("-999.99") + 6)
        slider_min_width = max(200, value_label_width * 2 + 120)
        # Hotfix to prevent slider labels from being cut off
        self.range_slider.setStyleSheet(f"SliderLabel {{ min-width: {value_label_width}px; }}")
        self.range_slider.setMinimumWidth(slider_min_width)
        self.range_slider.valueChanged.connect(self.range_changed.emit)

        self.invert_checkbox = QCheckBox(checkbox_label)
        self.invert_checkbox.setChecked(bool(invert))
        self.invert_checkbox.toggled.connect(self.invert_changed.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.range_slider)
        layout.addWidget(self.invert_checkbox)

    def value_range(self) -> list[float]:
        return list(self.range_slider.value())

    def is_inverted(self) -> bool:
        return self.invert_checkbox.isChecked()
    
    def set_slider_range(self, slider_range: list[float]):
        old_slider_range = (self.range_slider.minimum(), self.range_slider.maximum())
        old_slider_value = self.range_slider.value()
        self.range_slider.setRange(float(slider_range[0]), float(slider_range[1])) # type: ignore
        self.range_slider.setDecimals(2 if abs(float(slider_range[0])) < 10 else 0)
        new_value_range = (
            max(slider_range[0], interp(old_slider_value[0], old_slider_range, slider_range)),
            min(slider_range[1], interp(old_slider_value[1], old_slider_range, slider_range))
        )
        self.range_slider.setValue(new_value_range)
