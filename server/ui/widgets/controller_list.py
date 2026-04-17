from PyQt5.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QKeySequence, QPalette
from PyQt5.QtWidgets import QAbstractItemView, QAction, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton, QVBoxLayout, QWidget, QWidgetAction

from server.config import get_controller_entry, remove_controller_entry
from server.shared_state import controllers, register_controller_removed_callback, register_new_controller_callback, remove_controller
from server.ui.widgets.controller_card import ControllerCard


class ControllerListWidget(QWidget):
    focused_controller_changed = pyqtSignal(object)
    selection_changed = pyqtSignal()
    visualise_requested = pyqtSignal(bytes)
    mute_selected_requested = pyqtSignal()
    unmute_selected_requested = pyqtSignal()
    rezero_selected_requested = pyqtSignal()
    identify_requested = pyqtSignal(bytes)
    setup_wizard_requested = pyqtSignal()
    new_controller_signal = pyqtSignal(object)
    controller_removed_signal = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[bytes, ControllerCard] = {}
        self._items: dict[bytes, QListWidgetItem] = {}
        self._controller_order: list[bytes] = []
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
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
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
        self.list_widget.customContextMenuRequested.connect(self._open_context_menu)
        self._list_viewport = self.list_widget.viewport()
        if self._list_viewport is not None:
            self._list_viewport.installEventFilter(self)

        self.no_controllers_setup = QWidget(self._list_viewport)
        no_controllers_layout = QVBoxLayout(self.no_controllers_setup)
        no_controllers_layout.setContentsMargins(20, 20, 20, 20)
        no_controllers_layout.setSpacing(12)

        no_controllers_layout.addStretch(1)

        text_row = QHBoxLayout()
        text_row.addStretch(1)
        self.no_controllers_label = QLabel(
            "No controllers detected. To set up your controllers on a new network, click the button below to launch the setup wizard."
        )
        self.no_controllers_label.setWordWrap(True)
        self.no_controllers_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_controllers_label.setMaximumWidth(520)
        text_row.addWidget(self.no_controllers_label)
        text_row.addStretch(1)
        no_controllers_layout.addLayout(text_row)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.setup_wizard_button = QPushButton("Set Up Controllers...")
        self.setup_wizard_button.setMinimumHeight(40)
        self.setup_wizard_button.setMinimumWidth(220)
        self.setup_wizard_button.clicked.connect(self.setup_wizard_requested.emit)
        button_row.addWidget(self.setup_wizard_button)
        button_row.addStretch(1)
        no_controllers_layout.addLayout(button_row)

        no_controllers_layout.addStretch(1)
        self.no_controllers_setup.hide()

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
        self._build_shortcuts()

    def _build_shortcuts(self):
        def _add_action(text: str, shortcut: str, slot):
            action = QAction(text, self)
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.triggered.connect(slot)
            self.addAction(action)
            return action

        self.details_action = _add_action("Details", "Ctrl+D", self.show_details_for_context)
        self.identify_action = _add_action("Identify", "Ctrl+I", self.identify_context_controller)
        self.visualise_action = _add_action("Visualise", "Ctrl+Shift+V", self.visualise_context_controller)
        self.move_up_action = _add_action("Move up", "Alt+Up", self.move_context_controller_up)
        self.move_down_action = _add_action("Move down", "Alt+Down", self.move_context_controller_down)
        self.remove_action = _add_action("Remove", "Delete", self.remove_context_controller)

    def _context_target_mac(self) -> bytes | None:
        focused = self.focused_controller
        if focused in self._items:
            return focused
        selected = self.selected_controller_ids()
        if selected:
            return next(iter(selected))
        return None

    def _show_details(self, mac: bytes) -> None:
        state = controllers.get(mac)
        if state is None:
            return
        name = state.get_name().strip() or f"Controller {state.midi_channel}"
        mac_text = mac.hex()
        ip_text = state.source_ip or "-"
        QMessageBox.information(self, f"{name} Details", f"MAC: {mac_text}\nIP: {ip_text}")

    def show_details_for_context(self):
        mac = self._context_target_mac()
        if mac is not None:
            self._show_details(mac)

    def identify_context_controller(self):
        mac = self._context_target_mac()
        if mac is not None:
            self.identify_requested.emit(mac)

    def visualise_context_controller(self):
        mac = self._context_target_mac()
        if mac is not None:
            self.visualise_requested.emit(mac)

    def _move_controller_by(self, mac: bytes, delta: int):
        if mac not in self._controller_order:
            return
        old_index = self._controller_order.index(mac)
        new_index = old_index + delta
        if new_index < 0 or new_index >= len(self._controller_order):
            return
        self._controller_order[old_index], self._controller_order[new_index] = self._controller_order[new_index], self._controller_order[old_index]
        self.rebuild()
        self.set_focused_controller(mac)

    def move_context_controller_up(self):
        mac = self._context_target_mac()
        if mac is not None:
            self._move_controller_by(mac, -1)

    def move_context_controller_down(self):
        mac = self._context_target_mac()
        if mac is not None:
            self._move_controller_by(mac, 1)

    def _confirm_remove(self, mac: bytes) -> bool:
        state = controllers.get(mac)
        if state is None:
            return False
        display_name = state.get_name().strip() or f"Controller {state.midi_channel}"
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Remove Controller")
        dialog.setText(f"Remove {display_name} ({mac.hex()}) from this session and config?")
        remove_button = dialog.addButton("Remove", QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.exec_()
        return dialog.clickedButton() is remove_button

    def remove_context_controller(self):
        mac = self._context_target_mac()
        if mac is None:
            return
        if not self._confirm_remove(mac):
            return
        remove_controller_entry(mac)
        remove_controller(mac)

    def eventFilter(self, a0, a1):
        if a0 is self._list_viewport and a1 is not None and a1.type() in (QEvent.Type.Resize, QEvent.Type.Show) and self._list_viewport is not None:
            self.no_controllers_setup.setGeometry(self._list_viewport.rect())
        return super().eventFilter(a0, a1)

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
        if mac in self._controller_order:
            self._controller_order = [item for item in self._controller_order if item != mac]
        self.rebuild()

    def _ordered_controller_macs(self) -> list[bytes]:
        if not self._controller_order:
            self._controller_order = sorted(controllers.keys())
            return list(self._controller_order)

        live = set(controllers.keys())
        ordered = [mac for mac in self._controller_order if mac in live]
        missing = sorted(live - set(ordered))
        ordered.extend(missing)
        self._controller_order = ordered
        return list(self._controller_order)

    def _open_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if item is None:
            return

        mac = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(mac, bytes):
            return

        self._syncing_selection = True
        if not item.isSelected():
            self.list_widget.clearSelection()
            item.setSelected(True)
        self.list_widget.setCurrentItem(item)
        self._syncing_selection = False
        self.refresh_visible_cards()
        self.selection_changed.emit()
        self.focused_controller_changed.emit(self.focused_controller)

        menu = QMenu(self)
        title_label = QLabel(f"{controllers[mac].get_name().strip() or f'Controller {controllers[mac].midi_channel}'}")
        title_label.setStyleSheet("font-weight: bold; padding: 4px 12px;")
        title_action = QWidgetAction(menu)
        title_action.setDefaultWidget(title_label)
        menu.addAction(title_action)
        menu.addAction(self.details_action)
        menu.addAction(self.identify_action)
        menu.addAction(self.visualise_action)
        menu.addSeparator()
        menu.addAction(self.move_up_action)
        menu.addAction(self.move_down_action)
        menu.addAction(self.remove_action)

        viewport = self.list_widget.viewport()
        if viewport is None:
            return
        menu.exec_(viewport.mapToGlobal(pos))

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
            if self._list_viewport is not None:
                self.no_controllers_setup.setGeometry(self._list_viewport.rect())
            self.no_controllers_setup.show()
            self._update_empty_state_actions()
            self.focused_controller_changed.emit(None)
            self.selection_changed.emit()
            return

        self.no_controllers_setup.hide()

        self._syncing_selection = True
        first_item = None

        for mac in self._ordered_controller_macs():
            state = controllers.get(mac)
            if state is None:
                continue
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
        self._update_empty_state_actions()
        self.selection_changed.emit()
        self.focused_controller_changed.emit(self.focused_controller)

    def _update_empty_state_actions(self):
        has_controllers = bool(controllers)
        self.select_all_button.setEnabled(has_controllers)
        self.clear_button.setEnabled(has_controllers)
        self.mute_selected_button.setEnabled(has_controllers)
        self.unmute_selected_button.setEnabled(has_controllers)
        self.rezero_selected_button.setEnabled(has_controllers)

    def refresh_visible_cards(self):
        focused = self.focused_controller
        for mac, card in list(self._cards.items()):
            if mac not in controllers:
                continue
            card.refresh_from_state()
            item = self._items.get(mac)
            card.set_selected(item.isSelected() if item is not None else False)
            card.set_focused(focused == mac)
