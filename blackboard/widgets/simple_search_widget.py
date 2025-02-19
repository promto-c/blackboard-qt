# Type Checking Imports
# ---------------------
from typing import TYPE_CHECKING, Optional, Set, Union, Iterable
if TYPE_CHECKING:
    from blackboard.widgets import GroupableTreeWidget

# Standard Library Imports
# ------------------------
import fnmatch

# Third Party Imports
# -------------------
from qtpy import QtCore, QtGui, QtWidgets
from tablerqicon import TablerQIcon

# Local Imports
# -------------
from blackboard.utils import KeyBinder, TextExtraction, TreeItemUtil, TreeUtil


# Class Definitions
# -----------------
class MatchCountButton(QtWidgets.QPushButton):
    """Button that changes its appearance on mouse hover and displays match counts.

    Designed to display the number of matches in a search operation.
    When the mouse hovers over it, the button provides a visual indication that clicking it
    will clear the search results.

    Attributes:
        _current_label (str): Stores the current label text of the button.
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize the button with a parent widget, sets properties, and tooltip.

        Args:
            parent (QtWidgets.QWidget, optional): The parent widget of the button. Defaults to None.
        """
        super().__init__(parent, toolTip="Click to clear search")

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        self._current_label = ''

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Set up properties
        self.setProperty('widget-style', 'action-clear')
        self.setFixedHeight(16)

    # Public Methods
    # --------------
    def set_match_count(self, total_matches: int, has_more_results: bool = False):
        """Set the visibility and text of the button based on the total match count.
        
        If `has_more_results` is True, a `+` symbol is appended to indicate partial results.

        Args:
            total_matches (int): The number of matches to display.
            has_more_results (bool): Whether there are more results than displayed. Defaults to False.
        """
        self.setVisible(bool(total_matches))
        # Add `+` symbol if there are more results than displayed
        self.setText(f"{total_matches}+" if has_more_results else str(total_matches))

    # Overridden Methods
    # ------------------
    def enterEvent(self, event: QtCore.QEvent):
        """Handle mouse entry events, changing the icon and cursor.

        Args:
            event (QtCore.QEvent): The mouse enter event.
        """
        super().enterEvent(event)
        self._current_label = self.text()
        self.setIcon(TablerQIcon.x)
        self.setText('')
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def leaveEvent(self, event: QtCore.QEvent):
        """Handle mouse leave events, resetting the icon and cursor.

        Args:
            event (QtCore.QEvent): The mouse leave event.
        """
        super().leaveEvent(event)
        self.setIcon(QtGui.QIcon())
        self.setText(self._current_label)
        self.unsetCursor()


class SearchFieldButton(QtWidgets.QPushButton):

    def __init__(self, parent):
        super().__init__(
            icon=TablerQIcon(opacity=0.6).search,
            text='Global',
            cursor=QtCore.Qt.CursorShape.PointingHandCursor,
            parent=parent,
        )

        self.setStyleSheet('''
            QPushButton {
                border: 0px;
                color: #CCC;
                background: transparent;
                border-top-right-radius: 0;
                border-bottom-right-radius: 0;
                border-right: 1px solid gray;
                padding: 0 6;
                text-align: left;
            }
        ''')


class SimpleSearchWidget(QtWidgets.QFrame):

    FIXED_STRING_MATCH_FLAGS = QtCore.Qt.MatchFlag.MatchRecursive | QtCore.Qt.MatchFlag.MatchFixedString
    CONTAINS_MATCH_FLAGS = QtCore.Qt.MatchFlag.MatchRecursive | QtCore.Qt.MatchFlag.MatchContains
    WILDCARD_MATCH_FLAGS = QtCore.Qt.MatchFlag.MatchRecursive | QtCore.Qt.MatchFlag.MatchWildcard

    activated = QtCore.Signal()

    # Initialization and Setup
    # ------------------------
    def __init__(self, tree_widget: 'GroupableTreeWidget', parent: QtWidgets.QWidget = None):
        """Initialize the widget with a reference to the tree widget and sets up
        the UI components and signal connections.

        Args:
            tree_widget (GroupableTreeWidget): The tree widget to be searched.
            parent (QtWidgets.QWidget, optional): The parent widget. Defaults to None.
        """
        # Initialize the super class
        super().__init__(parent)

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
        self.tabler_icon = TablerQIcon(opacity=0.6)

        # Private Attributes
        # ------------------
        self._search_fields: Set[str] = set()
        self._default_search_fields: Set[str] = set()
        self._all_match_items = set()
        self._is_active = False
        self._history = []
        self._history_index = -1

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setFixedHeight(24)

        # Create Layouts
        # --------------
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create Widgets
        # --------------
        # Set up the search line edit widget
        self.search_field_button = SearchFieldButton(self)
        self.search_field_menu = QtWidgets.QMenu()
        self.search_field_button.setMenu(self.search_field_menu)

        self.line_edit = SearchEdit(self)

        # Create and set up the match count button (for showing match count)
        self.__init_match_count_action()

        # Add Widgets to Layouts
        # ----------------------
        layout.addWidget(self.search_field_button)
        layout.addWidget(self.line_edit)

    def __init_match_count_action(self):
        """Initialize the match count action and adds it to the line edit.
        """
        # Create and add the label for showing the total match count
        self.match_count_button = MatchCountButton(self)

        # Initialize a QWidgetAction to hold the match count button and set it as the default widget
        self.match_count_action = QtWidgets.QWidgetAction(self)
        self.match_count_action.setDefaultWidget(self.match_count_button)

        # Add the match count action to the line edit, positioned at the trailing end
        self.line_edit.addAction(self.match_count_action, QtWidgets.QLineEdit.ActionPosition.TrailingPosition)

        # Initially hide the match count button
        self.match_count_button.setVisible(False)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Install event filter on the line edit to detect focus changes
        self.line_edit.installEventFilter(self)

        # Connect signals to slots
        self.line_edit.textChanged.connect(self.deactivate)
        self.line_edit.textChanged.connect(self._highlight_matching_items)
        self.line_edit.textChanged.connect(self.line_edit.update_style)
        self.match_count_button.clicked.connect(self.clear_search)
        self.tree_widget.item_added.connect(self._filter_item)
        self.tree_widget.fetch_complete.connect(self._refresh_match_count)
        self.search_field_menu.aboutToShow.connect(self._show_search_fields_menu)

        # Bind keys using KeyBinder for _history navigation
        KeyBinder.bind_key('Enter', self.line_edit, self.activate)
        KeyBinder.bind_key('Return', self.line_edit, self.activate)
        KeyBinder.bind_key('Escape', self.line_edit, self.clear_search)
        KeyBinder.bind_key('Up', self.line_edit, lambda: self._navigate_history(-1))
        KeyBinder.bind_key('Down', self.line_edit, lambda: self._navigate_history(1))

    def eventFilter(self, obj, event):
        if obj == self.line_edit:
            if event.type() == QtCore.QEvent.Type.FocusIn:
                # Visually highlight SimpleSearchWidget when line edit is focused
                self.setProperty('in-focus', True)
                self.update_style()

            elif event.type() == QtCore.QEvent.Type.FocusOut:
                # Remove highlight when line edit loses focus
                self.setProperty('in-focus', False)
                self.update_style()

        return super().eventFilter(obj, event)

    # Public Methods
    # --------------
    def set_default_search_fields(self, fields: Iterable[Union[str, int]] = set()):
        """Set the default search fields to be used when clearing search."""
        # Convert to set and assign default search fields
        self._default_search_fields = set(fields)
        self.clear_search()

    def clear_search(self):
        """Clear the search and restore the default search fields."""
        if self._default_search_fields:
            # Restore the default fields when clearing the search
            self.set_search_fields(self._default_search_fields)
        else:
            # If no default fields set, fall back to global search (clears included fields)
            self.set_global_search_field()
        
        # Clear the line edit text
        self.line_edit.clear()

    def set_global_search_field(self):
        self._search_fields.clear()
        self._update_search_field_text()

    def set_search_field(self, field: Union[str, int], checked: bool = True, apply_update: bool = True):
        """Toggle whether the field is included in the search.
        """
        if isinstance(field, int):
            field = self.tree_widget.fields[field]

        if checked:
            self._search_fields.add(field)
        else:
            self._search_fields.discard(field)
        
        if apply_update:
            self._update_search_field_text()
            self.update()

    def set_search_fields(self, fields: Iterable[Union[str, int]], checked: bool = True, clear_existing: bool = True, apply_update: bool = True):
        """Set multiple fields for search with an option to clear existing fields or not."""
        if clear_existing:
            self._search_fields.clear()  # Clears all previous fields
        
        for field in fields:
            self.set_search_field(field, checked=checked, apply_update=False)

        # Reapply search with updated settings
        if apply_update:
            self._update_search_field_text()
            self.update()

    def set_text_as_selection(self):
        """Update the search edit text with the text of the currently selected items in the tree widget.
        """
        selected_indexes = self.tree_widget.selectedIndexes()
        fields = {index.column() for index in selected_indexes}
        keywords = {f'"{index.data()}"' for index in selected_indexes}

        self.set_search_fields(fields)             
        self.line_edit.setText('|'.join(keywords))
        self.line_edit.setFocus()

    def activate(self):
        """Activate the search functionality.
        """
        if not self._all_match_items and not self.tree_widget.fetch_manager.has_more_items_to_fetch:
            return

        self._set_property_active(True)
        self._apply_search()
        self.activated.emit()

        # Add to _history only if it's a new entry
        current_text = self.line_edit.text().strip()
        if current_text and (not self._history or self._history[-1] != current_text):
            self._history.append(current_text)
            self._history_index = -1

        if self.tree_widget.fetch_manager.has_more_items_to_fetch:
            self.tree_widget.fetch_manager.fetch_all()

    def deactivate(self):
        """Deactivate the search functionality.
        """
        if not self._is_active:
            return

        self._set_property_active(False)
        self._clear_search()

    def update(self):
        """Update the search and highlights matching items.
        """
        self._highlight_matching_items()

        if self._is_active:
            self._apply_search()

    def update_style(self):
        """Update the button's style based on its state.
        """
        self.style().unpolish(self)
        self.style().polish(self)

    # Class Properties
    # ----------------
    @property
    def matched_items(self):
        return self._all_match_items

    @property
    def is_active(self):
        return self._is_active
    
    @property
    def search_fields(self):
        return self._search_fields

    @property
    def default_search_fields(self):
        return self._default_search_fields

    # Private Methods
    # ---------------
    def _update_search_field_text(self):
        """Update the search field text based on the current search configuration.
        """
        if not self._search_fields:
            text = 'Global'
        elif len(self._search_fields) == 1:
            text = next(iter(self._search_fields))
        else:
            text = f'{len(self._search_fields)} fields'
        self.search_field_button.setText(text)

    def _show_search_fields_menu(self):
        """Show a menu to select which fields to search by.
        """
        self.search_field_menu.clear()

        # Add the global search action
        global_search_action = self.search_field_menu.addAction("Global Search")
        global_search_action.setCheckable(True)
        global_search_action.setChecked(not self._search_fields)
        global_search_action.triggered.connect(self.set_global_search_field)

        self.search_field_menu.addSeparator()

        # Add field-specific search actions
        for field in self.tree_widget.fields:
            action = self.search_field_menu.addAction(field)
            action.setCheckable(True)
            action.setChecked(field in self._search_fields)
            action.triggered.connect(lambda checked, field=field: self.set_search_field(field, checked))

    def _filter_item(self, tree_item: 'QtWidgets.QTreeWidgetItem'):
        """Determines whether a newly added tree item matches the current search criteria and updates its visibility or highlighting accordingly.

        Args:
            tree_item (QtWidgets.QTreeWidgetItem): The item that was added to the tree widget.
        """
        # Retrieve and sanitize the current search keyword from the input field
        keyword = self.line_edit.text().strip()
        if not keyword:
            return

        # Get the matched field indexes (an empty list if not matched)
        matched_field_indexes = self._get_matched_field_indexes(tree_item)

        # If the item matches the search filter, add it to the matched items set and update the displayed match count
        if matched_field_indexes:
            self._all_match_items.add(tree_item)
            self._refresh_match_count()

            # If the search is not active, highlight the matching item fields
            if not self.is_active:
                for matched_field_index in matched_field_indexes:
                    self.tree_widget.highlight_items({tree_item}, matched_field_index)

        # If the item doesn't match and the search is active, hide it
        elif self.is_active:
            tree_item.setHidden(True)

    def _get_matched_field_indexes(self, item: 'QtWidgets.QTreeWidgetItem') -> list:
        """Check if an item matches the search filter and return all matched field indexes.

        Args:
            item (QtWidgets.QTreeWidgetItem): The item to check.

        Returns:
            list: A list of matched column indexes. If no match is found, returns an empty list.
        """
        matched_indexes = []
        search_fields = self._search_fields or self.tree_widget.fields
        for field in search_fields:
            field_index = self.tree_widget.get_column_index(field)
            item_text = item.text(field_index)

            # Check quoted terms for exact match or unquoted terms with wildcard support
            if (any(item_text == term for term in self.quoted_terms) or
                any(self._is_match_unquoted_term(item_text, term) for term in self.unquoted_terms)
            ):
                matched_indexes.append(field_index)

        return matched_indexes

    def _is_match_unquoted_term(self, item_text: str, term: str) -> bool:
        """Helper method to check if item_text matches the unquoted term.

        Args:
            item_text (str): The text of the item to check.
            term (str): The term to match against.

        Returns:
            bool: True if the item_text matches the unquoted term, False otherwise.
        """
        if TextExtraction.is_contains_wildcard(term):
            return fnmatch.fnmatch(item_text, term)
        else:
            return term in item_text

    def _refresh_match_count(self):
        """Refresh the match count label to display the current number of matching items.
        """
        self.match_count_button.set_match_count(len(self._all_match_items), has_more_results=self.tree_widget.fetch_manager.has_more_items_to_fetch)

    def _clear_highlights(self):
        """Clear the highlight and matched items.
        """
        # Clear the highlight for all items
        self.tree_widget.clear_highlight()
        # Clear any previously matched items
        self._all_match_items.clear()
        self._refresh_match_count()

    def _highlight_matching_items(self):
        """Highlight the items in the tree widget that match the search criteria.
        """
        # Clear the highlight for all items
        self._clear_highlights()

        # Return if the keyword is empty
        if not (keyword := self.line_edit.text().strip()):
            return

        # Extract terms from the keyword for search filtering
        self.quoted_terms, self.unquoted_terms = TextExtraction.extract_terms(keyword)

        search_fields = self._search_fields or self.tree_widget.fields
        for field in search_fields:
            column_index = self.tree_widget.get_column_index(field)

            match_items = set()

            # Handle fixed string match terms with case-insensitive matching
            for term in self.quoted_terms:
                match_items.update(self.tree_widget.findItems(term, self.FIXED_STRING_MATCH_FLAGS, column_index))

            # Handle contains match terms
            for term in self.unquoted_terms:
                flags = self.WILDCARD_MATCH_FLAGS if TextExtraction.is_contains_wildcard(term) else self.CONTAINS_MATCH_FLAGS

                # Find items that contain the term, regardless of its position in the string
                match_items.update(self.tree_widget.findItems(term, flags, column_index))

            # Highlight the matched items
            self.tree_widget.highlight_items(match_items, column_index)

            # Store all matched items
            self._all_match_items.update(match_items)

        self._refresh_match_count()

    def _set_property_active(self, state: bool = True):
        """Set the active state of the button.
        """
        self._is_active = state
        self.setProperty('active', self._is_active)
        self.update_style()

    def _navigate_history(self, direction: int):
        """Navigate through the search history using the up/down arrow keys.
        """
        if not self._history:
            return

        # If starting navigation, set _history_index to position beyond the end
        if self._history_index == -1:
            self._history_index = len(self._history)

        # Adjust the _history index
        self._history_index += direction

        # Clamp the _history index
        self._history_index = max(0, min(self._history_index, len(self._history)))

        if self._history_index == len(self._history):
            # Beyond the last item, clear the line edit and reset _history_index
            self.line_edit.clear()
            self._history_index = -1
        else:
            # Set the text to the _history item
            self.line_edit.setText(self._history[self._history_index])

    def _apply_search(self):
        """Apply the filters specified by the user to the tree widget.
        """
        self.tree_widget.clear_highlight()

        # Hide all items
        TreeUtil.hide_all_items(self.tree_widget)
        # Show match items
        TreeItemUtil.set_items_visibility(self._all_match_items, is_visible=True)

    def _clear_search(self):
        """Clear the search and show all items.
        """
        # Show all items
        TreeUtil.show_all_items(self.tree_widget)
        self._highlight_matching_items()


class SearchEdit(QtWidgets.QLineEdit):
    """Widget for simplified search functionality within a groupable tree widget. 
    Supports keyword search, highlights matching items, and displays the total count of matches.

    Attributes:
        tree_widget (GroupableTreeWidget): The tree widget where search will be performed.
        _is_active (bool): Indicates whether the search filter is currently applied.
        _all_match_items (set): A set of items that match the current search criteria.
        included_fields (set): A set of fields to include in the search.
        _history (list): A list that stores the search _history.
        _history_index (int): The current index in the search _history for navigation.
    """

    PLACEHOLDER_TEXT = 'Type to Search'

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent: QtWidgets.QWidget = None):
        """Initialize the widget with a reference to the tree widget and sets up
        the UI components and signal connections.

        Args:
            tree_widget (GroupableTreeWidget): The tree widget to be searched.
            parent (QtWidgets.QWidget, optional): The parent widget. Defaults to None.
        """
        # Initialize the super class
        super().__init__(parent, placeholderText=self.PLACEHOLDER_TEXT)

        # Initialize setup
        self.__init_ui()

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Set the UI properties
        self.setProperty('widget-style', 'borderless')
        self.setProperty('has-placeholder', True)
        self.update_style()

    def update_style(self):
        """Update the button's style based on its state.
        """
        self.style().unpolish(self)
        self.style().polish(self)


# Main Function
# -------------
def main():
    """Create the application and main window, and show the widget.
    """
    import sys
    from blackboard.examples.example_data_dict import COLUMN_NAME_LIST, ID_TO_DATA_DICT
    from blackboard.widgets import GroupableTreeWidget, ScalableView
    from blackboard import theme

    # Create the application and the main window
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QMainWindow()

    # Set theme of QApplication to the dark theme
    theme.set_theme(app, 'dark')

    # Create the tree widget with example data
    tree_widget = GroupableTreeWidget()
    tree_widget.setHeaderLabels(COLUMN_NAME_LIST)
    tree_widget.add_items(ID_TO_DATA_DICT)

    # Create an instance of the widget and set it as the central widget
    search_widget = SimpleSearchWidget(tree_widget, parent=window)

    main_widget = QtWidgets.QWidget()
    main_layout = QtWidgets.QVBoxLayout(main_widget)

    main_layout.addWidget(search_widget)
    main_layout.addWidget(tree_widget)

    # search_widget.set_search_column('Name')
    shortcut = QtWidgets.QShortcut(QtGui.QKeySequence('Ctrl+F'), main_widget)
    shortcut.activated.connect(search_widget.set_text_as_selection)

    # Create the scalable view and set the tree widget as its central widget
    scalable_view = ScalableView(widget=main_widget)

    # Add the tree widget to the layout of the widget
    window.setCentralWidget(scalable_view)

    # Show the window
    window.show()

    # Run the application
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
