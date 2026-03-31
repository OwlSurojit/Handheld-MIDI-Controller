from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QAbstractItemView, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from server.config import get_controller_entry
from server.shared_state import controllers, register_controller_removed_callback, register_new_controller_callback
from server.ui.widgets.controller_card import ControllerCard


class ControllerListWidget(QWidget):
    focused_controller_changed = pyqtSignal(object)
    selection_changed = pyqtSignal()
    visualise_requested = pyqtSignal(bytes)
    mute_selected_requested = pyqtSignal()
    unmute_selected_requested = pyqtSignal()
    rezero_selected_requested = pyqtSignal()
    new_controller_signal = pyqtSignal(object)
    controller_removed_signal = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[bytes, ControllerCard] = {}
        self._items: dict[bytes, QListWidgetItem] = {}
        self._syncing_selection = False
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        top_actions = QHBoxLayout()
        top_actions.setSpacing(8)
        self.select_all_button = QPushButton("Select All")
        self.select_all_button.clicked.connect(self.select_all)
        top_actions.addWidget(self.select_all_button)

        self.clear_button = QPushButton("Clear Selection")
        self.clear_button.clicked.connect(self.clear_selection)
        top_actions.addWidget(self.clear_button)
        top_actions.addStretch()
        layout.addLayout(top_actions)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_widget.setSpacing(2)
        # Keep native selection mechanics but suppress default rectangular highlight
        # so card-level rounded styling is the only visible selection state.
        palette = self.list_widget.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 0, 0, 0))
        palette.setColor(QPalette.ColorRole.HighlightedText, palette.color(QPalette.ColorRole.Text))
        self.list_widget.setPalette(palette)
        self.list_widget.setStyleSheet(
            "QListWidget::item:selected{background:transparent;}"
            "QListWidget::item:hover{background:transparent;}"
        )
        self.list_widget.itemSelectionChanged.connect(self._on_item_selection_changed)
        self.list_widget.currentItemChanged.connect(self._on_current_item_changed)
        layout.addWidget(self.list_widget)

        bottom_actions = QHBoxLayout()
        bottom_actions.setSpacing(8)

        self.mute_selected_button = QPushButton("Mute Selected")
        self.mute_selected_button.clicked.connect(self.mute_selected_requested.emit)
        bottom_actions.addWidget(self.mute_selected_button)

        self.unmute_selected_button = QPushButton("Unmute Selected")
        self.unmute_selected_button.clicked.connect(self.unmute_selected_requested.emit)
        bottom_actions.addWidget(self.unmute_selected_button)

        self.rezero_selected_button = QPushButton("Re-zero Selected")
        self.rezero_selected_button.clicked.connect(self.rezero_selected_requested.emit)
        bottom_actions.addWidget(self.rezero_selected_button)

        bottom_actions.addStretch()
        layout.addLayout(bottom_actions)

        self.new_controller_signal.connect(lambda _state: self.rebuild())
        self.controller_removed_signal.connect(self._on_controller_removed)
        register_new_controller_callback(self.new_controller_signal.emit)
        register_controller_removed_callback(self.controller_removed_signal.emit)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(350)
        self.refresh_timer.timeout.connect(self.refresh_visible_cards)
        self.refresh_timer.start()

        self.rebuild()

    @property
    def focused_controller(self) -> bytes | None:
        current = self.list_widget.currentItem()
        mac = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        return mac if isinstance(mac, bytes) else None

    def selected_controller_ids(self) -> set[bytes]:
        selected: set[bytes] = set()
        for item in self.list_widget.selectedItems():
            mac = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(mac, bytes):
                selected.add(mac)
        return selected

    def selected_states(self):
        return [controllers[mac] for mac in self.selected_controller_ids() if mac in controllers]

    def set_focused_controller(self, controller_mac: bytes | None):
        if controller_mac not in self._items:
            controller_mac = None
        if controller_mac is not None:
            item = self._items[controller_mac]
            self._syncing_selection = True
            self.list_widget.clearSelection()
            item.setSelected(True)
            self.list_widget.setCurrentItem(item)
            self._syncing_selection = False
        else:
            self._syncing_selection = True
            self.list_widget.setCurrentItem(None)
            self._syncing_selection = False
        self.refresh_visible_cards()
        self.focused_controller_changed.emit(self.focused_controller)

    def select_all(self):
        self._syncing_selection = True
        if self.list_widget.count() > 0 and self.list_widget.currentRow() < 0:
            self.list_widget.setCurrentRow(0)
        self.list_widget.selectAll()
        self._syncing_selection = False
        self.refresh_visible_cards()
        self.selection_changed.emit()
        self.focused_controller_changed.emit(self.focused_controller)

    def clear_selection(self):
        self._syncing_selection = True
        self.list_widget.clearSelection()
        self.list_widget.setCurrentItem(None)
        self._syncing_selection = False
        self.refresh_visible_cards()
        self.selection_changed.emit()
        self.focused_controller_changed.emit(None)

    def sync_runtime_settings(self):
        for mac, state in controllers.items():
            cfg = get_controller_entry(mac)
            raw_channel = cfg.get("midi_channel", state.midi_channel)
            if isinstance(raw_channel, int) and 1 <= raw_channel <= 16:
                state.midi_channel = raw_channel
            state.set_name(str(cfg.get("name", "")).strip() or f"Controller {state.midi_channel}")
            state.set_muted(bool(cfg.get("muted", False)))
        self.refresh_visible_cards()

    def _on_controller_removed(self, mac):
        self.rebuild()

    def _on_card_clicked(self, controller_mac: bytes, modifiers, requested_checked):
        item = self._items.get(controller_mac)
        if item is None:
            return

        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        self._syncing_selection = True
        if requested_checked:
            item.setSelected(True)
            self.list_widget.setCurrentItem(item)
        elif requested_checked is False:
            if self.list_widget.currentItem() is item:
                self.list_widget.setCurrentItem(None)
            item.setSelected(False)
        elif ctrl:
            item.setSelected(not item.isSelected())
            self.list_widget.setCurrentItem(item)
        else:
            self.list_widget.clearSelection()
            item.setSelected(True)
            self.list_widget.setCurrentItem(item)
        self._syncing_selection = False

        # Keep current item selected so "focused" is always part of selection.
        current_item = self.list_widget.currentItem()
        if current_item is not None and not current_item.isSelected():
            current_item.setSelected(True)
        self.refresh_visible_cards()
        self.selection_changed.emit()
        self.focused_controller_changed.emit(self.focused_controller)

    def _on_current_item_changed(self, current, _previous):
        if self._syncing_selection:
            return
        if current is not None and not current.isSelected():
            current.setSelected(True)
        self.refresh_visible_cards()
        self.focused_controller_changed.emit(self.focused_controller)

    def _on_item_selection_changed(self):
        if self._syncing_selection:
            return
        current = self.list_widget.currentItem()
        if current is not None and not current.isSelected():
            current.setSelected(True)
        self.refresh_visible_cards()
        self.selection_changed.emit()

    def rebuild(self):
        old_focus = self.focused_controller
        old_selection = self.selected_controller_ids()
        self.list_widget.clear()
        self._cards.clear()
        self._items.clear()

        if not controllers:
            empty_item = QListWidgetItem("No controllers detected.")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(empty_item)
            self.focused_controller_changed.emit(None)
            self.selection_changed.emit()
            return

        self._syncing_selection = True
        first_item = None

        for mac, state in sorted(controllers.items()):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, mac)
            card = ControllerCard(state)
            card.clicked.connect(self._on_card_clicked)
            card.visualise_requested.connect(self.visualise_requested.emit)
            item.setSizeHint(card.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, card)

            if first_item is None:
                first_item = item
            self._cards[mac] = card
            self._items[mac] = item

            if mac in old_selection:
                item.setSelected(True)

        if old_focus is not None and old_focus in self._items:
            focused_item = self._items[old_focus]
            focused_item.setSelected(True)
            self.list_widget.setCurrentItem(focused_item)
        elif first_item is not None:
            first_item.setSelected(True)
            self.list_widget.setCurrentItem(first_item)
        self._syncing_selection = False

        self.refresh_visible_cards()
        self.selection_changed.emit()
        self.focused_controller_changed.emit(self.focused_controller)

    def refresh_visible_cards(self):
        focused = self.focused_controller
        for mac, card in list(self._cards.items()):
            if mac not in controllers:
                continue
            card.refresh_from_state()
            item = self._items.get(mac)
            card.set_selected(item.isSelected() if item is not None else False)
            card.set_focused(focused == mac)
