# Type Checking Imports
# ---------------------
from typing import Any, Optional

# Third Party Imports
# -------------------
from qtpy import QtWidgets, QtCore, QtGui


# Class Definitions
# -----------------
class SectionAction(QtWidgets.QWidgetAction):
    """A custom widget action that represents a section header in a menu and facilitates
    inserting additional actions or submenus under that section.
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent_menu: QtWidgets.QMenu, text: str = None, icon: QtGui.QIcon = None):
        """
        Args:
            parent_menu (QtWidgets.QMenu): The parent menu where the section will be added.
            text (str, optional): The text for the section header.
            icon (QtGui.QIcon, optional): An optional icon for the section header.
        """
        super().__init__(parent_menu)

        self.parent_menu = parent_menu

        # List to keep track of actions added under this section
        self.actions = []

        # Create a container widget
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        # Optional Icon
        if icon:
            self.icon_label = QtWidgets.QLabel()
            pixmap = icon.pixmap(16, 16)  # Icon size can be made configurable.
            self.icon_label.setPixmap(pixmap)
            layout.addWidget(self.icon_label)
        else:
            self.icon_label = None

        # Add the text label.
        self.text_label = QtWidgets.QLabel(text)
        layout.addWidget(self.text_label)

        # Set the layout to the container
        container.setLayout(layout)

        # Set the container as the default widget for the action
        self.setDefaultWidget(container)

        # Add the action to the parent menu
        self.parent_menu.addAction(self)

        # Add a separator after the section
        self.separator = self.parent_menu.addSeparator()

    def addAction(self, action: QtGui.QAction = None, icon: QtGui.QIcon = QtGui.QIcon(), text: str = '', toolTip: str = None, 
                  data: Any = None, **kwargs) -> QtGui.QAction:
        """Insert an action into the parent menu before the separator.

        If no action is provided, a new QAction is created.

        Args:
            action (Optional[QtGui.QAction]): The action to insert. If None, a new action is created.
            icon (QtGui.QIcon): Icon for the action.
            text (str): Text for the action.
            toolTip (Optional[str]): Tooltip for the action.
            data (Any): Optional data to associate with the action.

        Returns:
            QtGui.QAction: The inserted action.
        """
        if not isinstance(action, QtGui.QAction):
            text = text or action
            toolTip = toolTip or text
            action = QtGui.QAction(icon=icon, text=text, toolTip=toolTip, parent=self, **kwargs)
            if data is not None:
                action.setData(data)

        self.parent_menu.insertAction(self.separator, action)
        self.actions.append(action)

        return action

    def addMenu(self, title: str, **kwargs) -> QtWidgets.QMenu:
        """Insert a submenu into the parent menu before the separator.

        Args:
            title (str): The title of the submenu.
            **kwargs: Additional keyword arguments for ContextMenu.

        Returns:
            QtWidgets.QMenu: The created submenu.
        """
        menu = ContextMenu(title, self.parent_menu, **kwargs)
        menu_action = self.parent_menu.insertMenu(self.separator, menu)
        self.actions.append(menu_action)

        return menu

    def addSeparator(self) -> QtWidgets.QAction:
        """Insert another separator into the parent menu after the current section.

        Returns:
            QtWidgets.QAction: The created separator action.
        """
        return self.parent_menu.insertSeparator(self.separator)

    def clear(self):
        """Clear all actions added under this section.
        """
        for action in self.actions:
            self.parent_menu.removeAction(action)
        self.actions.clear()


class ContextMenu(QtWidgets.QMenu):
    """A custom context menu with extended functionality.
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, title: str = '', parent: Optional[QtWidgets.QWidget] = None, *args, **kwargs):
        """
        Args:
            title (str): The title of the menu.
            parent (Optional[QtWidgets.QWidget]): The parent widget for the menu.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        super().__init__(title, parent, *args, **kwargs)

        # Set UI attributes
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

    def addSection(self, text: str, icon: Optional[QtGui.QIcon] = None) -> 'SectionAction':
        """Add a new section header to the menu.

        Args:
            text (str): The section header text.
            icon (Optional[QtGui.QIcon]): Optional icon for the section.

        Returns:
            SectionAction: The created section action.
        """
        return SectionAction(self, text, icon)

    def insert_after_action(self, target_action: QtWidgets.QAction, action_to_insert: QtWidgets.QAction):
        """Insert an action after a specific target action in the menu.

        Args:
            target_action (QtWidgets.QAction): The action after which to insert.
            action_to_insert (QtWidgets.QAction): The action to insert.
        """
        actions = self.actions()
        try:
            index = actions.index(target_action)
        except ValueError:
            # If the target action is not found, simply add the action at the end.
            self.addAction(action_to_insert)
            return

        if index + 1 < len(actions):
            self.insertAction(actions[index + 1], action_to_insert)
        else:
            self.addAction(action_to_insert)


class ResizableMenu(ContextMenu):
    """A resizable popup menu with drag-and-resize functionality.

    Attributes:
        button (Optional[QtWidgets.QPushButton]): Optional button to position the menu relative to.
        resized (QtCore.Signal): Signal emitted when the menu is resized.
    """

    # Constants
    # ---------
    DEFAULT_RESIZE_HANDLE_SIZE = 20

    # Signals
    # -------
    resized = QtCore.Signal(QtCore.QSize)

    # Initialization and Setup
    # ------------------------
    def __init__(self, button: Optional[QtWidgets.QPushButton] = None,
                 resize_handle_size: int = DEFAULT_RESIZE_HANDLE_SIZE):
        """Initialize the popup menu and set up drag-resize functionality.

        Args:
            button (Optional[QtWidgets.QPushButton]): Optional button to position the menu relative to.
            resize_handle_size (int): Size of the resize handle in pixels.
        """
        super().__init__()

        # Store the arguments
        self.button = button
        self._resize_handle_size = resize_handle_size

        # Initialize setup
        self.__init_attributes()

    def __init_attributes(self):
        """Initialize drag-resize related attributes.
        """
        self._is_dragging = False
        self._drag_start_point = QtCore.QPoint()
        self._initial_size = self.size()

    # Private Methods
    # ---------------
    def _resize_handle_rect(self) -> QtCore.QRect:
        """Calculate and return the rectangle for the resize handle area."""
        return QtCore.QRect(
            self.width() - self._resize_handle_size,
            self.height() - self._resize_handle_size,
            self._resize_handle_size,
            self._resize_handle_size
        )

    # Overridden Methods
    # ------------------
    def keyPressEvent(self, event: QtGui.QKeyEvent):
        """Handle key press events to prevent closing the popup on Enter or Return keys.
        """
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            # Do not close the menu on Enter/Return.
            event.ignore()
        else:
            super().keyPressEvent(event)

    def showEvent(self, event: QtGui.QShowEvent):
        """Override show event to modify the position of the menu popup.
        """
        if self.button:
            # Adjust the position
            pos = self.button.mapToGlobal(QtCore.QPoint(0, self.button.height()))
            self.move(pos)
        super().showEvent(event)

    def resizeEvent(self, event: QtGui.QResizeEvent):
        """Handle the resize event and emit a signal with the new size.
        """
        self.resized.emit(self.size())
        super().resizeEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """Start dragging if the mouse is pressed within the resize handle area.
        """
        if self._resize_handle_rect().contains(event.pos()):
            # Only start dragging if the mouse is within the handle area
            self._is_dragging = True
            self._drag_start_point = event.pos()
            self._initial_size = self.size()
            self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.SizeFDiagCursor))
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        """Resize the menu if dragging; otherwise, update the cursor based on position.
        """
        # If dragging, resize the widget
        if self._is_dragging:
            delta = event.pos() - self._drag_start_point
            new_size = QtCore.QSize(
                max(self._initial_size.width() + delta.x(), self.minimumWidth()),
                max(self._initial_size.height() + delta.y(), self.minimumHeight())
            )
            self.resize(new_size)
        else:
            # Only change the cursor if the mouse is in the resize handle area
            if self._resize_handle_rect().contains(event.pos()):
                self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.SizeFDiagCursor))
            else:
                # Reset to default cursor
                self.unsetCursor()

            # Call base implementation for default behavior
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        """Stop dragging and reset the cursor when the mouse is released.
        """
        self._is_dragging = False
        self.unsetCursor()
        super().mouseReleaseEvent(event)


# Examples
# --------
if __name__ == '__main__':
    import sys
    from blackboard import theme

    # Create the application instance
    app = QtWidgets.QApplication(sys.argv)
    theme.set_theme(app, 'dark')

    # Main window setup
    window = QtWidgets.QMainWindow()
    central_widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(central_widget)

    # Button to trigger the display of the ResizableMenu
    button = QtWidgets.QPushButton("Edit Profile")
    layout.addWidget(button)
    window.setCentralWidget(central_widget)
    window.resize(400, 300)
    window.show()

    def show_menu():
        # Create a ResizableMenu anchored to the button
        menu = ResizableMenu(button)
        menu.setMinimumWidth(300)

        # Section 1: User Information (Custom Widget)
        # -------------------------------------------
        user_info_section = menu.addSection("User Info")

        # Create a custom widget action for editing username
        username_action = QtWidgets.QWidgetAction(menu)
        username_widget = QtWidgets.QWidget()
        username_layout = QtWidgets.QHBoxLayout(username_widget)
        username_layout.setContentsMargins(8, 4, 8, 4)
        username_layout.setSpacing(8)
        label_username = QtWidgets.QLabel("Username:")
        edit_username = QtWidgets.QLineEdit()
        edit_username.setPlaceholderText("Enter username")
        username_layout.addWidget(label_username)
        username_layout.addWidget(edit_username)
        username_widget.setLayout(username_layout)
        username_action.setDefaultWidget(username_widget)
        user_info_section.addAction(username_action)

        # Sync the width of the custom widget with the menu's width
        def sync_user_widget_width(new_size: QtCore.QSize):
            # Adjust width taking into account horizontal margins (8 on left and right).
            username_widget.setFixedWidth(new_size.width() - 16)
        menu.resized.connect(sync_user_widget_width)

        # Section 2: Actions
        # ------------------
        actions_section = menu.addSection("Actions")
        # Adding Save action with an icon (if available) for better recognition
        save_icon = QtGui.QIcon.fromTheme("document-save")  # Uses system theme icon if available
        save_action = actions_section.addAction(icon=save_icon, text="Save", toolTip="Save changes")
        # Adding Cancel action
        cancel_action = actions_section.addAction(text="Cancel", toolTip="Discard changes")

        # Insert a Help action after the Save action using the ContextMenu's method.
        help_icon = QtGui.QIcon.fromTheme("help-about")
        help_action = QtGui.QAction(help_icon, "Help", menu)
        help_action.setToolTip("Get help")
        menu.insert_after_action(save_action, help_action)

        # Optionally, connect actions to appropriate slots
        save_action.triggered.connect(lambda: print("Profile saved:", edit_username.text()))
        cancel_action.triggered.connect(lambda: print("Profile changes canceled"))
        help_action.triggered.connect(lambda: print("Help action triggered"))

        # Display the menu below the button
        pos = button.mapToGlobal(QtCore.QPoint(0, button.height()))
        menu.exec_(pos)

    # Connect the button click to the show_menu function
    button.clicked.connect(show_menu)

    # Execute the application's main loop
    sys.exit(app.exec_())
