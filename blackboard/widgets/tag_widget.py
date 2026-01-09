# Type Checking Imports
# ---------------------
from typing import List

# Third Party Imports
# -------------------
from qtpy import QtWidgets, QtCore, QtGui

# Local Imports
# -------------
from blackboard.utils.proxy_model import FlatProxyModel
from blackboard.widgets.momentum_scroll_widget import MomentumScrollListView


# Class Definitions
# -----------------
class TagListView(MomentumScrollListView):

    # Signal emitted when the tag list changes
    tag_changed = QtCore.Signal()

    # Initialization and Setup
    # ------------------------
    def __init__(
        self,
        parent=None,
        show_only_checked: bool = True,
        read_only: bool = False,
        editTriggers=QtWidgets.QListView.EditTrigger.NoEditTriggers,
        viewMode=QtWidgets.QListView.ViewMode.IconMode,
        resizeMode=QtWidgets.QListView.ResizeMode.Adjust,
        dragDropMode=QtWidgets.QListView.DragDropMode.NoDragDrop,
        mouseTracking=True,
        *args, **kwargs
    ):
        """Initialize the TagListView widget.
        """
        super().__init__(
            parent, editTriggers=editTriggers, viewMode=viewMode, resizeMode=resizeMode,
            dragDropMode=dragDropMode, mouseTracking=mouseTracking,
            *args, **kwargs
        )

        # Store the arguments
        self.show_only_checked = show_only_checked
        self.read_only = read_only

        # Initialize setup
        self.__init_attributes()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        self._proxy_model = FlatProxyModel(parent=self, show_only_checked=self.show_only_checked, show_only_leaves=True)
        self._proxy_model.set_show_checkbox(False)

        self._press_position = None
        super().setModel(self._proxy_model)
        self._proxy_model.layoutChanged.connect(self.tag_changed.emit)

    # Public Methods
    # --------------
    def get_tags(self) -> List[str]:
        """Retrieve all tags from the model.
        """
        return [self.model().index(row, 0).data() for row in range(self.model().rowCount())]

    def get_tags_count(self) -> int:
        """Get the count of tags.
        """
        return self.model().rowCount()

    def set_read_only(self, read_only: bool):
        """Enable or disable read-only mode for the widget.

        Args:
            read_only (bool): Whether the widget should be in read-only mode.
        """
        self.read_only = read_only

    def add_items(self, tags: List[str]):
        """Add multiple tags to the list.

        Args:
            tags (List[str]): List of tag names to add.
        """
        model = self.source_model or QtGui.QStandardItemModel()

        # Append new items to the model
        model.setRowCount(model.rowCount() + len(tags))
        for index, tag in enumerate(tags):
            display_text = str(tag) if not isinstance(tag, str) else tag
            item = QtGui.QStandardItem(display_text)
            item.setCheckable(True)
            item.setCheckState(QtCore.Qt.CheckState.Checked)

            # Store the original tag in a custom role
            item.setData(tag, QtCore.Qt.ItemDataRole.UserRole)

            model.setItem(model.rowCount() - len(tags) + index, item)

        self.setModel(model)

    # Class Properties
    # ----------------
    @property
    def source_model(self):
        return self._proxy_model.sourceModel()

    @property
    def proxy_model(self):
        return self._proxy_model

    # Override Methods
    # ----------------
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

        if self.read_only:
            return

        index = self.indexAt(event.pos())
        if index.isValid():
            self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        else:
            self.unsetCursor()

    def mousePressEvent(self, event):
        if self.read_only:
            super().mousePressEvent(event)
            return

        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._press_position = event.pos()  # Store mouse press position
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        super().mouseReleaseEvent(event)

        if self.read_only:
            return

        if self._press_position != event.pos():
            self._press_position = None
            return

        index = self.indexAt(event.pos())
        if not index.isValid():
            self._press_position = None
            return

        tag_name = index.data()

        if self.show_only_checked:
            new_state = QtCore.Qt.CheckState.Unchecked
        else:
            # Toggle the check state
            current_state = index.data(QtCore.Qt.ItemDataRole.CheckStateRole)
            new_state = QtCore.Qt.CheckState.Unchecked if current_state == QtCore.Qt.CheckState.Checked else QtCore.Qt.CheckState.Checked

        # Update the tag's check state and show feedback
        self.model().setData(index, new_state, QtCore.Qt.ItemDataRole.CheckStateRole)
        state_text = "Added" if new_state == QtCore.Qt.CheckState.Checked else "Removed"
        QtWidgets.QToolTip.showText(event.globalPos(), f"'{tag_name}' {state_text}.", self)

        self._press_position = None

    def setModel(self, model: QtGui.QStandardItemModel):
        """Override to set the model with additional configurations.
        """
        self._proxy_model.setSourceModel(model)


# Example usage
if __name__ == "__main__":
    import sys
    from blackboard import theme

    app = QtWidgets.QApplication(sys.argv)
    theme.set_theme(app, 'dark')

    tag_list_view = TagListView(read_only=True)

    # Add initial tags
    tag_list_view.add_items(["Tag 1", "Tag 3", "Tag 2"])
    tag_list_view.show()

    # Test sorting
    tag_list_view.add_items(["Tag 7", "Tag 5", "Tag 6"])

    sys.exit(app.exec_())
