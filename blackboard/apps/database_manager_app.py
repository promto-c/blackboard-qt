# Type Checking Imports
# ---------------------
from typing import TYPE_CHECKING, List, Tuple, Optional, Dict
if TYPE_CHECKING:
    from blackboard.utils.database.abstract_database import AbstractModel

# Standard Library Imports
# ------------------------
import os
import sys

# Third Party Imports
# -------------------
from qtpy import QtCore, QtGui, QtWidgets
from tablerqicon import TablerQIcon

# Local Imports
# -------------
from blackboard.utils.database import DatabaseManager, FieldInfo, ManyToManyField
from blackboard.widgets.main_window import MainWindow
from blackboard.widgets import TreeWidgetItem, DatabaseViewWidget
from blackboard.widgets.header_view import SearchableHeaderView
from blackboard.widgets.list_widget import EnumListWidget
from blackboard.widgets.label import LabelEmbedderWidget
from blackboard.widgets.button import ItemOverlayButton


# Class Definitions
# -----------------
class AddTableDialog(QtWidgets.QDialog):
    """
    UI Design:
    
    +--------------------------------------+
    |           Add Table                  |
    +--------------------------------------+
    | Table Name: [____________________]   |
    |                                      |
    | Primary Key Field:                   |
    |                                      |
    |   Name: [____________________]       |
    |   Type: [INTEGER      v]             |
    |                                      |
    | [ Create Table ]                     |
    +--------------------------------------+
    
    UI Components:
    - Table Name Input: QLineEdit for entering the table name.
    - Primary Key Field: Inputs for defining the primary key field:
      - Name: QLineEdit for the primary key field name.
      - Type: QComboBox for selecting the data type (e.g., INTEGER).
      - Autoincrement: QCheckBox for enabling auto-increment if the type is INTEGER.
    - Create Table Button: QPushButton to create the table with the primary key field.
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)

        # Store the arguments
        self.db_manager = db_manager

        # Initialize setup
        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setWindowTitle("Add Table")

        # Create Layouts
        # --------------
        layout = QtWidgets.QVBoxLayout(self)

        # Create Widgets
        # --------------
        # Table Name Section
        self.table_name_input = QtWidgets.QLineEdit()
        self.table_name_label = LabelEmbedderWidget(self.table_name_input, "Table Name")

        # Primary Key Field Section
        self.primary_key_name_input = QtWidgets.QLineEdit("id")
        self.primary_key_name_label = LabelEmbedderWidget(self.primary_key_name_input, "Primary Key Name")

        self.primary_key_type_dropdown = QtWidgets.QComboBox()
        self.primary_key_type_dropdown.addItems(DatabaseManager.PRIMARY_KEY_TYPES)
        self.primary_key_type_label = LabelEmbedderWidget(self.primary_key_type_dropdown, "Type")

        # Create Table Button
        self.create_table_button = QtWidgets.QPushButton("Create Table")

        # Add Widgets to Layouts
        # ----------------------
        layout.addWidget(self.table_name_label)
        layout.addWidget(self.primary_key_name_label)
        layout.addWidget(self.primary_key_type_label)
        layout.addStretch()
        layout.addWidget(self.create_table_button)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect signals to slots
        self.create_table_button.clicked.connect(self.add_table)

    # Public Methods
    # --------------
    def add_table(self):
        table_name = self.table_name_input.text()
        primary_key_name = self.primary_key_name_input.text()
        primary_key_type = self.primary_key_type_dropdown.currentText()

        primary_key_definition = f"{primary_key_type} PRIMARY KEY".strip()

        self.db_manager.create_table(table_name, {primary_key_name: primary_key_definition})

        self.accept()

class AddFieldDialog(QtWidgets.QDialog):
    """
    UI Design:
    
    +--------------------------------------+
    |              Add Field               |
    +--------------------------------------+
    | Field Name: [____________________]   |
    |                                      |
    | Field Type: [INTEGER      v]         |
    |                                      |
    | [ ] NOT NULL                         |
    |                                      |
    | Select Enum Table:                   |
    | [enum_table_dropdown]                |
    |                                      |
    | Enum Values:                         |
    | +----------------------------+       |
    | | [Value 1         ] [ - ] [^] [v]   |
    | | [Value 2         ] [ - ] [^] [v]   |
    | | [Value 3         ] [ - ] [^] [v]   |
    | +----------------------------+       |
    | [ Add New Value ]                    |
    |                                      |
    |                (Add Button)          |
    |                [ Add Field ]         |
    +--------------------------------------+
    """

    WINDOW_TITLE = 'Add Field'

    def __init__(self, db_manager: DatabaseManager, model: 'AbstractModel', parent=None):
        super().__init__(parent)

        # Store the arguments
        self.db_manager = db_manager
        self.model = model

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        self.existing_enum_tables = ["Create New Enum Table"] + self.db_manager.get_existing_enum_tables()
        self.use_existing_enum = False

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setWindowTitle(self.WINDOW_TITLE)

        # Create Layouts
        # --------------
        layout = QtWidgets.QVBoxLayout(self)

        # Create Widgets
        # --------------
        self.field_name_input = QtWidgets.QLineEdit()
        self.field_name_label = LabelEmbedderWidget(self.field_name_input, "Field Name")

        self.field_type_dropdown = QtWidgets.QComboBox()
        self.field_type_dropdown.addItems(DatabaseManager.FIELD_TYPES)
        self.field_type_label = LabelEmbedderWidget(self.field_type_dropdown, "Field Type")

        self.enum_table_dropdown = QtWidgets.QComboBox()
        self.enum_table_dropdown.addItems(self.existing_enum_tables)
        self.enum_table_label = LabelEmbedderWidget(self.enum_table_dropdown, "Enum Table")

        self.enum_list_widget = EnumListWidget(self)
        self.enum_values_label = LabelEmbedderWidget(self.enum_list_widget, "Enum Values")
        self.add_enum_value_button = QtWidgets.QPushButton("Add New Value")

        self.not_null_checkbox = QtWidgets.QCheckBox("NOT NULL")
        self.unique_checkbox = QtWidgets.QCheckBox("UNIQUE")
        self.add_button = QtWidgets.QPushButton("Add Field")

        # Add Widgets to Layouts
        # ----------------------
        layout.addWidget(self.field_name_label)
        layout.addWidget(self.field_type_label)

        layout.addWidget(self.enum_table_label)
        layout.addWidget(self.enum_values_label)
        layout.addWidget(self.add_enum_value_button)
        layout.addWidget(self.not_null_checkbox)
        layout.addWidget(self.unique_checkbox)

        layout.addStretch()
        layout.addWidget(self.add_button)
        
        # Hide enum-related fields by default
        self.toggle_enum_fields(False)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect signals to slots
        self.field_name_input.textChanged.connect(lambda text: self.add_button.setEnabled(bool(text)))
        self.field_type_dropdown.currentTextChanged.connect(self.toggle_enum_input)
        self.enum_table_dropdown.currentIndexChanged.connect(self.update_enum_list_based_on_selection)
        self.add_enum_value_button.clicked.connect(lambda: self.enum_list_widget.add_item())
        self.add_button.clicked.connect(self.add_field)

        self.add_button.setEnabled(False)

    # Public Methods
    # --------------
    def toggle_enum_input(self, field_type):
        is_enum = field_type == "ENUM"
        self.toggle_enum_fields(is_enum)

    def toggle_enum_fields(self, visible):
        self.enum_table_label.setVisible(visible)
        self.enum_values_label.setVisible(visible)
        self.add_enum_value_button.setVisible(visible and not self.use_existing_enum)

    def update_enum_list_based_on_selection(self):
        selected_enum_table = self.enum_table_dropdown.currentText()
        if selected_enum_table == "Create New Enum Table":
            self.use_existing_enum = False
            self.enum_list_widget.clear()
            self.enum_list_widget.setEnabled(True)
        else:
            self.use_existing_enum = True
            enum_values = self.db_manager.get_enum_values(selected_enum_table)
            self.enum_list_widget.set_values(enum_values)
            self.enum_list_widget.setDisabled(True)
        self.toggle_enum_fields(True)

    def add_field(self):
        field_name = self.field_name_input.text().strip()
        field_type = self.field_type_dropdown.currentText()
        not_null = "NOT NULL" if self.not_null_checkbox.isChecked() else ""
        unique = "UNIQUE" if self.unique_checkbox.isChecked() else ""

        field_definition = ' '.join([field_type, not_null, unique])

        enum_values = None
        enum_table = None

        if field_type == "ENUM":
            if self.use_existing_enum:
                enum_table = self.enum_table_dropdown.currentText()
            else:
                enum_values = self.enum_list_widget.get_values()

        if field_name and field_definition:
            self.model.add_field(
                field_name,
                field_definition,
                enum_values=enum_values,
                enum_table_name=enum_table
            )

        self.accept()

class AddRelationFieldDialog(QtWidgets.QDialog):
    """
    UI Design:
    
    +--------------------------------------+
    |          Add Relation Field          |
    +--------------------------------------+
    | Field Name: [table_field           ] |
    |                                      |
    | Reference Table: [ Table1       v]   |
    |                                      |
    | Reference Key Field: [ id       v]   |
    |                                      |
    | Reference Display Field: [ name   v] |
    |                                      |
    | [ ] NOT NULL                         |
    |                                      |
    | Relationship Type: [Many-to-One  v]  |
    |                                      |
    |                (Add Button)          |
    |       [ Add Relation Field ]         |
    +--------------------------------------+
    """

    DEFAULT_DISPLAY_NAME = 'name'

    def __init__(self, db_manager: DatabaseManager, model: 'AbstractModel', parent=None):
        super().__init__(parent)

        # Store the arguments
        self.db_manager = db_manager
        self.local_model = model

        # Initialize setup
        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setWindowTitle("Add Relation Field")

        # Create Layouts
        # --------------
        layout = QtWidgets.QVBoxLayout(self)

        # Create Widgets
        # --------------
        self.field_name_input = QtWidgets.QLineEdit()
        self.field_name_label = LabelEmbedderWidget(self.field_name_input, "Field Name")

        self.table_dropdown = QtWidgets.QComboBox()
        
        # Exclude current table from the list of reference tables
        table_names = self.db_manager.get_table_names()
        table_names.remove(self.local_model.name)
        self.table_dropdown.addItems(table_names)
        self.table_dropdown.setCurrentIndex(-1)
        self.table_label = LabelEmbedderWidget(self.table_dropdown, "Reference Table:")

        self.key_field_dropdown = QtWidgets.QComboBox()
        self.key_field_label = LabelEmbedderWidget(self.key_field_dropdown, "Reference Key Field")

        self.display_field_dropdown = QtWidgets.QComboBox()
        self.display_field_label = LabelEmbedderWidget(self.display_field_dropdown, "Reference Display Field")

        self.relationship_type_dropdown = QtWidgets.QComboBox()
        self.relationship_type_dropdown.addItems(["Many-to-One", "One-to-One"])
        self.relationship_type_label = LabelEmbedderWidget(self.relationship_type_dropdown, "Relationship Type")

        self.not_null_checkbox = QtWidgets.QCheckBox("NOT NULL")

        self.add_button = QtWidgets.QPushButton("Add Relation Field")

        # Add Widgets to Layouts
        # ----------------------
        layout.addWidget(self.field_name_label)
        layout.addWidget(self.table_label)
        layout.addWidget(self.key_field_label)
        layout.addWidget(self.display_field_label)
        layout.addWidget(self.relationship_type_label)
        layout.addWidget(self.not_null_checkbox)
        layout.addStretch()
        layout.addWidget(self.add_button)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        self.field_name_input.textChanged.connect(self._handle_add_button_state)
        self.table_dropdown.currentTextChanged.connect(self._handle_add_button_state)
        self.key_field_dropdown.currentTextChanged.connect(self._handle_add_button_state)

        self.table_dropdown.currentTextChanged.connect(self._update_fields)
        self.key_field_dropdown.currentTextChanged.connect(self._update_field_name)

        self.add_button.clicked.connect(self.add_relation_column)

        self._handle_add_button_state()

    # Public Methods
    # --------------
    def add_relation_column(self):
        field_name = self.field_name_input.text()
        reference_table = self.table_dropdown.currentText()
        key_field = self.key_field_dropdown.currentText()
        display_field = self.display_field_dropdown.currentText()
        relationship_type = self.relationship_type_dropdown.currentText()
        is_not_null = self.not_null_checkbox.isChecked()

        # Fetch the type of the referenced key field
        field_definition = self.db_manager.get_field_type(reference_table, key_field)

        if is_not_null:
            field_definition += " NOT NULL"

        if relationship_type == "Many-to-One":
            self.local_model.add_field(
                field_name,
                field_definition,
                foreign_key=f"{reference_table}({key_field})"
            )

        elif relationship_type == "One-to-One":
            # Add the column with a UNIQUE constraint
            self.local_model.add_field(
                field_name,
                field_definition + ' UNIQUE',
                foreign_key=f"{reference_table}({key_field})"
            )

        if display_field != key_field:
            # Store the display field information
            self.local_model.add_display_field(field_name, display_field)

        self.accept()

    # Private Methods
    # ---------------
    def _handle_add_button_state(self, text: str = ''):
        if not text.strip():
            self.add_button.setDisabled(True)
        elif self.field_name_input.text() and self.table_dropdown.currentText() and self.key_field_dropdown.currentText():
            self.add_button.setEnabled(True)

    # TODO: Handle composite primary keys
    def _update_fields(self, referenced_table_name: str = None):
        referenced_table_name = referenced_table_name or self.table_dropdown.currentText()
        if not referenced_table_name:
            return
        
        referenced_model = self.db_manager.get_model(referenced_table_name)

        # Retrieve primary keys and unique fields
        primary_keys = referenced_model.get_primary_keys()
        unique_fields = referenced_model.get_unique_fields()

        # Combine unique fields and primary keys
        reference_fields = primary_keys + unique_fields
        reference_display_fields = referenced_model.get_field_names(include_fk=False, include_m2m=False)

        # Clear and populate the dropdowns
        self.key_field_dropdown.clear()
        self.key_field_dropdown.addItems(reference_fields)
        self.display_field_dropdown.clear()
        self.display_field_dropdown.addItems(reference_display_fields)
        self.display_field_dropdown.setCurrentText(self.DEFAULT_DISPLAY_NAME if self.DEFAULT_DISPLAY_NAME in reference_display_fields else reference_display_fields[0])

    def _update_field_name(self, field_name: str):
        if not field_name:
            return
        self.field_name_input.setText(f"{self.table_dropdown.currentText()}_{field_name}")

class AddManyToManyFieldDialog(QtWidgets.QDialog):
    """Dialog for adding a Many-to-Many field between two tables.

    UI Design:
    
    +--------------------------------------+
    |        Add Many-to-Many Field        |
    +--------------------------------------+
    | Junction Table Name: [_____________] |
    |                                      |
    | From Table: [Table1             v]   |
    |                                      |
    | From Key Field: [id             v]   |
    |                                      |
    | From Display Field: [name       v]   |
    |                                      |
    | To Table: [Table2               v]   |
    |                                      |
    | To Key Field: [id               v]   |
    |                                      |
    | To Display Field: [name         v]   |
    |                                      |
    | Track Vice Versa: [ ]                |
    |                                      |
    |                (Add Button)          |
    |       [ Add Many-to-Many Field ]     |
    +--------------------------------------+
    """

    DEFAULT_DISPLAY_NAME = 'name'

    def __init__(self, db_manager: DatabaseManager, local_model: 'AbstractModel', parent=None):
        super().__init__(parent)

        # Store the arguments
        self.db_manager = db_manager
        self.local_model = local_model

        # Initialize setup
        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setWindowTitle("Add Many-to-Many Field")

        # Create Layouts
        layout = QtWidgets.QVBoxLayout(self)

        # Create Widgets
        self.junction_table_input = QtWidgets.QLineEdit()
        self.junction_table_label = LabelEmbedderWidget(self.junction_table_input, "Junction Table Name")

        self.from_table_dropdown = QtWidgets.QComboBox()
        self.from_table_dropdown.addItems([self.local_model.name])
        self.from_table_dropdown.setEnabled(False)
        self.from_key_field_dropdown = QtWidgets.QComboBox()
        self.from_display_field_dropdown = QtWidgets.QComboBox()

        self.to_table_dropdown = QtWidgets.QComboBox()
        table_names = self.db_manager.get_table_names()
        table_names.remove(self.local_model.name)
        self.to_table_dropdown.addItems(table_names)
        self.to_table_dropdown.setCurrentIndex(-1)
        self.to_table_label = LabelEmbedderWidget(self.to_table_dropdown, "To Table")

        self.to_key_field_dropdown = QtWidgets.QComboBox()
        self.to_display_field_dropdown = QtWidgets.QComboBox()

        self.track_vice_versa_checkbox = QtWidgets.QCheckBox("Track Vice Versa")

        self.add_button = QtWidgets.QPushButton("Add Many-to-Many Field")

        # Add Widgets to Layouts
        layout.addWidget(self.junction_table_label)
        layout.addWidget(self.from_table_dropdown)
        layout.addWidget(LabelEmbedderWidget(self.from_key_field_dropdown, "From Key Field"))
        layout.addWidget(LabelEmbedderWidget(self.from_display_field_dropdown, "From Display Field"))
        layout.addWidget(self.to_table_label)
        layout.addWidget(LabelEmbedderWidget(self.to_key_field_dropdown, "To Key Field"))
        layout.addWidget(LabelEmbedderWidget(self.to_display_field_dropdown, "To Display Field"))
        layout.addWidget(self.track_vice_versa_checkbox)
        layout.addStretch()
        layout.addWidget(self.add_button)

        # Initialize from_table key and display fields based on defaults
        self._init_from_table_fields()

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        self.to_table_dropdown.currentTextChanged.connect(self._update_to_table_fields)
        self.to_table_dropdown.currentTextChanged.connect(self._update_junction_table_name)
        self.add_button.clicked.connect(self.add_many_to_many_field)

    def _init_from_table_fields(self):
        """Initialize the 'from' table's key and display fields.
        """
        primary_keys = self.local_model.get_primary_keys()
        unique_fields = self.local_model.get_unique_fields()

        # Combine unique fields and primary keys
        reference_fields = primary_keys + unique_fields
        display_fields = self.local_model.get_field_names(include_fk=False, include_m2m=False)

        # Set default key and display fields for the "from" table
        self.from_key_field_dropdown.clear()
        self.from_key_field_dropdown.addItems(reference_fields)
        self.from_key_field_dropdown.setCurrentText('id' if 'id' in reference_fields else primary_keys[0] if primary_keys else reference_fields[0])

        self.from_display_field_dropdown.clear()
        self.from_display_field_dropdown.addItems(display_fields)
        self.from_display_field_dropdown.setCurrentText(self.DEFAULT_DISPLAY_NAME if self.DEFAULT_DISPLAY_NAME in display_fields else display_fields[0])

    def _update_to_table_fields(self):
        """Update the 'to' table's key and display fields based on the selected table."""
        table_name = self.to_table_dropdown.currentText()
        if not table_name:
            return
        
        model = self.db_manager.get_model(table_name)

        primary_keys = model.get_primary_keys()
        unique_fields = model.get_unique_fields()

        # Combine unique fields and primary keys
        reference_fields = primary_keys + unique_fields
        display_fields = model.get_field_names(include_fk=False, include_m2m=False)

        # Update the key and display fields for the "to" table
        self.to_key_field_dropdown.clear()
        self.to_key_field_dropdown.addItems(reference_fields)
        self.to_key_field_dropdown.setCurrentText('id' if 'id' in reference_fields else primary_keys[0] if primary_keys else reference_fields[0])

        self.to_display_field_dropdown.clear()
        self.to_display_field_dropdown.addItems(display_fields)
        self.to_display_field_dropdown.setCurrentText(self.DEFAULT_DISPLAY_NAME if self.DEFAULT_DISPLAY_NAME in display_fields else display_fields[0])

    def _update_junction_table_name(self):
        """Automatically set the junction table name based on selected tables.
        """
        related_table = self.to_table_dropdown.currentText()
        if related_table:
            # Sort table names alphabetically and join them with an underscore
            sorted_tables = sorted([self.local_model.name, related_table])
            junction_name = "_".join(sorted_tables)
            self.junction_table_input.setText(junction_name)

    def add_many_to_many_field(self):
        """Handle adding the many-to-many relationship field.
        """
        junction_table_name = self.junction_table_input.text()
        related_table = self.to_table_dropdown.currentText()
        local_field = self.from_key_field_dropdown.currentText()
        from_display_field = self.from_display_field_dropdown.currentText()
        related_field = self.to_key_field_dropdown.currentText()
        to_display_field = self.to_display_field_dropdown.currentText()
        track_vice_versa = self.track_vice_versa_checkbox.isChecked()

        self.db_manager.create_junction_table(
            from_table=self.local_model.name,
            to_table=related_table,
            from_field=local_field,
            to_field=related_field,
            junction_table_name=junction_table_name,
            track_field_name=f"{related_table}_{related_field}s",
            track_field_vice_versa_name=f"{self.local_model.name}_{local_field}s",
            from_display_field=from_display_field,
            to_display_field=to_display_field,
            track_vice_versa=track_vice_versa
        )

        self.accept()

class DBWidget(QtWidgets.QWidget):

    # Initialization and Setup
    # ------------------------
    def __init__(self):
        super().__init__()

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        # Attributes
        # ----------
        self.db_manager = None
        self.current_table = None
        self.field_name_to_info: Dict[str, 'FieldInfo'] = {}

        # Private Attributes
        # ------------------
        ...

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setWindowTitle("SQLite Database Manager")
        self.setGeometry(100, 100, 1200, 800)

        # Create Layouts
        # --------------
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # Create Widgets
        # --------------
        # Create a splitter
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        self.__init_left_widget()
        self.__init_data_view_widget()

        # Add Widgets to Layouts
        # ----------------------
        self.main_layout.addWidget(splitter)
        splitter.addWidget(self.left_widget)
        splitter.addWidget(self.data_view_widget)
        splitter.setStretchFactor(0, 0)  # widget_a gets a stretch factor of 1
        splitter.setStretchFactor(1, 2)  # widget_b gets a stretch factor of 2

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect signals to slots
        self.open_db_button.clicked.connect(self.open_database)
        self.create_db_button.clicked.connect(self.create_database)
        self.refresh_button.clicked.connect(self.refresh_data)

        self.add_table_button.clicked.connect(self.show_add_table_dialog)
        self.delete_table_button.triggered.connect(self.delete_table)
        self.tables_list_widget.currentItemChanged.connect(self.load_table_info)

        self.add_field_button.clicked.connect(self.show_add_field_dialog)
        self.add_relation_field_button.clicked.connect(self.show_add_relation_field_dialog)
        self.add_m2m_field_button.clicked.connect(self.show_add_many_to_many_field_dialog)
        self.delete_field_button.triggered.connect(self.delete_field)

    def __init_left_widget(self):
        """Create and configure the left widget.
        """
        # Create Layouts
        # --------------
        self.left_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.left_widget)

        top_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(top_layout)

        # Create Widgets
        # --------------
        self.db_path_line_edit = QtWidgets.QLineEdit(readOnly=True)
        self.db_path_label = LabelEmbedderWidget(self.db_path_line_edit, 'Database Path')

        self.open_db_button = QtWidgets.QPushButton(TablerQIcon.folder_open, '', toolTip="Open Database")
        self.create_db_button = QtWidgets.QPushButton(TablerQIcon.folder_plus, '', toolTip="Create Database")
        self.refresh_button = QtWidgets.QPushButton(TablerQIcon.refresh, '', toolTip="Refresh")
        self.add_table_button = QtWidgets.QPushButton(TablerQIcon.plus, '', toolTip="Add Table")

        self.tables_list_widget = QtWidgets.QListWidget()
        self.tables_label = LabelEmbedderWidget(self.tables_list_widget, 'Tables')
        self.tables_label.add_actions(self.add_table_button)
        self.delete_table_button = ItemOverlayButton()
        self.delete_table_button.register_to(self.tables_list_widget)

        self.add_field_button = QtWidgets.QPushButton(TablerQIcon.plus, '', toolTip="Add Field")
        self.add_relation_field_button = QtWidgets.QPushButton(TablerQIcon.link_plus, '', toolTip="Add Relation Field")
        self.add_m2m_field_button = QtWidgets.QPushButton(TablerQIcon.webhook, '', toolTip="Add Many-to-Many Field")

        self.fields_list_widget = QtWidgets.QListWidget()
        self.fields_label = LabelEmbedderWidget(self.fields_list_widget, 'Fields')
        self.fields_label.add_actions(self.add_m2m_field_button, self.add_relation_field_button, self.add_field_button)
        self.delete_field_button = ItemOverlayButton()
        self.delete_field_button.register_to(self.fields_list_widget)

        # Add Widgets to Layouts
        # ----------------------
        top_layout.addWidget(self.db_path_label)
        top_layout.addWidget(self.open_db_button)
        top_layout.addWidget(self.create_db_button)
        top_layout.addWidget(self.refresh_button)
        top_layout.setAlignment(self.db_path_label, QtCore.Qt.AlignmentFlag.AlignBottom)
        top_layout.setAlignment(self.open_db_button, QtCore.Qt.AlignmentFlag.AlignBottom)
        top_layout.setAlignment(self.create_db_button, QtCore.Qt.AlignmentFlag.AlignBottom)
        top_layout.setAlignment(self.refresh_button, QtCore.Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(self.tables_label)
        layout.addWidget(self.fields_label)

    def __init_data_view_widget(self):
        """Create and configure the data view widget.
        """
        # Create Widgets
        # --------------
        self.data_view_widget = QtWidgets.QWidget()
        data_view_layout = QtWidgets.QVBoxLayout(self.data_view_widget)

        self.data_view = DatabaseViewWidget(self.db_manager, parent=self)

        self.tree_data_widget = self.data_view.tree_widget

        # Add Widgets to Layouts
        # ----------------------
        data_view_layout.addWidget(self.data_view)

    def open_database(self):
        db_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Database", "", "SQLite Database Files (*.db *.sqlite)")
        if not db_name:
            return

        self.db_manager = DatabaseManager(db_name)
        self.db_path_line_edit.setText(db_name)
        self.load_table_and_view_names()

    def create_database(self):
        db_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Create Database", "", "SQLite Database Files (*.db *.sqlite)")
        if not db_name:
            return

        # Ensure the database file does not already exist
        if not os.path.exists(db_name):
            # Create an empty file
            open(db_name, 'w').close()
            self.db_manager = DatabaseManager(db_name)
            self.db_path_line_edit.setText(db_name)
            self.load_table_and_view_names()
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "Database file already exists.")

    def load_table_and_view_names(self):
        """Load the names of tables and views into the UI."""
        if not self.db_manager:
            return

        tables = self.db_manager.get_table_names()
        views = self.db_manager.get_view_names()
        self.data_view.set_database_manager(self.db_manager)

        self.tables_list_widget.clear()
        self.tables_list_widget.addItems(tables + views)

    def load_table_info(self, current_item: Optional[QtWidgets.QListWidgetItem] = None):
        """Load information about the selected table and display its columns and foreign keys.

        Args:
            current_item (Optional[QtWidgets.QListWidgetItem]): The currently selected item in the table list.

        Raises:
            ValueError: If there is an issue retrieving data from the database.
        """
        current_item = current_item or self.tables_list_widget.currentItem()

        if not current_item:
            return

        table_name = current_item.text()
        self.current_table = table_name
        self.current_model = self.db_manager.get_model(self.current_table)
        self.data_view.set_model(self.current_table)
        self.field_name_to_info = self.current_model.get_fields()

        self.fields_list_widget.clear()

        for field_info in self.field_name_to_info.values():
            # Display the column information
            column_definition = field_info.get_field_definition()

            if field_info.is_foreign_key:
                column_definition += f" (FK to {field_info.fk.related_table}.{field_info.fk.related_field})"

            self.fields_list_widget.addItem(column_definition)

        # TODO: Add Many-to-Many track fields to fields_list_widget
        many_to_many_fields = self.current_model.get_many_to_many_fields()
        for field_name, m2m in many_to_many_fields.items():
            column_definition = f"{field_name} ({m2m.junction_table})"
            self.fields_list_widget.addItem(column_definition)
        # ---

    def show_add_field_dialog(self):
        if not self.current_table:
            return

        dialog = AddFieldDialog(self.db_manager, self.current_model, self)
        if dialog.exec_():
            self.load_table_info()

    def show_add_relation_field_dialog(self):
        if not self.current_table:
            return

        dialog = AddRelationFieldDialog(self.db_manager, self.current_model, self)
        if dialog.exec_():
            self.load_table_info()

    def show_add_many_to_many_field_dialog(self):
        if not self.current_table:
            return

        dialog = AddManyToManyFieldDialog(self.db_manager, self.current_model, self)
        if dialog.exec_():
            self.load_table_info()

    def show_add_table_dialog(self):
        dialog = AddTableDialog(self.db_manager, self)
        if dialog.exec_():
            self.load_table_and_view_names()

    def delete_table(self, item: QtWidgets.QListWidgetItem):
        table_name = item.text()

        self.db_manager.delete_table(table_name)
        if table_name == self.current_table:
            self.current_table = None
        self.load_table_and_view_names()
        self.fields_list_widget.clear()
        self.tree_data_widget.clear()

    def delete_field(self, item: QtWidgets.QListWidgetItem):
        field_name = item.text().split()[0]
        self.current_model.delete_field(field_name)
        self.load_table_info()

    def refresh_data(self):
        self.load_table_and_view_names()
        if self.current_table:
            self.load_table_info()


if __name__ == '__main__':
    from blackboard import theme
    app = QtWidgets.QApplication(sys.argv)
    theme.set_theme(app, 'dark')
    widget = DBWidget()
    main_window = MainWindow(widget, use_scalable_view=True)
    main_window.show()
    sys.exit(app.exec_())
