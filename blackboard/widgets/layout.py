import math

from qtpy import QtCore, QtWidgets


class FlowLayout(QtWidgets.QLayout):
    """Layout that wraps items into rows, with optional uniform widths.

    When uniform mode is enabled, items in the same row share equal widths and
    rows are balanced using a column/row calculation.

    When uniform mode is disabled, items keep their own sizeHint().width()
    and are laid out greedily from left to right, wrapping when needed.
    """

    def __init__(
            self,
            min_item_width: int,
            h_spacing: int,
            v_spacing: int,
            parent: QtWidgets.QWidget | None = None,
            uniform: bool = True,
    ):
        """Initialize the flow layout.

        Args:
            min_item_width: Minimum width used to estimate column counts.
            h_spacing: Horizontal spacing between items.
            v_spacing: Vertical spacing between rows.
            parent: Optional parent widget.
            uniform: If True, items in each row are given uniform width.
        """
        super().__init__(parent)

        # Store the arguments
        self._items: list[QtWidgets.QLayoutItem] = []
        self._min_item_width = min_item_width
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._uniform = bool(uniform)

    # Public API
    # ----------
    def set_uniform(self, enabled: bool):
        """Enable or disable uniform item widths per row."""
        self._uniform = bool(enabled)
        self.invalidate()
        self.update()

    def is_uniform(self) -> bool:
        """Return True if uniform item widths are enabled."""
        return self._uniform

    # Overridden Methods
    # ------------------
    def addItem(self, item: QtWidgets.QLayoutItem):
        self._items.append(item)
        self.invalidate()

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QtWidgets.QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QtWidgets.QLayoutItem | None:
        if 0 <= index < len(self._items):
            item = self._items.pop(index)
            self.invalidate()
            return item
        return None

    def expandingDirections(self) -> QtCore.Qt.Orientation:
        return QtCore.Qt.Orientations(QtCore.Qt.Horizontal)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        if not self._items:
            return 0

        left, top, right, bottom = self.getContentsMargins()
        usable_width = max(1, width - left - right)

        if self._uniform:
            # Same logic as before: estimate rows from min_item_width.
            count = len(self._items)
            max_columns = max(1, usable_width // self._min_item_width)
            rows = math.ceil(count / max_columns)
            row_height = max(item.sizeHint().height() for item in self._items)
            return (
                rows * row_height
                + self._v_spacing * max(0, rows - 1)
                + top
                + bottom
            )

        # Non-uniform: greedy flow using each item's sizeHint().width().
        total_height = 0
        row_width = 0
        row_height = 0
        first_in_row = True

        for item in self._items:
            hint = item.sizeHint()
            item_w = hint.width()
            item_h = hint.height()

            needed_width = item_w
            if not first_in_row:
                needed_width += self._h_spacing

            if not first_in_row and row_width + needed_width > usable_width:
                # Finish current row and start a new one.
                total_height += row_height
                total_height += self._v_spacing
                row_width = 0
                row_height = 0
                first_in_row = True

            if first_in_row:
                row_width = item_w
                row_height = item_h
                first_in_row = False
            else:
                row_width += self._h_spacing + item_w
                row_height = max(row_height, item_h)

        # Add last row if any items.
        if not first_in_row:
            total_height += row_height

        return total_height + top + bottom

    def sizeHint(self) -> QtCore.QSize:
        return self.minimumSize()

    def minimumSize(self) -> QtCore.QSize:
        left, top, right, bottom = self.getContentsMargins()

        if not self._items:
            return QtCore.QSize(0, 0)

        if self._uniform:
            width = self._min_item_width + left + right
            height = max(item.sizeHint().height() for item in self._items) + top + bottom
            return QtCore.QSize(width, height)

        # Non-uniform: use max sizeHint as a conservative minimum.
        max_w = max(item.sizeHint().width() for item in self._items)
        max_h = max(item.sizeHint().height() for item in self._items)
        return QtCore.QSize(max_w + left + right, max_h + top + bottom)

    def setGeometry(self, rect: QtCore.QRect):
        super().setGeometry(rect)
        if not self._items:
            return

        if self._uniform:
            self._set_geometry_uniform(rect)
        else:
            self._set_geometry_non_uniform(rect)

    # Internal layout helpers
    # -----------------------
    def _set_geometry_uniform(self, rect: QtCore.QRect):
        """Lay out items with uniform width per row (balanced rows).
        """
        left, top, right, bottom = self.getContentsMargins()
        usable_width = max(1, rect.width() - left - right)
        count = len(self._items)

        max_columns = max(1, usable_width // self._min_item_width)
        rows = math.ceil(count / max_columns)
        columns = math.ceil(count / rows)

        x_origin = rect.x() + left
        y = rect.y() + top

        index = 0
        for row_index in range(rows):
            items_in_row = min(columns, count - index)
            if items_in_row <= 0:
                break

            row_space = max(1, usable_width - self._h_spacing * (items_in_row - 1))
            base_width = row_space // items_in_row
            extra = row_space - base_width * items_in_row

            x = x_origin
            row_height = 0
            for col in range(items_in_row):
                item = self._items[index]
                width = base_width + (1 if col < extra else 0)
                height = item.sizeHint().height()
                item.setGeometry(QtCore.QRect(x, y, width, height))
                x += width + self._h_spacing
                row_height = max(row_height, height)
                index += 1

            y += row_height
            if row_index < rows - 1:
                y += self._v_spacing

    def _set_geometry_non_uniform(self, rect: QtCore.QRect):
        """Lay out items with their natural widths (greedy flow).
        """
        left, top, right, bottom = self.getContentsMargins()
        usable_width = max(1, rect.width() - left - right)

        x = rect.x() + left
        y = rect.y() + top
        row_height = 0
        first_in_row = True

        for item in self._items:
            hint = item.sizeHint()
            item_w = hint.width()
            item_h = hint.height()

            needed_width = item_w
            if not first_in_row:
                needed_width += self._h_spacing

            if not first_in_row and (x - (rect.x() + left)) + needed_width > usable_width:
                # Move to next row.
                x = rect.x() + left
                y += row_height + self._v_spacing
                row_height = 0
                first_in_row = True

            if not first_in_row:
                x += self._h_spacing

            item.setGeometry(QtCore.QRect(x, y, item_w, item_h))
            x += item_w
            row_height = max(row_height, item_h)
            first_in_row = False
