# Type Checking Imports
# ---------------------
from typing import List, Optional, Union

# Third Party Imports
# -------------------
from qtpy import QtCore, QtGui, QtWidgets
from tablerqicon import TablerQIcon

# Local Imports
# -------------
from blackboard.widgets.momentum_scroll_widget import MomentumScrollArea


# Class Definitions
# -----------------
class TextUtil:

    @staticmethod
    def fuzzy_match(query: str, text: str) -> List[int]:
        """Check if all characters in the query appear in order in text and return the match
        indices for the optimal (tightest) match. If the query is not a subsequence, returns [].

        The optimal match is defined as the one where the span between the first and last
        matched characters (i.e. last index - first index + 1) is minimized. If there is a tie,
        the match with the later starting index is preferred.

        Examples:
            >>> TextUtil.fuzzy_match("", "Apple")
            []
            >>> TextUtil.fuzzy_match("p", "Apple")
            [1]
            >>> TextUtil.fuzzy_match("ap", "Apple")
            [0, 1]
            >>> TextUtil.fuzzy_match("ae", "Apple")
            [0, 4]
            >>> TextUtil.fuzzy_match("pp", "Apple")
            [1, 2]
            >>> TextUtil.fuzzy_match("aple", "Apple")
            [0, 1, 3, 4]
            >>> TextUtil.fuzzy_match("pl", "Apple")
            [2, 3]
            >>> TextUtil.fuzzy_match("ax", "Apple")
            []
        """
        if not query:
            return []

        best_match = None
        best_span = float('inf')
        best_first = float('inf')
        text_lower = text.lower()
        query_lower = query.lower()

        def dfs(q_idx: int, start: int, path: List[int]):
            """Depth-first search to find the optimal fuzzy match indices."""
            nonlocal best_match, best_span, best_first
            # If matched all characters in the query, evaluate this path.
            if q_idx == len(query_lower):
                current_span = path[-1] - path[0] + 1
                # Pick the match with the smallest span; on ties, pick earliest start.
                if current_span < best_span or (current_span == best_span and path[0] < best_first):
                    best_span = current_span
                    best_first = path[0]
                    best_match = path.copy()
                return

            for i in range(start, len(text_lower)):
                if text_lower[i] == query_lower[q_idx]:
                    path.append(i)
                    dfs(q_idx + 1, i + 1, path)
                    path.pop()

        dfs(0, 0, [])
        return best_match if best_match else []

    @staticmethod
    def fuzzy_match_score(query: str, candidate: str) -> float:
        """Compute an improved fuzzy match score that better reflects the UX.

        Scoring Details:
          - **Base Score:** 10 points per matched character.
          - **Contiguous Bonus:** For each adjacent pair of matched characters, add 5 points.
          - **Prefix Bonus:** If the candidate starts with the query, add 5 points.
          - **Density Bonus:** Proportional bonus for how "tight" the match is.

        Examples:
            >>> TextUtil.fuzzy_match_score("pe", "Grape")
            35.0
            >>> round(TextUtil.fuzzy_match_score("pe", "Apple"), 2)
            26.67
            >>> TextUtil.fuzzy_match_score("a", "Apple")
            25.0
            >>> TextUtil.fuzzy_match_score("a", "Date")
            20.0
            >>> TextUtil.fuzzy_match_score("nan", "Banana")
            50.0
            >>> TextUtil.fuzzy_match_score("ae", "Apple")
            29.0
            >>> round(TextUtil.fuzzy_match_score("ae", "Date"), 2)
            26.67
            >>> TextUtil.fuzzy_match_score("ae", "Removable item")
            25.0
        """
        indices = TextUtil.fuzzy_match(query, candidate)
        if not indices:
            return 0.0

        # Base score: each matched character is worth 10 points
        base_score = len(query) * 10

        # Contiguous bonus: check consecutive indices
        contiguous_bonus = 0
        for i in range(1, len(indices)):
            if indices[i] == indices[i - 1] + 1:
                contiguous_bonus += 5

        # Prefix bonus: add a bonus if the match starts at the beginning
        prefix_bonus = 5 if indices[0] == 0 else 0

        # Density bonus: a tighter match (smaller span) means the query letters are closer together.
        # Span is the distance between the first and last match positions (inclusive).
        span = indices[-1] - indices[0] + 1
        density = len(query) / span
        density_bonus = density * 10
        score = base_score + contiguous_bonus + prefix_bonus + density_bonus

        return score


class SearchHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, parent, background_color: str = "#662"):
        """Initialize the highlighter with the associated document.

        Args:
            parent (QTextDocument): The document to attach the highlighter to.
        """
        super().__init__(parent)
        self.search_text = ""
        self.highlight_format = QtGui.QTextCharFormat()
        self.highlight_format.setBackground(QtGui.QColor(background_color))

    def set_search_text(self, text: str):
        """Update the search text and refresh highlighting.

        Args:
            text (str): The search query.
        """
        self.search_text = text
        self.rehighlight()

    def highlightBlock(self, text: str):
        """Called for each block (line) of text. Applies the highlight format
        based on the fuzzy matching positions from the query.

        Args:
            text (str): The text in the current block.
        """
        if not self.search_text:
            return

        indices = TextUtil.fuzzy_match(self.search_text, text)
        if not indices:
            return

        for idx in indices:
            self.setFormat(idx, 1, self.highlight_format)


class DraggableItem(QtWidgets.QFrame):
    """A simple list item widget holding a label and a button.

    Args:
        text (str): Text to display.
        parent (Optional[QWidget]): Parent widget.
        checkable (bool): If True, a checkbox is added to the item.
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, text: str,
                 parent: Optional[Union[QtWidgets.QWidget, 'DraggableListWidget']] = None,
                 checkable: bool = False,
                 cursor: QtCore.Qt.CursorShape = QtCore.Qt.CursorShape.PointingHandCursor):
        super().__init__(parent, cursor=cursor)

        # Store the arguments
        self._text = text
        self._checkable = checkable
        self._check_state_connection = None

        # Initialize setup
        self.__init_ui()

        # if isinstance(parent, DraggableListWidget):
        #     # If the parent is a DraggableListWidget, add this item to it.
        #     parent.add_item(self)

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Create Widgets
        # --------------
        self.drag_handle = QtWidgets.QLabel(
            self,
            maximumWidth=20,
            pixmap=TablerQIcon(opacity=0.6, stroke_width=1).grip_vertical.pixmap(20, 20),
            cursor=QtCore.Qt.CursorShape.OpenHandCursor,
            toolTip="Drag to reorder",
            styleSheet="padding: 0px; margin: 0px;"
        )
        self.checkbox = QtWidgets.QCheckBox(self, visible=self._checkable)

        # TODO: Implement as class.
        # Use QPlainTextEdit so that QSyntaxHighlighter can be attached.
        self.label = QtWidgets.QPlainTextEdit(self)
        self.label.setStyleSheet("padding: 0px; margin: 0px; background-color: transparent; border: none")
        self.label.setPlainText(self._text)
        self.label.setReadOnly(True)
        self.label.setDisabled(True)
        self.label.setFrameStyle(QtWidgets.QFrame.Shape.NoFrame)
        self.label.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.label.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.label.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        
        self.highlighter = SearchHighlighter(self.label.document())

        # Add Widgets to Layouts
        # ----------------------
        layout = QtWidgets.QHBoxLayout(self, spacing=0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.drag_handle)
        layout.addWidget(self.checkbox)
        layout.addWidget(self.label)

        self.additional_layout = QtWidgets.QHBoxLayout()
        self.additional_layout.addStretch()
        self.additional_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.additional_layout)

    def set_text(self, text: str):
        """Set the text of the item and rehighlight."""
        self._text = text
        self.label.setPlainText(text)
        self.highlighter.rehighlight()

    @property
    def text(self) -> str:
        """Return the text of the item.
        """
        return self._text

    @text.setter
    def text(self, value: str):
        """Set the text of the item.
        """
        self.set_text(value)

    def isChecked(self) -> bool:
        """Return True if the item is checkable and the checkbox is checked,
        otherwise False.
        """
        return self.checkbox.isChecked() if self.checkbox else False

    def setChecked(self, state: bool):
        """Sets the checked state of the item's checkbox if it is checkable.

        Args:
            state (bool): True to check, False to uncheck.
        """
        self.checkbox.setChecked(state)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """Override the mouse press event for checkable items.
        
        For checkable items, if the click is outside the drag handle,
        toggle the checkbox and do not propagate the event further (i.e. no drag).
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._checkable:
            # Toggle the checkbox if the click is inside the drag handle region.
            if not self.drag_handle.geometry().contains(event.pos()):
                if self.checkbox:
                    self.checkbox.toggle()
                event.accept()
                return

        # For non-checkable items or clicks on the drag handle, do the default action.
        super().mousePressEvent(event)


class DraggableListWidget(MomentumScrollArea):
    """A scrollable draggable list with smooth animations supporting both vertical and horizontal orientations.

    In vertical mode, items are arranged top-to-bottom with fixed height,
    and the container's height is updated to include the item spacing and container margins.
    In horizontal mode, items are arranged left-to-right with fixed width.

    Args:
        parent (Optional[QWidget]): Parent widget.
        orientation (QtCore.Qt.Orientation): Orientation of the list.
        spacing (int): Spacing between items.
        container_margins (Optional[QMargins]): Margins around the container.
        widgetResizable (bool): Whether the widget is resizable.
    """

    # Signals
    itemMoved = QtCore.Signal(int, int, DraggableItem)
    itemAdded = QtCore.Signal(DraggableItem)
    itemRemoved = QtCore.Signal(DraggableItem)
    itemCheckStateChanged = QtCore.Signal(DraggableItem, bool)

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None,
                 orientation: QtCore.Qt.Orientation = QtCore.Qt.Orientation.Vertical,
                 spacing: int = 0,
                 container_margins: Optional[QtCore.QMargins] = None,
                 widgetResizable: bool = True):
        super().__init__(parent, widgetResizable=widgetResizable)

        # Store the arguments
        self.orientation = orientation
        self.spacing = spacing
        self.container_margins = container_margins or QtCore.QMargins(0, 0, 0, 0)

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        # The list of items in the current order.
        self.items: List[DraggableItem] = []
        self.visible_items: Optional[List[DraggableItem]] = None
        self.dragged_item: Optional[QtWidgets.QWidget] = None
        self.dragged_index: int = -1
        self.drag_offset = QtCore.QPoint(0, 0)
        self.animation_duration = 120  # milliseconds
        self.item_height = 26
        self.item_width = 100
        # Flag to disable drag operations during filtering.
        self._drag_enabled = True
        # Size hint guards keep embedded uses (e.g. menus) comfortably sized by default.
        self._size_hint_min_items = 4 if self.orientation == QtCore.Qt.Orientation.Vertical else 1
        self._size_hint_max_items: Optional[int] = 10 if self.orientation == QtCore.Qt.Orientation.Vertical else None

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Create a container widget to host the draggable items.
        self.container = QtWidgets.QFrame(self, mouseTracking=True)
        self.setWidget(self.container)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Install an event filter on the container to capture mouse and resize events.
        self.container.installEventFilter(self)

    # Public Methods
    # --------------
    def add_item(self, text: str | DraggableItem, checkable: bool = False) -> DraggableItem:
        """Adds a new DraggableItem to the list.

        Args:
            text (str or DraggableItem): Text for the item, or an existing item.
            checkable (bool): If True, the item will be created as checkable.

        Returns:
            DraggableItem: The added item.
        """
        if isinstance(text, DraggableItem):
            # If the text is already a DraggableItem, set its parent to the container.
            item = text
            if item.parent() != self.container:
                item.setParent(self.container)
        else:
            item = DraggableItem(text, self.container, checkable=checkable)
        if self.orientation == QtCore.Qt.Orientation.Vertical:
            item.setFixedHeight(self.item_height)
            item.setFixedWidth(self.container.width() - (self.container_margins.left() + self.container_margins.right()))
        self.items.append(item)
        idx = len(self.items) - 1
        self._position_item(item, idx, animate=False)
        self._update_container_size()
        self._connect_item_signals(item)
        item.show()
        self.itemAdded.emit(item)

        return item

    def add_items(self,
                  texts: List[Union[str, DraggableItem]],
                  checkable: bool = False
                  ) -> List[DraggableItem]:
        """
        Efficiently add multiple items without any animation.

        Args:
            texts: A list of strings (or DraggableItem instances) to add.
            checkable: If True, each new item will be created as checkable.
        Returns:
            The list of DraggableItem objects that were added.
        """
        # Temporarily turn off widget repaints for speed
        self.container.setUpdatesEnabled(False)

        new_items: List[DraggableItem] = []
        for t in texts:
            new_items.append(self.add_item(t, checkable=checkable))

        # Lay out all items at once, without animation
        self._relayout_items(animate=False)

        # Restore painting and animation
        self.container.setUpdatesEnabled(True)

        return new_items

    def _connect_item_signals(self, item: DraggableItem):
        """Connect per-item signals so consumers can respond to checkbox toggles."""
        if not item._checkable:
            return

        checkbox = item.checkbox
        slot = item._check_state_connection
        if slot is not None:
            try:
                checkbox.stateChanged.disconnect(slot)
            except (TypeError, RuntimeError):
                pass

        def _slot(state: int, _item=item):
            self._handle_item_checkbox_state_changed(_item, state)

        item._check_state_connection = _slot
        checkbox.stateChanged.connect(_slot)

    def _handle_item_checkbox_state_changed(self, item: DraggableItem, state: int):
        """Normalize checkbox state and emit a higher-level signal."""
        is_checked = QtCore.Qt.CheckState(state) == QtCore.Qt.CheckState.Checked
        self.itemCheckStateChanged.emit(item, is_checked)

    def _update_container_size(self):
        """
        Resize the container to fit `count` items (if given) or all items currently in self.items.
        """
        count = len(self.get_visible_items())
        if self.orientation == QtCore.Qt.Orientation.Vertical:
            total = (self.container_margins.top() + self.container_margins.bottom() +
                    count * self.item_height + max(count - 1, 0) * self.spacing)
            self.container.setFixedHeight(total)
        else:
            total = (self.container_margins.left() + self.container_margins.right() +
                    count * self.item_width + max(count - 1, 0) * self.spacing)
            self.container.setFixedWidth(total)

    def scroll_to_last(self,
                       orientation: QtCore.Qt.Orientation = QtCore.Qt.Orientation.Vertical,
                       animate: bool = None):
        """Smoothly animate scrolling to the end ("last" position) of the scroll area.
        """
        # Determine whether to use animation by default if not provided.
        animate = self.isVisible() if animate is None else animate

        # Choose the appropriate scroll bar and determine its target value.
        if orientation == QtCore.Qt.Orientation.Vertical:
            scroll_bar = self.verticalScrollBar()
        else:
            scroll_bar = self.horizontalScrollBar()

        end_value = scroll_bar.maximum()

        # If animation is disabled, jump directly to the end.
        if not animate:
            scroll_bar.setValue(end_value)
            return

        # Create and configure the scrolling animation.
        anim = QtCore.QPropertyAnimation(
            scroll_bar, b"value", self,
            duration=250,
            startValue=scroll_bar.value(),
            endValue=end_value,
            easingCurve=QtCore.QEasingCurve.Type.OutCubic
        )
        anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def item_at_pos(self, pos: QtCore.QPoint) -> Optional[int]:
        """Returns the index of the item at a given container position.

        Args:
            pos (QtCore.QPoint): Relative position.

        Returns:
            Optional[int]: Index if found, else None.
        """
        for i, widget in enumerate(self.items):
            if not widget.isVisible():
                continue
            if widget.geometry().contains(pos):
                return i

    def remove_item(self, item: DraggableItem, relayout: bool = True):
        """Removes an item from the list.

        Args:
            item (DraggableItem): The item to remove.
            
        Returns:
            bool: True if the item was removed, False otherwise.
        """
        if item not in self.items:
            return

        self.items.remove(item)
        item.setParent(None)
        item.deleteLater()
        if relayout:
            # If relayout is True, update the layout of remaining items.
            self._relayout_items()
        self.itemRemoved.emit(item)

    def clear(self):
        """Removes all items from the list."""
        for item in self.items.copy():
            self.remove_item(item, relayout=False)

    def filter_items(self, query: str):
        """Filter items based on the query using fuzzy matching and scoring.

        When no query is given, restore the cached user-defined order.
        Dragging is disabled while filtering.
        """
        if not query:
            # No filter query. Re-enable drag and restore the cached ordering if present.
            self._drag_enabled = True
            self.visible_items = None
            for item in self.items:
                item.drag_handle.setHidden(False)
                item.setVisible(True)
                item.highlighter.set_search_text("")
        else:
            self._drag_enabled = False
            visible_items_with_score = []
            # Use the cached order as the base so that you return to it later.
            for item in self.items:
                item.drag_handle.setHidden(True)
                if TextUtil.fuzzy_match(query, item.text):
                    item.setVisible(True)
                    item.highlighter.set_search_text(query)
                    score = TextUtil.fuzzy_match_score(query, item.text)
                    visible_items_with_score.append((item, score))
                else:
                    item.setVisible(False)
            visible_items_with_score.sort(key=lambda tup: tup[1], reverse=True)
            sorted_items = [tup[0] for tup in visible_items_with_score]
            self.visible_items = sorted_items
        self._relayout_items()

    def get_visible_items(self) -> List[DraggableItem]:
        """Returns a list of currently visible items.
        
        Returns:
            List[DraggableItem]: List of visible items.
        """
        return self.items if self.visible_items is None else self.visible_items

    def get_checked_items(self) -> List[DraggableItem]:
        """Return a list of all DraggableItem instances that are currently checked.

        Returns:
            List[DraggableItem]: Checked items in their current order.
        """
        return [item for item in self.items if item.isChecked()]

    def get_item_texts(self) -> List[str]:
        """Returns a list of texts from all items.
        """
        return [item.text for item in self.items]

    def move_item(self, from_index: int, to_index: int):
        """Moves an item from one index to another.

        Args:
            from_index (int): The current index of the item.
            to_index (int): The desired new index.
        """
        if 0 <= from_index < len(self.items) and 0 <= to_index < len(self.items):
            item = self.items.pop(from_index)
            self.items.insert(to_index, item)
            self._relayout_items()
            self.itemMoved.emit(from_index, to_index, item)

    # Private Methods
    # ---------------
    def _mouse_press_event(self, event: QtGui.QMouseEvent) -> bool:
        """Handles mouse press events on the container. Only initiates a drag if the event
        occurs over the drag handle of an item.
        """
        if not self._drag_enabled:
            return False
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            idx = self.item_at_pos(event.pos())
            if idx is not None:
                item = self.items[idx]
                # Map event position from container to item's coordinate system.
                pos_in_item = item.mapFromParent(event.pos())
                # Initiate drag only if click is inside the drag handle.
                if item.drag_handle.geometry().contains(pos_in_item):
                    self.dragged_item = item
                    self._original_index = idx
                    self.dragged_index = idx
                    self.drag_offset = event.pos() - item.pos()
                    item.raise_()
                    return True
        return False

    def _mouse_move_event(self, event: QtGui.QMouseEvent) -> bool:
        """Handles mouse move events on the container.

        Args:
            event (QtGui.QMouseEvent): The mouse move event.

        Returns:
            bool: True if handled.
        """
        if self.dragged_item and self._drag_enabled:
            if self.orientation == QtCore.Qt.Orientation.Vertical:
                # Clamp new Y position considering container margins.
                min_y = self.container_margins.top()
                max_y = self.container.height() - self.container_margins.bottom() - self.item_height
                new_y = event.pos().y() - self.drag_offset.y()
                new_y = max(min_y, min(new_y, max_y))
                self.dragged_item.move(self.container_margins.left(), new_y)
                # Compute relative position (subtract top margin) and effective cell height.
                relative_y = new_y - self.container_margins.top()
                cell_height = self.item_height + self.spacing
                new_index = int((relative_y + self.item_height / 2) // cell_height)
            else:
                min_x = self.container_margins.left()
                max_x = self.container.width() - self.container_margins.right() - self.item_width
                new_x = event.pos().x() - self.drag_offset.x()
                new_x = max(min_x, min(new_x, max_x))
                self.dragged_item.move(new_x, self.container_margins.top())
                relative_x = new_x - self.container_margins.left()
                cell_width = self.item_width + self.spacing
                new_index = int((relative_x + self.item_width / 2) // cell_width)
            new_index = max(0, min(new_index, len(self.items) - 1))
            if new_index != self.dragged_index:
                old_index = self.dragged_index
                self.items.pop(old_index)
                self.items.insert(new_index, self.dragged_item)
                self.dragged_index = new_index
                self._animate_reposition_except(self.dragged_item, old_index, new_index)
            return True
        return False

    def _mouse_release_event(self, event: QtGui.QMouseEvent) -> bool:
        """Handles mouse release events."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.dragged_item and self._drag_enabled:
            if self.orientation == QtCore.Qt.Orientation.Vertical:
                final_y = self.container_margins.top() + self.dragged_index * (self.item_height + self.spacing)
                final_pos = QtCore.QPoint(self.container_margins.left(), final_y)
            else:
                final_x = self.container_margins.left() + self.dragged_index * (self.item_width + self.spacing)
                final_pos = QtCore.QPoint(final_x, self.container_margins.top())
            self._animate_widget_to(self.dragged_item, final_pos)

            # Emit a signal if the item has been moved.
            if self._original_index != self.dragged_index:
                self.itemMoved.emit(self._original_index, self.dragged_index, self.dragged_item)

            self.dragged_item = None
            self.dragged_index = -1
            return True
        return False

    def _position_item(self, widget: DraggableItem, index: int, animate: bool = True):
        """Position one widget at the given index."""
        if self.orientation == QtCore.Qt.Orientation.Vertical:
            x = self.container_margins.left()
            y = self.container_margins.top() + index * (self.item_height + self.spacing)
            widget.setFixedWidth(self.container.width() - 
                                (self.container_margins.left() + self.container_margins.right()))
        else:
            x = self.container_margins.left() + index * (self.item_width + self.spacing)
            y = self.container_margins.top()
        target = QtCore.QPoint(x, y)
        if animate:
            self._animate_widget_to(widget, target)
        else:
            widget.move(target)

    def _relayout_items(self, animate: bool = None):
        """Positions all items according to the orientation, spacing, and margins.

        In vertical mode, items are laid out top-to-bottom; in horizontal mode, left-to-right.
        The container's fixed size is updated accordingly.

        Args:
            animate (bool): Whether to animate item repositioning.
        """
        animate = self.isVisible() if animate is None else animate

        for i, w in enumerate(self.get_visible_items()):
            self._position_item(w, i, animate)

        # Resize container to fit all items.
        self._update_container_size()

    def _axis_span_for_items(self, item_count: int) -> int:
        """Return the length along the primary axis required for ``item_count`` items."""
        item_count = max(item_count, 0)
        spacing_span = max(item_count - 1, 0) * self.spacing
        if self.orientation == QtCore.Qt.Orientation.Vertical:
            margin_span = self.container_margins.top() + self.container_margins.bottom()
            item_span = item_count * self.item_height
        else:
            margin_span = self.container_margins.left() + self.container_margins.right()
            item_span = item_count * self.item_width
        return margin_span + item_span + spacing_span

    def _effective_items_for_hint(self) -> int:
        visible_count = len(self.get_visible_items())
        min_items = max(self._size_hint_min_items, 0) if self._size_hint_min_items is not None else 0
        count = max(visible_count, min_items)
        if self._size_hint_max_items is not None:
            count = min(count, max(self._size_hint_max_items, min_items))
        return count

    def _apply_size_hint(self, base_size: QtCore.QSize) -> QtCore.QSize:
        """Combine the base size with our content-aware hint."""
        size = QtCore.QSize(max(base_size.width(), 0), max(base_size.height(), 0))
        axis_span = self._axis_span_for_items(self._effective_items_for_hint())
        if self.orientation == QtCore.Qt.Orientation.Vertical:
            size.setHeight(max(size.height(), axis_span))
        else:
            size.setWidth(max(size.width(), axis_span))
        return size

    def _animate_reposition_except(self, exclude_widget: QtWidgets.QWidget, old_index: int, new_index: int):
        """Animates items to their new positions, except for the dragged widget.

        Args:
            exclude_widget (QtWidgets.QWidget): The widget to exclude.
        """
        # Determine the range of affected indices
        start, end = sorted((old_index, new_index))
        for idx in range(start, end + 1):
            widget = self.items[idx]
            if widget is exclude_widget:
                continue

            # Compute target position based on the new index
            if self.orientation == QtCore.Qt.Orientation.Vertical:
                x = self.container_margins.left()
                y = self.container_margins.top() + idx * (self.item_height + self.spacing)
            else:
                x = self.container_margins.left() + idx * (self.item_width + self.spacing)
                y = self.container_margins.top()

            self._animate_widget_to(widget, QtCore.QPoint(x, y))

    def _animate_widget_to(self, widget: QtWidgets.QWidget, end_pos: QtCore.QPoint):
        """Animates a widget's position using QPropertyAnimation.

        Args:
            widget (QtWidgets.QWidget): The widget to animate.
            end_pos (QtCore.QPoint): The destination position.
        """
        anim = QtCore.QPropertyAnimation(
            widget, b"pos", widget,
            startValue=widget.pos(), endValue=end_pos,
            easingCurve=QtCore.QEasingCurve.Type.OutCubic,
            duration=self.animation_duration
        )
        anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    # Overridden Methods
    # ------------------
    def sizeHint(self) -> QtCore.QSize:
        return self._apply_size_hint(super().sizeHint())

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Intercepts events on the container for drag logic and resizing.

        Args:
            obj (QtCore.QObject): The object that sent the event.
            event (QtCore.QEvent): The event to process.

        Returns:
            bool: True if the event is handled; otherwise, False.
        """
        if obj == self.container:
            if event.type() == QtCore.QEvent.Type.Resize:
                # Adjust item width/height when container resizes.
                if self.orientation == QtCore.Qt.Orientation.Vertical:
                    new_width = event.size().width() - (self.container_margins.left() + self.container_margins.right())
                    for widget in self.items:
                        widget.setFixedWidth(new_width)
                return False
            if event.type() == QtCore.QEvent.Type.MouseButtonPress:
                return self._mouse_press_event(event)
            elif event.type() == QtCore.QEvent.Type.MouseMove:
                return self._mouse_move_event(event)
            elif event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                return self._mouse_release_event(event)
        return super().eventFilter(obj, event)
    
    def showEvent(self, event):
        self._relayout_items(animate=False)
        return super().showEvent(event)


# Example Usage
# -------------
if __name__ == "__main__":
    import sys
    from blackboard import theme

    app = QtWidgets.QApplication(sys.argv)
    theme.set_theme(app, 'dark')

    # Create a main window with a vertical layout to hold the draggable list and control buttons.
    main_window = QtWidgets.QWidget()
    
    search_field = QtWidgets.QLineEdit(placeholderText="Type to filter items...")

    draggable_list_widget = DraggableListWidget(
        orientation=QtCore.Qt.Orientation.Vertical,
        spacing=2,
        container_margins=QtCore.QMargins(4, 4, 4, 4)
    )

    # Connect signals to print notifications when items are added, removed, or moved.
    draggable_list_widget.itemAdded.connect(
        lambda item: print("Item added:", item.text)
    )
    draggable_list_widget.itemRemoved.connect(
        lambda item: print("Item removed:", item.text)
    )
    draggable_list_widget.itemMoved.connect(
        lambda old, new, widget: print(f"Item moved: {widget.text} from {old} to {new}")
    )

    for fruit in ["Apple", "Banana", "Cherry", "Date", "Elderberry", "Fig", "Grape"]:
        # Create some items as checkable.
        draggable_list_widget.add_item(fruit, checkable=True)

    for i in range(1, 4):
        item = DraggableItem(f"Removable Item {i}", draggable_list_widget, checkable=True)
        button = QtWidgets.QPushButton("X", item)
        button.clicked.connect(lambda _, item=item: draggable_list_widget.remove_item(item))
        item.additional_layout.addWidget(button)
        draggable_list_widget.add_item(item)

    draggable_list_widget.add_items(["One", "Two", "Three"], checkable=True)

    search_field.textChanged.connect(draggable_list_widget.filter_items)

    add_item_button = QtWidgets.QPushButton("Add Item")
    # Use a mutable counter stored in a list to generate unique item names.
    item_counter = [1]

    def on_add_item():
        # Create a new item with a unique number.
        new_text = f"New Item {item_counter[0]}"
        new_item = draggable_list_widget.add_item(new_text, checkable=True)
        print("Added item:", new_item.text)
        item_counter[0] += 1
        QtCore.QTimer.singleShot(0, lambda: draggable_list_widget.scroll_to_last())

        print(draggable_list_widget.get_item_texts())

    add_item_button.clicked.connect(on_add_item)

    # Create a separate button to clear all items from the list.
    clear_button = QtWidgets.QPushButton("Clear List")
    clear_button.clicked.connect(draggable_list_widget.clear)

    main_layout = QtWidgets.QVBoxLayout(main_window)
    main_layout.addWidget(search_field)
    main_layout.addWidget(draggable_list_widget)

    button_layout = QtWidgets.QHBoxLayout()
    button_layout.addWidget(add_item_button)
    button_layout.addWidget(clear_button)
    main_layout.addLayout(button_layout)

    main_window.resize(400, 400)
    main_window.show()

    sys.exit(app.exec_())
