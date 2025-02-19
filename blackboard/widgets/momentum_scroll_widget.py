# Third Party Imports
# -------------------
from qtpy import QtWidgets, QtCore, QtGui

# Local Imports
# -------------
from blackboard.utils import MomentumScrollHandler


# Class Definitions
# -----------------
class MomentumScrollMixin:
    """Mixin that adds momentum scrolling functionality to a widget using a MomentumScrollHandler.

    This mixin provides implementations for mouse press/move/release and wheel events.
    """

    def __init__(self, *args, **kwargs):
        # Call the next __init__ in the MRO and initialize the scroll handler.
        super().__init__(*args, **kwargs)

        self.scroll_handler = MomentumScrollHandler(self)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """Handle mouse press events and ignore them if the scroll handler consumes them.
        """
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self.scroll_handler.handle_mouse_press(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        """Handle mouse move events and ignore them if the scroll handler consumes them.
        """
        if self.scroll_handler.handle_mouse_move(event):
            event.ignore()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        """Handle mouse release events and ignore them if the scroll handler consumes them.
        """
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self.scroll_handler.handle_mouse_release(event)
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent):
        """Handle wheel events and pass them to the scroll handler.
        """
        self.scroll_handler.handle_wheel_event(event)


class MomentumScrollListView(MomentumScrollMixin, QtWidgets.QListView):
    """A QListView with momentum scrolling functionality.
    """

    def __init__(self, parent: QtWidgets.QWidget = None, dragEnabled: bool = False, *args, **kwargs):
        """Initialize the widget with momentum scrolling functionality.

        Args:
            parent: The parent widget.
            dragEnabled: Whether the widget should support drag and drop.
        """
        super().__init__(
            parent,
            dragEnabled=dragEnabled,
            horizontalScrollMode=QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel,
            verticalScrollMode=QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel,
            *args, **kwargs
        )


class MomentumScrollListWidget(MomentumScrollMixin, QtWidgets.QListWidget):
    """A QListWidget with momentum scrolling functionality.
    """

    def __init__(self, parent: QtWidgets.QWidget = None, dragEnabled: bool = False, *args, **kwargs):
        """Initialize the widget with momentum scrolling functionality.

        Args:
            parent: The parent widget.
            dragEnabled: Whether the widget should support drag and drop.
        """
        super().__init__(
            parent,
            dragEnabled=dragEnabled,
            horizontalScrollMode=QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel,
            verticalScrollMode=QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel,
            *args, **kwargs
        )


class MomentumScrollTreeView(MomentumScrollMixin, QtWidgets.QTreeView):
    """A QTreeView with momentum scrolling functionality.
    """

    def __init__(self, parent: QtWidgets.QWidget = None, *args, **kwargs):
        """Initialize the widget with momentum scrolling functionality.

        Args:
            parent: The parent widget.
        """
        super().__init__(
            parent,
            horizontalScrollMode=QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel,
            verticalScrollMode=QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel,
            *args, **kwargs
        )


class MomentumScrollTreeWidget(MomentumScrollMixin, QtWidgets.QTreeWidget):
    """A QTreeWidget with momentum scrolling functionality.
    """

    def __init__(self, parent: QtWidgets.QWidget = None, *args, **kwargs):
        """Initialize the widget with momentum scrolling functionality.

        Args:
            parent: The parent widget.
        """
        super().__init__(
            parent,
            horizontalScrollMode=QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel,
            verticalScrollMode=QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel,
            *args, **kwargs
        )


class MomentumScrollArea(MomentumScrollMixin, QtWidgets.QScrollArea):
    """A QScrollArea with momentum scrolling functionality.
    """

    def __init__(self, parent: QtWidgets.QWidget = None, *args, **kwargs):
        """Initialize the widget with momentum scrolling functionality.

        Args:
            parent: The parent widget.
        """
        super().__init__(
            parent,
            horizontalScrollBarPolicy=QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded,
            verticalScrollBarPolicy=QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded,
            *args, **kwargs
        )


if __name__ == '__main__':
    import sys
    from blackboard import theme

    app = QtWidgets.QApplication(sys.argv)
    theme.set_theme(app, 'dark')
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("Momentum Scroll Example")

    # Central widget with a vertical layout
    central_widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(central_widget)

    # Example 1: MomentumScrollListWidget with many items
    list_widget = MomentumScrollListWidget()
    for i in range(300):
        list_widget.addItem(f"Item {i + 1}")
    layout.addWidget(list_widget)

    # Example 2: MomentumScrollArea with a scrollable container
    scroll_area = MomentumScrollArea()
    container = QtWidgets.QWidget()
    container_layout = QtWidgets.QVBoxLayout(container)
    for i in range(50):
        label = QtWidgets.QLabel(f"Scrollable Label {i + 1}")
        container_layout.addWidget(label)
    scroll_area.setWidget(container)
    scroll_area.setWidgetResizable(True)
    layout.addWidget(scroll_area)

    # Example 3: Multi-Column MomentumScrollTreeWidget
    # This tree will have two columns and will generate content wide enough to require horizontal scrolling.
    tree_widget = MomentumScrollTreeWidget()
    tree_widget.setColumnCount(2)
    tree_widget.setHeaderLabels(["Column 1", "Column 2"])
    
    # Add parent and child items with longer text to force horizontal scrolling.
    for i in range(10):
        parent_text = f"Parent {i + 1} with extra long description to test horizontal scroll"
        parent_data = f"Data {i + 1} with extra long details to test horizontal scroll"
        parent_item = QtWidgets.QTreeWidgetItem(tree_widget, [parent_text, parent_data])
        for j in range(5):
            child_text = f"Child {i + 1}.{j + 1} with extended text"
            child_data = f"Value {i + 1}.{j + 1} with even more extended details"
            child_item = QtWidgets.QTreeWidgetItem(parent_item, [child_text, child_data])
            parent_item.addChild(child_item)
    tree_widget.expandAll()
    layout.addWidget(tree_widget)

    window.setCentralWidget(central_widget)
    window.resize(600, 800)
    window.show()

    sys.exit(app.exec_())
