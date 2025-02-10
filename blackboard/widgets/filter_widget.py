# Type Checking Imports
# ---------------------
from typing import TYPE_CHECKING, Any, Optional, List, Union, Dict, Tuple, Type
if TYPE_CHECKING:
    import datetime

# Standard Library Imports
# ------------------------
import fnmatch
from functools import partial

# Third Party Imports
# -------------------
from qtpy import QtWidgets, QtCore, QtGui
from tablerqicon import TablerQIcon

# Local Imports
# -------------
import blackboard as bb
from blackboard import widgets
from blackboard.widgets.menu import ContextMenu, ResizableMenu
from blackboard.widgets.line_edit import LineEdit
from blackboard.widgets.calendar_widget import CalendarSelectionMode, RangeCalendarWidget
from blackboard.enums.view_enum import FilterOperation, FieldType, FilterMode, DateRange


# Class Definitions
# -----------------
# TODO: Implement filter widget to support switch mode
class FilterSelectionBar(QtWidgets.QToolBar):
    """A toolbar widget that manages filter actions.

    Attributes:
        filter_changed: Signal to notify filter state changes.
    """

    # Initialization and Setup
    # ------------------------
    filter_changed = QtCore.Signal(str, bool)  # Signal to notify filter state changes
    filters_cleared = QtCore.Signal()  # Signal to notify when all filters are cleared

    def __init__(self, parent=None):
        """Initialize the FilterSelectionBar and set up UI components.

        Args:
            parent: The parent widget of this toolbar.
        """
        # Initialize the super class
        super().__init__(parent)

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        # Attributes
        # ----------
        self._actions: Dict[str, QtWidgets.QAction] = {}  # Dictionary to store checkable actions

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setWindowTitle("Filter Bar")
        self._customize_toolbar_components()
        self._update_ext_icon()

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        self.orientationChanged.connect(self._update_ext_icon)

    # Public Methods
    # --------------
    def add_filter(self, name: str):
        """Add a new checkable filter action to the toolbar.

        Args:
            name: The name of the filter to add.

        Raises:
            ValueError: If the filter already exists.
        """
        if name in self._actions:
            raise ValueError(f"Filter '{name}' already exists.")
        
        action = QtWidgets.QAction(name, self)
        action.setCheckable(True)  # Make the action checkable
        action.triggered.connect(partial(self._apply_filter_action, name))
        self._actions[name] = action  # Store the action

        self.addAction(action)  # Add the action to the toolbar

    def add_filters(self, names: list[str]):
        """Add multiple checkable filter actions to the toolbar.

        Args:
            names: A list of filter names to add.
        """
        for name in names:
            self.add_filter(name)

    def remove_filter(self, name: str):
        """Remove a filter action from the toolbar.

        Args:
            name: The name of the filter to remove.

        Raises:
            ValueError: If the filter is not found.
        """
        action = self._actions.pop(name, None)
        if action:
            self.removeAction(action)
        else:
            raise ValueError(f"Filter '{name}' not found.")

    def clear(self):
        """Remove all filter actions from the toolbar."""
        for name in list(self._actions.keys()):
            self.remove_filter(name)

    def clear_filters(self):
        """Uncheck all checked filters in the toolbar."""
        for action in self._actions.values():
            action.setChecked(False)
        self.filters_cleared.emit()

    def is_filter_checked(self, name: str) -> bool:
        """Return whether the given filter is checked.

        Args:
            name: The name of the filter to check.

        Returns:
            True if the filter is checked, otherwise False.

        Raises:
            ValueError: If the filter is not found.
        """
        action = self._actions.get(name)
        if action:
            return action.isChecked()
        raise ValueError(f"Filter '{name}' not found.")

    def set_filter_checked(self, filter_name: str, checked: bool = True, block_signal: bool = False):
        """Set the checked state of the given filter.

        Args:
            name: The name of the filter to set.
            checked: The checked state to set (default is True).
            block_signal: If True, block the signal emission (default is False).

        Raises:
            ValueError: If the filter is not found.
        """
        action = self._actions.get(filter_name)
        if not action:
            raise ValueError(f"Filter '{filter_name}' not found.")

        action.setChecked(checked)
        if block_signal:
            return

        self.filter_changed.emit(filter_name, checked)

    def apply_exclusive_filter(self, filter_name: str):
        """Apply the selected filter exclusively by clearing others.

        Args:
            filter_name: The name of the filter to apply exclusively.
        """
        self.clear_filters()
        self.set_filter_checked(filter_name, checked=True)

    def get_filter_names(self) -> List[str]:
        """Retrieve a list of all filter names.

        Returns:
            A list of all filter names.
        """
        return list(self._actions.keys())

    def get_filter_states(self) -> Dict[str, bool]:
        """Retrieve the state of all filters in a dictionary format.

        Returns:
            A dictionary with filter names as keys and their checked state as values.
        """
        return {name: action.isChecked() for name, action in self._actions.items()}

    def get_active_filters(self) -> List[str]:
        """Retrieve a list of all checked (active) filters.

        Returns:
            A list of all checked filter names.
        """
        return [name for name, action in self._actions.items() if action.isChecked()]

    # Class Properties
    # ----------------
    @property
    def filter_names(self) -> List[str]:
        return self.get_filter_names()

    @property
    def active_filters(self) -> List[str]:
        return self.get_active_filters()

    # Private Methods
    # ---------------
    def _customize_toolbar_components(self):
        """Customize the toolbar components.
        """
        self.qt_toolbar_ext_button: QtWidgets.QToolButton = self.findChild(QtWidgets.QToolButton, 'qt_toolbar_ext_button')
        self.qt_toolbar_ext_button.setStyleSheet('padding: 0;')
        self.qt_toolbar_ext_button.setFixedSize(20, 20)
        self.qt_toolbar_ext_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def _move_ext_button(self):
        """Move the toolbar extension button based on orientation.
        """
        if self.qt_toolbar_ext_button.isHidden():
            return

        if self.orientation() == QtCore.Qt.Orientation.Vertical:
            # Move button to the bottom of the toolbar in vertical orientation
            new_y = self.height() - self.qt_toolbar_ext_button.height()
            if self.qt_toolbar_ext_button.y() != new_y:
                self.qt_toolbar_ext_button.move(self.qt_toolbar_ext_button.x(), new_y)
        else:
            # Move button to the right end in horizontal orientation
            new_x = self.width() - self.qt_toolbar_ext_button.width()
            if self.qt_toolbar_ext_button.x() != new_x:
                self.qt_toolbar_ext_button.move(new_x, self.qt_toolbar_ext_button.y())

    def _update_ext_icon(self, _orientation=None):
        """Update the icon of the toolbar extension button.
        """
        self.qt_toolbar_ext_button.setIcon(TablerQIcon.chevron_down)

    def _apply_filter_action(self, filter_name: str, check_state: bool):
        """Apply the filter action logic, including exclusive selection if Ctrl is pressed."""
        if QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            self.apply_exclusive_filter(filter_name)
        else:
            self.filter_changed.emit(filter_name, check_state)

    # Overridden Methods
    # ------------------
    def paintEvent(self, event):
        """Handle the paint event for the toolbar.

        Args:
            event: The paint event.
        """
        super().paintEvent(event)
        self._move_ext_button()

# TODO: Add support to set column name mapping to filter widget
class FilterBarWidget(QtWidgets.QWidget):

    filter_changed = QtCore.Signal()
    filter_widget_removed = QtCore.Signal(str)

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent: QtWidgets.QWidget = None):
        super().__init__(parent)

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        # Private Attributes
        # ------------------
        self._filter_widgets: List['FilterWidget'] = []

    def __init_ui(self):
        """Initialize the UI of the widget.
        
        UI Wireframe:

            +-------------------------+
            | [Filter 1][Filter 2][+] |
            +-------------------------+
        """
        self.tabler_icon = TablerQIcon(opacity=0.6)

        # Create Layouts
        # --------------
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.filter_area_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(self.filter_area_layout)

        # Create Widgets
        # --------------
        # Add filter button
        self.add_filter_button = QtWidgets.QToolButton(
            self, icon=self.tabler_icon.plus, toolTip="Add Filter"
        )
        self.add_filter_button.setProperty('widget-style', 'round')
        self.add_filter_button.setFixedSize(24, 24)
        self.add_filter_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))

        # Add Widgets to Layouts
        self.main_layout.addWidget(self.add_filter_button)

        self.update_style()

    # Public Methods
    # --------------
    def update_style(self):
        """Update the button's style based on its state.
        """
        self.style().unpolish(self)
        self.style().polish(self)

    def add_filter_widget(self, filter_widget: 'FilterWidget'):
        """Add a filter widget to the filter area layout.
        """
        self.filter_area_layout.addWidget(filter_widget.button)
        self._filter_widgets.append(filter_widget)
        filter_widget.activated.connect(self.filter_changed.emit)
        filter_widget.removed.connect(self.remove_filter_widget)

    def remove_filter_widget(self, filter_widget: 'FilterWidget' = None):
        """Remove a filter widget from the filter area layout.
        """
        filter_widget = filter_widget or self.sender()
        if filter_widget not in self._filter_widgets:
            return

        self.filter_area_layout.removeWidget(filter_widget.button)
        filter_widget.button.deleteLater()
        self._filter_widgets.remove(filter_widget)
        self.filter_widget_removed.emit(filter_widget.filter_name)

    def clear(self):
        """Clear all filter widgets from the filter bar.
        """
        for filter_widget in self._filter_widgets:
            self.remove_filter_widget(filter_widget)
        self._filter_widgets.clear()

    def get_active_filters(self) -> List['FilterWidget']:
        """Return a list of currently active filters.
        """
        return [filter_widget for filter_widget in self._filter_widgets if filter_widget.is_active]

    def get_query_conditions(self) -> List[Dict[str, Dict['FilterOperation', Any]]]:
        """Return a list of query conditions for the active filters.
        """
        return [filter_widget.get_query_condition() for filter_widget in self.get_active_filters()]

    def count_filters(self) -> int:
        """Return the number of active filters.
        """
        return len(self._filter_widgets)

    # Class Properties
    # ----------------
    @property
    def filter_widgets(self) -> List['FilterWidget']:
        return self._filter_widgets


class MoreOptionsButton(QtWidgets.QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setIcon(TablerQIcon(opacity=0.6).dots_vertical)

        # Create the menu
        self.popup_menu = ContextMenu()

        self.clicked.connect(self.show_menu)

    def addAction(self, text: str, icon: QtGui.QIcon = None):
        """Add an action to the menu.
        """
        action = self.popup_menu.addAction(text)
        if icon is not None:
            action.setIcon(icon)

        return action

    def show_menu(self):
        """Display the menu at the button's position.
        """
        self.popup_menu.popup(self.mapToGlobal(self.rect().bottomLeft()))


class FilterButton(QtWidgets.QPushButton):

    MINIMUM_WIDTH, MINIMUM_HEIGHT = 42, 24

    def __init__(self, filter_widget: QtWidgets.QWidget = None, parent = None):
        super().__init__(
            parent, focusPolicy=QtCore.Qt.FocusPolicy.StrongFocus,
            checkable=True, cursor=QtCore.Qt.CursorShape.PointingHandCursor,
            minimumSize=QtCore.QSize(self.MINIMUM_WIDTH, self.MINIMUM_HEIGHT),
        )

        # Store the arguments
        self._filter_widget = filter_widget

        # Initialize setup
        self.__init_ui()

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self._object_to_connection_pairs: List[Tuple[QtCore.QObject, QtCore.QMetaObject.Connection]] = []
        self.popup_menu = ResizableMenu(button=self)
        self.setMenu(self.popup_menu)
        self.setFixedHeight(self.MINIMUM_HEIGHT)

        if self._filter_widget is not None:
            self.set_filter_widget(self._filter_widget)

    def set_filter_widget(self, filter_widget: 'FilterWidget'):
        """Set the popup menu for the filter button.
        """
        for object, connection in self._object_to_connection_pairs:
            object.disconnect(connection)
        self._object_to_connection_pairs.clear()

        self._filter_widget = filter_widget
        self.popup_menu.clear()

        if not self._filter_widget:
            return

        # Update the popup menu with the new filter widget
        action = QtWidgets.QWidgetAction(self.popup_menu)
        action.setDefaultWidget(self._filter_widget)
        self.popup_menu.addAction(action)

        resized_connection = self.popup_menu.resized.connect(self._filter_widget.setMinimumSize)
        self._object_to_connection_pairs.append((self.popup_menu, resized_connection))
        icon_changed_connection = self._filter_widget.windowIconChanged.connect(self.setIcon)
        self._object_to_connection_pairs.append((self._filter_widget, icon_changed_connection))

        self.setIcon(self._filter_widget.windowIcon())

    def setText(self, text: str):
        """Override the setText method to set both the button text and the tooltip.

        Args:
            text (str): The text to set on the button and as the tooltip.
        """
        super().setText(text)
        self.setToolTip(text)


class FilterWidget(QtWidgets.QWidget):

    SUPPORTED_TYPE: Optional[FilterOperation] = None
    CONDITIONS: List[FilterOperation] = []
    DEFAULT_OPERATION = FilterOperation.EQ

    activated = QtCore.Signal(bool)
    removed = QtCore.Signal()

    # Central registry mapping FieldType to widget class
    registry: Dict[FieldType, Type['FilterWidget']] = {}

    # Initialization and Setup
    # ------------------------
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Automatically register the subclass if it defines a SUPPORTED_TYPE attribute
        if cls.SUPPORTED_TYPE is not None:
            FilterWidget.registry[cls.SUPPORTED_TYPE] = cls
            cls.CONDITIONS = cls.SUPPORTED_TYPE.supported_operations

    def __init__(self, filter_name: str = '', display_name: str = None, parent: QtWidgets.QWidget = None):
        super().__init__(parent, QtCore.Qt.WindowType.Popup)

        # Store the filter name
        self.filter_name = filter_name
        self.display_name = display_name or filter_name

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        # Attributes
        # ------------------
        self.tabler_icon = TablerQIcon(opacity=0.6)

        # Private Attributes
        # ------------------
        self._value = None
        self._is_filter_applied = False
        self._initial_focus_widget: QtWidgets.QWidget = None
        self._saved_state = dict()
        self._filter_mode: 'FilterMode' = FilterMode.STANDARD

    def __init_ui(self):
        """Initialize the UI of the widget.

        UI Wireframe:

            ( FilterButton ▼ )
            +---------------------------------------------+
            | Condition ▼                    [Clear] [⋮] |
            | ------------------------------------------- |
            |                                             |
            |        Widget-specific content area         |
            |                                             |
            | ------------------------------------------- |
            |                     [Cancel] [Apply Filter] |
            +---------------------------------------------+

            [⋮]
            Manage
            - Remove Filter
            Switch to
            - Standard Filter
            - Toggle Filter
            - Advance Filter

        """
        # Set window title
        self.setWindowTitle(self.display_name)

        # Create Layouts
        # --------------
        # Main layout
        self.main_layout = QtWidgets.QVBoxLayout(self)

        # Title bar with remove icon
        self.title_layout = QtWidgets.QHBoxLayout()
        self.title_layout.setSpacing(3)
        self.main_layout.addLayout(self.title_layout)

        # Widget-specific content area
        self.widget_layout = QtWidgets.QVBoxLayout()
        self.main_layout.addLayout(self.widget_layout)

        # 
        self.buttons_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(self.buttons_layout)

        # Create Widgets
        # --------------
        # Initialize the filter button
        self._button = FilterButton(self, self.parent())
        self._clear_button_text()

        self.condition_combo_box = QtWidgets.QComboBox()
        self.condition_combo_box.setProperty('widget-style', 'clean')
        # Update the condition combo box
        for condition in self.CONDITIONS:
            self.condition_combo_box.addItem(condition.display_name, condition)
        self.condition_combo_box.setCurrentText(self.DEFAULT_OPERATION.display_name)

        self.clear_button = QtWidgets.QToolButton(self, icon=self.tabler_icon.clear_all, toolTip="Clear all")

        # Vertical ellipsis button with menu
        self.more_options_button = MoreOptionsButton(self)

        # Add "Remove Filter" action
        manage_section = self.more_options_button.popup_menu.addSection('Manage')
        self.remove_action = manage_section.addAction(
            icon=self.tabler_icon.trash, text="Remove Filter",
            toolTip="Remove this filter from Quick Access"
        )
        self.remove_action.setProperty('color', 'red')

        # Add "Switch Filter" action
        switch_to_section = self.more_options_button.popup_menu.addSection('Switch to')

        # TODO: Implement
        self.switch_to_standard_filter_action = switch_to_section.addAction(icon=self.tabler_icon.filter, text="Standard Filter")
        self.switch_to_toggle_filter_action = switch_to_section.addAction(icon=self.tabler_icon.toggle_left, text="Toggle Filter")
        self.switch_to_advance_filter_action = switch_to_section.addAction(icon=self.tabler_icon.filter_cog, text="Advance Filter")

        # Add Confirm and Cancel buttons
        self.cancel_button = QtWidgets.QPushButton("Cancel", cursor=QtCore.Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setProperty('widget-style', 'dialog')
        self.apply_button = QtWidgets.QPushButton("Apply Filter", cursor=QtCore.Qt.CursorShape.PointingHandCursor)
        self.apply_button.setProperty('widget-style', 'dialog')
        self.apply_button.setProperty('color', 'blue')

        # Add Widgets to Layouts
        # ----------------------
        self.title_layout.addWidget(self.condition_combo_box)
        self.title_layout.addStretch()
        self.title_layout.addWidget(self.clear_button)
        self.title_layout.addWidget(self.more_options_button)

        # Add Confirm and Cancel buttons
        self.buttons_layout.addStretch()
        self.buttons_layout.addWidget(self.cancel_button)
        self.buttons_layout.addWidget(self.apply_button)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect signals to slots
        self._button.toggled.connect(self.set_active)

        self.apply_button.clicked.connect(self.apply_filter)

        self.cancel_button.clicked.connect(self.discard_change)
        self.cancel_button.clicked.connect(self.hide_popup)

        self.clear_button.clicked.connect(self.set_filter_applied)
        self.clear_button.clicked.connect(self.clear_state)
        self.clear_button.clicked.connect(self.clear_filter)
        self.clear_button.clicked.connect(lambda: self.activated.emit(False))
        self.clear_button.clicked.connect(self.hide_popup)

        self.remove_action.triggered.connect(self.remove_filter)

        self.switch_to_toggle_filter_action.triggered.connect(lambda: self.set_filter_mode(FilterMode.TOGGLE))

        # Connect signals with the filter button
        self.activated.connect(self._update_active_state)
        self.activated.connect(self._update_button_text)

        bb.utils.KeyBinder.bind_key('Enter', self, self.apply_filter)

    # Private Methods
    # ---------------
    def _update_active_state(self, state: bool):
        """Update the active state based on the filter widget's state.
        """
        self._button.setChecked(state)

    def _update_button_text(self):
        """Update the button text.
        """
        self._button.setText(self.format_label(self.get_value()))

    def _clear_button_text(self):
        """Clear the button text.
        """
        self._button.setText(self._format_text(''))

    def _format_text(self, text: str) -> str:
        """Format the text to be displayed on the button.
        """
        return f"{self.display_name} • {text}"

    # Public Methods
    # --------------
    def update_style(self, widget: Optional[QtWidgets.QWidget] = None):
        """Update the style of the specified widget or self.
        """
        if not isinstance(widget, QtWidgets.QWidget):
            widget = None
        widget = widget or self.sender() or self

        self.style().unpolish(widget)
        self.style().polish(widget)

    def unset_popup(self):
        """Unset the popup menu for the filter button.
        """
        self._button.setMenu(None)

    def hide_popup(self):
        """Hide the popup menu.
        """
        self._button.popup_menu.hide()

    def apply_filter(self):
        """Apply the filter and hide the popup.
        """
        self.set_filter_applied()
        self.save_change()
        self.activated.emit(self.check_validity())
        self.hide_popup()

    def set_filter_mode(self, filter_mode: 'FilterMode'):
        self._filter_mode = filter_mode

        if filter_mode == FilterMode.TOGGLE:
            self._button.setMenu(None)
            self.setIcon(TablerQIcon.toggle_left)
        elif filter_mode == FilterMode.ADVANCED:
            ...
        else:
            ...

        self.hide_popup()

    def set_filter_applied(self):
        """Set the filter as applied.
        """
        self._is_filter_applied = True

    def save_state(self, key, value: Any = None):
        """Save the given state with the specified key.
        """
        self._saved_state[key] = value

    def load_state(self, key, default_value: Any = None):
        """Load the state associated with the given key.
        """
        return self._saved_state.get(key, default_value)

    def clear_state(self):
        """Clear all saved states.
        """
        self._saved_state.clear()

    def set_initial_focus_widget(self, widget):
        """Set the initial focus widget for the popup.
        """
        self._initial_focus_widget = widget

    def remove_filter(self):
        """Remove the filter.
        """
        self.removed.emit()
        self.hide_popup()

    def set_active(self, state: bool = True):
        """Set the active state of the filter.
        """
        if self._filter_mode == FilterMode.TOGGLE:
            icon = TablerQIcon.toggle_right if state else TablerQIcon.toggle_left
            self.setIcon(icon)
            self.activated.emit(state)

        else:
            self._button.setChecked(state)

    def get_filter_condition(self) -> 'FilterOperation':
        return self.condition_combo_box.currentData(QtCore.Qt.ItemDataRole.UserRole)

    def get_query_condition(self) -> Dict[str, Dict['FilterOperation', Any]]:
        return {
            self.filter_name: {
                self.get_filter_condition(): self.get_value()
            }
        }

    # Class Properties
    # ----------------
    @property
    def button(self):
        """Return the filter button.
        """
        return self._button

    @property
    def filter_mode(self):
        return self._filter_mode

    @property
    def is_active(self):
        """Check if the filter is active.
        """
        return self._button.isChecked()

    @property
    def selected_condition(self) -> 'FilterOperation':
        return self.get_filter_condition()

    # Utility Methods
    # ---------------
    @classmethod
    def create_for_field(cls, field_type: FieldType | str = FieldType.NULL, filter_name: str = None, display_name: str = None, parent = None):
        """Create an instance of the appropriate filter widget based on the given FieldType.

        If no widget is registered for the field type, raises a ValueError.
        """
        if not isinstance(field_type, FieldType):
            field_type = FieldType.from_sql(field_type)

        widget_cls = cls.registry.get(field_type, cls)
        return widget_cls(
            filter_name=filter_name,
            display_name=display_name,
            parent=parent
        )

    # Slot Implementations
    # --------------------
    def discard_change(self):
        """Discard changes. Must be implemented in subclasses.
        """
        raise NotImplementedError("Subclasses must implement discard_change")

    def save_change(self):
        """Save changes. Must be implemented in subclasses.
        """
        self.save_state('condition', self.selected_condition.display_name)

    def clear_filter(self):
        """Clear the filter condition. Must be implemented in subclasses.
        """
        self.condition_combo_box.setCurrentText(self.DEFAULT_OPERATION.display_name)
        self.save_state('condition', self.DEFAULT_OPERATION.display_name)

    def get_value(self) -> Any:
        """Get the filter values. Must be implemented in subclasses.
        """
        return self._value
    
    def set_value(self, value: Any):
        """Set the filter values. Must be implemented in subclasses.
        """
        self._value = value
        self._update_button_text()

    def format_label(self, value: List[Any] = '', use_format: bool = True):
        """Apply additional formatting to the text.

        This is a placeholder method intended to be overridden by subclasses 
        to provide specific formatting logic.

        Args:
            text (str): The text to format.

        Returns:
            str: The formatted text.
        """
        text = ', '.join(value) if isinstance(value, list) else value
        # Format the text based on the 'use_format' flag.
        text = self._format_text(text) if use_format else text

        return text

    def check_validity(self) -> bool:
        """Check if the current filter configuration is valid. Base implementation always returns True.
        
        Returns:
            bool: True if valid, False otherwise.
        """
        return True

    # Override Methods
    # ----------------
    def showEvent(self, event):
        """Override the show event to set the focus on the initial widget.
        """
        super().showEvent(event)

        if self._initial_focus_widget:
            self._initial_focus_widget.setFocus()

    def hideEvent(self, event):
        """Override the hide event to discard changes if not applying the filter.
        """
        if not self._is_filter_applied:
            self.discard_change()
        else:
            # Reset the flag if the widget is hidden after applying the filter
            self._is_filter_applied = False
        
        super().hideEvent(event)

    def setIcon(self, icon: QtGui.QIcon):
        """Set the icon for the filter widget and button.
        """
        self.setWindowIcon(icon)


class DateFilterWidget(FilterWidget):

    SUPPORTED_TYPE = FieldType.DATE
    DEFAULT_OPERATION = FilterOperation.BETWEEN

    # Define a mapping from FilterOperation to label formats
    FORMATTER_MAPPING: Dict['FilterOperation', str] = {
        FilterOperation.BEFORE: "Before {0}",
        FilterOperation.AFTER: "After {0}",
        FilterOperation.BETWEEN: "{0} ↔ {1}",
        FilterOperation.NOT_BETWEEN: "Not in {0} ↔ {1}",
        FilterOperation.EQ: "Equals {0}",
        FilterOperation.NEQ: "Does Not Equal {0}",
    }

    def __init__(self, filter_name: str = '', display_name: str = None, parent: QtWidgets.QWidget = None):
        super().__init__(filter_name=filter_name, display_name=display_name, parent=parent)

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        self.start_date, self.end_date = None, None

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setIcon(TablerQIcon.calendar)

        # Create widgets and layouts here
        self.calendar = RangeCalendarWidget(self)
        self.relative_date_combo_box = QtWidgets.QComboBox(self)
        for date_range in DateRange:
            self.relative_date_combo_box.addItem(str(date_range), date_range)

        # Set the layout for the widget
        self.widget_layout.addWidget(self.relative_date_combo_box)
        self.widget_layout.addWidget(self.calendar)

        self.set_initial_focus_widget(self.relative_date_combo_box)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect signals to slots
        self.relative_date_combo_box.currentIndexChanged.connect(self.select_relative_date_range)
        self.calendar.range_selected.connect(self.select_absolute_date_range)
        self.condition_combo_box.currentIndexChanged.connect(self._update_selection_mode)

    def _update_selection_mode(self, index):
        """Update the selection mode based on the selected condition.
        """
        if self.selected_condition.num_values == 1:
            self.calendar.set_selection_mode(CalendarSelectionMode.SINGLE)
        else:
            self.calendar.set_selection_mode(CalendarSelectionMode.RANGE)

    # Slot Implementations
    # --------------------
    def discard_change(self):
        """Discard changes and revert to the saved state.
        """
        current_index = self.load_state('current_index', 0)
        self.start_date, self.end_date = self.load_state('date_range', (None, None))
        filter_label = self.load_state('filter_label', '')

        self.relative_date_combo_box.setCurrentIndex(current_index)

        if current_index == 0:
            self.relative_date_combo_box.setItemText(0, filter_label)
        self.calendar.select_date_range(self.start_date, self.end_date)

    def save_change(self):
        """Save the current selection as the new state.
        """
        super().save_change()
        current_index = self.relative_date_combo_box.currentIndex()
        filter_label = self.relative_date_combo_box.currentText()
        
        date_range = self.calendar.get_date_range()
        self.start_date, self.end_date = date_range

        self.save_state('current_index', current_index)
        self.save_state('date_range', date_range)
        self.save_state('filter_label', filter_label)

    def get_value(self) -> List['datetime.date']:
        """Retrieve the current date values based on the selected condition.

        Returns:
            A list containing:
                - For single-date conditions (BEFORE, AFTER): [date]
                - For range conditions (BETWEEN, NOT_BETWEEN): [start_date, end_date]
                - For no-date conditions (IS_NULL, IS_NOT_NULL): []
        """
        py_start_date = self.start_date.toPyDate() if self.start_date else None
        py_end_date = self.end_date.toPyDate() if self.end_date else py_start_date

        if self.selected_condition.num_values == 2:
            return [py_start_date, py_end_date]
        elif self.selected_condition.num_values == 1:
            return py_start_date or py_end_date
        else:
            return

    def format_label(self, values: List['datetime.date'] | 'datetime.date'):
        # Retrieve the format string based on the selected condition
        format_str = self.FORMATTER_MAPPING.get(self.selected_condition, self.selected_condition.display_name)
        if not self.is_active:
            text = ''
        if self.selected_condition.num_values > 1:
            values = [value.isoformat() for value in values]
            text = format_str.format(*values)
        else:
            text = format_str.format(values.isoformat())

        # Update the label using the superclass method
        return super().format_label(text)

    def check_validity(self):
        return (
            self.relative_date_combo_box.currentText() != DateRange.SELECTED_DATE_RANGE.value or
            self.relative_date_combo_box.itemData(0) != DateRange.SELECTED_DATE_RANGE
        )

    def clear_filter(self):
        """Clear the selected date range and reset the relative date selector.
        """
        super().clear_filter()
        # Reset the relative date selector to its initial state
        self.relative_date_combo_box.setCurrentIndex(0)
        self.relative_date_combo_box.setItemText(0, str(DateRange.SELECTED_DATE_RANGE))

        # Clear any selections made in the calendar
        self.start_date, self.end_date = None, None
        self.calendar.clear()

    def select_relative_date_range(self, index):
        """Select a relative date range based on the index.
        """
        # Reset the first item text if a predefined relative date is selected
        if index > 0:
            self.relative_date_combo_box.setItemText(0, str(DateRange.SELECTED_DATE_RANGE))

        date_range: DateRange = self.relative_date_combo_box.currentData()
        start_date, end_date = date_range.get_date_range()
        self.calendar.select_date_range(start_date, end_date)

    def select_absolute_date_range(self, start_date, end_date):
        """Select an absolute date range based on the provided dates.
        """
        # Check if end_date is None (single date selection)
        if end_date is None or start_date == end_date:
            formatted_range = start_date.toString(QtCore.Qt.DateFormat.ISODate)
        else:
            formatted_range = f"{start_date.toString(QtCore.Qt.DateFormat.ISODate)} to {end_date.toString(QtCore.Qt.DateFormat.ISODate)}"

        # Update the first item in the relative date selector
        self.relative_date_combo_box.setItemText(0, formatted_range)

        # Set the first item as the current item
        self.relative_date_combo_box.setCurrentIndex(0)


# NOTE: WIP
class DateTimeFilterWidget(DateFilterWidget):

    SUPPORTED_TYPE = FieldType.DATETIME

    TIME_FORMAT = "HH:mm:ss"

    def __init__(self, filter_name: str = '', display_name: str = None, parent: QtWidgets.QWidget = None):
        super().__init__(filter_name=filter_name, display_name=display_name, parent=parent)

        # Additional setup for time range filtering
        self.__init_ui()

    def __init_ui(self):
        """Initialize UI elements for handling both date and time."""
        self.setIcon(TablerQIcon.calendar_clock)

        # Extend existing widgets to include time components
        self.time_layout = QtWidgets.QHBoxLayout()
        self.widget_layout.addLayout(self.time_layout)

        self.time_start_edit = QtWidgets.QTimeEdit(self, displayFormat=self.TIME_FORMAT)
        self.time_end_edit = QtWidgets.QTimeEdit(self, displayFormat=self.TIME_FORMAT)

        self.time_start_label = widgets.LabelEmbedderWidget(self.time_start_edit, 'Start Time', self)
        self.time_end_label = widgets.LabelEmbedderWidget(self.time_end_edit, 'End Time', self)

        # Add the time widgets to the UI layout
        self.time_layout.addWidget(self.time_start_label)
        self.time_layout.addWidget(self.time_end_label)

    def save_change(self):
        """Save the date and time range."""
        super().save_change()  # Call the base method to save date-related data
        
        # Save time-specific data
        start_time = self.time_start_edit.time().toString(QtCore.Qt.DateFormat.ISODate)
        end_time = self.time_end_edit.time().toString(QtCore.Qt.DateFormat.ISODate)

        # Emit signals or store state with combined date and time information
        self.save_state('start_time', start_time)
        self.save_state('end_time', end_time)
        # Combine date and time for emitting
        # TODO: Implement `get_value` and `format_label`
        ...

    def discard_change(self):
        """Revert changes for both date and time."""
        super().discard_change()  # Call the base method to discard date changes
        self.time_start_edit.setTime(self.load_state('start_time', QtCore.QTime()))
        self.time_end_edit.setTime(self.load_state('end_time', QtCore.QTime()))

# NOTE: WIP
class TextFilterWidget(FilterWidget):
    """A widget for filtering text data with various SQL-like operators.

    UI Wireframe:
        +----------------------------------+
        | Condition: [ Contains  v]        |
        | +------------------------------+ |
        | |  [ Enter text to filter... ] | |
        | +------------------------------+ |
        |                                  |
        | [ Clear ]             [ Apply ]  |
        +----------------------------------+
    """

    SUPPORTED_TYPE = FieldType.TEXT
    DEFAULT_OPERATION = FilterOperation.CONTAINS

    def __init__(self, filter_name: str = "Text Filter", display_name: str = None, parent: QtWidgets.QWidget = None):
        super().__init__(filter_name=filter_name, display_name=display_name, parent=parent)

        # Initialize setup specific to TextFilterWidget
        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        """Initialize the UI elements specific to the TextFilterWidget.
        """
        self.setIcon(TablerQIcon.letter_case)

        # Add a line edit for entering the text to filter
        self.text_edit = LineEdit(self, placeholderText="Enter text to filter...")

        # Add the line edit to the specific content area of the widget
        self.widget_layout.addWidget(self.text_edit)

        # Set the initial focus widget to the condition combo box
        self.set_initial_focus_widget(self.text_edit)

    def __init_signal_connections(self):
        """Initialize signal-slot connections for TextFilterWidget.
        """
        self.condition_combo_box.currentIndexChanged.connect(self.update_ui_for_condition)

    # Slot Implementations
    # --------------------
    def discard_change(self):
        """Revert the widget to its previously saved state.
        """
        saved_condition = self.load_state('condition', self.DEFAULT_OPERATION.display_name)
        self.condition_combo_box.setCurrentText(saved_condition)

        self.text_edit.setText(self.load_state('text', ""))

    def save_change(self):
        """Save the current state of the filter settings.
        """
        super().save_change()
        self.save_state('text', self.text_edit.text())

    def get_value(self):
        if not self.selected_condition.requires_value():
            return
        
        return self.text_edit.text()

    def clear_filter(self):
        """Clear all filter settings and reset to the default state.
        """
        super().clear_filter()
        self.text_edit.clear()
        self.save_state('text', '')

    def update_ui_for_condition(self, index: int):
        """Update UI components based on the selected condition.
        """
        # If the condition is 'Is Null' or 'Is Not Null', hide the text input
        if not self.selected_condition.requires_value():
            self.text_edit.hide()
        else:
            self.text_edit.show()

    def format_label(self, value: str) -> str:
        """Format the display label based on current inputs.
        """
        if not self.selected_condition.requires_value():
            text = self.selected_condition.display_name
        elif value:
            text = f"{self.selected_condition.display_name}: {value}"
        text = self.selected_condition.display_name

        return super().format_label(text)

    def check_validity(self):
        """Check if the filter is active based on current values.
        """
        return self.selected_condition.requires_value() or bool(self.text_edit.text())

class FilterEntryEdit(QtWidgets.QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.tabler_icon = TablerQIcon(opacity=0.6)

        self.setProperty('has-placeholder', True)
        self.addAction(self.tabler_icon.layout_grid_add, QtWidgets.QLineEdit.ActionPosition.LeadingPosition)

        # Set placeholder text and tooltip for the line edit
        self.setPlaceholderText("Press 'Enter' to add filters (separate with a comma, line break, or '|')")
        self.setToolTip('Enter filter items, separated by a comma, newline, or pipe. Press Enter to apply.')

        # Setup the completer (assuming a completer class is defined)
        completer = bb.utils.MatchContainsCompleter(self)
        self.setCompleter(completer)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        self.textChanged.connect(self.update_style)

    @staticmethod
    def split_keywords(input_string):
        """Regular expression that splits on | or , or spaces not within quotes.
        
        It captures quoted strings or sequences of characters outside quotes not including delimiters.
        """
        quoted_terms, unquoted_terms = bb.utils.TextExtraction.extract_terms(input_string)
        return quoted_terms + unquoted_terms

    def texts(self) -> List[str]:
        """Get the list of keywords from the line edit."""
        return self.split_keywords(self.text())

    def update_style(self):
        """Update the style of the line edit."""
        self.style().unpolish(self)
        self.style().polish(self)

    def setModel(self, model):
        """Set the model for the completer."""
        self.model = model
        self.proxy_model = bb.utils.FlatProxyModel(self.model, self)
        # Set the model for the completer
        self.completer().setModel(self.proxy_model)


class MultiSelectFilterWidget(FilterWidget):
    """A widget representing a filter with a checkable tree.
    """

    SUPPORTED_TYPE = FieldType.ENUM
    DEFAULT_OPERATION = FilterOperation.IN

    def __init__(self, filter_name: str = '', display_name: str = None, parent: QtWidgets.QWidget = None):
        super().__init__(filter_name=filter_name, display_name=display_name, parent=parent)

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        # Attributes
        # ----------
        ...

        # Private Attributes
        # ------------------
        self._custom_tags_item = None

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Create Layouts
        # --------------
        # Set the layout for the widget
        self.tag_layout = QtWidgets.QHBoxLayout()
        self.widget_layout.addLayout(self.tag_layout)

        # Create Widgets
        # --------------
        # Create widgets and layouts
        self.setIcon(TablerQIcon.list_check)

        # Tree view
        self.tree_view = widgets.MomentumScrollTreeView(
            self, headerHidden=True,
            rootIsDecorated = False
        )
        self.proxy_model = bb.utils.CheckableProxyModel()
        self.tree_view.setModel(self.proxy_model)

        self.filter_entry_edit = FilterEntryEdit(self)
        self.filter_entry_edit.setModel(self.tree_view.model())

        self.tag_list_view = widgets.TagListView(self, show_only_checked=True)
        self.tag_list_view.setModel(self.tree_view.model())

        # Copy button
        # TODO: Implement copy_button as reusable class
        self.copy_button = QtWidgets.QPushButton(self.tabler_icon.copy, '', self)

        # Add Widgets to Layouts
        # ----------------------
        self.tag_layout.addWidget(self.tag_list_view)
        self.tag_layout.addWidget(self.copy_button)
        self.widget_layout.addWidget(self.filter_entry_edit)
        self.widget_layout.addWidget(self.tree_view)

        self.set_initial_focus_widget(self.filter_entry_edit)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Input text field
        self.filter_entry_edit.editingFinished.connect(self.update_checked_state)
        self.filter_entry_edit.completer().activated.connect(self.update_checked_state)

        self.copy_button.clicked.connect(self.copy_data_to_clipboard)
        self.tag_list_view.tag_changed.connect(self.update_copy_button_state)

    def update_copy_button_state(self):
        """Update the state of the copy button based on the number of tags in the tag widget.
        """
        tag_count = self.tag_list_view.get_tags_count()
        self.copy_button.setEnabled(bool(tag_count))

        num_item_str = str(tag_count) if tag_count else ''
        self.copy_button.setText(num_item_str)

    def copy_data_to_clipboard(self):
        """Copy the tags to the clipboard.
        """
        full_text = ', '.join(self.tag_list_view.get_tags())

        clipboard = QtWidgets.qApp.clipboard()
        clipboard.setText(full_text)

        # Show tooltip message
        self.show_tool_tip(f'Copied:\n{full_text}', 5000)

    def show_tool_tip(self, text: str, msc_show_time: int = 1000):
        """Show a tooltip message for the given text.
        """
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), text, self, QtCore.QRect(), msc_show_time)

    def update_checked_state(self):
        """Update the checked state of the items based on the text in the line edit.
        """
        self.set_check_items(self.filter_entry_edit.texts())
        self.filter_entry_edit.clear()

    def add_new_tag_to_tree(self, tag_name: str):
        """Add a new tag to the tree, potentially in a new group.
        """
        # Check if the 'Custom Tags' group exists
        if not self._custom_tags_item:
            self._custom_tags_item = self.add_item('Custom Tags')

        # Add the new tag as a child of the 'Custom Tags' group
        new_tag_item = self.add_item(tag_name, self._custom_tags_item)

        self.tree_view.expandAll()
        return new_tag_item

    def setModel(self, model: QtCore.QAbstractItemModel):
        """Set the model for the widget.

        Args:
            model (QtCore.QAbstractItemModel): The model to set.
        """
        self.proxy_model.setSourceModel(model)
        self.filter_entry_edit.setModel(self.proxy_model)

        self.tag_list_view.setModel(self.proxy_model)
        self.tree_view.setModel(self.proxy_model)
        self.tree_view.expandAll()

    def set_check_items(self, keywords: List[str], checked_state: QtCore.Qt.CheckState = QtCore.Qt.CheckState.Checked):
        """Set the checked state for items matching the keywords.
        """
        filter_func = partial(self.filter_keywords, keywords)
        model_indexes = bb.utils.TreeUtil.get_model_indexes(self.tree_view.model(), filter_func=filter_func)

        for model_index in model_indexes:
            self.tree_view.model().setData(model_index, checked_state, QtCore.Qt.ItemDataRole.CheckStateRole)

        # TODO: Handle to add new inputs
        # # Check if the tag is a wildcard
        # is_wildcard = '*' in keyword

        # if not matching_items and not is_wildcard:
        #     # If no matching items and tag is not a wildcard, add as a new tag
        #     new_tag_item = self.add_new_tag_to_tree(keyword)
        #     matching_items.append(new_tag_item)

    # TODO: Add support when when add parent, children should be filtered
    @staticmethod
    def filter_keywords(keywords: List[str], index: QtCore.QModelIndex):
        """Filter items based on the provided keywords.
        """
        if not index.isValid():
            return False

        text = index.data()
        # Check each keyword against the text using fnmatch which supports wildcards like *
        return any(fnmatch.fnmatch(text, pattern) for pattern in keywords)

    def check_validity(self):
        """Check if the filter is active.
        """
        return bool(self.tag_list_view.get_tags())

    def restore_checked_state(self, checked_state_dict: dict, parent_index: QtCore.QModelIndex = QtCore.QModelIndex()):
        """Restore the checked state of items from the provided dictionary.
        """
        model_indexes = bb.utils.TreeUtil.get_model_indexes(self.tree_view.model(), parent_index)
        model_index_to_check_state = dict()

        is_proxy_model = isinstance(self.tree_view.model(), bb.utils.CheckableProxyModel)

        for model_index in model_indexes:
            text = model_index.data()
            checked_state = checked_state_dict.get(text, QtCore.Qt.CheckState.Unchecked)
            if is_proxy_model:
                model_index_to_check_state[model_index] = checked_state
            else:
                self.tree_view.model().setData(model_index, checked_state, QtCore.Qt.ItemDataRole.CheckStateRole)

        if is_proxy_model:
            self.tree_view.model().set_check_states(model_index_to_check_state)

    def get_checked_state_dict(self, parent_index: QtCore.QModelIndex = QtCore.QModelIndex()):
        """Return a dictionary of the checked state for each item.
        """
        return {
            model_index.data(): model_index.data(QtCore.Qt.ItemDataRole.CheckStateRole)
            for model_index in bb.utils.TreeUtil.get_model_indexes(self.tree_view.model(), parent_index)
        }

    def clear_filter(self):
        """Clear all selections in the tree widget.
        """
        super().clear_filter()

        # Uncheck all items in the tree widget
        self.uncheck_all()

        # Clear the line edit
        self.filter_entry_edit.clear()

    def uncheck_all(self, parent_index: QtCore.QModelIndex = QtCore.QModelIndex()):
        """Recursively unchecks all child indexes.
        """
        model_indexes = bb.utils.TreeUtil.get_model_indexes(self.tree_view.model(), parent_index, is_only_checked=True)

        for model_index in model_indexes:
            self.tree_view.model().setData(model_index, QtCore.Qt.CheckState.Unchecked, QtCore.Qt.ItemDataRole.CheckStateRole)

    def add_items(self, item_names: Union[Dict[str, List[str]], List[str]]):
        """Add items to the tree widget.

        Args:
            item_names (Union[Dict[str, List[str]], List[str]]): If a dictionary is provided, it represents parent-child relationships where keys are parent item names and values are lists of child item names. If a list is provided, it contains item names to be added at the root level.
        """
        if isinstance(self.tree_view.model(), bb.utils.CheckableProxyModel):
            self.tree_view_model = QtGui.QStandardItemModel()
            self.tree_view.setModel(self.tree_view_model)
            self.filter_entry_edit.setModel(self.tree_view_model)
            self.tag_list_view.setModel(self.tree_view_model)

        if isinstance(item_names, dict):
            self._add_items_from_dict(item_names)
        elif isinstance(item_names, list):
            self._add_items_from_list(item_names)
        else:
            raise ValueError("Invalid type for item_names. Expected a list or a dictionary.")

        self.tree_view.expandAll()

    # def add_item(self, item_label: str, parent: Optional[QtWidgets.QTreeWidgetItem] = None):
    #     """Adds a single item to the tree widget.

    #     Args:
    #         item_label (str): The label for the tree item.
    #         parent (QtWidgets.QTreeWidgetItem, optional): The parent item for this item. Defaults to None, in which case the item is added at the root level.

    #     Returns:
    #         QtWidgets.QTreeWidgetItem: The created tree item.
    #     """
    #     parent = parent or self.tree_view.invisibleRootItem()
    #     tree_item = QtWidgets.QTreeWidgetItem(parent, [item_label])
    #     tree_item.setFlags(tree_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsAutoTristate)
    #     tree_item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)

    #     return tree_item
    
    # Implement add_item for self.tree_view
    # TODO: Implement appendRow for CheckableProxyModel
    def add_item(self, item_label: str, parent_item: QtGui.QStandardItem = None):
        """Add a single item to the tree widget.
        """ 
        # Add items to the model
        parent_item = parent_item or self.tree_view_model
        item = QtGui.QStandardItem(str(item_label))
        item.setCheckable(True)
        item.setEditable(False)
        parent_item.appendRow(item)
        return item

    def _add_items_from_dict(self, item_dict: Dict[str, List[str]]):
        """Add items to the tree widget based on a dictionary of parent-child relationships.

        Args:
            item_dict (Dict[str, List[str]]): A dictionary where keys are parent item names and values are lists of child item names.
        """
        for parent_name, child_names in item_dict.items():
            parent_item = self.add_item(parent_name)
            self._add_items_from_list(child_names, parent_item)

    def _add_items_from_list(self, item_list: List[str], parent_item: Optional[QtGui.QStandardItem] = None):
        """Add items to the tree widget at the root level from a list of item names.

        Args:
            item_list (List[str]): A list of item names to be added at the root level.
            parent_item (Optional[QtGui.QStandardItem]): The parent item for the items. Defaults to None.
        """
        for item_name in item_list:
            self.add_item(item_name, parent_item)

    # Slot Implementations
    # --------------------
    def discard_change(self):
        """Discard changes and revert to the saved state.
        """
        checked_state_dict = self.load_state('checked_state', {})
        self.restore_checked_state(checked_state_dict)

    def save_change(self):
        """Save the changes and emit the filter data.
        """
        super().save_change()

        checked_state_dict = self.get_checked_state_dict()
        self.save_state('checked_state', checked_state_dict)

    def get_value(self) -> List[str]:
        return self.tag_list_view.get_tags()

    def set_value(self, values: List[str]):
        """Set the filter items.
        """
        # Uncheck all items in the tree widget and clear the line edit
        self.uncheck_all()
        self.filter_entry_edit.clear()
        # Set new
        self.set_check_items(values)

        self.tree_view.expandAll()
        self._update_button_text()


class FileTypeFilterWidget(FilterWidget):

    def __init__(self, filter_name: str = '', display_name: str = None, parent: QtWidgets.QWidget = None):
        super().__init__(filter_name=filter_name, display_name=display_name, parent=parent)

        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setIcon(TablerQIcon.file)

        # Custom file type input
        self.custom_input = QtWidgets.QLineEdit()
        self.custom_input.setPlaceholderText("Enter custom file types (e.g., txt)")
        self.custom_input.setProperty('has-placeholder', True)
        self.custom_input.addAction(self.tabler_icon.file_plus, QtWidgets.QLineEdit.ActionPosition.LeadingPosition)
        self.custom_input.textChanged.connect(self.update_style)
        self.widget_layout.addWidget(self.custom_input)

        self.set_initial_focus_widget(self.custom_input)

        # Preset file type groups with tooltips and extensions
        self.file_type_groups = {
            "Image Sequences": (["exr", "dpx", "jpg", "jpeg"], "Image sequence formats like EXR, DPX"),
            "Video Files": (["mp4", "avi", "mkv", 'mov'], "Video formats like MP4, AVI, MKV"),
            "Audio Files": (["mp3", "wav", "aac"], "Audio formats like MP3, WAV, AAC"),
            "Image Files": (["jpg", "png", "gif"], "Image formats like JPG, PNG, GIF"),
            "Document Files": (["pdf", "docx", "txt"], "Document formats like PDF, DOCX, TXT"),
            "3D Model Files": (["obj", "fbx", "stl", "blend"], "3D model formats like OBJ, FBX, STL, BLEND"),
            "Rig Files": (["bvh", "skel"], "Rig formats like BVH, SKEL"),
        }

        self.checkboxes = {}
        for group, (extensions, tooltip) in self.file_type_groups.items():
            checkbox = QtWidgets.QCheckBox(group)
            checkbox.setToolTip(tooltip)
            checkbox.extensions = extensions  # Store the extensions with the checkbox
            self.widget_layout.addWidget(checkbox)
            self.checkboxes[group] = checkbox

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        ...

    def check_validity(self):
        """Check if the filter is active (any file type is selected or custom types are specified).
        """
        # Check if any checkbox is checked
        if any(checkbox.isChecked() for checkbox in self.checkboxes.values()):
            return True

        # Check if there is any text in the custom input
        if self.custom_input.text().strip():
            return True

        # If none of the above conditions are met, return False
        return False

    def get_value(self):
        """Get the selected file extensions.
        """
        selected_extensions = list()
        
        for checkbox in self.checkboxes.values():
            if not checkbox.isChecked():
                continue

            selected_extensions.extend(checkbox.extensions)

        custom_types = self.get_custom_types()
        selected_extensions.extend(custom_types)

        return list(set(selected_extensions))

    def get_custom_types(self):
        """Get the custom file types from the input field.
        """
        custom_types = self.custom_input.text().strip().split(',')
        custom_types = [ext.strip() for ext in custom_types if ext.strip()]
        return custom_types

    def get_checked_state_dict(self):
        """Return a dictionary of the checked state for each checkbox.
        """
        return {
            checkbox.text(): checkbox.isChecked()
            for checkbox in self.checkboxes.values()
        }

    def uncheck_all(self):
        """Uncheck all checkboxes.
        """
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)

    def clear_filter(self):
        """Clear all selections and resets the filter to its initial state.
        """
        super().clear_filter()

        # Uncheck all checkboxes
        self.uncheck_all()
        # Clear the custom input field
        self.custom_input.clear()

    # Slot Implementations
    # --------------------
    def save_change(self):
        """Save the changes and emit the filter data.
        """
        super().save_change()

        # Save and add custom extensions
        self.save_state('custom_input', self.get_custom_types())
        self.save_state('checked_state', self.get_checked_state_dict())

    def discard_change(self):
        """Revert any changes made.
        """
        custom_input = self.load_state('custom_input', [])
        checked_state_dict = self.load_state('checked_state', {})

        if not checked_state_dict:
            self.uncheck_all()

        # Restore the state of checkboxes from the saved state
        for checkbox_text, checked in checked_state_dict.items():
            self.checkboxes[checkbox_text].setChecked(checked)

        # Restore the text of the custom input from the saved state
        custom_input_text = ', '.join(custom_input)
        self.custom_input.setText(custom_input_text)


class NumericFilterWidget(FilterWidget):
    """A widget for filtering numeric data with dynamic two-way condition handling.

    UI Wireframe:
        +----------------------------------+
        | Condition: [ Equal  v]           |
        | +------------------------------+ |
        | |  [ 0.0 ]    ...   [ ... ]    | |
        | +------------------------------+ |
        |                                  |
        | [ Clear ]             [ Apply ]  |
        +----------------------------------+
    """

    SUPPORTED_TYPE = FieldType.NUMERIC

    FORMATTER_MAPPING: Dict[FilterOperation, str] = {
        FilterOperation.BETWEEN: "{0} ↔ {1}",
        FilterOperation.NOT_BETWEEN: "Not in {0} ↔ {1}",
        FilterOperation.GT: "> {0}",
        FilterOperation.LT: "< {0}",
        FilterOperation.EQ: "= {0}",
        FilterOperation.NEQ: "≠ {0}",
    }

    def __init__(self, filter_name: str = "Numeric Filter", display_name: str = None, parent: QtWidgets.QWidget = None):
        super().__init__(filter_name=filter_name, display_name=display_name, parent=parent)

        # Initialize setup specific to NumericFilterWidget
        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        """Initialize the UI elements specific to the NumericFilterWidget.
        """
        self.setIcon(TablerQIcon.filter)  # Set an appropriate icon for numeric filter

        # Create Layouts
        # --------------
        self.value_layout = QtWidgets.QHBoxLayout()
        self.widget_layout.addLayout(self.value_layout)

        # Create Widgets
        # --------------
        # Add line edits for entering numeric values with placeholders
        self.lower_value_edit = LineEdit(self, placeholderText="Lower limit...", validator=QtGui.QDoubleValidator())
        self.lower_value_label = widgets.LabelEmbedderWidget(self.lower_value_edit, 'From')
        self.upper_value_edit = LineEdit(self, placeholderText="Upper limit...", validator=QtGui.QDoubleValidator())
        self.upper_value_label = widgets.LabelEmbedderWidget(self.upper_value_edit, 'To')

        # Add Widgets to Layouts
        # ----------------------
        # Add the line edits to the specific content area of the widget
        self.value_layout.addWidget(self.lower_value_label)
        self.value_layout.addWidget(QtWidgets.QLabel("↔", self))
        self.value_layout.addWidget(self.upper_value_label)

        # Set the initial focus widget to the condition combo box
        self.set_initial_focus_widget(self.lower_value_edit)

    def __init_signal_connections(self):
        """Initialize signal-slot connections for NumericFilterWidget.
        """
        self.condition_combo_box.currentIndexChanged.connect(self.update_ui_for_condition)
        self.lower_value_edit.textChanged.connect(self.handle_input_change)
        self.upper_value_edit.textChanged.connect(self.handle_input_change)

    # Slot Implementations
    # --------------------
    def discard_change(self):
        """Revert the widget to its previously saved state.
        """
        saved_condition = self.load_state('condition', FilterOperation.EQ.display_name)
        self.condition_combo_box.setCurrentText(saved_condition)

        self.lower_value_edit.setText(self.load_state('lower_value', ""))
        self.upper_value_edit.setText(self.load_state('upper_value', ""))

    def save_change(self):
        """Save the current state of the filter settings.
        """
        super().save_change()
        self.save_state('lower_value', self.lower_value_edit.text())
        self.save_state('upper_value', self.upper_value_edit.text())

    def get_value(self) -> Optional[Tuple[float, ...]]:
        if not self.selected_condition.requires_value():
            return
        lower_value = self.lower_value_edit.text()
        upper_value = self.upper_value_edit.text()

        if self.selected_condition.num_values == 2:
            if lower_value and upper_value:
                return sorted([float(lower_value), float(upper_value)])
            else:
                return
        elif self.selected_condition.num_values == 1:
            value = lower_value or upper_value
            if value:
                return float(value)
            else:
                return

    def clear_filter(self):
        """Clear all filter settings and reset to the default state.
        """
        super().clear_filter()
        self.lower_value_edit.clear()
        self.upper_value_edit.clear()

    def update_ui_for_condition(self, index: int):
        """Update UI components based on the selected condition.
        """
        lower_value = self.lower_value_edit.text()
        upper_value = self.upper_value_edit.text()
        if self.selected_condition == FilterOperation.GT:
            if lower_value:
                self.upper_value_edit.clear()
            elif upper_value:
                self.lower_value_edit.setText(upper_value)
                self.upper_value_edit.clear()
        elif self.selected_condition == FilterOperation.LT:
            if upper_value:
                self.lower_value_edit.clear()
            elif lower_value:
                self.upper_value_edit.setText(lower_value)
                self.lower_value_edit.clear()
        elif self.selected_condition == FilterOperation.EQ:
            if lower_value:
                self.upper_value_edit.setText(lower_value)
            elif upper_value:
                self.lower_value_edit.setText(upper_value)

    def handle_input_change(self):
        """Adjust the condition dynamically based on user input.
        """
        lower_value = self.lower_value_edit.text()
        upper_value = self.upper_value_edit.text()

        if lower_value and upper_value:
            if lower_value == upper_value:
                self.condition_combo_box.setCurrentText(FilterOperation.EQ.display_name)
            else:
                self.condition_combo_box.setCurrentText(FilterOperation.BETWEEN.display_name)
        elif lower_value:
            self.condition_combo_box.setCurrentText(FilterOperation.GT.display_name)
        elif upper_value:
            self.condition_combo_box.setCurrentText(FilterOperation.LT.display_name)

    def format_label(self, values: Tuple[float, ...]) -> None:
        """Format the display label based on current inputs.
        """
        # Retrieve the format string based on the selected condition
        format_str = self.FORMATTER_MAPPING.get(self.selected_condition, self.selected_condition.display_name)
        if self.selected_condition.is_multi_value():
            text = format_str.format(*values)
        else:
            text = format_str.format(values)

        # Update the label using the superclass method
        return super().format_label(text)

    def check_validity(self):
        """Check if the filter is active based on current values.
        """
        return self.selected_condition.requires_value() or bool(self.lower_value_edit.text() or self.upper_value_edit.text())


class BooleanFilterWidget(FilterWidget):
    """A widget for filtering boolean data with options for True, False, NULL, and NOT NULL.

    UI Wireframe:
        +----------------------------------+
        | Condition: [ Equals    v]        |
        |                                  |
        |     [ False ]   [ True ]         | <-- only visible when condition is Equals/Not Equals
        |                                  |
        | [ Clear ]             [ Apply ]  |
        +----------------------------------+
    """

    SUPPORTED_TYPE = FieldType.BOOLEAN
    DEFAULT_OPERATION = FilterOperation.EQ

    def __init__(self, filter_name: str = "Boolean Filter", display_name: str = None, parent: QtWidgets.QWidget = None):
        super().__init__(filter_name=filter_name, display_name=display_name, parent=parent)

        # Initialize setup
        self.__init_ui()

    def __init_ui(self):
        """Initialize the UI elements specific to the BooleanFilterWidget."""
        self.setIcon(TablerQIcon.checkbox)

        # Create a widget for the boolean value selection.
        self.value_widget = QtWidgets.QWidget()
        value_layout = QtWidgets.QHBoxLayout(self.value_widget)
        # Instead of radio buttons, use checkable push buttons.
        self.btn_false = QtWidgets.QPushButton("False", checkable=True)
        self.btn_true = QtWidgets.QPushButton("True", checkable=True)

        value_layout.addWidget(self.btn_false)
        value_layout.addWidget(self.btn_true)

        # Group the buttons so that only one is checked at a time.
        self.boolean_group = QtWidgets.QButtonGroup(self)
        self.boolean_group.setExclusive(True)
        self.boolean_group.addButton(self.btn_false, id=0)
        self.boolean_group.addButton(self.btn_true, id=1)
    
        # Set default selection.
        self.btn_true.setChecked(True)
    
        self.widget_layout.addWidget(self.value_widget)
    
        # Set initial focus.
        self.set_initial_focus_widget(self.condition_combo_box)
    
        # Initialize the value field visibility based on the default condition.
        self.condition_combo_box.currentIndexChanged.connect(self.on_condition_changed)
        # self.on_condition_changed()
    
    def on_condition_changed(self):
        # When condition is EQ or NEQ, show the boolean value widget; otherwise, hide it.
        if self.selected_condition.requires_value():
            self.value_widget.show()
        else:
            self.value_widget.hide()
    
    # Slot implementations.
    def discard_change(self):
        """Revert the widget to its previously saved state.
        """
        saved_condition = self.load_state('condition', FilterOperation.EQ.display_name)
        self.condition_combo_box.setCurrentText(saved_condition)

        # Load the saved boolean value.
        saved_bool = self.load_state('value', True)
        if saved_bool:
            self.btn_true.setChecked(True)
        else:
            self.btn_false.setChecked(True)
    
    def save_change(self):
        """Save the current state of the filter settings."""
        super().save_change()
        # Save the boolean value only if the condition requires it.
        if self.selected_condition.requires_value():
            # The button group's checked id: 1 for True, 0 for False.
            selected_bool = bool(self.boolean_group.checkedId())
            self.save_state('value', selected_bool)
        else:
            self.save_state('value', None)

    def format_label(self, _values=None):
        # Format a label based on the condition and (if applicable) the boolean value.
        if self.selected_condition.requires_value():
            selected_bool = "True" if self.boolean_group.checkedId() == 1 else "False"
            label_text = f"{self.display_name}: {self.selected_condition.display_name} {selected_bool}"
        else:
            label_text = f"{self.display_name}: {self.selected_condition.display_name}"
        return label_text
    
    def clear_filter(self):
        """Clear the filter settings and reset to the default state."""
        # Reset condition to "Equals" (default) and select True.
        super().clear_filter()
        self.btn_true.setChecked(True)
        self.save_state('value', True)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])

    bb.theme.set_theme(app, 'dark')

    main_window = QtWidgets.QMainWindow()
    main_layout = QtWidgets.QHBoxLayout()

    # sequence_to_shot = {
    #     "100": [
    #         "100_010_001", "100_020_050"
    #     ],
    #     "101": [
    #         "101_022_232", "101_023_200"
    #     ],
    # }
    # shot_filter_widget.add_items(sequence_to_shot)
    # shots = ['102_212_010', '103_202_110']
    # shot_filter_widget.add_items(shots)


    # NOTE: Test set model
    # Creating a QStandardItemModel
    model = QtGui.QStandardItemModel()

    # Defining parent nodes (fruit categories)
    citrus = QtGui.QStandardItem('Citrus Fruits')
    tropical = QtGui.QStandardItem('Tropical Fruits')
    berries = QtGui.QStandardItem('Berries')

    # Adding child nodes to citrus
    citrus.appendRow(QtGui.QStandardItem('Lemon'))
    citrus.appendRow(QtGui.QStandardItem('Orange'))
    citrus.appendRow(QtGui.QStandardItem('Lime'))
    citrus.appendRow(QtGui.QStandardItem('Tangerine'))

    # Adding child nodes to tropical
    tropical.appendRow(QtGui.QStandardItem('Mango'))
    tropical.appendRow(QtGui.QStandardItem('Papaya'))
    tropical.appendRow(QtGui.QStandardItem('Kiwi'))
    tropical.appendRow(QtGui.QStandardItem('Dragon Fruit'))

    # Adding child nodes to berries
    berries.appendRow(QtGui.QStandardItem('Strawberry'))
    berries.appendRow(QtGui.QStandardItem('Raspberry'))
    berries.appendRow(QtGui.QStandardItem('Blackberry'))

    # Adding parent nodes to the model
    model.appendRow(citrus)
    model.appendRow(tropical)
    model.appendRow(berries)

    # Date Filter Setup
    date_filter_widget = DateFilterWidget(filter_name="Date")
    date_filter_widget.activated.connect(print)
    # Date Filter Setup
    date_time_filter_widget = DateTimeFilterWidget(filter_name="Date Time")
    date_time_filter_widget.activated.connect(print)
    # Shot Filter Setup
    shot_filter_widget = MultiSelectFilterWidget(filter_name="Shot")

    # Setting the model for the tree view
    shot_filter_widget.setModel(model)

    shots = ['102_212_010', '103_202_110']
    # shot_filter_widget.add_items(shots)

    shot_filter_widget.activated.connect(print)

    # File Type Filter Setup
    file_type_filter_widget = FileTypeFilterWidget(filter_name="File Type")
    file_type_filter_widget.activated.connect(print)

    is_active_filter_widget = BooleanFilterWidget(filter_name='Is Active')
    is_active_filter_widget.activated.connect(print)

    show_hidden_filter_widget = FilterWidget(filter_name='Show Hidden')
    show_hidden_filter_widget.set_filter_mode(FilterMode.TOGGLE)
    # TODO: ...
    show_hidden_filter_widget.activated.connect(print)

    numeric_filter_widget = NumericFilterWidget(filter_name='Value')
    numeric_filter_widget.activated.connect(print)

    text_filter_widget = TextFilterWidget(filter_name='Name')
    text_filter_widget.activated.connect(print)

    # Filter bar
    filter_bar_widget = FilterBarWidget()
    filter_bar_widget.add_filter_widget(date_filter_widget)
    filter_bar_widget.add_filter_widget(date_time_filter_widget)
    filter_bar_widget.add_filter_widget(shot_filter_widget)
    filter_bar_widget.add_filter_widget(file_type_filter_widget)
    filter_bar_widget.add_filter_widget(is_active_filter_widget)
    filter_bar_widget.add_filter_widget(show_hidden_filter_widget)
    filter_bar_widget.add_filter_widget(numeric_filter_widget)
    filter_bar_widget.add_filter_widget(text_filter_widget)

    # Adding widgets to the layout
    main_layout.addWidget(filter_bar_widget)
    
    main_widget = QtWidgets.QWidget()
    main_widget.setLayout(main_layout)
    main_window.setCentralWidget(main_widget)

    main_window.show()
    app.exec_()
