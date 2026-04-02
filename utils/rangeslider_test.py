from PyQt5 import QtWidgets as QtW
from PyQt5.QtCore import Qt
from superqt import QLabeledDoubleRangeSlider, QLabeledDoubleSlider

app = QtW.QApplication([])

slider = QLabeledDoubleRangeSlider(Qt.Orientation.Horizontal)
slider.setRange(-1.0, 1.0)
slider.setDecimals(5)
slider.setValue((-0.5, 0.5))
slider.show()

app.exec_()