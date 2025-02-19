# Type Checking Imports
# ---------------------
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional, Union
if TYPE_CHECKING:
    from blackboard.utils.database import AbstractModel, DatabaseManager, ManyToManyField, FieldInfo
    from blackboard.widgets.groupable_tree_widget import TreeWidgetItem

# Standard Library Imports
# ------------------------
import uuid
from enum import Enum
from functools import partial
import ast
import operator
import re

# Third Party Imports
# -------------------
from qtpy import QtWidgets, QtCore, QtGui
from tablerqicon import TablerQIcon

# Local Imports
# -------------
import blackboard as bb
from blackboard import widgets
from blackboard.widgets.momentum_scroll_widget import MomentumScrollArea
from blackboard.widgets.filter_widget import FilterWidget, MultiSelectFilterWidget
from blackboard.utils.database.sql_query_builder import SQLQueryBuilder


# Class Definitions
# -----------------
class DataViewWidget(QtWidgets.QWidget):
    """A widget for displaying and interacting with a data view.
    """

    LABEL: str = 'Data View'

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent: QtWidgets.QWidget = None, identifier: Optional[str] = None):
        """Initialize the widget and set up the UI, signal connections.
        """
        # Initialize the super class
        super().__init__(parent)

        # Generate a unique identifier if none is provided
        self.identifier = identifier or str(uuid.uuid4())

        # Initialize setup
        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        """Initialize the UI of the widget.

        UI Wireframe:

            |--[W1]: filter_bar_widget--|

            +---------------------------------------------------+ -+
            | [Filter 1][Filter 2][+]     [[W2]: search_widget] |  | -> [L1]: top_bar_area_layout
            +---------------------------------------------------+ -+
            | [W3]: general_tool_bar| - - | [W4]: view_tool_bar |  | -> [L2]: utility_area_layout
            |                                                   |  |
            |                                                   |  |
            |               [[W5]: tree_widget]                 |  | -> [L3]: main_view_layout
            |                                                   |  |
            |                                                   |  |
            +---------------------------------------------------+ -+
        """
        # Create Layouts
        # --------------
        # [L0]: Set main layout as vertical layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # [L1]: Add top bar layout as horizontal layout
        self.top_bar_area_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(self.top_bar_area_layout)

        # [L2]: Add utility layout
        self.utility_area_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(self.utility_area_layout)

        # [L3]: Add main tree layout
        self.main_view_layout = QtWidgets.QVBoxLayout()
        self.main_layout.addLayout(self.main_view_layout)

        # Create Widgets
        # --------------
        # [W1]: Create top left filter bar
        self.filter_bar_widget = widgets.FilterBarWidget(self)
        self.add_filter_button = self.filter_bar_widget.add_filter_button

        # [W5]: Create asset tree widget
        self.tree_widget = widgets.GroupableTreeWidget(parent=self)

        # [W2]: Search field
        self.search_widget = widgets.SimpleSearchWidget(tree_widget=self.tree_widget, parent=self)
        self.search_widget.setMinimumWidth(200)

        # [W3], [W4]: General tool bar and view utility bar
        self.general_tool_bar = QtWidgets.QToolBar(self)
        self.view_tool_bar = widgets.TreeUtilityToolBar(self.tree_widget)

        # Add Widgets to Layouts
        # ----------------------
        # Add [W1], [W2] to [L1]
        # Add left filter bar and right search edit to top bar layout
        self.top_bar_area_layout.addWidget(self.filter_bar_widget, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        self.top_bar_area_layout.addWidget(self.search_widget, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        # Add [W3], [W4] to [L2]
        # Add left general tool bar and right view tool bar
        self.utility_area_layout.addWidget(self.general_tool_bar, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        self.utility_area_layout.addWidget(self.view_tool_bar, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        # Add [W5] to [L3]
        # Add tree widget to main tree widget
        self.main_view_layout.addWidget(self.tree_widget)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect signals to slots
        self.tree_widget.reload_requested.connect(self.populate)
        self.filter_bar_widget.filter_changed.connect(self.populate)

        bb.utils.KeyBinder.bind_key('Ctrl+F', self.tree_widget, self.search_widget.set_text_as_selection)

    # Public Methods
    # --------------
    def add_filter_widget(self, filter_widget: 'FilterWidget'):
        self.filter_bar_widget.add_filter_widget(filter_widget)

    def save_state(self, settings: QtCore.QSettings, group_name: str = 'data_view'):
        self.tree_widget.save_state(settings, group_name)
    
    def load_state(self, settings: QtCore.QSettings, group_name: str = 'data_view'):
        self.tree_widget.load_state(settings, group_name)

    def populate(self):
        fields = self.tree_widget.fields
        conditions = self.filter_bar_widget.get_query_conditions()

        ...

        # Logic to filter data then populate
        raise NotImplementedError(f"{self.__class__.__name__}.populate must be implemented by subclasses.")

    # Special Methods
    # ---------------
    def __hash__(self):
        return hash(self.identifier)

class FileBrowseWidget(QtWidgets.QWidget):

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent: QtWidgets.QWidget = None):
        """Initializes the FileBrowseWidget with a line edit and a browse button.

        Args:
            parent: The parent widget, if any.
        """
        super().__init__(parent)

        # Initialize setup
        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Create Layouts
        # --------------
        layout = QtWidgets.QHBoxLayout(self)

        # Create Widgets
        # --------------
        self.line_edit = QtWidgets.QLineEdit()
        self.browse_button = QtWidgets.QPushButton("Browse")

        # Add Widgets to Layouts
        # ----------------------
        layout.addWidget(self.line_edit)
        layout.addWidget(self.browse_button)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect signals to slots
        self.browse_button.clicked.connect(self.browse_file)

    # Public Methods
    # --------------
    def browse_file(self):
        """Opens a file dialog to allow the user to select a file and populates the line edit.
        """
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select File")
        if not file_name:
            return
        self.line_edit.setText(file_name)
    
    def get_value(self) -> str:
        """Returns the current text in the line edit, or None if it is empty.
        """
        return self.line_edit.text()


class AddEditRecordDialog(QtWidgets.QDialog):
    """A dialog for adding or editing records in the database.
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, db_manager: 'DatabaseManager', model: 'AbstractModel', data_dict: dict = None, parent=None):
        super().__init__(parent)

        # Store the arguments
        self.model = model
        self.db_manager = db_manager
        self.data_dict = data_dict

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        self.field_name_to_input_widgets: Dict[str, QtWidgets.QWidget] = {}
        self.field_name_to_info = self.model.get_fields()
        self.many_to_many_fields = self.model.get_many_to_many_fields()

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setWindowTitle("Add/Edit Record")

        # Create Layouts
        # --------------
        # Create Main Layout
        main_layout = QtWidgets.QVBoxLayout(self)

        # Create Scroll Area
        scroll_area = MomentumScrollArea(self)
        scroll_area.setWidgetResizable(True)  # Ensure the scroll area resizes its content widget

        # Create Content Widget for Scroll Area
        scroll_content = QtWidgets.QWidget()
        scroll_area.setWidget(scroll_content)

        # Create a vertical layout for the content widget
        form_layout = QtWidgets.QVBoxLayout(scroll_content)
        form_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)  # Align widgets to the top

        # Create Widgets for Each Field
        for field_name, field_info in self.field_name_to_info.items():
            # Skip the primary key field; it is usually auto-managed by SQLite
            if field_info.type == 'INTEGER' and field_info.is_primary_key:
                continue

            input_widget = self.create_input_widget(field_info)
            label_widget = widgets.LabelEmbedderWidget(input_widget, field_name)
            form_layout.addWidget(label_widget)
            self.field_name_to_input_widgets[field_name] = input_widget

        # Handle Many-to-Many Fields
        for track_field_name, many_to_many_field in self.many_to_many_fields.items():
            m2m_widget = self.create_many_to_many_widget(many_to_many_field)
            label_widget = widgets.LabelEmbedderWidget(m2m_widget, track_field_name)
            form_layout.addWidget(label_widget)
            self.field_name_to_input_widgets[track_field_name] = m2m_widget

        # Populate Widgets with Existing Data (for Edit Mode)
        if self.data_dict:
            for field, value in self.data_dict.items():
                if field not in self.field_name_to_input_widgets:
                    continue

                self.set_input_value(field, value)

        # Create Submit Button
        self.submit_button = QtWidgets.QPushButton("Submit")

        # Add Widgets to Layouts
        # ----------------------
        # Add the scroll area and button to the main layout
        main_layout.addWidget(scroll_area)
        main_layout.addWidget(self.submit_button, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect signals to slots
        self.submit_button.clicked.connect(self.update_record)

    # Public Methods
    # --------------
    def update_record(self):
        """Handle the submission of the form.
        """
        new_values = self.get_record_data()

        # Check only required fields, excluding INTEGER PRIMARY KEY fields
        required_fields = [
            field_name for field_name, field_info in self.field_name_to_info.items()
            if field_info.is_not_null and not (field_info.type == 'INTEGER' and field_info.is_primary_key)
        ]

        if not all(new_values.get(field) is not None for field in required_fields):
            QtWidgets.QMessageBox.warning(self, "Error", "Please fill in all required fields.")
            return

        if self.data_dict:
            # Determine which fields have changed
            updated_data_dict = {field: new_value for field, new_value in new_values.items() if new_value != self.data_dict.get(field)}

            if not updated_data_dict:
                QtWidgets.QMessageBox.information(self, "No Changes", "No changes were made.")
                return

            # Get the primary key field name and its value
            pk_field = self.model.get_primary_keys()[0]
            pk_value = self.data_dict.get(pk_field)

            self.model.update_record(updated_data_dict, pk_value, pk_field, handle_m2m=bool(self.many_to_many_fields))

        else:
            # Filter out primary key fields and create a dictionary for insertion
            data_filtered = {
                field_name: new_values[field_name]
                for field_name, field_info in self.field_name_to_info.items()
                if not (field_info.type == 'INTEGER' and field_info.is_primary_key)
            }

            for track_field_name in self.many_to_many_fields.keys():
                if track_field_name not in new_values:
                    continue
                data_filtered[track_field_name] = new_values[track_field_name]

            # Insert the record using the updated insert_record method
            self.model.insert_record(data_filtered, handle_m2m=bool(self.many_to_many_fields))

        self.accept()

    def create_input_widget(self, field_info: 'FieldInfo') -> QtWidgets.QWidget:
        """Create an appropriate input widget based on the field information.
        """
        if field_info.is_foreign_key:
            # Handle foreign keys by offering a dropdown of related records
            fk = field_info.fk
            referenced_model = self.db_manager.get_model(fk.related_table)
            display_field = self.model.get_display_field(field_info.name)
            widget = QtWidgets.QComboBox()

            if display_field:
                # Case 1: Display field is set
                related_records = list(
                    referenced_model.query(
                        fields=[fk.related_field, display_field],
                    )
                )
                display_field_info = referenced_model.get_field(display_field)

                for record in related_records:
                    if not display_field_info.is_unique:
                        display_value = self.format_combined_display(
                            record[display_field],
                            record[fk.related_field],
                            fk.related_field
                        )
                    else:
                        display_value = record[display_field]

                    key_value = record[fk.related_field]
                    widget.addItem(display_value, key_value)

            else:
                # Case 2: Display field is NOT set
                related_records = list(
                    referenced_model.query(
                        fields=[fk.related_field],
                    )
                )

                for record in related_records:
                    key_value = record[fk.related_field]
                    display_value = str(key_value)  # Convert to string for display
                    widget.addItem(display_value, key_value)

            return widget

        # Handle Enum Fields
        if enum_table_name := self.db_manager.get_enum_table_name(self.model.name, field_info.name):
            enum_values = self.db_manager.get_enum_values(enum_table_name)
            widget = QtWidgets.QComboBox()
            widget.addItems(enum_values)
            return widget

        # Handle Different Data Types
        if field_info.type == "INTEGER":
            widget = QtWidgets.QSpinBox()
            widget.setRange(-2147483648, 2147483647)
            widget.setSpecialValueText("")
            return widget
        elif field_info.type == "REAL":
            widget = QtWidgets.QDoubleSpinBox()
            widget.setSpecialValueText("")
            return widget
        elif field_info.type == "TEXT":
            return QtWidgets.QLineEdit()
        elif field_info.type == "BLOB":
            return FileBrowseWidget()
        elif field_info.type == "DATETIME":
            return QtWidgets.QDateTimeEdit(QtCore.QDateTime.currentDateTime(), calendarPopup=True)
        else:
            return QtWidgets.QLineEdit()

    def format_combined_display(self, display_value: str, key_value: Union[int, str], key_name: str) -> str:
        """Format the display field combined with the key value and key name.
        """
        return f"{display_value} ({key_name}: {key_value})"

    def set_input_value(self, field_name: str, value: Any):
        """Set the value of the input widget associated with the given field name.
        """
        input_widget = self.field_name_to_input_widgets.get(field_name)
        field_info = self.field_name_to_info.get(field_name)

        if isinstance(input_widget, QtWidgets.QComboBox):
            if field_info and field_info.is_foreign_key:
                # If the field is a foreign key, find the corresponding display value
                fk = field_info.fk
                referenced_model = self.db_manager.get_model(fk.related_table)
                display_field = self.model.get_display_field(field_info.name)

                if display_field:
                    # Case 1: Display field is set
                    display_field_info = referenced_model.get_field(display_field)
                    display_text = referenced_model.query_one(
                        fields=[display_field],
                        condition={
                            fk.related_field: value,
                        },
                        as_dict=False,
                    )[0]
                    display_text = self.format_combined_display(display_text, value, fk.related_field) if display_field_info.is_unique else display_text

                    input_widget.setCurrentText(display_text)

                else:
                    # Case 2: Display field is NOT set
                    input_widget.setCurrentText(str(value))

        elif isinstance(input_widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
            if value is None or value == 'None':
                input_widget.clear()
            else:
                input_widget.setValue(value)

        elif isinstance(input_widget, QtWidgets.QLineEdit):
            input_widget.setText("" if value is None else str(value))

        elif isinstance(input_widget, QtWidgets.QDateTimeEdit):
            input_widget.setDateTime(QtCore.QDateTime.fromString(value, "yyyy-MM-dd HH:mm:ss") if value else QtCore.QDateTime.currentDateTime())

        elif isinstance(input_widget, QtWidgets.QListWidget):
            selected_values = set(value)
            for i in range(input_widget.count()):
                item = input_widget.item(i)
                item_value = item.data(QtCore.Qt.ItemDataRole.UserRole)
                item.setCheckState(QtCore.Qt.CheckState.Checked if item_value in selected_values else QtCore.Qt.CheckState.Unchecked)

    def get_record_data(self) -> Dict[str, Any]:
        """Retrieve data from all input widgets.
        """
        return {field: self.get_input_value(input_widget) for field, input_widget in self.field_name_to_input_widgets.items()}

    def get_input_value(self, input_widget: QtWidgets.QWidget) -> Any:
        """Retrieve the value from a single input widget.
        """
        if isinstance(input_widget, QtWidgets.QComboBox):
            return input_widget.currentData() or input_widget.currentText()
        elif isinstance(input_widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
            return input_widget.value()
        elif isinstance(input_widget, QtWidgets.QLineEdit):
            return input_widget.text() or None
        elif isinstance(input_widget, QtWidgets.QDateTimeEdit):
            return input_widget.dateTime().toString("yyyy-MM-dd HH:mm:ss") if input_widget.dateTime() != input_widget.minimumDateTime() else None
        elif isinstance(input_widget, FileBrowseWidget):
            return input_widget.get_value() or None
        elif isinstance(input_widget, QtWidgets.QListWidget):
            # Retrieve the checked items from the QListWidget
            selected_items = []
            for index in range(input_widget.count()):
                item = input_widget.item(index)
                if item.checkState() == QtCore.Qt.Checked:
                    selected_items.append(item.data(QtCore.Qt.ItemDataRole.UserRole) or item.text())
            return selected_items

        return None

    def create_many_to_many_widget(self, many_to_many_field: 'ManyToManyField') -> QtWidgets.QListWidget:
        """Create a QListWidget with checkable items for a many-to-many relationship.
        """
        widget = QtWidgets.QListWidget()

        # Get all possible related records
        display_field = self.model.get_display_field(many_to_many_field.track_field_name)
        referenced_model = self.db_manager.get_model(many_to_many_field.related_fk.related_table)
        related_records = referenced_model.query(
            fields=[many_to_many_field.local_fk.related_field, display_field],
        )

        # Add items to the list widget
        for record in related_records:
            item = QtWidgets.QListWidgetItem(record[display_field])
            item.setData(QtCore.Qt.ItemDataRole.UserRole, record[many_to_many_field.local_fk.related_field])
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)
            widget.addItem(item)

        return widget


# NOTE: WIP
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

class FunctionalColumnDialog(QtWidgets.QDialog):
    def __init__(self, db_manager, model: 'AbstractModel', sample_data, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.model = model
        self.sample_data = sample_data
        self.init_ui()

    def init_ui(self):
        """Initialize the UI components."""
        self.setWindowTitle("Create Functional Column")
        layout = QtWidgets.QVBoxLayout(self)

        # Column Selector
        self.column_selector = QtWidgets.QListWidget()
        self.column_selector.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.column_selector.addItems(self.model.get_field_names())
        layout.addWidget(QtWidgets.QLabel("Select Columns:"))
        layout.addWidget(self.column_selector)

        # Function Input
        self.function_input = QtWidgets.QLineEdit()
        self.function_input.setPlaceholderText("Enter function, e.g., <col1> - <col2>")
        layout.addWidget(QtWidgets.QLabel("Define Function:"))
        layout.addWidget(self.function_input)

        # Tree Widget for Preview
        self.preview_tree = QtWidgets.QTreeWidget()
        self.preview_tree.setColumnCount(len(self.sample_data[0]) + 1)  # +1 for the new column
        self.preview_tree.setHeaderLabels(list(self.sample_data[0].keys()) + ['New Column'])
        layout.addWidget(QtWidgets.QLabel("Preview:"))
        layout.addWidget(self.preview_tree)

        # Buttons
        self.create_button = QtWidgets.QPushButton("Create Column")
        self.create_button.clicked.connect(self.create_column)
        layout.addWidget(self.create_button)

        # Connect signals
        self.column_selector.itemSelectionChanged.connect(self.update_preview)
        self.function_input.textChanged.connect(self.auto_select_columns)
        self.function_input.textChanged.connect(self.update_preview)

        # Initial Preview
        self.update_preview()

    def auto_select_columns(self):
        """Automatically select columns in the list based on the function input."""
        function_text = self.function_input.text()
        used_columns = self.extract_used_columns(function_text)

        # Auto-select columns in the list widget
        for i in range(self.column_selector.count()):
            item = self.column_selector.item(i)
            item.setSelected(item.text() in used_columns)

    def extract_used_columns(self, function_text):
        """Extract column names used in the function."""
        # Use regex to find patterns like <col_name>
        return set(re.findall(r"<(.*?)>", function_text))

    def update_preview(self):
        """Update the tree preview of the functional column based on sample data."""
        selected_columns = [item.text() for item in self.column_selector.selectedItems()]
        function_text = self.function_input.text()

        # Clear previous items
        self.preview_tree.clear()

        # Check if the function is valid and safe
        try:
            for row in self.sample_data:
                preview_row = {col: row[col] for col in selected_columns if col in row}
                result = self.evaluate_function(function_text, preview_row)
                
                # Create tree widget items for each row
                item = QtWidgets.QTreeWidgetItem([str(row[col]) for col in row.keys()] + [str(result)])
                self.preview_tree.addTopLevelItem(item)

        except Exception as e:
            error_item = QtWidgets.QTreeWidgetItem(["Error: " + str(e)])
            self.preview_tree.addTopLevelItem(error_item)

    def evaluate_function(self, function_text, row):
        """Evaluate the function safely using the provided row data."""
        for col, value in row.items():
            function_text = function_text.replace(f"<{col}>", str(value))

        node = ast.parse(function_text, mode='eval')
        return self.safe_eval(node.body)

    def safe_eval(self, node):
        """Evaluate an expression node safely."""
        if isinstance(node, ast.BinOp):
            left = self.safe_eval(node.left)
            right = self.safe_eval(node.right)
            operator_func = SAFE_OPERATORS.get(type(node.op))
            if operator_func:
                return operator_func(left, right)
        elif isinstance(node, ast.Num):
            return node.n
        raise ValueError("Invalid expression")

    def create_column(self):
        """Create the new functional column in the database."""
        column_name, ok = QtWidgets.QInputDialog.getText(self, "Column Name", "Enter name for new column:")
        if ok and column_name:
            QtWidgets.QMessageBox.information(self, "Success", f"Column '{column_name}' created successfully.")
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "Column creation cancelled.")

class DatabaseViewWidget(DataViewWidget):

    LABEL: str = 'Database View'

    def __init__(self, db_manager: 'DatabaseManager' = None, parent: QtWidgets.QWidget = None, identifier: Optional[str] = None):
        super().__init__(parent, identifier)

        # Store the arguments
        self.db_manager = db_manager

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        self._base_model = None
        self._database = None

        if self.db_manager:
            self.set_database_manager(self.db_manager)

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.add_relation_column_menu = self.tree_widget.header_menu.addMenu('Add Relation Column')
        self.add_functional_column_action = self.tree_widget.header_menu.addAction('Add Functional Column')

        self.add_filter_menu = QtWidgets.QMenu(self)

        self.add_record_button = QtWidgets.QPushButton(TablerQIcon.file_plus, 'Add Record')
        self.delete_record_button = QtWidgets.QPushButton(TablerQIcon.file_minus, 'Delete Record')

        self.general_tool_bar.addWidget(self.add_record_button)
        self.general_tool_bar.addWidget(self.delete_record_button)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect signals to slots
        self.add_filter_button.clicked.connect(self.show_add_filter_menu)
        self.tree_widget.about_to_show_header_menu.connect(self.handle_header_context_menu)
        self.add_record_button.clicked.connect(self.show_add_record_dialog)
        self.delete_record_button.clicked.connect(self.delete_record)
        self.tree_widget.itemDoubleClicked.connect(self.edit_record)

        self.tree_widget.field_changed.connect(self.update_add_filter_menu)

        # NOTE: WIP
        self.add_functional_column_action.triggered.connect(self.open_functional_column_dialog)

    def show_add_filter_menu(self):
        """Show the add filter menu.
        """
        self.add_filter_menu.exec_(QtGui.QCursor.pos())

    def handle_header_context_menu(self, field_chain: str):
        """Handle the header context menu signal.

        Args:
            column_index (int): The index of the column where the context menu was requested.
        """
        self.add_relation_column_menu.clear()
        self.add_relation_column_menu.setDisabled(True)

        if not self._base_model:
            return

        # Retrieve related table model
        related_model_name = self._base_model.resolve_model(field_chain)
        if not related_model_name:
            return

        related_model = self.db_manager.get_model(related_model_name)

        # Create a menu action for each foreign key relation
        for related_field in related_model.field_names[1:]:
            self.add_relation_column_menu.addAction(
                related_field,
                partial(self.add_field, f"{field_chain}.{related_field}")
            )

        self.add_relation_column_menu.setEnabled(True)

    # NOTE: WIP
    def open_functional_column_dialog(self):
        """Open the Functional Column Dialog to create a new column.
        """
        if not self._base_model:
            QtWidgets.QMessageBox.warning(self, "Error", "No table selected.")
            return

        # Fetch sample data for preview (e.g., first 5 rows)
        sample_data = list(self._base_model.query())[:5]

        # Create and show the Functional Column Dialog
        dialog = FunctionalColumnDialog(self.db_manager, self._base_model, sample_data, self)
        dialog.exec_()

    def set_database_manager(self, db_manager: 'DatabaseManager'):
        """Set the database manager for handling database operations.
        """
        self.db_manager = db_manager
        self._database = self.db_manager.database if self.db_manager else None

    def set_model(self, model_name: str):
        """Set the current table and load its data.
        """
        if not model_name:
            self._base_model = None
            return

        self._base_model = self.db_manager.get_model(model_name)
        self._load_model_data()

    def _load_model_data(self):
        """Load the data for the current table into the tree widget.
        """
        if not self.db_manager or not self._base_model:
            return

        primary_key = self._base_model.get_primary_keys()
        fields = self._base_model.get_field_names()

        if not primary_key:
            primary_key = 'rowid'
            fields.insert(0, primary_key)

        self.tree_widget.clear()
        self.tree_widget.set_primary_key(primary_key)
        self.tree_widget.setHeaderLabels(fields)
        
        self.populate()

    def show_add_record_dialog(self):
        """Show the dialog to add a new record to the current table.
        """
        if not self._base_model:
            return

        dialog = AddEditRecordDialog(self.db_manager, self._base_model)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.populate()

    def edit_record(self, item: 'TreeWidgetItem', column):
        """Edit the selected record from the tree widget.
        """
        row_data = {self.tree_widget.headerItem().text(col): item.get_value(col) for col in range(self.tree_widget.columnCount())}
        dialog = AddEditRecordDialog(self.db_manager, self._base_model, row_data)

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.populate()

    # TODO: Add support composite pks
    def delete_record(self):
        """Delete the selected record from the database, supporting composite primary keys."""
        if not self._base_model:
            return

        if not (current_item := self.tree_widget.currentItem()):
            return

        # Get the primary key fields and their values
        pk_fields = self._base_model.get_primary_keys()
        pk_values = {pk_field: current_item[pk_field] for pk_field in pk_fields}

        # Construct a human-readable representation of the primary key(s) for the confirmation dialog
        pk_display = ", ".join(f"{field}: '{value}'" for field, value in pk_values.items())

        # Show confirmation dialog
        confirm = QtWidgets.QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete the record with {pk_display}?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if confirm == QtWidgets.QMessageBox.Yes:
            self._base_model.delete_record(pk_values)
            self.populate()

    def update_add_filter_menu(self):
        """Show a context menu with available columns for creating filters.
        """
        self.add_filter_menu.clear()

        for field in self.tree_widget.fields:
            action = self.add_filter_menu.addAction(field)
            action.triggered.connect(partial(self.create_filter_widget, field))

    def create_filter_widget(self, field_chain: str):
        """Create a filter widget based on the selected column and its data type.
        """
        # The column represents a relation, split to get the table and field names
        related_table, related_field = SQLQueryBuilder.resolve_model_field(
            self._base_model.name,
            field_chain=field_chain,
            relationships=self._database.get_relationships(self._base_model.name),
            as_tuple=True
        )
        field_type = self._database.get_field_type(related_table, related_field)

        if '.' in field_chain:
            # TODO: Handle the column based on its type if it is not TEXT
            # Fetch possible values from the related table
            possible_values = self._database.query(
                model_name=related_table,
                fields=related_field,
                distinct=True,
                as_dict=False,
            )

            # Create a MultiSelectFilterWidget with the possible values
            filter_widget = MultiSelectFilterWidget(filter_name=field_chain)
            filter_widget.add_items(list(possible_values))

        else:
            # Instantiate the filter widget
            filter_widget = FilterWidget.create_for_field(
                filter_name=field_chain,
                field_type=field_type,
            )

        if filter_widget:
            self.add_filter_widget(filter_widget)

    # TODO: Add a reference to the view to query this added relation column when fetching more data.
    def add_field(self, field_chain: str):
        """Add a field to the tree widget.
        """
        field_names = self.tree_widget.fields.copy()

        # Check if the field already exists
        if field_chain in field_names:
            return
        field_names.append(field_chain)
        self.tree_widget.setHeaderLabels(field_names)

        self.populate()

    def populate(self):
        generator = self._base_model.query(
            fields=self.tree_widget.fields,
            conditions=self.filter_bar_widget.get_query_conditions(),
        )
        self.tree_widget.set_generator(generator)


# Main Function
# -------------
def main():
    """Create the application and main window, and show the widget.
    """
    import sys
    from blackboard.utils.file_path_utils import FilePatternQuery

    # Create the application and the main window
    app = QtWidgets.QApplication(sys.argv)
    # Set theme of QApplication to the dark theme
    bb.theme.set_theme(app, 'dark')

    # Mock up data
    pattern = "blackboard/examples/projects/{project_name}/seq_{sequence_name}/{shot_name}/{asset_type}"
    work_file_query = FilePatternQuery(pattern)
    filters = {
        'project_name': ['ProjectA'],
        'shot_name': ['shot01', 'shot02'],
    }
    generator = work_file_query.query_files(filters)

    # Create an instance of the widget
    database_view_widget = DataViewWidget()
    database_view_widget.tree_widget.set_fields(work_file_query.fields)
    database_view_widget.search_widget.set_default_search_fields(['shot_name'])
    database_view_widget.tree_widget.create_thumbnail_column('file_path')
    database_view_widget.tree_widget.set_generator(generator)

    # Date Filter Setup
    date_filter_widget = widgets.DateFilterWidget(filter_name="Date")
    date_filter_widget.activated.connect(print)
    # Shot Filter Setup
    shot_filter_widget = widgets.MultiSelectFilterWidget(filter_name="Shot")
    sequence_to_shots = {
        "100": [
            "100_010_001", 
            "100_020_050",
        ],
        "101": [
            "101_022_232", 
            "101_023_200",
        ],
    }
    shot_filter_widget.add_items(sequence_to_shots)
    shot_filter_widget.activated.connect(print)

    # File Type Filter Setup
    file_type_filter_widget = widgets.FileTypeFilterWidget(filter_name="File Type")
    file_type_filter_widget.activated.connect(print)

    show_hidden_filter_widget = widgets.BooleanFilterWidget(filter_name='Show Hidden')
    show_hidden_filter_widget.activated.connect(print)

    # Filter bar
    database_view_widget.add_filter_widget(date_filter_widget)
    database_view_widget.add_filter_widget(shot_filter_widget)
    database_view_widget.add_filter_widget(file_type_filter_widget)
    database_view_widget.add_filter_widget(show_hidden_filter_widget)

    # Create the scalable view and set the tree widget as its central widget
    scalable_view = widgets.ScalableView(widget=database_view_widget)

    # Show the widget
    scalable_view.show()

    # Run the application
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
