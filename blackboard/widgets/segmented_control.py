from __future__ import annotations

from typing import Iterable

from qtpy import QtCore, QtWidgets

from blackboard.widgets import FlowLayout


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

        self._items: list[str] = []
        self._buttons: list[QtWidgets.QToolButton] = []
        self._group = QtWidgets.QButtonGroup(
            self,
            exclusive=True,
        )

        self.__init_ui()
        self.__init_connections()

        self.set_items(items)

    def __init_ui(self):
        """Initialize the UI and create buttons.
        """
        self._layout = FlowLayout(
            min_item_width=self.MIN_ITEM_WIDTH,
            h_spacing=self.H_SPACING,
            v_spacing=self.V_SPACING,
            parent=self,
        )
        self._layout.setContentsMargins(
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
            self.CONTENT_MARGIN,
        )

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

    def set_items(self, items: Iterable[str]) -> list[QtWidgets.QToolButton]:
        """Set multiple segments to the control.

        Args:
            items: Iterable of text labels for new segments.

        Returns:
            List of created QToolButton instances.
        """
        self._items = list(items)
        for index, text in enumerate(self._items):
            button = QtWidgets.QToolButton(
                self,
                text=text,
                checkable=True,
                autoRaise=False,
                minimumHeight=self.ITEM_HEIGHT,
            )
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Fixed,
            )

            self._group.addButton(button, index)
            self._buttons.append(button)
            self._layout.addWidget(button)

        if self._buttons:
            self._buttons[0].setChecked(True)

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
