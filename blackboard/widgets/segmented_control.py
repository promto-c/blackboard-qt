from __future__ import annotations

from typing import Iterable

import math

from qtpy import QtCore, QtGui, QtWidgets


# Segmented Controls
# ------------------
class SegmentedControl(QtWidgets.QFrame):
    """Segmented control with uniform items, auto-wrap, and balanced rows."""

    valueChanged = QtCore.Signal(str)

    ITEM_HEIGHT = 32
    MIN_ITEM_WIDTH = 90
    H_SPACING = 4
    V_SPACING = 4
    CONTENT_MARGIN = 4

    # Initialization and Setup
    # ------------------------
    def __init__(
            self,
            items: Iterable[str],
            parent: QtWidgets.QWidget | None = None,
    ):
        """Initialize the segmented control and populate items.

        Args:
            items: Iterable of text labels for each segment.
            parent: Optional parent widget.
        """
        super().__init__(parent)

        self._items: list[str] = list(items)
        self._buttons: list[QtWidgets.QToolButton] = []
        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(True)

        self.__init_ui()
        self.__init_connections()

    def __init_ui(self):
        """Initialize the UI and create buttons.
        """
        self._main_layout = QtWidgets.QVBoxLayout(self)
        self._main_layout.setContentsMargins(
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
        )
        self._main_layout.setSpacing(self.V_SPACING)

        for index, text in enumerate(self._items):
            button = QtWidgets.QToolButton(self)
            button.setText(text)
            button.setCheckable(True)
            button.setAutoRaise(False)
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Fixed,
            )
            button.setMinimumHeight(self.ITEM_HEIGHT)

            self._group.addButton(button, index)
            self._buttons.append(button)

        if self._buttons:
            self._buttons[0].setChecked(True)

        self._rebuild_layout()

    def __init_connections(self):
        """Initialize signal-slot connections.
        """
        self._group.idToggled.connect(self._emit_value_changed)

    # Public Methods
    # --------------
    def current_value(self) -> str:
        """Return the text of the currently selected segment.

        Returns:
            The text of the current segment, or an empty string if none is selected.
        """
        checked = self._group.checkedButton()
        return checked.text() if checked else ""

    @property
    def value(self) -> str:
        """Convenience property for the selected segment text.
        """
        return self.current_value()

    # Private Methods
    # ---------------
    def _clear_rows(self):
        """Remove all row layouts from the main layout (buttons are kept).
        """
        while self._main_layout.count():
            item = self._main_layout.takeAt(0)
            child_layout = item.layout()
            if child_layout is not None:
                # Detach widgets but don't delete them.
                while child_layout.count():
                    sub_item = child_layout.takeAt(0)
                    widget = sub_item.widget()
                    if widget is not None:
                        widget.setParent(self)
                child_layout.deleteLater()

    def _rebuild_layout(self):
        """Rebuild the row layouts based on current width and item count.
        """
        self._clear_rows()

        count = len(self._buttons)
        if not count:
            return

        total_width = max(1, self.width())
        left, top, right, bottom = self._main_layout.getContentsMargins()
        usable_width = max(1, total_width - left - right)

        # Determine maximum columns by minimum width, then balance rows/columns.
        max_columns = max(1, usable_width // self.MIN_ITEM_WIDTH)
        rows = math.ceil(count / max_columns)
        columns = math.ceil(count / rows)

        index = 0
        for _row in range(rows):
            row_layout = QtWidgets.QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(self.H_SPACING)

            items_in_row = min(columns, count - index)
            for col in range(items_in_row):
                button = self._buttons[index]
                row_layout.addWidget(button)
                row_layout.setStretch(col, 1)
                index += 1

            self._main_layout.addLayout(row_layout)

    # Private Methods
    # ---------------
    def _emit_value_changed(self, button_id: int, checked: bool):
        """Emit valueChanged when a button becomes checked.
        """
        if not checked:
            return
        checked_button = self._group.button(button_id)
        if checked_button is not None:
            self.valueChanged.emit(checked_button.text())

    # Overridden Methods
    # ------------------
    def resizeEvent(self, event: QtGui.QResizeEvent):
        """Rebuild layout when the control is resized.
        """
        super().resizeEvent(event)
        self._rebuild_layout()
