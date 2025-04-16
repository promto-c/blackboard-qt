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
        """Check if all characters in the query appear in order in text.
        Returns a list of indices in text where each query character is found.
        If the query is not a subsequence of text, returns an empty list.

        Parameters:
            query (str): The search query (case-insensitive).
            text (str): The text to search within.

        Returns:
            List[int]: A list of indices for each character matched or an empty list if no match.

        Examples:
            >>> TextUtil.fuzzy_match("", "Apple")
            []
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
        query = query.lower()
        text_lower = text.lower()
        indices = []
        pos = 0
        for char in query:
            pos = text_lower.find(char, pos)
            if pos == -1:
                return []
            indices.append(pos)
            pos += 1
        return indices

    @staticmethod
    def fuzzy_match_score(query: str, candidate: str) -> int:
        """Compute the fuzzy match score based on how well the candidate string matches the query.
        The algorithm rewards both contiguous matches in the candidate and matches occurring at the prefix.
        
        Scoring Details:
          - Each matched character contributes a base score.
          - Matches that occur contiguously add an increasing bonus.
          - If the candidate begins with the query, a fixed prefix bonus is awarded.
          - If the entire query is not found in sequence, a score of 0 is returned.

        Parameters:
            query (str): The search query (case-insensitive).
            candidate (str): The text in which to search for the query.

        Returns:
            int: The computed match score. A higher score indicates a better match.

        Examples:
            >>> TextUtil.fuzzy_match_score("pe", "Grape")
            8
            >>> TextUtil.fuzzy_match_score("pe", "Apple")
            6
            >>> TextUtil.fuzzy_match_score("a", "Apple")
            8
            >>> TextUtil.fuzzy_match_score("a", "Date")
            3
            >>> TextUtil.fuzzy_match_score("nan", "Banana")
            15
        """
        # Normalize the candidate and query for case-insensitive matching.
        candidate = candidate.lower()
        qry = query.lower()

        # Scoring parameters.
        base_score = 1          # score for each matched character.
        contiguous_bonus = 2    # bonus for each contiguous match.
        prefix_bonus = 5        # bonus if candidate starts with the query.

        score = 0
        consecutive = 0
        query_index = 0

        for char in candidate:
            if query_index < len(qry) and char == qry[query_index]:
                consecutive += 1
                score += base_score + (consecutive * contiguous_bonus)
                query_index += 1
            else:
                consecutive = 0

        # If the entire query was not matched, return 0
        if query_index != len(qry):
            return 0

        # Add prefix bonus if candidate starts with query.
        if candidate.startswith(qry):
            score += prefix_bonus

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
        parent (Optional[QtWidgets.QWidget]): Parent widget.
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, text: str, parent: Optional[Union[QtWidgets.QWidget, 'DraggableListWidget']] = None):
        super().__init__(parent)

        # Store the arguments
        self._text = text

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
            cursor=QtCore.Qt.CursorShape.SizeAllCursor,
            toolTip="Drag to reorder",
            styleSheet="padding: 0px; margin: 0px;"
        )
        # TODO: Implement as class.
        # Use QPlainTextEdit so that QSyntaxHighlighter can be attached.
        self.label = QtWidgets.QPlainTextEdit(self)
        self.label.setStyleSheet("padding: 0px; margin: 0px; background-color: transparent; border: none")
        self.label.setPlainText(self._text)
        self.label.setReadOnly(True)
        self.label.setDisabled(True)
        self.label.setFrameStyle(QtWidgets.QFrame.NoFrame)
        self.label.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.label.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.label.setFocusPolicy(QtCore.Qt.NoFocus)
        
        self.highlighter = SearchHighlighter(self.label.document())

        # Add Widgets to Layouts
        # ----------------------
        layout = QtWidgets.QHBoxLayout(self, spacing=0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.drag_handle)
        layout.addWidget(self.label)

        self.additional_layout = QtWidgets.QHBoxLayout()
        self.additional_layout.addStretch()
        self.additional_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.additional_layout)

    def set_text(self, text: str):
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


class DraggableListWidget(MomentumScrollArea):
    """A scrollable draggable list with smooth animations supporting both
    vertical and horizontal orientations.

    In vertical mode, items are arranged top-to-bottom with fixed height,
    and the container's height is updated to include the item spacing and container margins.
    In horizontal mode, items are arranged left-to-right with fixed width, and the container's width is updated similarly.

    Args:
        parent (Optional[QtWidgets.QWidget]): Parent widget.
        orientation (QtCore.Qt.Orientation): Primary orientation for layout.
            Use QtCore.Qt.Vertical (default) for a vertical list and
            QtCore.Qt.Horizontal for a horizontal list.
        spacing (int): Space in pixels between adjacent items.
        container_margins (Optional[QtCore.QMargins]): Margins around items inside the container.
            If None, defaults to 0 on all sides.
    """

    # Signals
    itemMoved = QtCore.Signal(int, int, QtWidgets.QWidget)
    itemAdded = QtCore.Signal(QtWidgets.QWidget)
    itemRemoved = QtCore.Signal(QtWidgets.QWidget)

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
        self._cached_order: Optional[List[DraggableItem]] = None
        self.dragged_item: Optional[QtWidgets.QWidget] = None
        self.dragged_index: int = -1
        self.drag_offset = QtCore.QPoint(0, 0)
        self.animation_duration = 120  # milliseconds
        self.item_height = 26
        self.item_width = 100
        # Flag to disable drag operations during filtering.
        self._drag_enabled = True

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
    def add_item(self, text: str | DraggableItem) -> DraggableItem:
        """Adds a new DraggableItem to the list.

        Args:
            text (str or DraggableItem): The text for the new item or an existing DraggableItem.

        Returns:
            DraggableItem: The newly created item.
        """
        if isinstance(text, DraggableItem):
            # If the text is already a DraggableItem, set its parent to the container.
            item = text
            if item.parent() != self.container:
                item.setParent(self.container)
        else:
            # Create a new DraggableItem with the given text.
            item = DraggableItem(text, self.container)

        if self.orientation == QtCore.Qt.Orientation.Vertical:
            item.setFixedHeight(self.item_height)
            # Set width of the item to fill the container minus margins.
            item.setFixedWidth(self.container.width() - (self.container_margins.left() + self.container_margins.right()))
        item.show()
        self.items.append(item)
        # Reposition items instantly (without individual widget animation)
        self._relayout_items()
        self.itemAdded.emit(item)

        return item

    def scroll_to_last(scroll_area: MomentumScrollArea,
                       orientation: QtCore.Qt.Orientation = QtCore.Qt.Orientation.Vertical,
                       animate: bool = None):
        """Smoothly animate scrolling to the end ("last" position) of the scroll area.
        For vertical orientation, it scrolls to the bottom.
        For horizontal orientation, it scrolls to the right.
        
        Args:
            scroll_area (MomentumScrollArea): The scroll area instance.
            orientation (QtCore.Qt.Orientation): The orientation to scroll.
                Use QtCore.Qt.Orientation.Vertical (default) or QtCore.Qt.Orientation.Horizontal.
            animate (bool, optional): Whether to animate the scrolling.
                If None, defaults to the scroll area's visibility (i.e. scroll_area.isVisible()).
                If False, scrolling jumps directly without animation.
        """
        # Determine whether to use animation by default if not provided.
        animate = scroll_area.isVisible() if animate is None else animate

        # Choose the appropriate scroll bar and determine its target value.
        if orientation == QtCore.Qt.Orientation.Vertical:
            scroll_bar = scroll_area.verticalScrollBar()
        else:
            scroll_bar = scroll_area.horizontalScrollBar()

        end_value = scroll_bar.maximum()

        # If animation is disabled, jump directly to the end.
        if not animate:
            scroll_bar.setValue(end_value)
            return

        # Create and configure the scrolling animation.
        anim = QtCore.QPropertyAnimation(
            scroll_bar, b"value", scroll_area,
            duration=250,
            startValue=scroll_bar.value(),
            endValue=end_value,
            easingCurve=QtCore.QEasingCurve.Type.OutCubic
        )
        anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def item_at_pos(self, pos: QtCore.QPoint) -> Optional[int]:
        """Returns the index of the item at the given container position.

        Args:
            pos (QtCore.QPoint): The position relative to the container widget.

        Returns:
            Optional[int]: Index of the item if found; otherwise, None.
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

    def clear_items(self):
        """Removes all items from the list."""
        for item in self.items.copy():
            self.remove_item(item, relayout=False)

    def filter_items(self, query: str):
        """Filter items based on the search query using fuzzy matching and scoring.

        Visible items are those whose original text contains the query's characters in order.
        For visible items, update the highlighter and compute a similarity score using
        TextUtil.fuzzy_match_score. Then sort the visible items by descending score.

        While filtering, drag-to-reorder is disabled.
        When the query is empty, the cached ordering (reflecting the user's custom order)
        is restored.
        """
        if not query:
            # No filter query. Re-enable drag and restore the cached ordering if present.
            self._drag_enabled = True
            if self._cached_order is not None:
                self.items = list(self._cached_order)
                self._cached_order = None
            for item in self.items:
                item.setVisible(True)
                item.highlighter.set_search_text("")
        else:
            self._drag_enabled = False
            # Cache the current ordering if this is the first filtering operation.
            if self._cached_order is None:
                self._cached_order = list(self.items)
            visible_items_with_score = []
            # Use the cached order as the base so that you return to it later.
            for item in self._cached_order:
                if TextUtil.fuzzy_match(query, item.text):
                    item.setVisible(True)
                    item.highlighter.set_search_text(query)
                    score = TextUtil.fuzzy_match_score(query, item.text)
                    visible_items_with_score.append((item, score))
                else:
                    item.setVisible(False)
            visible_items_with_score.sort(key=lambda tup: tup[1], reverse=True)
            sorted_items = [tup[0] for tup in visible_items_with_score]
            self.items = sorted_items
        self._relayout_items()

    def get_visible_items(self) -> List[DraggableItem]:
        """Returns a list of currently visible items.
        
        Returns:
            List[DraggableItem]: List of visible items.
        """
        return [item for item in self.items if item.isVisible()]

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
        """Handles mouse press events on the container.

        Args:
            event (QtGui.QMouseEvent): The mouse press event.

        Returns:
            bool: True if handled.
        """
        if not self._drag_enabled:
            return False
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            idx = self.item_at_pos(event.pos())
            if idx is not None:
                self.dragged_item = self.items[idx]
                self._original_index = idx
                self.dragged_index = idx
                self.drag_offset = event.pos() - self.dragged_item.pos()
                self.dragged_item.raise_()
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
                self._animate_reposition_except(self.dragged_item)
            return True
        return False

    def _mouse_release_event(self, event: QtGui.QMouseEvent) -> bool:
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

    def _relayout_items(self, animate: bool = None):
        """Positions all items according to the orientation, spacing, and margins.

        In vertical mode, items are laid out top-to-bottom; in horizontal mode, left-to-right.
        The container's fixed size is updated accordingly.

        Args:
            animate (bool): Whether to animate item repositioning.
        """
        animate = self.isVisible() if animate is None else animate
        visible_items = self.get_visible_items()
        for i, widget in enumerate(visible_items):
            if self.orientation == QtCore.Qt.Orientation.Vertical:
                x = self.container_margins.left()
                y = self.container_margins.top() + i * (self.item_height + self.spacing)
                target_pos = QtCore.QPoint(x, y)
                widget.setFixedWidth(self.container.width() - (self.container_margins.left() + self.container_margins.right()))
            else:
                x = self.container_margins.left() + i * (self.item_width + self.spacing)
                y = self.container_margins.top()
                target_pos = QtCore.QPoint(x, y)
            if animate:
                self._animate_widget_to(widget, target_pos)
            else:
                widget.move(target_pos)
        if self.orientation == QtCore.Qt.Orientation.Vertical:
            new_height = (self.container_margins.top() +
                          self.container_margins.bottom() +
                          len(visible_items) * self.item_height +
                          (max(len(visible_items) - 1, 0)) * self.spacing)
            self.container.setFixedHeight(new_height)
        else:
            new_width = (self.container_margins.left() +
                         self.container_margins.right() +
                         len(visible_items) * self.item_width +
                         (max(len(visible_items) - 1, 0)) * self.spacing)
            self.container.setFixedWidth(new_width)

    def _animate_reposition_except(self, exclude_widget: QtWidgets.QWidget):
        """Animates items to their new positions, except for the dragged widget.

        Args:
            exclude_widget (QtWidgets.QWidget): The widget to exclude.
        """
        for widget in self.items:
            if widget is exclude_widget or not widget.isVisible():
                continue
            if self.orientation == QtCore.Qt.Orientation.Vertical:
                idx = self.get_visible_items().index(widget)
                x = self.container_margins.left()
                y = self.container_margins.top() + idx * (self.item_height + self.spacing)
                target_pos = QtCore.QPoint(x, y)
            else:
                idx = self.get_visible_items().index(widget)
                x = self.container_margins.left() + idx * (self.item_width + self.spacing)
                y = self.container_margins.top()
                target_pos = QtCore.QPoint(x, y)
            self._animate_widget_to(widget, target_pos)

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
    
    search_field = QtWidgets.QLineEdit()
    search_field.setPlaceholderText("Type to filter items...")

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
        draggable_list_widget.add_item(fruit)
    
    for i in range(1, 4):
        item = DraggableItem(f"Removable Item {i}", draggable_list_widget)
        button = QtWidgets.QPushButton("X", item)
        button.clicked.connect(lambda _, item=item: draggable_list_widget.remove_item(item))
        item.additional_layout.addWidget(button)
        draggable_list_widget.add_item(item)

    search_field.textChanged.connect(draggable_list_widget.filter_items)

    add_item_button = QtWidgets.QPushButton("Add Item")
    # Use a mutable counter stored in a list to generate unique item names.
    item_counter = [1]

    def on_add_item():
        # Create a new item with a unique number.
        new_text = f"New Item {item_counter[0]}"
        new_item = draggable_list_widget.add_item(new_text)
        print("Added item:", new_item.text)
        item_counter[0] += 1
        QtCore.QTimer.singleShot(0, lambda: draggable_list_widget.scroll_to_last())

        print(draggable_list_widget.get_item_texts())

    add_item_button.clicked.connect(on_add_item)

    # Create a separate button to clear all items from the list.
    clear_button = QtWidgets.QPushButton("Clear List")
    clear_button.clicked.connect(draggable_list_widget.clear_items)

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
