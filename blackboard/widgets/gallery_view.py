# Type Checking Imports
# ---------------------
from typing import Any, Dict, List, Union, Iterable

# Standard Library Imports
# ------------------------
import sys
import os
import glob
import weakref

# Third Party Imports
# -------------------
from qtpy import QtCore, QtGui, QtWidgets
from tablerqicon import TablerQIcon

# Local Imports
# -------------
from blackboard.widgets.momentum_scroll_widget import MomentumScrollListWidget
from blackboard.widgets.thumbnail_widget import ThumbnailWidget
from blackboard.widgets.graphic_effect import DropShadowEffect
from blackboard.widgets.rule_widget import SortRuleWidget, GroupRuleWidget


# Class Definitions
# -----------------
class CloneWidget(QtCore.QObject):
    """Generic widget cloner that clones any widget, including nested child widgets, and synchronizes properties and signals."""

    def __init__(self, original_widget, parent=None):
        super().__init__(parent)
        self.original_widget = original_widget
        self.cloned_widget = self.clone_widget(original_widget, parent)
        self.connections = []  # Track connections for safe disconnection
        self.synchronize_widgets(self.original_widget, self.cloned_widget)

        # Connect the destroyed signals to clean up connections
        original_widget.destroyed.connect(self.cleanup_connections)
        self.cloned_widget.destroyed.connect(self.cleanup_connections)

    def clone_widget(self, widget, parent):
        """Recursively clone the given widget, including its layout and child widgets."""
        cloned = widget.__class__(parent)  # Create a new instance of the same class
        
        # Copy properties of the widget
        for i in range(widget.metaObject().propertyCount()):
            prop = widget.metaObject().property(i)
            if not prop.isWritable():
                continue

            cloned.setProperty(prop.name(), widget.property(prop.name()))

        # Clone and set the layout if the widget has one
        if widget.layout():
            original_layout = widget.layout()
            cloned_layout = self.clone_layout(original_layout, cloned)

            # Recursively clone child widgets and add to the cloned layout
            self.clone_layout_items(original_layout, cloned_layout, cloned)

        return cloned

    def clone_layout(self, layout, parent):
        """Clone a layout, including its properties (margins, spacing, etc.) without the items."""
        layout_type = type(layout)
        cloned_layout = layout_type(parent)  # Create a new layout of the same type

        # Copy layout properties
        cloned_layout.setContentsMargins(layout.contentsMargins())
        cloned_layout.setSpacing(layout.spacing())
        cloned_layout.setAlignment(layout.alignment())

        return cloned_layout

    def clone_layout_items(self, original_layout, cloned_layout, parent):
        for i in range(original_layout.count()):
            item = original_layout.itemAt(i)
            child = item.widget()

            if child:
                cloned_child = self.clone_widget(child, parent)
                cloned_layout.addWidget(cloned_child)
            elif item.spacerItem():
                spacer = item.spacerItem()
                cloned_spacer = QtWidgets.QSpacerItem(
                    spacer.sizeHint().width(), spacer.sizeHint().height(),
                    spacer.expandingDirections() & QtCore.Qt.Orientation.Horizontal,
                    spacer.expandingDirections() & QtCore.Qt.Orientation.Vertical)
                cloned_layout.addItem(cloned_spacer)
            elif item.layout():
                nested_layout = item.layout()
                cloned_nested_layout = self.clone_layout(nested_layout)
                self.clone_layout_items(nested_layout, cloned_nested_layout, parent)
                cloned_layout.addLayout(cloned_nested_layout)

    def synchronize_widgets(self, original, clone):
        """Synchronize properties and signals of the original and cloned widgets, including all children."""
        self.synchronize_widget_properties(original, clone)

        # Recursively synchronize each child widget
        if not original.layout():
            return
        for i in range(original.layout().count()):
            original_child = original.layout().itemAt(i).widget()
            cloned_child = clone.layout().itemAt(i).widget()
            if original_child and cloned_child:
                self.synchronize_widgets(original_child, cloned_child)

    def synchronize_widget_properties(self, original, clone):
        """Synchronize properties and signals for individual widget."""
        # Create weak references to original and clone to prevent deletion issues
        original_ref = weakref.ref(original)
        clone_ref = weakref.ref(clone)

        # Iterate over all properties with notify signals
        for i in range(original.metaObject().propertyCount()):
            prop = original.metaObject().property(i)
            if prop.isWritable() and prop.hasNotifySignal():
                # Get the notify signal for the property
                signal_name = bytes(prop.notifySignal().name()).decode()

                # Retrieve the signal from the original and clone using the signal name
                signal = getattr(original, signal_name, None)
                clone_signal = getattr(clone, signal_name, None)

                # Connect signals if they exist and track connections
                if signal and clone_signal:
                    conn1 = signal.connect(lambda value, p=prop, c_ref=clone_ref: self.set_property_safe(c_ref, p.name(), value))
                    conn2 = clone_signal.connect(lambda value, p=prop, o_ref=original_ref: self.set_property_safe(o_ref, p.name(), value))
                    self.connections.append((signal, conn1))
                    self.connections.append((clone_signal, conn2))

    def set_property_safe(self, widget_ref, property_name, value):
        """Set a property on a widget if it still exists."""
        widget = widget_ref()
        if widget is not None:
            widget.setProperty(property_name, value)

    def cleanup_connections(self):
        """Disconnect all signals to prevent errors when the widgets are deleted."""
        for signal, connection in self.connections:
            try:
                signal.disconnect(connection)
            except TypeError:
                pass  # Ignore if already disconnected
        self.connections.clear()

    def get_cloned_widget(self):
        """Return the cloned widget."""
        return self.cloned_widget


class AutoWidgetAction(QtWidgets.QWidgetAction):
    def __init__(self, widget, parent=None):
        super().__init__(parent)
        self._widget = widget

    def createWidget(self, parent):
        return CloneWidget(self._widget, parent).cloned_widget

class CustomToolBar(QtWidgets.QToolBar):
    def __init__(self, parent=None):
        super().__init__(parent)

    def addWidget(self, widget):
        # Wrap the cloned widget in AutoWidgetAction and add to the toolbar
        widget_action = AutoWidgetAction(widget, self)
        super().addAction(widget_action)

    def addAction(self, action: QtGui.QAction = None, icon: QtGui.QIcon = None, text: str = '', toolTip: str = None, 
                  data: Any = None, *args, **kwargs) -> QtGui.QAction:
        if not isinstance(action, QtGui.QAction):
            toolTip = toolTip or text
            action = QtGui.QAction(icon=icon, text=text, toolTip=toolTip, *args, **kwargs)
            if data is not None:
                action.setData(data)

        super().addAction(action)

        # Access the widget for the action and set the cursor
        self.widgetForAction(action).setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        return action

class GallerySectionHeader(QtWidgets.QWidget):
    """Section header widget for gallery groups."""
    
    def __init__(self, group_name: str, gallery_widget: 'GalleryWidget' = None):
        super().__init__(gallery_widget)

        self.gallery_widget = gallery_widget
        self.group_name = group_name
        self.collapsed = False

        self.__init_ui()

    def __init_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Collapse/expand icon using TablerQIcon
        self.icon_label = QtWidgets.QLabel(self)
        self.icon_label.setFixedSize(24, 24)
        self.update_icon()
        layout.addWidget(self.icon_label)

        # Group name label
        self.label = QtWidgets.QLabel(self.group_name, self)
        self.label.setStyleSheet('''
            QLabel {
                background-color: rgba(127, 127, 127, 0.4);
            }
            QLabel:hover {
                background-color: rgba(127, 127, 127, 0.6);
            }
        ''')
        layout.addWidget(self.label)

        # Set layout
        self.setLayout(layout)

        # Make the entire widget clickable
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        """Handle mouse press events to toggle only on left-click."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.toggle()

        super().mousePressEvent(event)

    def toggle(self):
        """Toggle the collapse state of the section."""
        self.collapsed = not self.collapsed
        self.update_icon()
        # Pass the group name to the gallery widget
        self.gallery_widget.toggle_section(self.group_name, self.collapsed)

    def update_icon(self):
        """Update the icon based on the collapse state."""
        icon = TablerQIcon.chevron_down if not self.collapsed else TablerQIcon.chevron_right
        self.icon_label.setPixmap(icon.pixmap(20, 20))

class GallerySectionItem(QtWidgets.QListWidgetItem):

    HEIGHT=32

    # Initialization and Setup
    # ------------------------
    def __init__(self, gallery_widget: 'GalleryWidget', group_name: str):
        super().__init__(gallery_widget)

        # Store the arguments
        self.gallery_widget = gallery_widget
        self.group_name = group_name

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        self.items: List[QtWidgets.QListWidgetItem] = []

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)

        self.header_widget = GallerySectionHeader(self.group_name, self.gallery_widget)
        self.gallery_widget.setItemWidget(self, self.header_widget)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect to the viewport_resized signal
        self.gallery_widget.viewport_resized.connect(self._update_size)

    # Public Methods
    # --------------
    def add_item(self, item: QtWidgets.QListWidgetItem):
        insert_position = self.gallery_widget.row(self) + len(self.items) + 1
        self.gallery_widget.insertItem(insert_position, item)
        self.items.append(item)
        self._update_size()

    # Private Methods
    # ---------------
    def _update_size(self):
        """Update the size hint when the viewport is resized."""
        new_width = self.listWidget().viewport().width() - 20
        self.setSizeHint(QtCore.QSize(new_width, self.HEIGHT))

class GalleryCard(QtWidgets.QWidget):

    ViewMode = QtWidgets.QListWidget.ViewMode

    DEFAULT_SIZE = 150

    def __init__(self, image_path, data_fields: Dict[str, Any], parent: 'GalleryWidget' = None):
        super().__init__(parent)

        # Store the arguments
        self.image_path = image_path
        self.data_fields = data_fields

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        self._card_size = self.DEFAULT_SIZE
        self._view_mode = QtWidgets.QListWidget.ViewMode.IconMode

        self.field_widgets: Dict[str, QtWidgets.QWidget] = {}

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Create Layouts
        # --------------
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create Widgets
        # --------------
        self.title_widget = QtWidgets.QLabel('Title', self)
        self.content_area = QtWidgets.QSplitter(self)

        # Thumbnail widget at the top
        self.thumbnail_widget = ThumbnailWidget(self.image_path, parent=self)

        # Form-like widget to show data fields
        self.form_widget = QtWidgets.QWidget(self)
        self.form_layout = QtWidgets.QVBoxLayout(self.form_widget)

        for field, value in self.data_fields.items():
            label = QtWidgets.QLabel(str(value))
            label.setToolTip(field)
            self.form_layout.addWidget(label)
            self.field_widgets[field] = label

        self.content_area.addWidget(self.thumbnail_widget)
        self.content_area.addWidget(self.form_widget)
        self.content_area.setHandleWidth(0)
        self.content_area.handle(1).setEnabled(False)

        # Add Widgets to Layouts
        # ----------------------
        layout.addWidget(self.title_widget)
        layout.addWidget(self.content_area)

        self.set_view_mode()

    def set_field_visibility(self, field, visible):
        """Set the visibility of a specific field."""
        if field in self.field_widgets:
            self.field_widgets[field].setVisible(visible)

    def set_card_size(self, size: int = DEFAULT_SIZE):
        self._card_size = size
        self.thumbnail_widget.setFixedSize(size, size)
        if self._view_mode == GalleryCard.ViewMode.IconMode:
            self.content_area.setMinimumHeight(0)
            self.content_area.setMaximumHeight(16777215)
            self.content_area.setFixedWidth(size)
        else:
            self.content_area.setMinimumWidth(0)
            self.content_area.setMaximumWidth(16777215)
            self.content_area.setFixedHeight(size)

    def set_view_mode(self, view_mode: ViewMode = ViewMode.IconMode):
        """Adjust the layout based on the view mode."""
        self._view_mode = view_mode
        if self._view_mode == GalleryCard.ViewMode.IconMode:
            # Unset the fixed height
            self.content_area.setOrientation(QtCore.Qt.Orientation.Vertical)
        else:
            self.content_area.setOrientation(QtCore.Qt.Orientation.Horizontal)

        self.set_card_size(self._card_size)

class GalleryWidgetItem(QtWidgets.QListWidgetItem):

    def __init__(self, parent: Union['GalleryWidget', 'GallerySectionItem'], data_fields: Dict[str, Any]):
        if isinstance(parent, GallerySectionItem):
            self.gallery_widget = parent.gallery_widget
            super().__init__()
            parent.add_item(self)

        else:
            self.gallery_widget = parent
            super().__init__(self.gallery_widget)

        self.data_fields = data_fields

        self.image_path = data_fields.get(self.gallery_widget.image_field)
        self.gallery_card = GalleryCard(self.image_path, self.data_fields, self.gallery_widget)
        self.setSizeHint(self.gallery_card.sizeHint())

        self.gallery_widget.setItemWidget(self, self.gallery_card)

    def get_value(self, field: str, default: Any = None) -> Any:
        return self.data_fields.get(field, default)

class InvisibleItemDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter, option, index):
        if index.row() == 0:
            # Skip painting for the spacer item
            return
        else:
            super().paint(painter, option, index)

class GalleryManipulationToolBar(QtWidgets.QToolBar):
    """A unified toolbar for sorting, grouping, and managing field visibility."""

    def __init__(self, parent: 'GalleryWidget'):
        super().__init__(parent)
        self.gallery_widget = parent

        # Initialize setup
        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        self.setIconSize(QtCore.QSize(22, 22))
        self.setProperty('widget-style', 'overlay')

        # Get available fields from the gallery view
        fields = self.gallery_widget.get_available_fields()

        # Sort
        self.sort_rule_button = QtWidgets.QPushButton(TablerQIcon.arrows_sort, 'Sort', self)
        self.sort_rule_button.setMinimumWidth(100)
        self.sort_rule_menu = QtWidgets.QMenu(self.sort_rule_button)
        
        # Initialize SortRuleWidget and add it to the menu as a popup
        self.sort_rule_widget = SortRuleWidget(self.gallery_widget)
        self.sort_rule_widget.set_fields(fields)
        # self.sort_rule_widget.sort_rule_applied.connect(self.apply_sort_rule)

        # Add the SortRuleWidget to the sort menu
        widget_action = QtWidgets.QWidgetAction(self.sort_rule_menu)
        widget_action.setDefaultWidget(self.sort_rule_widget)
        self.sort_rule_menu.addAction(widget_action)
        
        # Assign the menu to the button
        self.sort_rule_button.setMenu(self.sort_rule_menu)

        # Group
        self.group_button = QtWidgets.QPushButton(TablerQIcon.layout_2, 'Group', self)
        self.group_button.setMinimumWidth(100)
        self.group_rule_menu = QtWidgets.QMenu(self.group_button)
        self.group_button.setMenu(self.group_rule_menu)

        # Initialize GroupRuleWidget and add it to the group menu as a popup
        self.group_rule_widget = GroupRuleWidget(self)
        self.group_rule_widget.set_fields(fields)

        # Add the GroupRuleWidget to the group menu
        group_widget_action = QtWidgets.QWidgetAction(self.group_rule_menu)
        group_widget_action.setDefaultWidget(self.group_rule_widget)
        self.group_rule_menu.addAction(group_widget_action)

        # Show/Hide Fields Button
        self.fields_action = QtGui.QAction(TablerQIcon.list, 'Show/Hide Fields')

        self.addAction(self.fields_action)
        self.addSeparator()
        self.addWidget(self.sort_rule_button)
        self.addWidget(self.group_button)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        self.group_rule_widget.rules_applied.connect(self.gallery_widget.set_group_by_fields)
        self.group_rule_widget.rules_applied.connect(self.group_rule_menu.hide)
        self.sort_rule_widget.rules_applied.connect(self.gallery_widget.set_sort_rules)
        self.sort_rule_widget.rules_applied.connect(self.sort_rule_menu.hide)
        self.fields_action.triggered.connect(self.show_field_settings)

    def show_field_settings(self):
        """Show the field visibility settings.
        """
        self.gallery_widget.open_visualize_settings()

class GalleryViewToolBar(CustomToolBar):

    BUTTON_SIZE = 22

    DEFAULT_RESIZE_MODE = ThumbnailWidget.ResizeMode.Fit

    def __init__(self, parent: 'GalleryWidget'):
        """Initialize the GalleryViewToolBar."""
        super().__init__(parent)
        self.gallery_widget = parent
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize attributes."""
        self.tabler_icon = TablerQIcon(opacity=0.8)
        self.current_resize_mode = self.DEFAULT_RESIZE_MODE

    def __init_ui(self):
        """Initialize the UI of the toolbar."""
        self.setIconSize(QtCore.QSize(self.BUTTON_SIZE, self.BUTTON_SIZE))
        self.setProperty('widget-style', 'overlay')

        # Add actions to the toolbar
        self._add_view_mode_actions()
        self.addSeparator()

        # Add Resize Mode actions
        self._add_resize_mode_actions()
        self.addSeparator()

        # Add size slider
        self._add_size_slider_widget()
        self.addSeparator()

        self.reload_action = self.addAction(
            icon=self.tabler_icon.reload,
            text="Refresh Gallery",
        )

    def __init_signal_connections(self):
        """Initialize signal-slot connections."""
        # Additional signal connections can be added here if needed
        self.size_slider.valueChanged.connect(self.gallery_widget.set_card_size)
        self.reload_action.triggered.connect(self.gallery_widget.reload_requested.emit)

    def _add_view_mode_actions(self):
        """Add view mode actions to the toolbar."""
        view_mode_group = QtWidgets.QActionGroup(self)
        view_mode_group.setExclusive(True)

        # Define view modes with icons and tooltips
        view_modes = {
            QtWidgets.QListWidget.ViewMode.IconMode: (self.tabler_icon.layout_grid, "Grid View"),
            QtWidgets.QListWidget.ViewMode.ListMode: (self.tabler_icon.list_details, "List View"),
        }

        for mode, (icon, text) in view_modes.items():
            action = self.addAction(
                icon=icon,
                text=text,
                checkable=True,
                data=mode,
            )
            view_mode_group.addAction(action)
            # Check the current view mode
            if mode == self.gallery_widget.viewMode():
                action.setChecked(True)

        # Connect the action group's triggered signal
        view_mode_group.triggered.connect(self.set_view_mode)

    def _add_resize_mode_actions(self):
        """Add resize mode actions to the toolbar."""
        # Create an action group for mutual exclusivity
        resize_mode_group = QtWidgets.QActionGroup(self)
        resize_mode_group.setExclusive(True)

        # Define resize modes and corresponding icons
        resize_modes = {
            ThumbnailWidget.ResizeMode.Fit: (self.tabler_icon.aspect_ratio, "Fit Image"),
            ThumbnailWidget.ResizeMode.Fill: (self.tabler_icon.box_padding, "Fill Image"),
        }

        for mode, (icon, text) in resize_modes.items():
            action = self.addAction(
                icon=icon,
                text=text,
                checkable=True,
                data=mode
            )
            resize_mode_group.addAction(action)
            # Check the default resize mode
            if mode == self.current_resize_mode:
                action.setChecked(True)

        # Connect the action group's triggered signal
        resize_mode_group.triggered.connect(self.set_resize_mode)

    def _add_size_slider_widget(self):
        self.slider_widget = QtWidgets.QWidget()
        slider_layout = QtWidgets.QHBoxLayout(self.slider_widget)
        self.size_button = QtWidgets.QToolButton(self.slider_widget, icon=TablerQIcon.sort_ascending_small_big)
        # Add size slider
        self.size_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.size_slider.setMinimum(50)
        self.size_slider.setMaximum(300)
        self.size_slider.setValue(150)  # Default value
        self.size_slider.setMaximumWidth(100)
        self.size_slider.setToolTip("Adjust Thumbnail Size")
        slider_layout.addWidget(self.size_button)

        # TODO: Fix bug when clone widget with layout, .., then add slider_widget instead of size_slider
        # slider_layout.addWidget(self.size_slider)
        # self.addWidget(self.slider_widget)

        self.addWidget(self.size_slider)

    def set_resize_mode(self, mode: Union[QtWidgets.QAction, ThumbnailWidget.ResizeMode]):
        """Set the image resize mode based on the selected action or directly with ResizeMode.

        Args:
            action: An instance of QAction carrying ResizeMode data or a direct ResizeMode value.
        """
        if isinstance(mode, QtWidgets.QAction):
            mode = mode.data()

        if not isinstance(mode, ThumbnailWidget.ResizeMode):
            return

        self.current_resize_mode = mode
        self.gallery_widget.set_resize_mode(mode)

    def set_view_mode(self, mode: Union[QtWidgets.QAction, QtWidgets.QListWidget.ViewMode]):
        """Set the view mode based on the selected action.
        """
        if isinstance(mode, QtWidgets.QAction):
            mode = mode.data()

        self.gallery_widget.setViewMode(mode)

class GalleryWidget(MomentumScrollListWidget):

    viewport_resized = QtCore.Signal()
    reload_requested = QtCore.Signal()
    TOP_MARGIN = 20

    def __init__(self, parent=None):
        super().__init__(parent)

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        # Initialize available fields as an empty list
        self.fields = []
        self.visible_fields = {}
        self.group_items: Dict[str, GallerySectionItem] = {}
        self.group_by_fields = []
        self.sort_rules = []
        self.data_dicts: List[Dict[str, Any]] = []  # Store items to support re-grouping
        self.image_field = None

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Create the spacer item
        self.spacer_item = QtWidgets.QListWidgetItem()
        self.spacer_item.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
        self.insertItem(0, self.spacer_item)

        self.setViewMode(QtWidgets.QListWidget.ViewMode.IconMode)
        self.setResizeMode(QtWidgets.QListWidget.ResizeMode.Adjust)
        self.setMovement(QtWidgets.QListWidget.Movement.Static)
        self.setSpacing(10)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)

        # Set the custom item delegate
        self.setItemDelegate(InvisibleItemDelegate(self))

        # Configure overlay layout
        self.overlay_layout = QtWidgets.QHBoxLayout(self)
        self.overlay_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.overlay_layout.setContentsMargins(8, 8, 16, 8)

        # Initialize and add toolbars
        self.general_tool_bar = QtWidgets.QToolBar(self)
        self.manipulation_tool_bar = GalleryManipulationToolBar(self)
        self.utility_tool_bar = GalleryViewToolBar(self)

        self.manipulation_tool_bar.setGraphicsEffect(DropShadowEffect())
        self.utility_tool_bar.setGraphicsEffect(DropShadowEffect())

        # Add toolbars
        self.overlay_layout.addWidget(self.general_tool_bar, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        self.overlay_layout.addWidget(self.manipulation_tool_bar, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        self.overlay_layout.addWidget(self.utility_tool_bar, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

    # Public Methods
    # --------------
    def set_image_field(self, field_name):
        """Set the field name that contains the image path or thumbnail."""
        self.image_field = field_name

    def get_available_fields(self):
        """Return a list of available fields for grouping, sorting, and visibility."""
        return self.fields

    def set_group_by_fields(self, rules: List['GroupRuleWidget.GroupRule']):
        """Set the fields by which to group the items and reorganize the view."""
        self.group_by_fields = [rule.field for rule in rules]
        self._reorganize_items()

    def set_sort_rules(self, rules: List['SortRuleWidget.SortRule']):
        """Set the sorting rules and re-sort the items."""
        self.sort_rules = rules
        self._reorganize_items()

    def set_resize_mode(self, mode: 'ThumbnailWidget.ResizeMode' = ThumbnailWidget.ResizeMode.Fit):
        for list_item in self.iter_items():
            item_widget = self.itemWidget(list_item)
            if not item_widget or not isinstance(item_widget, GalleryCard):
                continue
            item_widget.thumbnail_widget.set_resize_mode(mode)

    def add_item(self, datadict: Dict[str, Any]):
        """Add an item to the gallery and store it for future grouping.

        Args:
            datadict (dict): A dictionary containing the data for the item.
                Expected to include the image path field and other data fields.
        """
        # Store the item for later re-grouping if needed
        self.data_dicts.append(datadict)
        self._add_item(datadict)

    def _add_item(self, datadict: Dict[str, Any]):
        if self.group_by_fields:
            self._insert_item_by_group(datadict)
        else:
            _item = GalleryWidgetItem(self, datadict)

    def toggle_section(self, group_name, collapsed):
        """Show or hide items under the specified section."""
        if group_name not in self.group_items:
            return

        group_item = self.group_items[group_name]
        for item in group_item.items:
            item.setHidden(collapsed)

    def open_visualize_settings(self):
        """Open a dialog for visualization settings."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Visualize Settings")

        # Layout for the dialog
        dialog_layout = QtWidgets.QVBoxLayout(dialog)

        # Checkbox for toggling field visibility
        field_toggle_layout = QtWidgets.QVBoxLayout()
        field_toggle_layout.addWidget(QtWidgets.QLabel("Field Visibility:"))

        # Example field checkboxes
        self.field_checkboxes = {}
        for field in self.fields:
            checkbox = QtWidgets.QCheckBox(field)
            checkbox.setChecked(self.visible_fields.get(field, True))
            checkbox.stateChanged.connect(lambda state, field=field: self.toggle_field_visibility(field, state))
            field_toggle_layout.addWidget(checkbox)
            self.field_checkboxes[field] = checkbox

        dialog_layout.addLayout(field_toggle_layout)

        # Set dialog layout and show it
        dialog.setLayout(dialog_layout)
        dialog.exec_()

    def set_card_size(self, size):
        """Set the size of gallery items based on the slider value."""
        for list_item in self.iter_items():
            item_widget = self.itemWidget(list_item)
            if not item_widget or not isinstance(item_widget, GalleryCard):
                continue
            item_widget.set_card_size(size)
            list_item.setSizeHint(item_widget.sizeHint())

        # Refresh the view
        self.model().layoutChanged.emit()

    def set_fields(self, fields: Iterable[str]):
        """Set the available fields for grouping, sorting, and visibility.

        Args:
            fields (list): A list of field names (strings) to be set as available fields.
        """
        self.fields = list(fields)
        # Initialize all fields as visible by default
        self.visible_fields = {field: True for field in fields}

        self.manipulation_tool_bar.sort_rule_widget.set_fields(fields)
        self.manipulation_tool_bar.group_rule_widget.set_fields(fields)

    def toggle_field_visibility(self, field, state):
        """Toggle visibility of a specific field."""
        visible = state == QtCore.Qt.CheckState.Checked
        self.visible_fields[field] = visible

        # Update all GalleryItemWidgets to reflect the new visibility state
        for list_item in self.iter_items():
            item_widget = self.itemWidget(list_item)
            if isinstance(item_widget, GalleryCard):
                item_widget.set_field_visibility(field, visible)

        # Refresh the view
        self.model().layoutChanged.emit()

    # Iterator over items excluding spacer_item
    def iter_items(self):
        """Iterator over items excluding spacer_item."""
        for index in range(self.count()):
            list_item = self.item(index)
            yield list_item

    # Private Methods
    # ---------------
    def _sort_value(self, value):
        """Convert the value to a sortable type."""
        if value is None:
            return ''  # Sort None values as empty strings
        if isinstance(value, str):
            # Try to convert strings to numbers if possible
            try:
                return float(value)
            except ValueError:
                return value.lower()  # For case-insensitive sorting
        return value

    def _reorganize_items(self):
        """Reorganize items based on current grouping and sorting rules."""
        # Clear all items in the gallery
        self.clear()
        self.group_items.clear()

        # Reorganize stored items according to grouping and sorting
        data_dicts = self.data_dicts.copy()

        # Apply sorting
        if self.sort_rules:
            # Sort the items starting from the last sort field
            for rule in reversed(self.sort_rules):
                field = rule.field
                reverse = rule.order == SortRuleWidget.SortOrder.DESCENDING
                data_dicts.sort(key=lambda item: self._sort_value(item.get(field, None)), reverse=reverse)

        # Re-insert items considering grouping
        for data_dict in data_dicts:
            self._add_item(data_dict)

    def _insert_item_by_group(self, data_fields):
        """Insert the item into the gallery view by its group.
        """
        # Determine group name based on current grouping fields
        group_values = [str(data_fields.get(field, 'Ungrouped')) for field in self.group_by_fields]
        group_name = ' - '.join(group_values)

        # Create a section header if the group doesn't exist
        if group_name not in self.group_items:
            group_item = GallerySectionItem(self, group_name)
            self.group_items[group_name] = group_item
        else:
            group_item = self.group_items[group_name]

        _item = GalleryWidgetItem(group_item, data_fields)

    def _update_spacer_item_size(self):
        # Set the size hint for the spacer item
        full_width = self.viewport().width() - 20
        self.spacer_item.setSizeHint(QtCore.QSize(full_width, self.TOP_MARGIN))

    # Overridden Methods
    # ------------------
    def setViewMode(self, mode: QtWidgets.QListWidget.ViewMode):
        """Override setViewMode to update item widgets."""
        super().setViewMode(mode)
        # Update all item widgets to adjust their layout
        for list_item in self.iter_items():
            item_widget = self.itemWidget(list_item)
            if not item_widget or not isinstance(item_widget, GalleryCard):
                continue
            item_widget.set_view_mode(mode)
            list_item.setSizeHint(item_widget.sizeHint())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_spacer_item_size()
        self.viewport_resized.emit()

    def clear(self):
        """Override the clear method to handle the spacer_item."""
        # Store the spacer item temporarily before clearing
        if self.spacer_item:
            super().takeItem(0)
        # Clear all items
        super().clear()
        # Re-insert the spacer_item at position 0
        if self.spacer_item:
            super().insertItem(0, self.spacer_item)

    def count(self):
        """Override count to exclude spacer_item."""
        total_count = super().count()
        return total_count - 1 if self.spacer_item else total_count

    def item(self, row):
        """Override item to adjust for spacer_item at index 0."""
        adjusted_row = row + 1 if self.spacer_item else row
        return super().item(adjusted_row)

    def row(self, item):
        """Override row to adjust for spacer_item at index 0."""
        row = super().row(item)
        return row - 1 if self.spacer_item and row > 0 else 0

    def takeItem(self, row):
        """Override takeItem to adjust for spacer_item at index 0."""
        adjusted_row = row + 1 if self.spacer_item else row
        return super().takeItem(adjusted_row)

    def insertItem(self, row, item):
        """Override insertItem to adjust for spacer_item at index 0."""
        adjusted_row = row + 1 if self.spacer_item else row
        super().insertItem(adjusted_row, item)


class GalleryWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Gallery")
        self.setGeometry(100, 100, 800, 800)
        self.__init_ui()

    def __init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Create QListWidget with vertical scroll and wrap items horizontally
        self.gallery_view_widget = GalleryWidget(self)
        layout.addWidget(self.gallery_view_widget)

        self.setLayout(layout)

def get_image_paths(directory, extensions=('*.jpg', '*.png', '*.jpeg', '*.gif', '*.webp')):
    """Fetch image paths from the specified directory with the given extensions."""
    image_paths = []
    for ext in extensions:
        image_paths.extend(glob.glob(os.path.join(directory, ext)))
    return image_paths


if __name__ == "__main__":
    from blackboard import theme
    app = QtWidgets.QApplication(sys.argv)
    theme.set_theme(app, 'dark')

    # Specify directory to load images
    directory = ''
    image_files = get_image_paths(directory)

    # Example metadata for images
    vfx_shot_metadata = [
        {
            'Thumbnail': image_files[0],
            "Shot Name": "shot_001",
            "Description": "Explosion in the background with debris flying.",
            "Frame Range": "1001-1100",
            "Artist": "Alice Smith",
            "Shot Type": "FX",
            "Status": "In Progress",
        },
        {
            'Thumbnail': image_files[1],
            "Shot Name": "shot_002",
            "Description": "Character enters the frame from the left.",
            "Frame Range": "1050-1150",
            "Artist": "Bob Johnson",
            "Shot Type": "Compositing",
            "Status": "Complete",
        },
        {
            'Thumbnail': image_files[2],
            "Shot Name": "shot_003",
            "Description": "Background matte painting integration.",
            "Frame Range": "1200-1300",
            "Artist": "Alice Smith",
            "Shot Type": "Matte Painting",
            "Status": "Review",
        },
        {
            'Thumbnail': image_files[3],
            "Shot Name": "shot_004",
            "Description": "Fire effect on building collapse.",
            "Frame Range": "1150-1250",
            "Artist": "Charlie Davis",
            "Shot Type": "FX",
            "Status": "Pending",
        },
        {
            'Thumbnail': image_files[4],
            "Shot Name": "shot_005",
            "Description": "Character close-up with lighting adjustments.",
            "Frame Range": "1100-1200",
            "Artist": "Bob Johnson",
            "Shot Type": "Compositing",
            "Status": "In Progress",
        },
        {
            'Thumbnail': image_files[5],
            "Shot Name": "shot_006",
            "Description": "CG assets integrated into live-action plate.",
            "Frame Range": "1300-1400",
            "Artist": "Charlie Davis",
            "Shot Type": "Integration",
            "Status": "Complete",
        },
        {
            'Thumbnail': image_files[6],
            "Shot Name": "shot_007",
            "Description": "Water simulation running through the street.",
            "Frame Range": "1400-1500",
            "Artist": "Alice Smith",
            "Shot Type": "FX",
            "Status": "In Progress",
        },
        {
            'Thumbnail': image_files[7],
            "Shot Name": "shot_008",
            "Description": "Sky replacement with volumetric clouds.",
            "Frame Range": "1250-1350",
            "Artist": "Bob Johnson",
            "Shot Type": "Matte Painting",
            "Status": "Review",
        },
        {
            'Thumbnail': image_files[8],
            "Shot Name": "shot_009",
            "Description": "Car chase with motion blur effects.",
            "Frame Range": "1500-1600",
            "Artist": "Charlie Davis",
            "Shot Type": "Compositing",
            "Status": "Pending",
        },
        {
            'Thumbnail': image_files[9],
            "Shot Name": "shot_010",
            "Description": "Day-to-night color grading transformation.",
            "Frame Range": "1601-1700",
            "Artist": "Alice Smith",
            "Shot Type": "Color Grading",
            "Status": "In Progress",
        },
        {
            'Thumbnail': image_files[10],
            "Shot Name": "shot_011",
            "Description": "Explosion aftermath with dust and smoke simulation.",
            "Frame Range": "1700-1800",
            "Artist": "Bob Johnson",
            "Shot Type": "FX",
            "Status": "Pending",
        },
        {
            'Thumbnail': image_files[11],
            "Shot Name": "shot_012",
            "Description": "Green screen replacement with futuristic cityscape.",
            "Frame Range": "1801-1900",
            "Artist": "Charlie Davis",
            "Shot Type": "Compositing",
            "Status": "Complete",
        },
        {
            'Thumbnail': image_files[12],
            "Shot Name": "shot_013",
            "Description": "Spaceship takeoff with realistic exhaust flames.",
            "Frame Range": "1900-2000",
            "Artist": "Alice Smith",
            "Shot Type": "FX",
            "Status": "In Progress",
        },
        {
            'Thumbnail': image_files[13],
            "Shot Name": "shot_014",
            "Description": "Character shadow enhancement for evening scene.",
            "Frame Range": "2001-2100",
            "Artist": "Bob Johnson",
            "Shot Type": "Compositing",
            "Status": "Review",
        },
        {
            'Thumbnail': image_files[14],
            "Shot Name": "shot_015",
            "Description": "CG building destruction with camera shake effect.",
            "Frame Range": "2101-2200",
            "Artist": "Charlie Davis",
            "Shot Type": "FX",
            "Status": "Pending",
        },
    ]

    # Initialize and show the gallery window
    window = GalleryWindow()
    # Set available fields dynamically
    fields = ["Artist", "Shot Type", "Status", "Shot Name", "Frame Range", "Date", "Thumbnail"]
    window.gallery_view_widget.set_fields(fields)
    # Set the field that contains the image path
    window.gallery_view_widget.set_image_field('Thumbnail')
    
    # Add items to the gallery based on metadata
    for metadata in vfx_shot_metadata:
        window.gallery_view_widget.add_item(metadata)

    window.show()
    sys.exit(app.exec_())
