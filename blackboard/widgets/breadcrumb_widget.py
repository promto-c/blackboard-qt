# Type Checking Imports
# ---------------------
from typing import List, Dict

# Third Party Imports
# -------------------
from qtpy import QtCore, QtGui, QtWidgets


# Class Definitions
# -----------------
class BreadcrumbWidget(QtWidgets.QWidget):
    """A breadcrumb navigation widget using qtpy.

    This widget displays a series of clickable items separated by arrow labels,
    allowing navigation between hierarchical levels in an application.

    Attributes:
        path_list (List[str]): List of breadcrumb entries.
    """
    clicked = QtCore.Signal(int)

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent: QtWidgets.QWidget = None, paths: List[str] = None):
        """Initialize a BreadcrumbWidget widget.

        Args:
            parent (QtWidgets.QWidget, optional): The parent widget. Defaults to None.
            paths (List[str], optional): A list of strings representing each level in the breadcrumb trail.
                For example, ["Home", "Products", "Electronics", "Cameras"].
        """
        super().__init__(parent)

        self._custom_widgets: Dict[int, QtWidgets.QWidget] = {}
        self._init_ui()
        self.set_paths(paths)

    def _init_ui(self):
        """Set up the user interface components for the breadcrumb widget."""
        layout = QtWidgets.QHBoxLayout(self, spacing=0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

    # Public Methods
    # --------------
    def set_paths(self, paths: List[str]):
        """Update the breadcrumb trail with a new path list.

        This method clears the current breadcrumbs and rebuilds the UI with the new entries.

        Args:
            paths (List[str]): A new list of breadcrumb entries.
        """
        self._paths = paths

        # Clear all widgets from the current layout.
        while self.layout().count():
            item = self.layout().takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self._paths:
            self.setHidden(True)
            return

        self._assemble_breadcrumbs()

    def set_widget(self, index: int, widget: QtWidgets.QWidget):
        """Replace the breadcrumb at `index` with a custom widget.

        If breadcrumbs are already shown, this will remove the old item
        and insert your widget in its place. The custom widget is also
        remembered so that calling `set_paths` again will reapply it.

        Args:
            index (int): The breadcrumb level to replace (0-based).
            widget (QtWidgets.QWidget): The widget to insert at that level.
        """
        # remember for rebuilds
        self._custom_widgets[index] = widget

        layout = self.layout()
        # layout items: [btn0, sep, btn1, sep, btn2, ...]
        pos = index * 2
        # remove old
        old_item = layout.takeAt(pos)
        if old_item is not None:
            old_w = old_item.widget()
            if old_w:
                old_w.deleteLater()
        # insert new
        layout.insertWidget(pos, widget)

    # Class Properties
    # ----------------
    @property
    def paths(self) -> List[str]:
        """Get the current breadcrumb paths.

        Returns:
            List[str]: The current list of breadcrumb entries.
        """
        return self._paths
    
    @paths.setter
    def paths(self, paths: List[str]):
        """Set the breadcrumb paths.

        Args:
            paths (List[str]): A new list of breadcrumb entries.
        """
        self.set_paths(paths)

    # Private Methods
    # ---------------
    def _assemble_breadcrumbs(self):
        """Assemble the breadcrumb trail UI.
        """
        layout = self.layout()
        for idx, name in enumerate(self._paths):
            if idx > 0:
                separator = QtWidgets.QLabel(">")
                layout.addWidget(separator)

            button = QtWidgets.QPushButton(name, flat=True, cursor=QtCore.Qt.CursorShape.PointingHandCursor)
            # Connect the button click to the handler using lambda to capture the current index.
            button.clicked.connect(lambda _, idx=idx: self.clicked.emit(idx))
            layout.addWidget(button)

        self.setHidden(False)


# Example Usages
# --------------
if __name__ == '__main__':
    import sys
    from blackboard import theme

    app = QtWidgets.QApplication(sys.argv)
    theme.set_theme(app, "dark")
    # Define an example breadcrumb path.
    path = ["Home", "Products", "Electronics", "Cameras"]

    # Set up the layout and add the BreadcrumbWidget.
    breadcrumb = BreadcrumbWidget(paths=path)
    combo = QtWidgets.QComboBox()
    combo.addItems(["v1", "v2", "v3"])
    breadcrumb.set_widget(1, combo)
    breadcrumb.clicked.connect(lambda index: print(f"Clicked on: {breadcrumb.paths[index]}"))

    breadcrumb.show()
    sys.exit(app.exec_())
