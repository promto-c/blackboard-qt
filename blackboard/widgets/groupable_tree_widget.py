# Type Checking Imports
# ---------------------
from typing import Any, Dict, List, Union, Tuple, Optional, Generator, Iterable

# Standard Library Imports
# ------------------------
import uuid
from numbers import Number
from collections import defaultdict
from functools import partial

# Third Party Imports
# -------------------
from qtpy import QtWidgets, QtCore, QtGui
from tablerqicon import TablerQIcon

# Local Imports
# -------------
import blackboard as bb
from blackboard import widgets
# NOTE: test
from blackboard.widgets.header_view import SearchableHeaderView
from blackboard.utils.tree_utils import TreeUtil, TreeItemUtil
from blackboard.utils.data_fetch_manager import FetchManager
from blackboard.widgets.menu import ContextMenu
from blackboard.widgets.momentum_scroll_widget import MomentumScrollTreeWidget


# Class Definitions
# -----------------
class TreeWidgetItem(QtWidgets.QTreeWidgetItem):
    """Extend QTreeWidgetItem to handle various data formats and store additional data in the user role.

    Attributes:
        id (Any): The ID of the item.
    """

    # Maximum number of bytes to display
    MAX_BYTES_DISPLAY = 16

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent: Union[QtWidgets.QTreeWidget, QtWidgets.QTreeWidgetItem], 
                 item_data: Union[Dict[str, Any], List[Any]] = None, item_id: Any = None):
        """Initialize with the given parent and item data.

        Args:
            parent (Union[QtWidgets.QTreeWidget, QtWidgets.QTreeWidgetItem]): Parent widget or item.
            item_data (Union[Dict[str, Any], List[str]], optional): Data for the item, as a list of values or a dictionary with keys matching the headers of the parent widget. Defaults to `None`.
            item_id (Any, optional): The ID of the item. Defaults to `None`.
        """
        # Store the item's ID
        self.id = item_id

        # Determine the format of the data (list or dict) and prepare it for the item
        if isinstance(item_data, list):
            item_values = item_data
        elif isinstance(item_data, dict):
            # Retrieve column names from the parent widget
            fields = TreeUtil.get_field_names(parent)
            # Match data to columns
            item_values = [item_data.get(field, '') for field in fields]

        # Call superclass constructor to initialize the item with formatted data
        super().__init__(parent, map(self._convert_to_str, item_values))

        # Set the UserRole data for the item.
        self._set_user_role_data(item_values)

    def _convert_to_str(self, value: Any) -> str:
        """Convert a given value to a string, decoding bytes if necessary, with size limitation.

        Args:
            value (Any): The value to convert to a string.

        Returns:
            str: The string representation of the value.
        """
        if isinstance(value, bytes):
            if len(value) > self.MAX_BYTES_DISPLAY:
                # Truncate the bytes and append an indicator
                truncated = value[:self.MAX_BYTES_DISPLAY]
                return truncated.hex() + '... (truncated)'
            return value.hex()
        elif isinstance(value, list):
            return ''

        return str(value)

    # Public Methods
    # --------------
    def get_value(self, column: Union[int, str], data_role: QtCore.Qt.ItemDataRole = QtCore.Qt.ItemDataRole.UserRole) -> Any:
        """Retrieves the value for the specified column and role.

        Args:
            column (Union[int, str]): Column index or name.
            data_role (QtCore.Qt.ItemDataRole, optional): Data role to retrieve. Defaults to UserRole.

        Returns:
            Any: The value associated with the column and role.
        """
        # Get the column index from the column name if necessary
        column_index = self.treeWidget().get_column_index(column) if isinstance(column, str) else column

        # Get the data for the specified role and column
        value = self.data(column_index, data_role) or self.data(column_index, QtCore.Qt.ItemDataRole.DisplayRole)

        return value

    def set_value(self, column: Union[int, str], value: Any, data_role: Optional[QtCore.Qt.ItemDataRole] = None):
        """Set the value for the specified column and role.

        Args:
            column (Union[int, str]): Column index or name.
            value (Any): Value to set.
            data_role (QtCore.Qt.ItemDataRole, optional): Role under which to set the value. Defaults to UserRole.
        """
        # Get the column index from the column name if necessary
        column_index = self.treeWidget().get_column_index(column) if isinstance(column, str) else column

        # Set the value for the specified role and column
        if data_role is None:
            # Set both UserRole and DisplayRole data
            self.setData(column_index, QtCore.Qt.ItemDataRole.UserRole, value)
            self.setData(column_index, QtCore.Qt.ItemDataRole.DisplayRole, self._convert_to_str(value))

            # Special handling for lists and booleans
            if isinstance(value, list):
                self._set_tag_list_view(column_index, value)
            elif isinstance(value, bool):
                check_state = QtCore.Qt.CheckState.Checked if value else QtCore.Qt.CheckState.Unchecked
                self.setData(column_index, QtCore.Qt.ItemDataRole.CheckStateRole, check_state)
        else:
            # Set data for the specified role
            self.setData(column_index, data_role, value)

    # Private Methods
    # ---------------
    def _set_user_role_data(self, item_values: List[Any]):
        """Set the UserRole data for the item.

        Args:
            item_values (List[Any]): The list of values to set as the item's data.
        """
        # Iterate through each column and set its value in the UserRole data
        for column_index, value in enumerate(item_values):
            self.set_value(column_index, value, QtCore.Qt.ItemDataRole.UserRole)

    def _set_tag_list_view(self, column_index: int, values: List[str]):
        """Set up a TagListView with the given list of tags and assign it to the specified column.

        Args:
            column_index (int): The column index where the TagListView will be set.
            values (List[str]): The list of tags to populate the TagListView.
        """
        # Create the TagListView widget
        tag_list_view = widgets.TagListView(self.treeWidget(), read_only=True)
        tag_list_view.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        tag_list_view.add_items(values)

        # NOTE: Workaround
        tag_list_view.sizeHint = partial(self.sizeHint, column_index)
        # Set the TagListView as the widget for the specified item and column
        self.treeWidget().setItemWidget(self, column_index, tag_list_view)

    def __getitem__(self, key: Union[int, str]) -> Any:
        """Retrieve the value of the UserRole data for the given column.

        Args:
            key (Union[int, str]): Column index or name.

        Returns:
            Any: The value stored under UserRole.
        """
        return self.get_value(key)

    def __lt__(self, other_item: 'TreeWidgetItem') -> bool:
        """Compare this item with another item to determine the sort order.

        Args:
            other_item (TreeWidgetItem): Item to compare against.

        Returns:
            bool: True if this item is less than the other item, False otherwise.
        """
        # Get the column that is currently being sorted
        column = self.treeWidget().sortColumn()

        # Get the UserRole data for the column for both this item and the other item
        self_data = self.get_value(column)
        other_data = other_item.get_value(column)

        # If this item's UserRole data is None, consider it less; if other data is None, consider it greater
        if self_data is None:
            return True
        if other_data is None:
            return False

        # Try to compare data directly. If the comparison fails, compare their string representations
        try:
            return self_data < other_data
        except TypeError:
            return str(self_data) < str(other_data)

    def __hash__(self):
        """Return the hash of the item based on its ID.
        """
        return hash(self.id)

class ColumnManagementWidget(QtWidgets.QTreeWidget):

    # Initialization and Setup
    # ------------------------
    def __init__(self, tree_widget: 'GroupableTreeWidget'):
        super().__init__(tree_widget)

        # Store the arguments
        self.tree_widget = tree_widget

        # Initialize setup
        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setHeaderHidden(True)
        self.setColumnCount(2)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setItemsExpandable(False)
        self.setRootIsDecorated(False)

        # Set the minimum width for the first column
        self.header().setMinimumSectionSize(20)
        self.setColumnWidth(0, 20)  # Adjust the size of the first column

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        self.tree_widget.header().sectionMoved.connect(self.update_columns)
        self.tree_widget.model().headerDataChanged.connect(self.update_columns)

        self.itemClicked.connect(self.toggle_check_state)
        self.itemChanged.connect(self.set_column_visibility)

    def toggle_check_state(self, tree_item: QtWidgets.QTreeWidgetItem, column: int):
        """Toggle the checkbox state when an item's text (second column) is clicked.
        """
        if column != 1:
            return

        current_state = tree_item.checkState(0)
        new_state = QtCore.Qt.CheckState.Checked if current_state == QtCore.Qt.CheckState.Unchecked else QtCore.Qt.CheckState.Unchecked
        tree_item.setCheckState(0, new_state)  # Toggle the check state

    def sync_column_order(self):
        """Synchronize the column order.
        """
        for i in range(self.topLevelItemCount()):
            column_name = self.topLevelItem(i).text(1)
            visual_index = self.tree_widget.get_column_visual_index(column_name)
            self.tree_widget.header().moveSection(visual_index, i)

    def set_column_visibility(self, item: QtWidgets.QTreeWidgetItem, column: int):
        """Set the visibility of a column based on the item's check state.
        """
        column_name = item.text(1)
        is_hidden = item.checkState(0) == QtCore.Qt.CheckState.Unchecked
        column_index = self.tree_widget.get_column_index(column_name)

        self.tree_widget.setColumnHidden(column_index, is_hidden)

    def update_columns(self):
        """Update the columns.
        """
        self.clear()

        if not self.tree_widget.fields:
            return

        logical_indexes = [self.tree_widget.get_column_logical_index(i) for i in range(self.tree_widget.columnCount())]
        header_names = [self.tree_widget.fields[i] for i in logical_indexes]

        self.addItems(header_names)

    def addItem(self, label: str, is_checked: bool = False):
        """Add an item to the tree.

        Args:
            label (str): The label for the tree item.
            is_checked (bool): Whether the item should be checked by default.
        """
        # Create a new tree widget item with an empty first column and the specified label
        tree_item = QtWidgets.QTreeWidgetItem(self, ['', label])
        # Convert boolean is_checked to Qt.CheckState, then set the tree item's check state
        check_state = QtCore.Qt.CheckState.Checked if is_checked else QtCore.Qt.CheckState.Unchecked
        tree_item.setCheckState(0, check_state)

    def addItems(self, labels: Iterable[str]):
        """Add multiple items to the tree.
        """
        for column_visual_index, label in enumerate(labels):
            column_logical_index = self.tree_widget.get_column_logical_index(column_visual_index)
            is_checked = not self.tree_widget.isColumnHidden(column_logical_index)
            self.addItem(label, is_checked)

    def dropEvent(self, event: QtGui.QDropEvent):
        """Handle the drop event.
        """
        # Attempt to find the item at the drop position.
        target_item = self.itemAt(event.pos())

        if self.dropIndicatorPosition() == QtWidgets.QAbstractItemView.DropIndicatorPosition.OnItem:

            new_row_index = self.indexFromItem(target_item).row()

            # Perform the move operation within the same level.
            for selected_item in self.selectedItems():
                # Take the item out of its current position.
                taken_item = self.takeTopLevelItem(self.indexOfTopLevelItem(selected_item))
                # Insert it at the determined position.
                self.insertTopLevelItem(new_row_index, taken_item)
            
            event.ignore()
        else:
            # If not reparenting, use the default behavior which is already correct for same-level moves.
            super().dropEvent(event)

        self.sync_column_order()

class TreeUtilityToolBar(QtWidgets.QToolBar):

    DEFAULT_HEIGHT = 24
    
    def __init__(self, tree_widget: 'GroupableTreeWidget'):
        # Initialize the super class
        super().__init__(parent=tree_widget)

        # Store the arguments
        self.tree_widget = tree_widget

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        # Attributes
        # ----------
        self.tabler_icon = TablerQIcon(opacity=0.8)

        # Private Attributes
        # ------------------
        ...

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setFixedHeight(self.DEFAULT_HEIGHT)
        self.setIconSize(QtCore.QSize(20, 20))

        # Create Layouts
        # --------------
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)

        # Add a stretchable spacer to the toolbar to align items to the left
        spacer = QtWidgets.QWidget(self)
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        # Add Widgets to Layouts
        # ----------------------
        self.fit_in_view_action = self.add_action(
            icon=self.tabler_icon.arrow_autofit_content,
            tooltip="Fit columns in view",
        )
        self.word_wrap_action = self.add_action(
            icon=self.tabler_icon.text_wrap,
            tooltip="Toggle word wrap",
            checkable=True,
        )
        # self.set_uniform_row_height_action = self.add_action(
        #     icon=self.tabler_icon.arrow_autofit_height,
        #     tooltip="Toggle uniform row height",
        #     checkable=True,
        # )

        self.uniform_row_height_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, self)
        self.uniform_row_height_slider.setRange(16, 200)
        self.uniform_row_height_slider.setFixedHeight(20)
        self.uniform_row_height_slider.setSingleStep(4)
        self.uniform_row_height_slider.setValue(GroupableTreeWidget.DEFAULT_ROW_HEIGHT)
        self.uniform_row_height_slider.setToolTip("Set uniform row height")  # Tooltip added
        self.addWidget(self.uniform_row_height_slider)

        self.reload_action = self.add_action(
            icon=self.tabler_icon.reload,
            tooltip="Reload",
        )

    def add_action(self, icon: QtGui.QIcon, tooltip: str, checkable: bool = False) -> QtGui.QAction:
        """Adds an action to the toolbar."""
        action = self.addAction(icon, '')
        action.setToolTip(tooltip)
        action.setCheckable(checkable)

        # Access the widget for the action and set the cursor
        self.widgetForAction(action).setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        
        return action

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect signals to slots
        self.fit_in_view_action.triggered.connect(self.tree_widget.fit_column_in_view)
        self.word_wrap_action.toggled.connect(self.tree_widget.setWordWrap)
        # self.set_uniform_row_height_action.triggered.connect(self.toggle_uniform_row_height)
        self.uniform_row_height_slider.valueChanged.connect(self.tree_widget.set_row_height)
        self.reload_action.triggered.connect(self.tree_widget.reload_requested.emit)


# TODO: Fix cell color blending when set color adaptive at first column
class GroupableTreeWidget(MomentumScrollTreeWidget):
    """A QTreeWidget subclass that displays data in a tree structure with the ability to group data by a specific column.

    Attributes:
        fields (List[str]): The list of column names to be displayed in the tree widget.
        groups (Dict[str, TreeWidgetItem]): A dictionary mapping group names to their tree widget items.
    """
    # Default value
    DEFAULT_ROW_HEIGHT = 24

    # Signals emitted by the GroupableTreeWidget
    ungrouped_all = QtCore.Signal()
    item_added = QtCore.Signal(TreeWidgetItem)
    drag_started = QtCore.Signal(QtCore.Qt.DropActions)
    about_to_show_header_menu = QtCore.Signal(str)
    fetch_complete = QtCore.Signal()
    reload_requested = QtCore.Signal()
    field_changed = QtCore.Signal()

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent: QtWidgets.QWidget = None, *args, **kwargs):
        # Call the parent class constructor
        super().__init__(
            parent, uniformRowHeights=True,
            dragDropMode=QtWidgets.QAbstractItemView.DragDropMode.DragOnly,
            contextMenuPolicy=QtCore.Qt.ContextMenuPolicy.CustomContextMenu,
            selectionMode=QtWidgets.QTreeWidget.SelectionMode.ExtendedSelection,
            selectionBehavior=QtWidgets.QTreeWidget.SelectionBehavior.SelectItems,
            sortingEnabled=True,
            wordWrap=True,
            *args, **kwargs,
        )

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        # Attributes
        # ----------
        # Field lists for grouping and adaptive styling.
        self._fields: List[str] = []
        self.color_adaptive_fields: List[str] = []
        self.grouped_fields: List[str] = []

        # Managers and delegates for data and UI handling.
        self.fetch_manager = FetchManager(self)
        self.highlight_item_delegate = widgets.HighlightItemDelegate()
        self.thumbnail_delegate = widgets.ThumbnailDelegate(self)

        # Private Attributes
        # ------------------
        self._primary_key = None
        self._row_height = self.DEFAULT_ROW_HEIGHT
        self._selected_field = 0
        self._id_to_tree_item: Dict[Any, QtWidgets.QTreeWidgetItem] = {}

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Reset sorting
        self.sortByColumn(-1, QtCore.Qt.SortOrder.AscendingOrder)

        # Set up the context menu
        self.header().setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        # Set the item delegate for highlight search item
        self.setItemDelegate(self.highlight_item_delegate)

        # NOTE: Test
        # self.searchable_header = SearchableHeaderView(self)

        self.set_row_height(self._row_height)
        self._create_header_menu()

        self.overlay_layout = QtWidgets.QHBoxLayout(self)
        self.overlay_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.overlay_layout.setContentsMargins(16, 16, 16, 16)

        # Add data fetching buttons from FetchManager to overlay_layout
        self.overlay_layout.addWidget(self.fetch_manager.data_fetching_buttons)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect signal of header
        self.header().customContextMenuRequested.connect(self._show_header_context_menu)

        self.itemExpanded.connect(self._toggle_expansion_for_selected)
        self.itemCollapsed.connect(self._toggle_expansion_for_selected)
        self.itemSelectionChanged.connect(self._highlight_selected_items)

        self.highlight_item_delegate.highlight_changed.connect(self.update)

        # Connect FetchManager signals
        self.fetch_manager.data_fetched.connect(self.update_item)
        self.fetch_manager.loaded_all.connect(self.fetch_complete.emit)

        self.verticalScrollBar().valueChanged.connect(self._track_scroll_position)

        # Key Binds
        # ---------
        # Create a shortcut for the copy action and connect its activated signal
        bb.utils.KeyBinder.bind_key(QtGui.QKeySequence.StandardKey.Copy, self, self.copy_selected_cells)

    # Public Methods
    # --------------
    def create_thumbnail_column(self, source_column_name: str = 'file_path', sequence_range_column_name: str = 'sequence_range'):
        """Create a thumbnail column with specific source and sequence range columns.

        Args:
            source_column_name (str): The name of the source column. Defaults to 'file_path'.
            sequence_range_column_name (str): The name of the sequence range column. Defaults to 'sequence_range'.
        """
        if 'thumbnail' not in self._fields:
            self._fields.append('thumbnail')
        self.setHeaderLabels(self._fields)

        source_column = self._fields.index(source_column_name)
        thumbnail_column = self._fields.index('thumbnail')
        sequence_range_column = self._fields.index(sequence_range_column_name) if sequence_range_column_name in self._fields else None

        self.thumbnail_delegate.set_thumbnail_column(thumbnail_column)
        self.thumbnail_delegate.set_source_column(source_column)
        self.thumbnail_delegate.set_sequence_range_column(sequence_range_column)

        self.setItemDelegateForColumn(thumbnail_column, self.thumbnail_delegate)

    def highlight_items(self, tree_items: Iterable['TreeWidgetItem'], focused_column_index: int = None):
        """Highlight the specified `tree_items` in the tree widget.

        Args:
            tree_items (Iterable[TreeWidgetItem]): The tree items to highlight.
            focused_column_index (Optional[int]): The focused column index. Defaults to None.
        """
        self.highlight_item_delegate.add_highlight_items(tree_items, focused_column_index)

    def clear_highlight(self):
        """Clear highlights from all items.
        """
        self.highlight_item_delegate.clear_highlight_items()

    def set_row_height(self, height: Optional[int] = None):
        """Set the row height for all items in the tree widget.

        Args:
            height (Optional[int]): The desired row height. If None, use the current row height.
        """
        # Set the row height for all items
        self._row_height = height or self._row_height

        # Adjust item height using stylesheet
        self.setStyleSheet(f"""
            QTreeView::item {{
                height: {height}px;
            }}
        """)

    # TODO: Move out
    def get_column_value_range(self, column: int, child_level: int = 0) -> Tuple[Optional['Number'], Optional['Number']]:
        """Get the value range of a specific column at a given child level.

        Args:
            column (int): The index of the column.
            child_level (int): The child level to calculate the range for. Defaults to 0 (top-level items).

        Returns:
            Tuple[Optional[Number], Optional[Number]]: A tuple containing the minimum and maximum values,
            or (None, None) if no valid values are found.
        """
        # Get the items at the specified child level
        items = TreeUtil.get_items(self, target_depth=child_level)

        # Collect the values from the specified column in the items
        try:
            values = [
                item.get_value(column)
                for item in items
                if isinstance(item.get_value(column), Number)
            ]
        except AttributeError:
            values = [
                item.data(column, QtCore.Qt.ItemDataRole.UserRole) or item.data(column, QtCore.Qt.ItemDataRole.DisplayRole)
                for item in items
                if isinstance(item.data(column, QtCore.Qt.ItemDataRole.UserRole) or item.data(column, QtCore.Qt.ItemDataRole.DisplayRole), Number)
            ]

        # If there are no valid values, return None
        if not values:
            return None, None

        # Calculate the minimum and maximum values
        min_value = min(*values)
        max_value = max(*values)

        # Return the value range
        return min_value, max_value

    # TODO: Handle by field type
    def apply_color_adaptive(self, field: str):
        """Apply adaptive color mapping to a specific column at the appropriate child level determined by the group column.

        This method calculates the minimum and maximum values of the column at the appropriate child level determined by the group column
        and applies an adaptive color mapping based on the data distribution within the column.
        The color mapping dynamically adjusts to the range of values.

        Args:
            column (int): The index of the column to apply the adaptive color mapping.
        """
        if field in self.color_adaptive_fields:
            return

        self.color_adaptive_fields.append(field)

        # Determine the child level based on the presence of a grouped column
        child_level = len(self.grouped_fields)

        # Calculate the minimum and maximum values of the column at the determined child level
        column = self.get_column_index(field)
        min_value, max_value = self.get_column_value_range(column, child_level)

        # Create and set the adaptive color mapping delegate for the column
        delegate = widgets.AdaptiveColorMappingDelegate(self, min_value, max_value)
        self.setItemDelegateForColumn(column, delegate)

    def remove_color_adaptive(self, field: str):
        """Remove adaptive color mapping from a specific column.

        This method removes the adaptive color mapping from the specified column by resetting
        the item delegate to None and removing the column from the list of adaptive color-mapped columns.

        Args:
            field (str): The field to remove adaptive color mapping from.
        """
        if field not in self.color_adaptive_fields:
            return

        # Reset the item delegate for the column, removing the adaptive color mapping
        self.color_adaptive_fields.remove(field)
        self.setItemDelegateForColumn(self.get_column_index(field), None)

    def clear_color_adaptive(self):
        """Clear the color adaptive for all columns in the tree widget.
        """
        for field in self.color_adaptive_fields:
            self.setItemDelegateForColumn(self.get_column_index(field), None)

        self.color_adaptive_fields.clear()

    def get_column_index(self, column_name: str) -> Optional[int]:
        """Retrieve the index of the specified column name.

        Args:
            column_name (str): The name of the column.

        Returns:
            Optional[int]: The index of the column if found, otherwise None.
        """
        return self._fields.index(column_name) if column_name in self._fields else None

    def get_column_visual_index(self, column: Union[str, int]) -> int:
        """Retrieve the visual index of the specified column.

        Args:
            column (Union[str, int]): The column name or index.

        Returns:
            int: The visual index of the column.
        """
        if isinstance(column, str):
            column = self.get_column_index(column)

        return self.header().visualIndex(column)

    def get_column_logical_index(self, visual_index: int) -> int:
        """Retrieve the logical index of the specified visual index.

        Args:
            visual_index (int): The visual index.

        Returns:
            int: The logical index of the visual index.
        """
        return self.header().logicalIndex(visual_index)

    # TODO: Handle id or primary key
    def add_items(self, data_dicts: List[Dict[str, Any]], parent: Optional[QtWidgets.QTreeWidgetItem] = None):
        """Add multiple items to the tree widget.

        Args:
            data_dicts (List[Dict[str, Any]]): A list of data dictionaries to add.
            parent (Optional[QtWidgets.QTreeWidgetItem]): The parent item. If None, items are added at the root level.
        """
        for data_dict in data_dicts:
            self.add_item(data_dict, parent=parent)

    def add_item(self, data_dict: Dict[str, Any], item_id: Optional[Union[str, Tuple[str, ...]]] = None, parent: Optional[QtWidgets.QTreeWidgetItem] = None) -> TreeWidgetItem:
        """Add an item to the tree widget, considering groupings if applicable.

        Args:
            data_dict (Dict[str, Any]): The data for the new item.
            item_id (Optional[Union[str, Tuple[str, ...]]]): The ID of the item. If None, the primary key from data_dict is used.
            parent (Optional[QtWidgets.QTreeWidgetItem]): The parent item. Defaults to None.

        Returns:
            TreeWidgetItem: The newly added tree item.
        """
        parent = parent or self.invisibleRootItem()

        # Generate a unique ID if not provided
        if not item_id:
            if isinstance(self._primary_key, list):
                # Handle composite key
                item_id = tuple(data_dict.get(key) for key in self._primary_key)
            else:
                # Handle single key
                item_id = data_dict.get(self._primary_key) or uuid.uuid1()

        # Determine the parent for the new item
        if parent is self.invisibleRootItem() and self.grouped_fields:
            for grouped_field_name in self.grouped_fields:
                # If the tree is grouped, find the appropriate parent group item
                group_value = data_dict.get(grouped_field_name, "_others")

                if group_value not in parent.child_grouped_dict:
                    new_grouped_item = TreeWidgetItem(parent, [group_value])
                    new_grouped_item.setExpanded(True)
                    new_grouped_item.child_grouped_dict = {}
                    parent.child_grouped_dict[group_value] = new_grouped_item
                    parent = new_grouped_item
                else:
                    parent = parent.child_grouped_dict[group_value]

        # Create a new TreeWidgetItem and add it to the parent
        tree_item = TreeWidgetItem(parent, item_data=data_dict, item_id=item_id)

        # Update dictionary
        self._id_to_tree_item[item_id] = tree_item

        # Emit a signal that an item has been added
        self.item_added.emit(tree_item)

        return tree_item

    def get_item_by_id(self, item_id: Any) -> Optional[TreeWidgetItem]:
        return self._id_to_tree_item.get(item_id)

    def set_primary_key(self, primary_key: Union[str, List[str]]):
        """Set the primary key for the tree widget.

        Args:
            primary_key (Union[str, List[str]]): The primary key, either as a single string or a list of strings for composite keys.
        """
        self._primary_key = primary_key

    def update_item(self, data_dict: Dict[str, Any], update_key: Optional[Union[str, List[str]]] = None, add_if_not_exist: bool = True) -> Optional[TreeWidgetItem]:
        """Update an item in the tree widget based on a specified update key or add it as a new item if it doesn't exist.

        Args:
            data_dict (Dict[str, Any]): The data to update the item with.
            update_key (Optional[Union[str, Tuple[str]]]): The key(s) to use for identifying the item to update. If None, the primary key is used.
            add_if_not_exist (bool): If True, add a new item if the specified item doesn't exist. Defaults to True.

        Returns:
            Optional[TreeWidgetItem]: The updated or newly added tree item, or None if not found and add_if_not_exist is False.
        """
        # Use the provided update_key or fall back to the primary key
        update_key = update_key or self._primary_key

        if not update_key:
            item_id = uuid.uuid1()
        # Handle single key or composite key
        elif isinstance(update_key, list):
            # Create a tuple of item_id values from the composite key
            item_id = tuple(data_dict[key] for key in update_key)
        else:
            # Single key case
            item_id = data_dict[update_key]

        # Find the item by ID
        tree_item = self.get_item_by_id(item_id)

        # If item doesn't exist and add_if_not_exist is True, add a new item
        if not tree_item:
            if add_if_not_exist:
                tree_item = self.add_item(data_dict, item_id=item_id)
            else:
                return None

        # Update the item data
        for key, value in data_dict.items():
            if key not in self._fields:
                continue
            tree_item.set_value(key, value)

        # Refresh the display
        self.update()

        return tree_item

    def group_by(self, column: Union[int, str]):
        """Group the items in the tree widget by the values in the specified column.

        Args:
            column (Union[int, str]): The index or name of the column to group by.
        """
        if not isinstance(column, int):
            column = self.get_column_index(column)

        # Hide the grouped column
        self.setColumnHidden(column, True)

        # Group the data and add the tree items to the appropriate group
        if not self.grouped_fields:
            parent_item = self.invisibleRootItem()
            parent_item.child_grouped_dict = {}
            self.group_items(parent_item, column)
        else:
            lowest_grouped_items = TreeUtil.get_items(self, target_depth=len(self.grouped_fields) - 1)
            for lowest_grouped_item in lowest_grouped_items:
                self.group_items(lowest_grouped_item, column)

        # Get the label for the column that we want to group by and the label for the first column 
        grouped_field_name = self.headerItem().text(column)
        self.grouped_fields.append(grouped_field_name)

        # Store original and rename the first column
        first_column_name = self._fields[0]
        self.headerItem().setData(0, QtCore.Qt.ItemDataRole.UserRole, first_column_name)
        grouped_column_names_str = ' / '.join(self.grouped_fields + [first_column_name])
        self.setHeaderLabel(grouped_column_names_str)

        # Expand all items
        self.expandAll()

        # Resize first columns to fit their contents
        self.resizeColumnToContents(0)

    # TODO: Move to util
    def group_items(self, parent_item: QtWidgets.QTreeWidgetItem, column: int):
        """Group items under the parent item based on the values in the specified column.

        Args:
            parent_item (QtWidgets.QTreeWidgetItem): The parent item for grouping.
            column (int): The column index to group by.
        """
        # Take all children from the parent item
        target_items = parent_item.takeChildren()
        # Create groups based on the target items
        grouped_name_to_tree_items = TreeItemUtil.group_items_by_field(target_items, column)

        # Iterate through each group and its items
        for grouped_name, items in grouped_name_to_tree_items.items():
            # Create a new QTreeWidgetItem for the group
            grouped_item = TreeWidgetItem(parent_item, [grouped_name])
            grouped_item.child_grouped_dict = {}
            parent_item.child_grouped_dict[grouped_name] = grouped_item
            grouped_item.addChildren(items)

    def fit_column_in_view(self):
        """Adjust the width of all columns to fit the entire view.
        """
        TreeUtil.fit_column_in_view(self)

    def ungroup_all(self):
        """Ungroup all the items in the tree widget.
        """
        # Return if there are no groups to ungroup
        if not self.grouped_fields:
            return

        # Reset the header label
        self.setHeaderLabel(self._fields[0])
        
        # Show hidden column
        for grouped_field_name in self.grouped_fields:
            column_index = self.get_column_index(grouped_field_name)
            self.setColumnHidden(column_index, False)

        # Get target items at a specific child level
        target_items = TreeUtil.get_items(self, target_depth=len(self.grouped_fields))

        # Reparent to root and remove the empty grouped items
        TreeItemUtil.remove_items(target_items)
        self.clear()
        self.addTopLevelItems(target_items)

        # Clear the grouped columns
        self.grouped_fields.clear()

        # Resize first columns to fit their contents
        self.resizeColumnToContents(0)

        # Emit signal for ungrouped all
        self.ungrouped_all.emit()

    def copy_selected_cells(self):
        """Copy selected cells to the clipboard.
        """
        # Get selected indexes from the view
        selected_indexes = self.selectedIndexes()
        all_items = TreeUtil.get_items(self)

        # Sort the cells based on their global row and column
        sorted_indexes = sorted(
            selected_indexes, 
            key=lambda index: (
                all_items.index(self.itemFromIndex(index)),
                index.column()
            )
        )

        # Initialize a dictionary to store cell texts and a set to store columns
        cell_dict: Dict[int, Dict[int, str]] = defaultdict(lambda: defaultdict(str))
        columns = set()

        # Fill the cell_dict with cell texts
        for index in sorted_indexes:
            tree_item = self.itemFromIndex(index)
            global_row = all_items.index(tree_item)
            column = index.column()

            cell_value = tree_item.text(column)
            cell_text = '' if cell_value is None else str(cell_value)
            cell_text = f'"{cell_text}"' if ('\t' in cell_text or '\n' in cell_text) else cell_text

            cell_dict[global_row][column] = cell_text
            columns.add(column)

        # Create row texts ensuring all columns are included
        row_texts = ['\t'.join(row[column] for column in sorted(columns)) for row in cell_dict.values()]
        full_text = '\n'.join(row_texts)

        # Copy to clipboard
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(full_text)

        # Show tooltip message
        self.show_tool_tip(f'Copied:\n{full_text}', 5000)

    def show_tool_tip(self, text: str, msc_show_time: int = 1000):
        """Show a tooltip message.

        Args:
            text (str): The text to display in the tooltip.
            msc_show_time (int): The time to display the tooltip in milliseconds. Defaults to 1000.
        """
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), text, self, QtCore.QRect(), msc_show_time)

    def paste_cells_from_clipboard(self):
        """Paste cells from the clipboard. Further implementation is required.
        """
        # NOTE: Further Implementation Required
        # TODO: Implement popup window to confirm pasting data into each column.
        model = self.selectionModel()
        model_indexes = model.selectedIndexes()

        # Get the text from the clipboard
        clipboard = QtWidgets.QApplication.clipboard()
        text = clipboard.text()
        
        # Split the text into rows and columns
        rows = text.split('\n')
        rows = [row.split('\t') for row in rows]

        # Get the current selected item

        # Get the current row and column

        # Paste the values into the tree widget

        print('Not implemented')

    def set_fields(self, fields: Iterable[str]):
        self.setHeaderLabels(fields)

    def save_state(self, settings: QtCore.QSettings, group_name: str = 'tree_widget'):
        """Save the state of the tree widget.

        Args:
            settings (QtCore.QSettings): The settings object to save the state.
            group_name (str): The group name for the settings. Defaults to 'tree_widget'.
        """
        settings.beginGroup(group_name)
        settings.setValue('header_state', self.header().saveState())
        settings.setValue('color_adaptive_fields', self.color_adaptive_fields)
        settings.setValue('grouped_fields', self.grouped_fields)
        settings.setValue('uniform_row_height', self._row_height)
        settings.endGroup()

    def load_state(self, settings: QtCore.QSettings, group_name: str = 'tree_widget'):
        """Load the state of the tree widget.

        Args:
            settings (QtCore.QSettings): The settings object to load the state.
            group_name (str): The group name for the settings. Defaults to 'tree_widget'.
        """
        settings.beginGroup(group_name)
        header_state = settings.value('header_state', QtCore.QByteArray)
        color_adaptive_fields = settings.value('color_adaptive_fields', type=list)
        grouped_fields = settings.value('grouped_fields', type=list)
        uniform_row_height = int(settings.value('uniform_row_height', self.DEFAULT_ROW_HEIGHT))
        settings.endGroup()

        if not header_state:
            return

        self.header().restoreState(header_state)
        self._restore_color_adaptive_fields(color_adaptive_fields)
        for grouped_field in grouped_fields:
            self.group_by(grouped_field)
        self.set_row_height(uniform_row_height)
        self.column_management_widget.update_columns()

    def set_generator(self, generator: Optional[Generator], is_fetch_all: bool = False):
        """Set a new generator, clearing the existing task before setting the new generator.

        Args:
            generator (Optional[Generator]): The generator to set.
        """
        self.clear()
        self.fetch_manager.set_generator(generator)

        if is_fetch_all:
            self.fetch_manager.fetch_all()
        else:
            first_batch_size = self._calculate_dynamic_batch_size()
            self.fetch_manager.fetch(first_batch_size)

    # Class Properties
    # ----------------
    @property
    def fields(self) -> List[str]:
        return self._fields

    # Private Methods
    # ---------------
    def _create_header_menu(self):
        """Create a context menu for the header of the tree widget.

        Context Menu:
            +-------------------------------+
            | Grouping                      | - [0]
            | - Group by this column        |
            | - Ungroup all                 |
            | ----------------------------- |
            | Visualization                 | - [1]
            | - Set Color Adaptive          |
            | - Reset All Color Adaptive    |
            | ----------------------------- |
            | - Fit in View                 |
            | ----------------------------- |
            | Manage Columns                | - [2]
            | - Show/Hide Columns >         |
            | - Hide This Column            |
            +-------------------------------+
        """
        # Create the context menu
        self.header_menu = ContextMenu()

        # [0] - Add 'Grouping' section with actions: 'Group by this column' and 'Ungroup all'
        grouping_section_action = self.header_menu.addSection('Grouping')
        self.group_by_action = grouping_section_action.addAction(text='Group by this column')
        ungroup_all_action = grouping_section_action.addAction(text='Ungroup all')
        # [1] - Add 'Visualization' section with actions: 'Set Color Adaptive', 'Reset All Color Adaptive', and 'Fit in View'
        visualization_section_action = self.header_menu.addSection('Visualization')
        apply_color_adaptive_action = visualization_section_action.addAction(text='Set Color Adaptive')
        reset_all_color_adaptive_action = visualization_section_action.addAction(text='Reset All Color Adaptive')
        visualization_section_action.addSeparator()
        fit_column_in_view_action = visualization_section_action.addAction(text='Fit in View')
        # [2] - Add 'Manage Columns' section with actions for column management
        manage_columns_section_action = self.header_menu.addSection('Manage Columns')
        show_hide_column_menu = manage_columns_section_action.addMenu('Show/Hide Columns')
        self.column_management_widget = ColumnManagementWidget(self)
        column_management_widget_action = QtWidgets.QWidgetAction(self)
        column_management_widget_action.setDefaultWidget(self.column_management_widget)
        show_hide_column_menu.addAction(column_management_widget_action)
        hide_this_column = manage_columns_section_action.addAction(text='Hide This Column')

        # Connect actions to their corresponding methods
        self.group_by_action.triggered.connect(lambda: self.group_by(self._selected_field))
        ungroup_all_action.triggered.connect(self.ungroup_all)
        apply_color_adaptive_action.triggered.connect(lambda: self.apply_color_adaptive(self._selected_field))
        reset_all_color_adaptive_action.triggered.connect(self.clear_color_adaptive)
        fit_column_in_view_action.triggered.connect(self.fit_column_in_view)
        hide_this_column.triggered.connect(lambda: self.hideColumn(self._selected_field))

    def _show_header_context_menu(self, pos: QtCore.QPoint):
        """Show a context menu for the header of the tree widget.

        Args:
            pos (QtCore.QPoint): The position where the right-click occurred.
        """
        # Get the index of the column where the right click occurred
        self._selected_field = self._fields[self.header().logicalIndexAt(pos)]

        # Emit the custom signal with the column index
        self.about_to_show_header_menu.emit(self._selected_field)

        # Disable 'Group by this column' on grouped column
        if self._selected_field in self.grouped_fields:
            self.group_by_action.setEnabled(False)

        # Show the context menu
        self.header_menu.popup(QtGui.QCursor.pos())

    def _highlight_selected_items(self):
        """Highlight the specified `tree_items` in the tree widget.
        """
        self.highlight_item_delegate.set_selected_items(self.selectedItems())

    def _toggle_expansion_for_selected(self, reference_item: QtWidgets.QTreeWidgetItem):
        """Toggle the expansion state of selected items.

        Args:
            reference_item (QtWidgets.QTreeWidgetItem): The clicked item whose expansion state will be used as a reference.
        """
        # Get the currently selected items
        selected_items = self.selectedItems()

        # If no items are selected, return early
        if not selected_items:
            return

        # Set the expanded state of all selected items to match the expanded state of the clicked item
        for i in selected_items:
            i.setExpanded(reference_item.isExpanded())

    def _calculate_dynamic_batch_size(self) -> int:
        """Estimate the number of items that can fit in the current view.

        Returns:
            int: Estimated number of items that can fit in the view.
        """
        # Estimate the number of items based on the visible height and row height
        visible_height = self.viewport().height()
        estimated_items = (visible_height // self._row_height) + 1 if self._row_height > 0 else self.fetch_manager.DEFAULT_BATCH_SIZE

        # Ensure the batch size is at least the default batch size
        return max(estimated_items, self.fetch_manager.DEFAULT_BATCH_SIZE)

    def _track_scroll_position(self, value: int):
        """Track the scroll position and fetch more data if the threshold is reached.

        Args:
            value (int): The current scroll value.
        """
        if not self.fetch_manager.has_more_items_to_fetch:
            return
        if value >= self.verticalScrollBar().maximum() - self.fetch_manager.THRESHOLD_TO_FETCH_MORE:
            self.fetch_manager.fetch_more()

    def _restore_color_adaptive_fields(self, fields: List[str]):
        """Restore the color adaptive columns.

        Args:
            fields (List[int]): The fields to restore.
        """
        self.clear_color_adaptive()

        for field in fields:
            self.apply_color_adaptive(field)

    # Override Methods
    # ----------------
    def setHeaderLabels(self, labels: Iterable[str]):
        """Set the names of the columns in the tree widget.

        Args:
            labels (Iterable[str]): The iterable of column names to be set.
        """
        # Store the column names for later use
        self._fields = list(labels)

        # Set the number of columns and the column labels
        self.setColumnCount(len(self._fields))
        super().setHeaderLabels(self._fields)
        self.field_changed.emit()

    def hideColumn(self, column: Union[int, str]):
        """Hide the specified column.

        Args:
            column (Union[int, str]): The column index or name.
        """
        column_index = self.get_column_index(column) if isinstance(column, str) else column
        super().hideColumn(column_index)

    def startDrag(self, supported_actions: QtCore.Qt.DropActions):
        """Handle drag event of the tree widget.

        Args:
            supported_actions (QtCore.Qt.DropActions): The supported actions for the drag event.
        """
        self.drag_started.emit(supported_actions)

    def clear(self):
        """Clear the tree widget and stop any current tasks.
        """
        self.fetch_manager.stop_fetch()
        self._id_to_tree_item.clear()
        super().clear()

    def scrollContentsBy(self, dx: int, dy: int):
        """Update positions of visible item widgets during scrolling.
        """
        super().scrollContentsBy(dx, dy)

        if widgets.ScalableView.is_scalable(self):
            self.model().layoutChanged.emit()

    def setItemWidget(self, item: QtWidgets.QTreeWidgetItem, column: int, widget: QtWidgets.QWidget):
        """Add a widget to an item and tracking the new one for position updates.
        """
        # NOTE: Workaround to manually forward mouse events from the TagListView to the QTreeWidget's viewport
        if isinstance(widget, widgets.TagListView):
            widget.viewport().installEventFilter(self)

        super().setItemWidget(item, column, widget)

    # NOTE: This implementation includes a workaround to manually forward mouse events from the TagListView
    #       to the QTreeWidget's viewport. This is necessary because the QTreeWidgetItem does not inherently
    #       receive mouse events from embedded widgets like TagListView. Without this workaround, interactions
    #       such as selection or item editing would not function correctly when the TagListView is clicked.
    def eventFilter(self, source: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Filter events from the source widget, specifically handling mouse events from a TagListView.

        Args:
            source (QtCore.QObject): The source of the event, typically a widget like TagListView.
            event (QtCore.QEvent): The event to be filtered, such as a mouse event.

        Returns:
            bool: True if the event is handled and forwarded; otherwise, False.
        """
        if isinstance(source.parentWidget(), widgets.TagListView) and isinstance(event, QtGui.QMouseEvent):
            # Forward mouse events to the viewport of the QTreeWidget
            mapped_event = QtGui.QMouseEvent(
                event.type(),
                self.viewport().mapFromGlobal(event.globalPos()),
                event.button(),
                event.buttons(),
                event.modifiers(),
            )
            # Forward the event to the tree widget
            return QtWidgets.QApplication.sendEvent(self.viewport(), mapped_event)
        return super().eventFilter(source, event)


# Main Function
# -------------
def main():
    """Create the application and main window, and show the widget.
    """
    import sys
    from blackboard.examples.example_data_dict import COLUMN_NAME_LIST, ID_TO_DATA_DICT
    from blackboard.examples.example_generator import generate_file_paths

    # Create the application and the main window
    app = QtWidgets.QApplication(sys.argv)
    # NOTE: Test window icon
    app.setWindowIcon(QtGui.QIcon('image_not_available_placeholder.png'))

    # Set theme of QApplication to the dark theme
    bb.theme.set_theme(app, 'dark')

    # Create an instance of the widget
    generator = generate_file_paths('blackboard', delay_duration_sec=0.05)
    tree_widget = GroupableTreeWidget()
    tree_widget.set_fields(['id', 'file_path'])
    tree_widget.create_thumbnail_column('file_path')
    tree_widget.set_generator(generator)

    # tree_widget = GroupableTreeWidget()
    # tree_widget.setHeaderLabels(COLUMN_NAME_LIST)
    # tree_widget.add_items(ID_TO_DATA_DICT)

    # Show the window and run the application
    tree_widget.show()

    # Run the application
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
