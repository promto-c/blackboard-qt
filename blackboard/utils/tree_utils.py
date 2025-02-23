# Type Checking Imports
# ---------------------
from typing import Any, Callable, List, Optional, Tuple, Dict, Iterable, Union

# Standard Library Imports
# ------------------------
from collections import defaultdict

# Third Party Imports
# -------------------
from qtpy import QtCore, QtGui, QtWidgets


# Class Definitions
# -----------------
class TreeUtil:

    @classmethod
    def get_items(cls, parent_item: Union['QtWidgets.QTreeWidget', 'QtWidgets.QTreeWidgetItem'],
                  is_only_leaf: bool = False, is_only_checked: bool = False,
                  filter_func: Optional[Callable[['QtWidgets.QTreeWidgetItem'], bool]] = None,
                  max_depth: Optional[int] = None, target_depth: Optional[int] = None,
                  current_depth: int = 0,
                  ) -> List['QtWidgets.QTreeWidgetItem']:
        """Recursively gathers all child items from a QTreeWidget, performing a depth-first search traversal.

        Args:
            parent_item (Union[QtWidgets.QTreeWidget, QtWidgets.QTreeWidgetItem]): The parent item or the tree widget 
                to start traversal from. If a QTreeWidget is provided, it starts from the root.
            is_only_leaf (bool): Whether to include only leaf nodes.
            is_only_checked (bool): Whether to include only checked nodes.
            filter_func (Callable[['QtWidgets.QTreeWidgetItem'], bool]): Optional function to filter items.
            max_depth (Optional[int]): The maximum depth to traverse. If None or negative, traverses all depths.
            target_depth (Optional[int]): The specific depth from which to collect items. If None, collects from all depths.
            current_depth (int): The current depth of the traversal. Defaults to 0.

        Returns:
            List['QtWidgets.QTreeWidgetItem']: A list of QtWidgets.QTreeWidgetItem, including all child items in the tree.
        """
        # Get the root item of the tree widget if not provided
        if isinstance(parent_item, QtWidgets.QTreeWidget):
            parent_item = parent_item.invisibleRootItem()

        # Initialize an empty list to hold the traversed items
        items = []

        # If max_depth is defined and current_depth exceeds it, stop traversal
        if max_depth is not None and max_depth >= 0 and current_depth > max_depth:
            return items

        # If target_depth is defined and current_depth does not match it, continue traversal without collecting
        if target_depth is not None and current_depth < target_depth:
            for child_index in range(parent_item.childCount()):
                # Retrieve the child item at the current index
                child_item = parent_item.child(child_index)

                # Recursively add child items, incrementing the current depth
                items.extend(cls.get_items(child_item, is_only_leaf, is_only_checked, filter_func, 
                                           max_depth, target_depth, current_depth + 1))
            return items

        # Recursively traverse the children of the current item
        for child_index in range(parent_item.childCount()):
            # Retrieve and store the child item at the current index
            child_item = parent_item.child(child_index)

            # Optionally filter by check state if only_checked is True
            if is_only_checked and child_item.checkState(0) == QtCore.Qt.CheckState.Unchecked:
                continue

            # Check if the child item has children
            if child_item.childCount() > 0:
                # Recursively add the child items to the list, incrementing the current depth
                items.extend(cls.get_items(child_item, is_only_leaf, is_only_checked, filter_func, 
                                           max_depth, target_depth, current_depth + 1))
                if is_only_leaf:
                    continue

            # Apply the filter function to the child item if provided
            if filter_func and not filter_func(child_item):
                continue

            # Add the child item to the list if target_depth is None or current_depth matches target_depth
            if target_depth is None or current_depth == target_depth:
                items.append(child_item)

        return items

    @staticmethod
    def get_column_values(items: List['QtWidgets.QTreeWidgetItem'], column: int, 
                          role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> List[Optional[str]]:
        """Retrieve values from a specific column across a list of QTreeWidgetItem, using a specified data role.

        Args:
            items (List[QtWidgets.QTreeWidgetItem]): The list of items to extract column values from.
            column (int): The index of the column to retrieve values from.
            role (int): The data role to use when retrieving data. Defaults to DisplayRole.

        Returns:
            List[Optional[str]]: A list of values from the specified column for each item.
        """
        return [item.data(column, role) for item in items]

    @staticmethod
    def show_all_items(tree_widget: 'QtWidgets.QTreeWidget'):
        """Show all items in the QTreeWidget.

        Args:
            tree_widget (QtWidgets.QTreeWidget): The tree widget to expand.
        """
        TreeItemUtil.set_items_visibility([tree_widget.invisibleRootItem()], True)

    @staticmethod
    def hide_all_items(tree_widget: 'QtWidgets.QTreeWidget'):
        """Hide all items in the QTreeWidget.

        Args:
            tree_widget (QtWidgets.QTreeWidget'): The tree widget to collapse.
        """
        TreeItemUtil.set_items_visibility([tree_widget.invisibleRootItem()], False)

    @classmethod
    def get_model_indexes(cls, model: 'QtCore.QAbstractItemModel', parent: 'QtCore.QModelIndex' = QtCore.QModelIndex(), 
                          column: int = 0, is_only_leaf: bool = False, is_only_checked: bool = False,
                          data_match: Optional[Tuple['QtCore.Qt.ItemDataRole', Any]] = None,
                          filter_func: Optional[Callable[['QtCore.QModelIndex'], bool]] = None) -> List['QtCore.QModelIndex']:
        """Retrieve QModelIndexes from a QAbstractItemModel based on specified criteria.

        This function performs a depth-first search of the model's tree structure,
        collecting indexes based on the provided column number. It optionally filters
        indexes to include only leaf nodes, nodes matching specific data, or nodes that
        pass a custom filter function.

        Args:
            model: The QAbstractItemModel to search.
            column: The column number from which to retrieve QModelIndexes.
            is_only_checked: If True, only indexes with checked state will be returned.
            is_only_leaf: True if only leaf node indexes should be returned; False otherwise.
            data_match: Optional tuple (role, value) to match data in the nodes.
            filter_func: Optional function that takes a QModelIndex and returns a bool
                         indicating whether the index should be included.

        Returns:
             List['QtCore.QModelIndex']: A list of QModelIndex objects that meet the specified criteria.
        """
        indexes = []

        if not model:
            return indexes

        # Iterate through the model's rows and columns
        for row in range(model.rowCount(parent)):
            # Get the QModelIndex for the current row
            index = model.index(row, column, parent)
            if not index.isValid():
                continue

            # Optionally filter by check state if only_checked is True
            if is_only_checked and index.data(QtCore.Qt.ItemDataRole.CheckStateRole) == QtCore.Qt.CheckState.Unchecked:
                continue

            # Check if the index is a leaf node
            if model.hasChildren(index):
                indexes.extend(cls.get_model_indexes(model, index, column, is_only_leaf, is_only_checked, data_match, filter_func))
                if is_only_leaf:
                    continue

            # Apply custom filter function if provided
            if filter_func and not filter_func(index):
                continue

            # Match data if a specific role and value are provided
            if data_match is not None:
                role, value = data_match
                if model.data(index, role) != value:
                    continue

            # Add the index to the list
            indexes.append(index)

        return indexes
    
    @classmethod
    def get_model_data_list(cls, model: 'QtCore.QAbstractItemModel', parent: 'QtCore.QModelIndex' = QtCore.QModelIndex(),
                            column: int = 0, is_only_leaf: bool = False, is_only_checked: bool = False,
                            data_match: Optional[Tuple['QtCore.Qt.ItemDataRole', Any]] = None,
                            filter_func: Optional[Callable[['QtCore.QModelIndex'], bool]] = None) -> List[str]:
        """Retrieve data from a QAbstractItemModel based on specified criteria.

        This function retrieves data from the model based on the provided column number.
        It optionally filters data to include only leaf nodes, nodes matching specific data,
        or nodes that pass a custom filter function.

        Args:
            model: The QAbstractItemModel to search.
            parent: The parent QModelIndex to start the search from.
            column: The column number from which to retrieve data.
            is_only_checked: If True, only data from indexes with checked state will be returned.
            is_only_leaf: True if only data from leaf node indexes should be returned; False otherwise.
            data_match: Optional tuple (role, value) to match data in the nodes.
            filter_func: Optional function that takes a QModelIndex and returns a bool
                         indicating whether the index should be included.

        Returns:
            List[str]: A list of data strings that meet the specified criteria.
        """
        indexes = cls.get_model_indexes(model, parent, column, is_only_leaf, is_only_checked, data_match, filter_func)
        return [model.data(index) for index in indexes if index.isValid()]

    @staticmethod
    def get_shown_column_indexes(tree_widget: 'QtWidgets.QTreeWidget') -> List[int]:
        """Get the indexes of the shown columns in the tree widget.

        Args:
            tree_widget (QtWidgets.QTreeWidget): The tree widget to get shown column indexes from.

        Returns:
            List[int]: A list of indexes for the shown columns.
        """
        return [column_index for column_index in range(tree_widget.columnCount()) if not tree_widget.isColumnHidden(column_index)]

    # NOTE: May not use
    @staticmethod
    def get_child_level(item: 'QtWidgets.QTreeWidgetItem') -> int:
        """Get the child level of TreeWidgetItem

        Returns:
            int: The child level of the TreeWidgetItem
        """
        # Initialize child level
        child_level = 0

        # Iterate through the parent items to determine the child level
        while item.parent():
            # Increment child level for each parent
            child_level += 1
            # Update item to be its parent
            item = item.parent()

        # Return the final child level
        return child_level

    @classmethod
    def fit_column_in_view(cls, tree_widget: 'QtWidgets.QTreeWidget'):
        """Adjust the width of all columns to fit the entire view.

            This method resizes columns so that their sum is equal to the width of the view minus the width of the vertical scroll bar. 
        It starts by reducing the width of the column with the largest width by 10% until all columns fit within the expected width.
        """
        # Resize all columns to fit their contents
        cls.resize_all_to_contents(tree_widget)

        # Compute the available width in the view.
        available_width = tree_widget.size().width() - tree_widget.verticalScrollBar().width()
        total_width = sum(tree_widget.columnWidth(column) for column in range(tree_widget.columnCount()))

        # Reduce the width of the widest column until the total width is within bounds.
        while total_width > available_width:
            # Find the column with the largest width
            largest_column = max(range(tree_widget.columnCount()), key=lambda x: tree_widget.columnWidth(x))
            # Reduce the width of the largest column by 10%
            new_width = tree_widget.columnWidth(largest_column) - available_width // 10
            if new_width <= 0:
                break
            tree_widget.setColumnWidth(largest_column, new_width)
            # Update the sum of the column widths
            total_width -= tree_widget.columnWidth(largest_column) - new_width

    @staticmethod
    def resize_all_to_contents(tree_widget: 'QtWidgets.QTreeWidget'):
        """Resize all columns in the object to fit their contents.
        """
        # Iterate through all columns
        for column_index in range(tree_widget.columnCount()):
            # Resize the column to fit its contents
            tree_widget.resizeColumnToContents(column_index)

    @staticmethod
    def get_item_data_dict(tree_widget: 'QtWidgets.QTreeWidget', item: 'QtWidgets.QTreeWidgetItem') -> Dict[str, Optional[str]]:
        """Retrieve data from a QTreeWidgetItem and return it as a dictionary.

        Args:
            tree_widget (QtWidgets.QTreeWidget): The tree widget containing the item.
            item (QtWidgets.QTreeWidgetItem): The item to extract data from.

        Returns:
            Dict[str, Optional[str]]: A dictionary where keys are column headers and values are the data in the corresponding columns.
        """
        data_dict = {}
        
        # Get the column headers from the tree widget
        headers = [tree_widget.headerItem().text(column) for column in range(tree_widget.columnCount())]
        
        # Assuming you want to get data from all columns
        for column in range(item.columnCount()):
            # Retrieve the text from each column of the item using the header as the key
            data_dict[headers[column]] = item.text(column)
        
        return data_dict

    @classmethod
    def get_all_item_data_dicts(cls, tree_widget: 'QtWidgets.QTreeWidget', parent_item: Optional['QtWidgets.QTreeWidgetItem'] = None) -> Dict[str, Dict[str, Optional[str]]]:
        """Retrieve data from all items in the QTreeWidget as a dictionary of dictionaries.

        Args:
            tree_widget (QtWidgets.QTreeWidget): The tree widget to traverse.
            parent_item (Optional[QtWidgets.QTreeWidgetItem]): The parent item to start traversal from. If None, starts from the root.

        Returns:
            Dict[str, Dict[str, Optional[str]]]: A dictionary where keys are item texts and values are dictionaries containing data for each column.
        """
        parent_item = parent_item or tree_widget.invisibleRootItem()
        all_data = {}

        def traverse_item(item: 'QtWidgets.QTreeWidgetItem'):
            item_data = cls.get_item_data_dict(tree_widget, item)
            all_data[item.text(0)] = item_data  # Using the text from the first column as the key

            for row in range(item.childCount()):
                child_item = item.child(row)
                traverse_item(child_item)

        traverse_item(parent_item)
        return all_data

    @staticmethod
    def get_field_names(tree_item: Union[QtWidgets.QTreeWidget, QtWidgets.QTreeWidgetItem]) -> List[str]:
        """Retrieve field/column names from a QTreeWidget or QTreeWidgetItem.

        Args:
            tree_item: The QTreeWidget or QTreeWidgetItem to extract column names from.

        Returns:
            List of column names.
        """
        # Determine if the tree_item is a QTreeWidget or a QTreeWidgetItem
        if isinstance(tree_item, QtWidgets.QTreeWidget):
            header_item = tree_item.headerItem()
        elif isinstance(tree_item, QtWidgets.QTreeWidgetItem):
            header_item = tree_item.treeWidget().headerItem()
        else:
            raise TypeError("tree_item must be a QTreeWidget or QTreeWidgetItem.")

        # Extract and return column names
        return [header_item.data(i, QtCore.Qt.ItemDataRole.UserRole) or header_item.text(i) for i in range(header_item.columnCount())]


class TreeItemUtil:

    @staticmethod
    def get_model_indexes(tree_items: Iterable[QtWidgets.QTreeWidgetItem], only_shown: bool = True, column_index: Optional[int] = None) -> List[QtCore.QModelIndex]:
        """Get the model index for each column in the tree widget.

        Args:
            tree_items (List[QtWidgets.QTreeWidgetItem]): The tree widget items to get model indexes for.
            only_shown (bool): If True, only get indexes for shown columns. If False, get indexes for all columns.
            column_index (Optional[int]): If provided, get indexes for this specific column only.

        Returns:
            List[QtCore.QModelIndex]: A list of model indexes for each column in the tree widget.
        """
        if not tree_items:
            return []

        _reference_item = tree_items[0] if isinstance(tree_items, list) else next(iter(tree_items))
        tree_widget = _reference_item.treeWidget()

        # Determine the list of column indices to process
        if column_index is not None:
            column_indexes = [column_index]
        else:
            column_indexes = (
                only_shown and TreeUtil.get_shown_column_indexes(tree_widget) or 
                range(tree_widget.columnCount())
            )

        model_indexes = []
        for column_index in column_indexes:
            # Get the model index for each column
            model_indexes.extend([
                tree_widget.indexFromItem(tree_item, column_index)
                for tree_item in tree_items
            ])

        # Return the list of model indexes
        return model_indexes

    @staticmethod
    def remove_items(items: List['QtWidgets.QTreeWidgetItem']):
        """Remove the specified QTreeWidgetItems from their parents in the tree widget.

        Args:
            items (List[QtWidgets.QTreeWidgetItem]): The list of items to be removed.
        """
        for item in items:
            # Remove the item from its parent
            parent = item.parent() or item.treeWidget().invisibleRootItem()
            parent.removeChild(item)

    @staticmethod
    def reparent_items(items: List['QtWidgets.QTreeWidgetItem'],
                       target_parent: Optional['QtWidgets.QTreeWidgetItem'] = None):
        """Reparent the specified QTreeWidgetItems to a new parent item in the tree widget.

        Args:
            items (List[QtWidgets.QTreeWidgetItem]): The list of items to be reparented.
            target_parent (Optional[QtWidgets.QTreeWidgetItem]): The new parent item or None for top-level.
        """
        # If the target parent is not specified, use the invisible root item to move items to the top level
        target_parent = target_parent or items[0].treeWidget().invisibleRootItem()

        # Remove items from their current parents and add them to the new parent
        TreeItemUtil.remove_items(items)
        target_parent.addChildren(items)

    @staticmethod
    def group_items_by_field(items: List[QtWidgets.QTreeWidgetItem], field: int, default_group: str = 'uncategorized') -> Dict[str, List[QtWidgets.QTreeWidgetItem]]:
        """Group the data into a dictionary mapping group names to lists of tree items.

        Args:
            items (List[QtWidgets.QTreeWidgetItem]): The data to be grouped.
            field (int): The column index to extract the grouping key.
            default_group (str, optional): The fallback group name if no data is found. Defaults to 'uncategorized'.

        Returns:
            Dict[str, List[QtWidgets.QTreeWidgetItem]]: A dictionary mapping group names to lists of tree items.
        """
        # Create a defaultdict to store the groups
        group_name_to_tree_items = defaultdict(list)

        for item in items:
            key_data = item.data(field, QtCore.Qt.ItemDataRole.UserRole) or default_group
            group_name_to_tree_items[key_data].append(item)

        return group_name_to_tree_items

    @classmethod
    def set_items_visibility(cls, items: List[QtWidgets.QTreeWidgetItem],
                             is_visible: bool,
                             is_affect_parents: bool = True,
                             is_affect_children: bool = True):
        """Set visibility of the specified items, along with their parents and children if desired.

        Args:
            items (List[QtWidgets.QTreeWidgetItem]): The list of items whose visibility will be set.
            is_visible (bool): The visibility state to apply (True for show, False for hide).
            is_affect_parents (bool): Whether to affect the visibility of parent items. Defaults to True.
            is_affect_children (bool): Whether to affect the visibility of child items. Defaults to True.
        """
        for item in items:
            item.setHidden(not is_visible)

            if is_affect_parents:
                cls.__set_parents_visibility(item, is_visible)

            if is_affect_children:
                cls.__set_children_visibility(item, is_visible)

    @staticmethod
    def __set_parents_visibility(item: QtWidgets.QTreeWidgetItem, is_visible: bool):
        """Set visibility of all parent items of the given item.

        Args:
            item (QtWidgets.QTreeWidgetItem): The item whose parents' visibility will be set.
            is_visible (bool): Whether items should be visible (True for show, False for hide).
        """
        parent = item.parent()
        while parent:
            parent.setHidden(not is_visible)
            if is_visible:
                parent.setExpanded(True)
            parent = parent.parent()

    @classmethod
    def __set_children_visibility(cls, item: QtWidgets.QTreeWidgetItem, is_visible: bool):
        """Set visibility of all child items of the given item.

        Args:
            item (QtWidgets.QTreeWidgetItem): The item whose children's visibility will be set.
            is_visible (bool): Whether items should be visible (True for show, False for hide).
        """
        for i in range(item.childCount()):
            child = item.child(i)
            child.setHidden(not is_visible)
            cls.__set_children_visibility(child, is_visible)


class ItemOverlay(QtCore.QObject):
    """An overlay to add a hoverable widget to items in various item-based widgets.

    This overlay allows you to add any widget (e.g., buttons, labels) to the right side of an item
    in widgets like QTreeWidget, QListWidget, or QTableWidget when the mouse hovers over it.

    Attributes:
        hover_widget (QtWidgets.QWidget): The widget that appears on hover.
        parent_widget (QtWidgets.QAbstractItemView): The widget to which this overlay is applied.
        current_item (QtWidgets.QTreeWidgetItem or QtWidgets.QListWidgetItem or QtWidgets.QTableWidgetItem):
            The item currently hovered by the mouse.
    """

    def __init__(self, hover_widget: QtWidgets.QWidget):
        """Initialize the ItemOverlay with the specified hover widget.

        Args:
            hover_widget (QtWidgets.QWidget): The widget to display when hovering over an item.
        """
        super().__init__(hover_widget)
        self.hover_widget = hover_widget
        self.parent_widget: QtWidgets.QAbstractItemView = None
        self._current_item = None

        self.hover_widget.hide()

    def register_to(self, parent_widget: QtWidgets.QAbstractItemView):
        """Register the overlay to the specified item-based widget.

        Args:
            parent_widget (QtWidgets.QAbstractItemView): The widget to enhance with a hoverable widget.
        """
        self.parent_widget = parent_widget
        self.parent_widget.setMouseTracking(True)
        self.parent_widget.viewport().installEventFilter(self)
        self.hover_widget.setParent(self.parent_widget)

    def handle_mouse_move(self, event: QtGui.QMouseEvent):
        """Handle the mouse move event to show the hover widget on the hovered item.

        Args:
            event (QtGui.QMouseEvent): The mouse move event.
        """
        try:
            item = self.parent_widget.itemAt(event.pos())
        except:
            item = self.parent_widget.indexAt(event.pos())

        if item == self._current_item:
            return

        self.hover_widget.hide()
        if item:
            self.show_hover_widget(item)
        self._current_item = item

    def handle_leave_event(self, event: QtCore.QEvent):
        """Handle the leave event to hide the hover widget when the mouse leaves the parent widget.

        Args:
            event (QtCore.QEvent): The leave event.
        """
        # Ensure that the mouse isn't over the hover widget before hiding it
        mouse_pos = self.parent_widget.mapFromGlobal(QtGui.QCursor.pos())
        if not self.hover_widget.geometry().contains(mouse_pos):
            self.hover_widget.hide()
            self._current_item = None

    def show_hover_widget(self, item):
        """Show the hover widget at the right edge of the hovered item.

        Args:
            item: The item currently hovered by the mouse.
        """
        if isinstance(item, QtCore.QModelIndex):
            item_rect = self.parent_widget.visualRect(item)
        else:
            item_rect = self.parent_widget.visualItemRect(item)

        # Adjust for header height if needed
        header_offset = 0
        if isinstance(self.parent_widget, QtWidgets.QTreeView):
            header_offset = self.parent_widget.header().height()
        elif isinstance(self.parent_widget, QtWidgets.QTableView):
            header_offset = self.parent_widget.horizontalHeader().height()

        item_rect.moveTop(item_rect.top() + header_offset)
        self.hover_widget.move(item_rect.right() - self.hover_widget.width(), item_rect.top())
        self.hover_widget.show()

    @property
    def current_item(self):
        """Return the item currently being hovered over by the mouse.

        Returns:
            The currently hovered item.
        """
        return self._current_item

    def eventFilter(self, source: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Filter events for the parent widget's viewport to handle mouse movements and leave events.

        Args:
            source (QtCore.QObject): The source object of the event.
            event (QtCore.QEvent): The event to be filtered.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
        if event.type() == QtCore.QEvent.Type.MouseMove and source is self.parent_widget.viewport():
            self.handle_mouse_move(event)
        elif event.type() == QtCore.QEvent.Type.Leave and source is self.parent_widget.viewport():
            self.handle_leave_event(event)
        return super().eventFilter(source, event)


if __name__ == "__main__":
    import sys

    def handle_button_click():
        item = overlay.current_item
        if item:
            print(f"Item clicked: {item.text(0)}")

    app = QtWidgets.QApplication(sys.argv)

    # Example using QTreeWidget
    tree_widget = QtWidgets.QTreeWidget()
    tree_widget.setColumnCount(2)
    tree_widget.setHeaderHidden(True)
    for i in range(5):
        item = QtWidgets.QTreeWidgetItem(tree_widget)
        item.setText(0, f"Tree Item {i + 1}")
        item.setText(1, f"Tree Item {i + 1}")

    # Example using QListWidget
    list_widget = QtWidgets.QListWidget()
    for i in range(5):
        item = QtWidgets.QListWidgetItem(f"List Item {i + 1}")
        list_widget.addItem(item)

    # Example using QTableWidget
    table_widget = QtWidgets.QTableWidget(5, 1)
    for i in range(5):
        item = QtWidgets.QTableWidgetItem(f"Table Item {i + 1}")
        table_widget.setItem(i, 0, item)
        table_widget.setItem(i, 1, item)

    # Create a hover button
    hover_button = QtWidgets.QPushButton("X")
    hover_button.setStyleSheet("background-color: none; border: none;")
    hover_button.setFixedSize(20, 20)

    # Apply the ItemOverlay to different widgets
    overlay = ItemOverlay(hover_button)
    overlay.register_to(tree_widget)
    # overlay.register_to(list_widget)
    # overlay.register_to(table_widget)
    hover_button.clicked.connect(handle_button_click)

    # Display the widgets (choose one to display)
    tree_widget.show()
    # list_widget.show()
    # table_widget.show()

    sys.exit(app.exec_())
