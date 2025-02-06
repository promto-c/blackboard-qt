# Type Checking Imports
# ---------------------
from typing import TYPE_CHECKING, List, Optional, Dict
if TYPE_CHECKING:
    from .abstract_database import AbstractModel

# Standard Library Imports
# ------------------------
import sqlite3

# Local Imports
# -------------
from .sqlite_database import SQLiteDatabase
from .schema import RelationChain


# Class Definitions
# -----------------
# NOTE: WIP
class DatabaseManager:

    FIELD_TYPES = ["INTEGER", "REAL", "TEXT", "BLOB", "NULL", "DATETIME", "ENUM"]
    PRIMARY_KEY_TYPES = ["INTEGER", "TEXT"]

    DB_TYPE_TO_DATABASE = {
        'sqlite': SQLiteDatabase
    }

    def __init__(self, db_name: str, db_type: str = 'sqlite'):
        """Initialize a DatabaseManager instance to interact with a SQLite database.

        Args:
            db_name (str): The name of the SQLite database file.

        Raises:
            sqlite3.Error: If there is an error connecting to the database.
        """
        self._db_name = db_name

        self.database = self.DB_TYPE_TO_DATABASE.get(db_type)(db_name)
        self.connection = self.database.connection
        self.cursor = self.database.cursor

    # Table Manager
    # -------------
    def is_table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the current database.

        Args:
            table_name (str): The name of the table to check.

        Returns:
            bool: True if the table exists, False otherwise.
        """
        return self.database.is_table_exists(table_name)

    def create_table(self, table_name: str, fields: Dict[str, str]):
        """Create a new table in the database with specified fields.

        Args:
            table_name (str): The name of the table to create.
            fields (Dict[str, str]): A dictionary mapping field names to their SQLite data types.
        """
        return self.database.create_table(table_name, fields)

    def delete_table(self, table_name: str):
        """Delete an entire table from the database.

        Args:
            table_name (str): The name of the table to delete.
        """
        self.database.delete_table(table_name)

    def get_table_names(self) -> List[str]:
        """Retrieve the names of all tables in the database.

        Returns:
            List[str]: A list of table names present in the database.

        Raises:
            sqlite3.Error: If there is an error executing the SQL command.
        """
        return self.database.get_table_names()

    def get_view_names(self) -> List[str]:
        """Retrieve the names of all views in the database.

        Returns:
            List[str]: A list of view names present in the database.

        Raises:
            sqlite3.Error: If there is an error executing the SQL command.
        """
        return self.database.get_view_names()

    def get_field_type(self, table_name: str, field_name: str) -> str:
        """Retrieve the data type of a specific field in a specified table.

        Args:
            table_name (str): The name of the table.
            field_name (str): The name of the field.

        Returns:
            str: The data type of the field.
        """
        return self.database.get_field_type(table_name, field_name)

    def get_model(self, table_name: str) -> 'AbstractModel':
        return self.database.get_model(table_name)
    
    # Additional
    def create_junction_table(self, from_table: str, to_table: str, from_field: str = 'id', to_field: str = 'id',
                              junction_table_name: Optional[str] = None, track_field_name: str = None, track_field_vice_versa_name: str = None,
                              from_display_field: Optional[str] = None, to_display_field: Optional[str] = None,
                              track_vice_versa: bool = False):
        """Create a junction table to represent a many-to-many relationship between two tables.

        Args:
            from_table (str): The name of the first table involved in the relationship.
            to_table (str): The name of the second table involved in the relationship.
            from_field (str): The field in the first table that is referenced by the foreign key (default is 'id').
            to_field (str): The field in the second table that is referenced by the foreign key (default is 'id').
            junction_table_name (Optional[str]): The name of the junction table to be created. Defaults to '{from_table}_{to_table}' in alphabetical order.
            from_display_field (Optional[str]): The field from the "from" table to be used for display purposes.
            to_display_field (Optional[str]): The field from the "to" table to be used for display purposes.
            track_vice_versa (bool): Whether to track the relationship in both directions.

        Raises:
            sqlite3.Error: If there is an error executing the SQL command.
        """
        return self.database.create_junction_table(
            from_table, to_table, from_field, to_field,
            junction_table_name, track_field_name, track_field_vice_versa_name,
            from_display_field, to_display_field, track_vice_versa
        )
    # -------------

    # TODO: May obsolete
    def get_existing_enum_tables(self) -> List[str]:
        """Get a list of existing enum tables.

        Returns:
            List[str]: A list of table names that match the 'enum_%' pattern.
        """
        self.database.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'enum_%'")
        return [row[0] for row in self.cursor.fetchall()]

    def get_enum_table_name(self, table_name: str, field_name: str) -> Optional[str]:
        """Retrieve the name of the enum table associated with a given field.
        """
        try:
            self.database.cursor.execute('''
                SELECT enum_table_name FROM _meta_enum_field
                WHERE table_name = ? AND field_name = ?;
            ''', (table_name, field_name))
        except sqlite3.OperationalError:
            pass

        if not (results := self.database.cursor.fetchone()):
            return

        return results[0]

    def get_enum_values(self, enum_table_name: str) -> List[str]:
        """Retrieve all values from an enum table.

        Args:
            enum_table_name (str): The name of the enum table.

        Returns:
            List[str]: A list of enum values.

        Raises:
            sqlite3.Error: If there is an error executing the SQL command.
        """
        enum_model = self.get_model(enum_table_name)
        return enum_model.get_possible_values('value')

    def create_enum_table(self, table_name: str, values: List[str]):
        """Create a table to store enum values.

        Args:
            enum_name (str): The name of the enum.
            values (List[str]): The values of the enum.

        Raises:
            sqlite3.Error: If there is an error executing the SQL command.
        """
        if not table_name.isidentifier():
            raise ValueError("Invalid enum name")

        self.database.cursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT UNIQUE)")

        # Insert enum values
        for value in values:
            self.database.cursor.execute(f"INSERT OR IGNORE INTO {table_name} (value) VALUES (?)", (value,))

        self.connection.commit()

# NOTE: WIP
class ViewModel:
    """A class that constructs and executes SQL queries based on specified tables, fields, and relationships."""
    def __init__(self, db_manager: 'DatabaseManager'):
        self._db_manager = db_manager
        self._database = db_manager._database
        self._connection = self._database.connection
        self._table_name = ''
        self._selected_fields = []
        self._relation_chains = []
        self._join_tables = set()
        self._aliases = {}
        self._alias_counter = 1

    def set_table(self, table_name: str):
        """Set the base table for the query."""
        if not table_name.isidentifier():
            raise ValueError("Invalid table name")
        self._table_name = table_name

    def set_fields(self, field_list: List[str]):
        """Set the fields to select from the base table."""
        if not all(field.isidentifier() for field in field_list):
            raise ValueError("Invalid field name in field list")
        self._selected_fields.extend(field_list)

    def add_relation_field(self, field_chain: str):
        """Add a related field to select, specifying the chain of relationships."""
        # Parse the relation chain using RelationChain class
        relation_chain = RelationChain.parse(field_chain, self._db_manager)
        self._relation_chains.append(relation_chain)
        # Cache join tables
        for step in relation_chain.steps:
            self._join_tables.add((step.local_table, step.foreign_key, step.related_table, step.related_field))
        # Add the select fields
        self._selected_fields.extend(relation_chain.select_fields)

    def prepare_query(self) -> str:
        """Prepare the SQL query based on the set table, fields, and relationships."""
        if not self._table_name:
            raise ValueError("Table name is not set.")
        # Start building the query
        query = f"SELECT "
        fields = []
        # Add fields from the base table
        for field in self._selected_fields:
            if '.' not in field:
                fields.append(f"{self._table_name}.{field}")
            else:
                # If field is already qualified, use it as is
                fields.append(field)
        query += ', '.join(fields)
        query += f" FROM {self._table_name} AS {self._table_name}"
        # Add JOINs
        join_clauses = []
        for relation_chain in self._relation_chains:
            current_table = self._table_name
            current_alias = self._aliases.get(current_table, current_table)
            for step in relation_chain.steps:
                # Generate an alias for the referenced table if not already aliased
                if step.related_table not in self._aliases:
                    alias = f"{step.related_table}_alias{self._alias_counter}"
                    self._alias_counter += 1
                    self._aliases[step.related_table] = alias
                else:
                    alias = self._aliases[step.related_table]
                # Build the JOIN clause
                join_clause = f" LEFT JOIN {step.related_table} AS {alias} ON {current_alias}.{step.foreign_key} = {alias}.{step.related_field}"
                join_clauses.append(join_clause)
                # Update current table and alias
                current_alias = alias
                current_table = step.related_table
        # Append the JOIN clauses to the query
        query += ' '.join(join_clauses)
        return query

    def execute(self):
        """Execute the prepared query and return the results."""
        query = self.prepare_query()
        cursor = self._database.connection.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        return results
