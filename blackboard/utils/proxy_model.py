# Type Checking Imports
# ---------------------
from typing import Any, List, Union

# Third Party Imports
# -------------------
from qtpy import QtCore, QtGui, QtWidgets


# Class Definitions
# -----------------
class FlatProxyModel(QtCore.QSortFilterProxyModel):

    # Initialization and Setup
    # ------------------------
    def __init__(self, source_model: QtCore.QAbstractItemModel = None, parent: QtWidgets.QWidget = None, show_only_checked: bool = False, show_only_leaves: bool = False):
        super().__init__(parent)
        self.show_only_checked = show_only_checked
        self.show_only_leaves = show_only_leaves
        self._flat_map = list()
        self._is_show_checkbox = True

        self.parent_widget = parent

        # Install event filter on the parent widget if it exists
        if isinstance(parent, QtWidgets.QWidget):
            parent.installEventFilter(self)

        if source_model is not None:
            self.setSourceModel(source_model)

    # Public Methods
    # --------------
    def set_show_checkbox(self, state: bool = True):
        self._is_show_checkbox = state
        self.invalidateFilter()

    def set_filter_checked_items(self, state: bool = True):
        self.show_only_checked = state
        # Rebuild flat map with new filter setting
        self._flat_map.clear()
        self._populate_flat_map()

    def set_filter_only_leaves(self, state: bool = True):
        self.show_only_leaves = state
        # Rebuild flat map with new filter setting
        self._flat_map.clear()
        self._populate_flat_map()

    # Private Methods
    # ---------------
    def _on_rows_inserted(self, parent, first, last):
        """Handle insertion of rows into the source model."""
        model = self.sourceModel()
        new_indices = []
        for row in range(first, last + 1):
            index = model.index(row, 0, parent)
            if self._is_accept(index):
                new_indices.append(index)

        # Find the insertion point in the flat map
        if not new_indices:
            return
        
        insert_position = len(self._flat_map)
        if self._flat_map:
            for i, idx in enumerate(self._flat_map):
                if idx.row() > first and idx.parent() == parent:
                    insert_position = i
                    break

        # Insert the new indices at the found position
        self._flat_map[insert_position:insert_position] = new_indices

        if self.parent_widget and not self.parent_widget.isHidden():
            self._sort()

        self.layoutChanged.emit()

    def _on_rows_removed(self, parent, first, last):
        """Handle removal of rows from the source model."""
        # Remove indices in the specified range with the correct parent
        new_flat_map = list()
        removed_count = 0
        for idx in self._flat_map:
            if idx.parent() == parent:
                if first <= idx.row() <= last:
                    removed_count += 1
                elif idx.row() > last:
                    # Adjust the row of the remaining indices
                    new_index = self.sourceModel().index(idx.row() - removed_count, idx.column(), parent)
                    new_flat_map.append(new_index)
                else:
                    new_flat_map.append(idx)
            else:
                new_flat_map.append(idx)

        self._flat_map = new_flat_map

        if self.parent_widget and not self.parent_widget.isHidden():
            self._sort()

        self.layoutChanged.emit()

    def _update_flat_map(self, top_left: QtCore.QModelIndex, bottom_right: QtCore.QModelIndex, roles: List[QtCore.Qt.ItemDataRole]):
        """Update only the changed items in the flat map, considering different parents."""
        if QtCore.Qt.ItemDataRole.CheckStateRole not in roles:
            return

        model = self.sourceModel()
        parent_index = top_left.parent()
        top_row = top_left.row()
        bottom_row = bottom_right.row()

        # We need to filter out and reinsert only those indices in the affected range and with the correct parent
        new_indices = []
        for row in range(top_row, bottom_row + 1):
            index = model.index(row, 0, parent_index)
            if not self._is_accept(index):
                continue
            new_indices.append(index)

        # Filter out the old indices in the range with the same parent
        self._flat_map = [idx for idx in self._flat_map if not (idx.row() >= top_row and idx.row() <= bottom_row and idx.parent() == parent_index)]

        # Find the correct insertion point
        insert_position = next((i for i, idx in enumerate(self._flat_map) if idx.row() >= top_row and idx.parent() == parent_index), len(self._flat_map))

        # Insert the new indices at the correct position
        self._flat_map[insert_position:insert_position] = new_indices

        # Notify views that the layout has changed
        self.layoutChanged.emit()

    def _populate_flat_map(self, parent_index: QtCore.QModelIndex = QtCore.QModelIndex()):
        """Recursively populate the flat map with item data and indices."""
        model = self.sourceModel()
        for row in range(model.rowCount(parent_index)):
            index = model.index(row, 0, parent_index)

            if model.hasChildren(index):
                self._populate_flat_map(index)

            if not self._is_accept(index):
                continue

            self._flat_map.append(index)

        self._sort()

    def _is_accept(self, index: QtCore.QModelIndex):
        if self.show_only_checked and self.sourceModel().data(index, QtCore.Qt.CheckStateRole) != QtCore.Qt.Checked:
            return False

        if self.show_only_leaves and self.sourceModel().hasChildren(index):
            return False

        return True

    # Override Methods
    # ----------------
    def setSourceModel(self, source_model: QtCore.QAbstractItemModel):
        """Set the source model and create the flat map."""
        self.beginResetModel()
        self._flat_map.clear()
        old_model = self.sourceModel()

        try:
            if old_model is not None:
                old_model.dataChanged.disconnect(self._update_flat_map)
                old_model.rowsInserted.disconnect(self._on_rows_inserted)
                old_model.rowsRemoved.disconnect(self._on_rows_removed)
                old_model.modelAboutToBeReset.disconnect(self._on_source_model_about_to_be_reset)
                old_model.modelReset.disconnect(self._on_source_model_reset)
        except (RuntimeError, TypeError):
            pass

        super().setSourceModel(source_model)
        source_model.dataChanged.connect(self._update_flat_map)
        source_model.rowsInserted.connect(self._on_rows_inserted)
        source_model.rowsRemoved.connect(self._on_rows_removed)
        source_model.modelAboutToBeReset.connect(self._on_source_model_about_to_be_reset)
        source_model.modelReset.connect(self._on_source_model_reset)
        self._populate_flat_map()
        self.endResetModel()

    def _on_source_model_about_to_be_reset(self):
        """Handle the source model being reset."""
        self.beginResetModel()
        self._flat_map.clear()

    def _on_source_model_reset(self):
        """Handle the source model being reset."""
        self.endResetModel()

    def mapFromSource(self, source_index):
        """Map from source model index to proxy model index."""
        try:
            return self.index(self._flat_map.index(source_index), 0)
        except ValueError:
            return QtCore.QModelIndex()

    def mapToSource(self, proxy_index):
        """Map from proxy model index to source model index."""
        if 0 <= proxy_index.row() < len(self._flat_map):
            return self._flat_map[proxy_index.row()]
        return QtCore.QModelIndex()

    def rowCount(self, parent=QtCore.QModelIndex()):
        """Return the number of items in the flat model."""
        if parent.isValid():
            return 0
        return len(self._flat_map)

    def index(self, row, column, parent=QtCore.QModelIndex()):
        """Create an index in the proxy model."""
        if parent.isValid() or column != 0 or not (0 <= row < len(self._flat_map)):
            return QtCore.QModelIndex()
        return self.createIndex(row, column)

    def parent(self, index):
        """Ensure that this model behaves as a flat list (no parent)."""
        return QtCore.QModelIndex()

    def itemFromIndex(self, proxy_index):
        try:
            if proxy_index.isValid():
                source_index = self.mapToSource(proxy_index)
                return self.sourceModel().itemFromIndex(source_index)
        except AttributeError:
            pass

        return None

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not self._is_show_checkbox and role == QtCore.Qt.CheckStateRole:
            return None
        return super().data(index, role)

    def sort(self, column, order=QtCore.Qt.AscendingOrder):
        super().sort(column, order)
        self.layoutAboutToBeChanged.emit()
        self._sort()
        self.layoutChanged.emit()

    def _sort(self):
        """Sorts the items in the proxy model based on a specific column and order."""
        if not self.sourceModel():
            return

        # Define a key function for sorting based on the data of the column
        def sort_key(index):
            return self.sourceModel().data(index, QtCore.Qt.DisplayRole)

        # Sort the flat map using the defined key function and the specified order
        self._flat_map.sort(key=sort_key, reverse=(self.sortOrder() == QtCore.Qt.DescendingOrder))

    def eventFilter(self, source, event):
        """Override the eventFilter method to handle events from the parent widget."""
        # Check if the event is a show event
        if event.type() == QtCore.QEvent.Show and source == self.parent_widget:
            self._sort()
            return True  # Event is handled

        # Call the base class method for default event handling
        return super().eventFilter(source, event)

class CheckableProxyModel(QtCore.QSortFilterProxyModel):
    """A proxy model to support checkable items and additional rows.
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, source_model: QtCore.QAbstractItemModel = None, parent=None):
        """Initialize the proxy model and its state tracking dictionary."""
        super().__init__(parent)
        self.check_states = dict()
        # To store additional rows data
        self._additional_rows = list()

        if source_model is not None:
            self.setSourceModel(source_model)

    # Public Methods
    # --------------
    def update_parent(self, child_index: QtCore.QModelIndex):
        """Update the check state of parent items based on child states."""
        parent_index = self.parent(child_index)
        while parent_index.isValid():
            children_states = {self.data(self.index(row, 0, parent_index), QtCore.Qt.CheckStateRole)
                               for row in range(self.rowCount(parent_index))}
            new_state = QtCore.Qt.PartiallyChecked if len(children_states) > 1 else next(iter(children_states))
            self.check_states[parent_index] = new_state
            self.dataChanged.emit(parent_index, parent_index, [QtCore.Qt.CheckStateRole])
            parent_index = self.parent(parent_index)

    def update_children(self, parent_index: QtCore.QModelIndex, value: Any):
        """Recursively update the check state of all child items."""
        for row in range(self.rowCount(parent_index)):
            child_index = self.index(row, 0, parent_index)
            self.check_states[child_index] = value
            self.dataChanged.emit(child_index, child_index, [QtCore.Qt.CheckStateRole])
            self.update_children(child_index, value)

    def set_check_states(self, check_states):
        """Set the check states from a given dictionary without setting each item individually."""
        self.check_states = check_states
        self._emit_data_changed()

    def _emit_data_changed(self):
        """Emit dataChanged signal for all affected indexes."""
        for index in self.check_states.keys():
            self.dataChanged.emit(index, index, [QtCore.Qt.CheckStateRole])

    # Override Methods
    # ----------------
    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:
        """Retrieve data at the given index for the specified role.
        """
        if role == QtCore.Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            return self.check_states.get(index, QtCore.Qt.CheckState.Unchecked)
        
        # TODO: Add support additional rows
        if not index.parent().isValid() and role == QtCore.Qt.DisplayRole:
            row = index.row() - super().rowCount(index.parent())
            if row >= 0 and row < len(self._additional_rows):
                return self._additional_rows[row][index.column()]
        # ---

        return super().data(index, role)

    def setData(self, index: QtCore.QModelIndex, value: Any, role: int = QtCore.Qt.ItemDataRole.EditRole) -> bool:
        """Set data at the given index for the specified role.
        """
        if role == QtCore.Qt.CheckStateRole and index.column() == 0:
            self.check_states[index] = value
            self.dataChanged.emit(index, index, [role])
            self.update_parent(index)
            self.update_children(index, value)
            return True
        return super().setData(index, value, role)

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlags:
        """Return the item flags for the given index.
        """
        return super().flags(index) | QtCore.Qt.ItemFlag.ItemIsUserCheckable

    def itemFromIndex(self, proxy_index):
        try:
            if proxy_index.isValid():
                source_index = self.mapToSource(proxy_index)
                return self.sourceModel().itemFromIndex(source_index)
        except AttributeError:
            pass

    def rowCount(self, parent=QtCore.QModelIndex()):
        if parent.isValid():
            # When the parent is valid, we're looking at children of a parent, so do not add additional rows count
            return super().rowCount(parent)
        else:
            # When the parent is not valid, we're looking at the root level, add additional rows count
            return super().rowCount(parent) + len(self._additional_rows)

    # TODO: Add support additional rows
    # def index(self, row, column, parent=QtCore.QModelIndex()):
    #     source_row_count = super().rowCount(parent)

    #     if row < source_row_count:
    #         return super().index(row, column, parent)
    #     else:
    #         return self.createIndex(row, column, self._additional_rows[row - source_row_count])

    def appendRow(self, item: Union[str, List[str]]):
        """Append an additional row to the model.
        """
        if isinstance(item, str):
            self._additional_rows.append([item])
        elif isinstance(item, list):
            self._additional_rows.append(item)
        else:
            raise ValueError("Unsupported item type. Expected str or list of str.")

        # Notify the view that the model has changed
        self.layoutChanged.emit()
