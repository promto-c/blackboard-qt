
# Type Checking Imports
# ---------------------
from typing import TYPE_CHECKING, Generator, List, Tuple, Union, Optional, Dict, Any
if TYPE_CHECKING:
    from blackboard.enums.view_enum import SortOrder, GroupOperator

# Standard Library Imports
# ------------------------
import logging
import sqlite3
import json

# Local Imports
# -------------
from blackboard.utils.database.abstract_database import AbstractDatabase, AbstractModel
from blackboard.utils.database.schema import FieldInfo, ManyToManyField, ForeignKey
from blackboard.utils.database.sql_query_builder import SQLQueryBuilder, QueryContext, DataSerializer


# Class Definitions
# -----------------
class ContextAwareRow(sqlite3.Row):

    cursor: 'ContextAwareCursor'

    def __new__(cls, cursor: 'ContextAwareCursor', row: Tuple[Any, ...]) -> 'ContextAwareRow':
        obj = super().__new__(cls, cursor, row)
        obj.cursor = cursor
        return obj

    def __getitem__(self, key: str | int) -> Any:
        # Get the original value.
        value = super().__getitem__(key)

        if not (context := self.cursor.context):
            return value

        if isinstance(key, int):
            field_chain = context.get_field_by_index(key)
        else:
            field_chain = context.get_field_by_alias(key)
        model_field_name = context.resolve_model_field(field_chain)

        if field_chain in context.grouped_fields:
            value = json.loads(value)

        serializer = context.serializers.get(model_field_name)
        if not serializer:
            return value

        if value in context.grouped_fields:
            value = [serializer.deserialize(v) for v in value]
        else:
            value = serializer.deserialize(value)

        return value


class ContextAwareCursor(sqlite3.Cursor):

    def __init__(self, connection: sqlite3.Connection, context: 'QueryContext' = None):
        super().__init__(connection)
        self.row_factory = ContextAwareRow
        self.context = context

    def set_query_context(self, context: 'QueryContext'):
        self.context = context


class SQLiteDatabase(AbstractDatabase):

    # Initialization and Setup
    # ------------------------
    def __init__(self, database: str, read_only: bool = False, check_same_thread: bool = False):
        """Initialize the AbstractDatabase with a database name.

        Args:
            db_name (str): The name of the database file or connection string.
        """
        self._database = database
        if read_only:
            self._connection = sqlite3.connect(f'file:///{self._database}?mode=ro' ,uri=True, check_same_thread=check_same_thread)
        else:
            self._connection = sqlite3.connect(self._database, check_same_thread=check_same_thread)

    # Class Properties
    # ----------------
    @property
    def database(self) -> str:
        """Get the current database.
        """
        return self._database

    @property
    def connection(self) -> sqlite3.Connection:
        """Get the current database connection.
        """
        return self._connection

    def cursor(self) -> 'ContextAwareCursor':
        return ContextAwareCursor(self._connection)

    # Public Methods
    # --------------
    def execute_raw(self, query: str, parameters: Optional[List[Any]] = None) -> sqlite3.Cursor:
        """Execute a raw SQL query that modifies data (INSERT, UPDATE, DELETE).
        """
        cursor = self._connection.cursor()
        try:
            if parameters:
                cursor.execute(query, parameters)
            else:
                cursor.execute(query)
            self._connection.commit()
            return cursor
        finally:
            cursor.close()

    def create_junction_table(self, from_table: str, to_table: str, from_field: str = 'id', to_field: str = 'id',
                              junction_table_name: Optional[str] = None, track_field_name: str = None, track_field_vice_versa_name: str = None,
                              from_display_field: Optional[str] = None, to_display_field: Optional[str] = None,
                              track_vice_versa: bool = False) -> 'AbstractModel':
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
        # Assign the default junction table name if not provided
        junction_table_name = junction_table_name or f"{'_'.join(sorted([from_table, to_table]))}"
        track_field_name = track_field_name or f"{to_table}_{to_field}s"
        track_field_vice_versa_name = track_field_vice_versa_name or f"{from_table}_{from_field}s"

        # Set keys
        from_table_key = f"{from_table}_{from_field}"
        to_table_key = f"{to_table}_{to_field}"

        # Construct the SQL for creating the junction table
        sql = f"""
            CREATE TABLE IF NOT EXISTS {junction_table_name} (
                {from_table_key} TEXT NOT NULL,
                {to_table_key} TEXT NOT NULL,
                PRIMARY KEY ({from_table_key}, {to_table_key}),
                FOREIGN KEY ({from_table_key}) REFERENCES {from_table}({from_field}) ON DELETE CASCADE,
                FOREIGN KEY ({to_table_key}) REFERENCES {to_table}({to_field}) ON DELETE CASCADE
            );
        """
        # Execute the SQL command
        self.execute_raw(sql)

        self._create_meta_many_to_many_table()

        # Track the many-to-many relationship in the metadata table
        self.execute_raw('''
            INSERT OR REPLACE INTO _meta_many_to_many (
                from_table, track_field_name, junction_table
            ) VALUES (?, ?, ?);
        ''', (from_table, track_field_name, junction_table_name))

        # Add display field metadata for the "to" table
        if to_display_field:
            junction_model = self.get_model(junction_table_name)
            junction_model.add_display_field(to_table_key, to_display_field)

            from_model = self.get_model(from_table)
            from_model.add_display_field(track_field_name, to_display_field)

        # Optionally track the relationship in the reverse direction
        if track_vice_versa:
            self.execute_raw('''
                INSERT OR REPLACE INTO _meta_many_to_many (
                    from_table, track_field_name, junction_table
                ) VALUES (?, ?, ?);
            ''', (to_table, track_field_vice_versa_name, junction_table_name))

            # Add display field metadata for the "from" table
            if from_display_field:
                junction_model = self.get_model(junction_table_name)
                junction_model.add_display_field(from_table_key, from_display_field)

                to_model = self.get_model(to_table)
                to_model.add_display_field(track_field_vice_versa_name, from_display_field)

        return self.get_model(junction_table_name)

    # Private Methods
    # ---------------
    def _create_meta_many_to_many_table(self):
        """Create the meta table to store many-to-many relationship information.
        """
        fields = {
            'from_table': 'TEXT NOT NULL',
            'track_field_name': 'TEXT NOT NULL',
            'junction_table': 'TEXT NOT NULL',
            'PRIMARY KEY': '(from_table, track_field_name)'
        }
        self.create_table('_meta_many_to_many', fields)

    # Overridden Methods
    # ------------------
    def get_foreign_keys(self, model_name: str) -> Generator[ForeignKey, None, None]:
        """Retrieve foreign key constraints for the specified table.

        Args:
            model_name (str): The name of the table from which to retrieve foreign keys.

        Yields:
            ForeignKey: Each foreign key constraint as a `ForeignKey` instance.
        
        Raises:
            ValueError: If the table name is not a valid Python identifier.
        """
        if not model_name or not model_name.isidentifier():
            raise ValueError("Invalid model name")

        # Convert each row (sqlite3.Row) to a dictionary, then create a ForeignKey instance.
        yield from (
            ForeignKey.from_dict(row, local_table=model_name)
            for row in self.query_raw(f"PRAGMA foreign_key_list('{model_name}')")
        )

    def query_raw(self, query: str | QueryContext, parameters: Optional[List[Any]] = None,
                  as_dict: bool = True, is_single_field: bool = False) -> Generator[Dict[str, Any] | Tuple[Any, ...], None, None]:
        """Execute a raw SQL query and yield results as dictionaries or tuples.

        Args:
            query (str): The SQL query to execute.
            parameters (Optional[List[Any]]): A list of parameters to bind to the query.
                If None, the query is executed without parameters.
            as_dict (bool): If True, each row is returned as a dictionary mapping column names
                to values. If False, each row is returned as a tuple.

        Yields:
            Union[Dict[str, Any], Tuple[Any, ...]]: Each row from the query result.
        """
        cursor = self.cursor()
        if isinstance(query, QueryContext):
            context = query
            cursor.set_query_context(context)
            query = context.query
            parameters = context.parameters

        if parameters:
            cursor.execute(query, parameters)
        else:
            cursor.execute(query)

        try:
            if as_dict:
                yield from map(dict, cursor)
            elif is_single_field:
                yield from map(lambda x: x[0], cursor)
            else:
                yield from map(tuple, cursor)
        finally:
            cursor.close()

    def query(self, model_name: str, fields: Optional[List[str]] = None, 
              conditions: Optional[Dict[Union['GroupOperator', str], Any]] = None,
              relationships: Dict[str, str] = None, order_by: Optional[Dict[str, 'SortOrder']] = None,
              serializers: Optional[Dict[str, 'DataSerializer']] = None,
              limit: Optional[int] = None, as_dict: bool = True,
              ) -> Generator[Tuple[Any, ...] | Dict[str, Any], None, None]:
        """Retrieve data from a specified table as a generator.

        Args:
            fields (Optional[List[str]]): Specific fields to retrieve. Defaults to all fields.
            conditions (Optional[Dict[Union[GroupOperator, str], Any]]): SQL WHERE clause conditions.
            relationships (Optional[Dict[str, str]]): Relationship mappings.
            order_by (Optional[Dict[str, SortOrder]]): Fields and sort order.
            limit (Optional[int]): Maximum number of rows to retrieve.
            as_dict (bool): If True, yield rows as dictionaries; if False, as tuples.

        Yields:
            Tuple[Any, ...] | Dict[str, Any]: Each row from the query result.
        """
        is_single_field = isinstance(fields, str)
        if is_single_field:
            fields = [fields]

        # Merge provided relationships with default relationships.
        if relationships:
            relationships = self.get_relationships(model_name) | relationships
        else:
            relationships = self.get_relationships(model_name)

        if serializers:
            serializers = self.get_serializers(model_name) | serializers
        else:
            serializers = self.get_serializers(model_name)

        context = SQLQueryBuilder.build_context(
            model=model_name,
            fields=fields,
            conditions=conditions,
            relationships=relationships,
            serializers=serializers,
            order_by=order_by,
            limit=limit,
        )

        yield from self.query_raw(
            query=context, as_dict=as_dict, is_single_field=is_single_field,
        )

    def is_table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the current database.

        Args:
            table_name (str): The name of the table to check.

        Returns:
            bool: True if the table exists, False otherwise.
        """
        row = self.query_one(
            model_name='sqlite_master',
            fields=['name'],
            conditions={
                'type': 'table',
                'name': table_name
            }
        )

        return bool(row)

    def create_table(self, table_name: str, fields: Dict[str, str]) -> 'AbstractModel':
        """Create a new table in the database with specified fields.

        Args:
            table_name (str): The name of the table to create.
            fields (Dict[str, str]): A dictionary mapping field names to their SQLite data types.

        Raises:
            ValueError: If the table name is not a valid Python identifier.
            sqlite3.Error: If there is an error executing the SQL command.
        """
        if not table_name.isidentifier():
            raise ValueError("Invalid table name")

        fields_str = ', '.join([f"{name} {type_}" for name, type_ in fields.items()])
        self.execute_raw(f"CREATE TABLE IF NOT EXISTS {table_name} ({fields_str})")

        return self.get_model(table_name)

    def delete_table(self, table_name: str):
        """Delete an entire table from the database.

        Args:
            table_name (str): The name of the table to delete.

        Raises:
            ValueError: If the table name is not a valid Python identifier.
            sqlite3.Error: If there is an error executing the SQL command.
        """
        if not table_name.isidentifier():
            raise ValueError("Invalid table name")

        self.execute_raw(f"DROP TABLE IF EXISTS '{table_name}'")

    def get_table_names(self) -> List[str]:
        """Retrieve the names of all tables in the database.

        Returns:
            List[str]: A list of table names present in the database.

        Raises:
            sqlite3.Error: If there is an error executing the SQL command.
        """
        return list(
            self.query(
                model_name='sqlite_master',
                fields='name',
                conditions={
                    'type': 'table'
                },
                as_dict=False,
            )
        )

    def get_view_names(self) -> List[str]:
        """Retrieve the names of all views in the database.

        Returns:
            List[str]: A list of view names present in the database.

        Raises:
            sqlite3.Error: If there is an error executing the SQL command.
        """
        return list(
            self.query(
                model_name='sqlite_master',
                fields='name',
                conditions={
                    'type': 'view'
                },
                as_dict=False,
            )
        )

    def get_field_type(self, table_name: str, field_name: str) -> str:
        """Retrieve the data type of a specific field in a specified table.

        Args:
            table_name (str): The name of the table.
            field_name (str): The name of the field.

        Returns:
            str: The data type of the field.

        Raises:
            ValueError: If the table name or field name is not a valid Python identifier.
            sqlite3.Error: If there is an error executing the SQL command.
        """
        if not table_name.isidentifier() or not field_name.isidentifier():
            raise ValueError("Invalid table name or field name")

        return self.query_raw_one(
            "SELECT type FROM pragma_table_info(?) WHERE name = ?",
            (table_name, field_name),
            as_dict=False
        )[0]

    def get_model(self, table_name: str):
        return SQLiteModel(self, table_name)

    def close(self):
        """Close the database cursor and connection.

        This method ensures that both the cursor and the connection to the SQLite database
        are properly closed. It is idempotent, meaning that calling it multiple times
        will have no adverse effects.

        Raises:
            sqlite3.Error: If an error occurs while closing the cursor or connection.
        """
        try:
            if self._connection:
                self._connection.close()
                self._connection = None
                print("Connection closed successfully.")
        except sqlite3.Error as e:
            print(f"Error closing connection: {e}")
            raise

class SQLiteModel(AbstractModel):
    def __init__(self, database: SQLiteDatabase, model_name: str):
        super().__init__(database=database, model_name=model_name)

        self._connection = self._database.connection

    def get_unique_fields(self) -> List[str]:
        """Retrieve the names of fields with unique constraints in a specified table.

        Returns:
            List[str]: A set of field names that have unique constraints.

        Raises:
            ValueError: If the table name is not a valid Python identifier.
            sqlite3.Error: If there is an error executing the SQL command.
        """
        if not self.name.isidentifier():
            raise ValueError("Invalid table name")

        unique_fields = []

        # Iterate over the indexes and find those that are unique
        for index in self._database.query_raw(f"PRAGMA index_list({self.name})"):
            # Skip if the index is not unique
            if not index['unique']:
                continue  
            for field in self._database.query_raw(f"PRAGMA index_info({index['name']})"):
                unique_fields.append(field['name'])

        return unique_fields

    def get_fields(self, include_many_to_many: bool = False) -> Dict[str, 'FieldInfo']:
        """Retrieve all fields of the specified table, including unique constraints and many-to-many relationships.

        Args:
            include_many_to_many (bool): Whether to include many-to-many relationship fields. Defaults to False.

        Returns:
            Dict[str, FieldInfo]: A dictionary where keys are field names and values are FieldInfo dataclass instances, 
                representing the fields in the table and their properties.

        Raises:
            ValueError: If the table name is not a valid Python identifier.
            sqlite3.Error: If there is an error executing the SQL command.
        """
        if not self.name.isidentifier():
            raise ValueError("Invalid table name")

        # Retrieve field information
        fields = self._database.query_raw(f"PRAGMA table_info({self.name})", as_dict=False)

        # Get unique fields using the new method
        unique_fields = self.get_unique_fields()

        # Create a dictionary mapping field names to FieldInfo objects
        name_to_field_info = {field[1]: FieldInfo(*field, is_unique=(field[1] in unique_fields)) for field in fields}

        # Add foreign key information to the FieldInfo objects
        foreign_keys = self.get_foreign_keys()
        for foreign_key in foreign_keys:
            name_to_field_info[foreign_key.local_field].fk = foreign_key

        # Include many-to-many fields if requested
        if include_many_to_many:
            many_to_many_fields = self.get_many_to_many_fields()
            for field_name, m2m_field in many_to_many_fields.items():
                # Add the many-to-many field with a reference to the junction table
                name_to_field_info[field_name] = FieldInfo(
                    name=field_name,
                    type='MANY_TO_MANY',  # Use a custom type for many-to-many fields
                    m2m=m2m_field  # Store the many-to-many relationship info
                )

        return name_to_field_info

    def get_field(self, field_name: str) -> FieldInfo:
        """Get information for a specific field (column) in a table.

        Args:
            field_name (str): The name of the field to get information for.

        Returns:
            FieldInfo: The FieldInfo instance representing the field's information.

        Raises:
            ValueError: If the table or field name is invalid or the field does not exist.
            sqlite3.Error: If there is an error executing the SQL command.
        """
        if not field_name.isidentifier():
            raise ValueError("Invalid table or field name")

        # Try to retrieve field information for the specific field from the table's columns
        row = self._database.query_raw_one(
            f"SELECT * FROM pragma_table_info(?) WHERE name = ?",
            (self.name, field_name),
            as_dict=False
        )

        if row is not None:
            # Field exists in the table columns
            column_id, name, data_type, not_null, default_value, primary_key = row

            # Check if the field is unique
            unique_fields = self.get_unique_fields()
            is_unique = field_name in unique_fields

            # Initialize FieldInfo
            field_info = FieldInfo(
                cid=column_id,
                name=name,
                type=data_type,
                notnull=bool(not_null),
                dflt_value=default_value,
                pk=bool(primary_key),
                is_unique=is_unique
            )

            # Retrieve foreign key information for the field
            foreign_key = self.get_foreign_key(field_name)
            if foreign_key:
                field_info.fk = foreign_key
        else:
            # Field is not in the table's columns; check if it's a many-to-many relationship
            try:
                m2m_field = self.get_many_to_many_field(field_name)
                # Initialize FieldInfo with m2m field
                field_info = FieldInfo(
                    name=field_name,
                    m2m=m2m_field
                )
            except ValueError:
                # Field is neither a column nor a many-to-many relationship
                raise ValueError(f"Field '{field_name}' does not exist in table '{self.name}'")

        return field_info

    def get_field_names(self, include_fk: bool = True, include_m2m: bool = False,
                        exclude_regular: bool = False) -> List[str]:
        """Retrieve the names of the fields (columns) in a specified table, with options to include or exclude foreign keys (FK) and many-to-many (M2M) fields.

        Args:
            include_fk (bool): Whether to include foreign key fields. Default is True.
            include_m2m (bool): Whether to include many-to-many fields. Default is False.
            exclude_regular (bool): Whether to exclude regular (non-FK, non-M2M) fields. Default is False.

        Returns:
            List[str]: A list of field names in the specified table.

        Raises:
            ValueError: If the table name is not a valid Python identifier.
            sqlite3.Error: If there is an error executing the SQL command.
        """
        if not self.name.isidentifier():
            raise ValueError("Invalid table name")

        # Retrieve all fields
        fields_info = self.get_fields()
        
        # Get many-to-many fields if needed
        m2m_fields = self.get_many_to_many_fields() if include_m2m else {}

        # Filter fields based on options
        field_names = []
        for field_name, field_info in fields_info.items():
            is_fk = field_info.is_foreign_key
            is_m2m = field_name in m2m_fields

            # Include/exclude based on provided options
            if exclude_regular and not is_fk and not is_m2m:
                continue
            if (include_fk and is_fk) or (include_m2m and is_m2m) or (not is_fk and not is_m2m):
                field_names.append(field_name)

        # Add M2M fields if included
        if include_m2m:
            field_names.extend(m2m_fields.keys())

        return field_names

    def get_many_to_many_fields(self) -> Dict[str, 'ManyToManyField']:
        """Retrieve all many-to-many relationships for a specified table.

        Returns:
            Dict[str, ManyToManyField]: A dictionary where keys are `track_field_name` and values are ManyToManyField 
                instances representing the relationships.
        """
        if not self.name.isidentifier():
            raise ValueError("Invalid table name")

        # Return an empty dictionary if the _meta_many_to_many table does not exist
        if not self._database.is_table_exists('_meta_many_to_many'):
            return {}

        # Fetch all many-to-many relationships for the table
        records = self._database.query(
            model_name='_meta_many_to_many',
            fields=['track_field_name', 'junction_table'],
            conditions={
                'from_table': self.name, 
            }
        )

        many_to_many_relationships = {}

        for record in records:
            # Retrieve foreign keys from the junction table
            foreign_keys = self.get_foreign_keys(record['junction_table'])
            local_fk = None
            related_fk = None

            for fk in foreign_keys:
                if fk.related_table == self.name:
                    local_fk = fk
                else:
                    related_fk = fk

            if not local_fk or not related_fk:
                raise ValueError(f"Foreign keys referencing '{self.name}' and '{related_fk.related_table}' not found in '{record['junction_table']}'.")

            # Create the ManyToManyField instance
            many_to_many_field = ManyToManyField(
                track_field_name=record['track_field_name'],
                local_table=self.name,
                related_table=related_fk.related_table,
                junction_table=record['junction_table'],
                local_fk=local_fk,
                related_fk=related_fk
            )

            # Use track_field_name as the key in the dictionary
            many_to_many_relationships[record['track_field_name']] = many_to_many_field

        return many_to_many_relationships

    def get_many_to_many_field(self, field_name: str) -> 'ManyToManyField':
        """Retrieve a specific many-to-many relationship for a specified table and field.

        Args:
            table_name (str): The name of the table to retrieve the many-to-many relationship for.
            field_name (str): The name of the field representing the many-to-many relationship.

        Returns:
            ManyToManyField: An instance representing the many-to-many relationship.

        Raises:
            ValueError: If the field does not represent a many-to-many relationship.
        """
        if not self.name.isidentifier() or not field_name.isidentifier():
            raise ValueError("Invalid field name")

        # Check if the _meta_many_to_many table exists
        if not self._database.is_table_exists('_meta_many_to_many'):
            return

        # Fetch the specific many-to-many relationship
        record = self._database.query_one(
            model_name='_meta_many_to_many',
            fields=['track_field_name', 'junction_table'],
            conditions={
                'from_table': self.name,
                'track_field_name': field_name,
            },
            as_dict=False
        )

        if not record:
            raise ValueError(f"No many-to-many relationship found for field '{field_name}' in table '{self.name}'.")

        track_field_name, junction_table = record

        # Retrieve foreign keys from the junction table
        foreign_keys = self._database.get_foreign_keys(junction_table)
        local_fk = None
        related_fk = None

        for fk in foreign_keys:
            if fk.related_table == self.name:
                local_fk = fk  # Foreign key referencing the local table
            else:
                related_fk = fk  # Foreign key referencing the remote table
                related_table = related_fk.related_table

        if not local_fk or not related_fk:
            raise ValueError(f"Foreign keys referencing '{self.name}' and '{related_table}' not found in '{junction_table}'.")

        # Create the ManyToManyField instance
        many_to_many_field = ManyToManyField(
            track_field_name=track_field_name,
            local_table=self.name,
            related_table=related_table,
            junction_table=junction_table,
            local_fk=local_fk,
            related_fk=related_fk
        )

        return many_to_many_field

    def get_many_to_many_field_names(self) -> List[str]:
        """Retrieve the track field names of all many-to-many relationships for the current table.

        Returns:
            List[str]: A list of track field names representing many-to-many relationships in the current table.
        """
        return list(self.get_many_to_many_fields().keys())

    def get_primary_keys(self) -> List[str]:
        """Retrieve the primary keys of a specified table.
        
        Args:
            table_name (str): The name of the table to retrieve primary keys from.

        Returns:
            List[str]: A list of primary key field names. If it's a composite key, multiple fields are returned.
        """
        if not self.name.isidentifier():
            raise ValueError("Invalid table name")

        fields = self._database.query_raw(
            f"PRAGMA table_info({self.name})"
        )

        # Filter fields to include only those that are part of the primary key
        return [field['name'] for field in fields if field['pk']]

    def get_many_to_many_data(self, track_field_name: str, from_values: Optional[List[Union[int, str, float]]] = None,
                              display_field: str = '', display_field_label: str = '') -> List[Dict[str, Union[int, str, float]]]:
        """Retrieve the display field data related to specific records in a many-to-many relationship.

        Args:
            table_name (str): The name of the table from which the relationship starts.
            track_field_name (str): The field name that tracks the many-to-many relationship.
            from_values (Optional[List[Union[int, str, float]]]): A list of values in the from_table to match. If None, retrieve for all.
            display_field (str): The name of the display field in the related table to retrieve.

        Returns:
            List[Dict[str, Union[int, str, float]]]: A list of dictionaries, each containing the 'id' from the original table and the corresponding list of related tags or other display fields.
        """
        cursor = self._database.cursor()

        m2m = self.get_many_to_many_field(track_field_name)

        # Use the provided display field or fall back to the related field
        display_field = display_field or m2m.related_fk.related_field

        # If no specific from_values were provided, retrieve them from the junction table.
        if from_values is None:
            cursor.execute(f'''
                SELECT DISTINCT {m2m.local_fk.local_field}
                FROM {m2m.junction_table}
            ''')
            from_values = [row[0] for row in cursor.fetchall()]

        # Cast the local field to the appropriate key type.
        key_type = self.get_field_type(m2m.local_fk.related_field)

        # Build placeholders for the SQL IN clause.
        placeholders = ', '.join('?' for _ in from_values)
        
        # Use JSON_GROUP_ARRAY instead of GROUP_CONCAT.
        query = f'''
            SELECT CAST({m2m.junction_table}.{m2m.local_fk.local_field} AS {key_type}) AS {m2m.local_fk.related_field},
                JSON_GROUP_ARRAY({m2m.related_table}.{display_field}) AS {track_field_name}
            FROM {m2m.junction_table}
            JOIN {m2m.related_table}
                ON {m2m.junction_table}.{m2m.related_fk.local_field} = {m2m.related_table}.{m2m.related_fk.related_field}
            WHERE {m2m.junction_table}.{m2m.local_fk.local_field} IN ({placeholders})
            GROUP BY {m2m.junction_table}.{m2m.local_fk.local_field}
        '''

        cursor.execute(query, from_values)
        results = cursor.fetchall()
        cursor.close()

        display_field_label = display_field_label or track_field_name

        # Load the JSON array from the query result; no need to manually convert types.
        return [
            {
                m2m.local_fk.related_field: row[0],
                display_field_label: json.loads(row[1]) if row[1] is not None else []
            }
            for row in results
        ]

    def add_field(self, field_name: str, field_definition: str, foreign_key: Optional[str] = None, enum_values: Optional[List[str]] = None, enum_table_name: Optional[str] = None):
        """Add a new field to an existing table, optionally with a foreign key or enum constraint.

        Args:
            table_name (str): The name of the table to add the field to.
            field_name (str): The name of the new field.
            field_definition (str): The data type of the new field.
            foreign_key (Optional[str]): A foreign key constraint in the form of "related_table(related_field)".
            enum_values (Optional[List[str]]): A list of enum values if the field is of enum type.
            enum_table_name (Optional[str]): The name of an existing enum table if the field is an enum.

        Raises:
            ValueError: If the table name or field name is not a valid Python identifier.
            sqlite3.Error: If there is an error executing the SQL command.
        """
        if not field_name.isidentifier():
            raise ValueError("Invalid table name or field name")

        # Handle enum values or existing enum table
        if enum_values or enum_table_name:
            if not enum_table_name:
                enum_table_name = f"enum_{field_name}"
                self.create_enum_table(enum_table_name, enum_values)

            field_definition = "TEXT"
            foreign_key = f"{enum_table_name}(id)"
            self._add_enum_metadata(field_name, enum_table_name)

        # Fetch existing fields and foreign keys
        fields = self.get_fields()
        foreign_keys = self.get_foreign_keys()

        # Create a new table schema with the new field
        new_fields = [field.get_field_definition() for field in fields.values()]

        # Add the new field definition
        new_fields.append(f"{field_name} {field_definition}")

        # Include existing foreign keys
        new_fields.extend(fk.get_field_definition() for fk in foreign_keys)

        # Add the new foreign key constraint if provided
        if foreign_key:
            new_fields.append(f"FOREIGN KEY({field_name}) REFERENCES {foreign_key}")

        new_fields_str = ', '.join(new_fields)

        temp_table_name = f"{self.name}_temp"
        self._cursor.execute(f"CREATE TABLE {temp_table_name} ({new_fields_str})")

        # Copy data from the old table to the new table
        old_fields_str = ', '.join(fields.keys())
        self._cursor.execute(f"INSERT INTO {temp_table_name} ({old_fields_str}) SELECT {old_fields_str} FROM {self.name}")

        # Drop the old table and rename the new table
        self._cursor.execute(f"DROP TABLE {self.name}")
        self._cursor.execute(f"ALTER TABLE {temp_table_name} RENAME TO {self.name}")

        self._connection.commit()

    def delete_field(self, field_name: str):
        """Delete a field from a table by recreating the table without that field.

        Args:
            table_name (str): The name of the table to delete the field from.
            field_name (str): The name of the field to delete.

        Raises:
            ValueError: If the table name or field name is not a valid Python identifier.
            sqlite3.Error: If there is an error executing the SQL command.
        """
        if not field_name.isidentifier():
            raise ValueError("Invalid table name or field name")

        # Retrieve the table information
        fields = self.get_fields(self.name)

        # Disable foreign key constraints temporarily
        cursor = self._database.cursor()
        cursor.execute("PRAGMA foreign_keys=off;")
        try:
            # Filter out the field to be deleted
            new_fields = [field for field in fields.values() if field.name != field_name]
            field_names_str = ', '.join([field.name for field in new_fields])

            # Retrieve and filter foreign key constraints
            field_definitions = [field.get_field_definition() for field in new_fields]
            foreign_keys = self.get_foreign_keys()
            field_definitions.extend([fk.get_field_definition() for fk in foreign_keys if fk.from_field != field_name])
            field_definitions_str = ', '.join(field_definitions)

            # Create a temporary table with the new schema
            temp_table_name = f"{self.name}_temp"
            cursor.execute(f"CREATE TABLE {temp_table_name} ({field_definitions_str})")
            cursor.execute(f"INSERT INTO {temp_table_name} ({field_names_str}) SELECT {field_names_str} FROM {self.name}")
            # Replace the old table with the new one
            cursor.execute(f"DROP TABLE {self.name}")
            cursor.execute(f"ALTER TABLE {temp_table_name} RENAME TO {self.name}")

            # Remove the display field metadata
            self._remove_display_field(field_name)

            # Commit the transaction
            self._connection.commit()

        except sqlite3.Error as e:
            logging.error(f"Error deleting field '{field_name}' from table '{self.name}': {e}")
            self._connection.rollback()
            raise

        finally:
            # Re-enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys=on;")

    def insert_record(self, data_dict: Dict[str, Union[int, str, float, None]],
                      handle_m2m: bool = False) -> int:
        """Insert a new record into a table.

        Args:
            table_name (str): The name of the table to insert the record into.
            data_dict (Dict[str, Union[int, str, float, None]]): A dictionary mapping field names to their values.
            handle_m2m (bool): Whether to handle many-to-many relationships. Defaults to False.

        Returns:
            int: The rowid of the newly inserted record.

        Raises:
            ValueError: If the table name or field names are not valid Python identifiers.
            sqlite3.Error: If there is an error executing the SQL command.
        """
        if not all(f.isidentifier() for f in data_dict.keys()):
            raise ValueError("Invalid table name or field names")

        # Separate M2M data from the main data if handling M2M relationships
        m2m_data = {}
        if handle_m2m:
            for track_field_name in self.get_many_to_many_field_names():
                if track_field_name not in data_dict:
                    continue
                m2m_data[track_field_name] = data_dict.pop(track_field_name)

        # Insert the main record
        field_names = ', '.join(data_dict.keys())
        placeholders = ', '.join(['?'] * len(data_dict))
        sql = f"INSERT INTO {self.name} ({field_names}) VALUES ({placeholders})"
        cursor = self._database.cursor()
        cursor.execute(sql, list(data_dict.values()))
        self._connection.commit()

        # Get the primary key of the newly inserted record
        rowid = cursor.lastrowid

        # Insert M2M data into the junction table(s) if handling M2M relationships
        if handle_m2m:
            for track_field_name, selected_values in m2m_data.items():
                self._update_junction_table(track_field_name, rowid, selected_values, is_rowid=True)

        return rowid
    
    def delete_record(self, pk_values: Union[Dict[str, Any], Any], pk_field: Optional[str] = None):
        """Delete a specific record from a table by primary key, including related data in many-to-many junction tables.

        Args:
            table_name (str): The name of the table to delete the record from.
            pk_values (Union[Dict[str, Any], Any]): The primary key value(s) for the record to delete.
                Can be a single value or a dictionary of field-value pairs for composite keys.
            pk_field (Optional[str]): The name of the primary key field, required only for single-key deletions.

        Raises:
            ValueError: If the table name or primary key field is not a valid Python identifier.
            sqlite3.Error: If there is an error executing the SQL command.
        """
        # Determine if the deletion is for a single key or composite keys
        if isinstance(pk_values, dict):
            # Composite key handling
            if not all(isinstance(k, str) and k.isidentifier() for k in pk_values.keys()):
                raise ValueError("Invalid primary key fields")

            # Create a dynamic WHERE clause for composite keys
            where_clause = " AND ".join(f"{field} = ?" for field in pk_values.keys())
            where_values = list(pk_values.values())

        elif pk_field and pk_field.isidentifier():
            # Single key handling
            if not pk_field.isidentifier():
                raise ValueError("Invalid primary key field")

            where_clause = f"{pk_field} = ?"
            where_values = [pk_values]
        else:
            raise ValueError("Primary key field is required for single-key deletions")

        # TODO: Handle composite pks
        # First, delete related data in the many-to-many junction tables
        m2m_fields = self.get_many_to_many_fields()
        cursor = self._database.cursor()
        for m2m_field in m2m_fields.values():
            junction_table = m2m_field.junction_table

            # Delete related entries in the junction table
            cursor.execute(f'''
                DELETE FROM {junction_table}
                WHERE {m2m_field.local_fk.local_field} = ?
            ''', (list(pk_values.values())[0],))

        # Then, delete the main record from the table
        query = f"DELETE FROM {self.name} WHERE {where_clause}"
        cursor.execute(query, where_values)
        self._connection.commit()

    # TODO: Handle composite pks
    def update_record(self, data_dict: Dict[str, Union[int, str, float, None]], 
                      pk_value: Union[int, str, float], pk_field: str = 'rowid', handle_m2m: bool = False):
        """Update an existing record in a table by primary key.

        Args:
            table_name (str): The name of the table containing the record to update.
            data_dict (Dict[str, Union[int, str, float, None]]): A dictionary mapping field names to their new values.
            pk_value (Union[int, str, float]): The primary key value of the record to update.
            pk_field (str): The name of the primary key field. Defaults to 'rowid'.
            handle_m2m (bool): Whether to handle many-to-many relationships. Defaults to False.

        Raises:
            ValueError: If the table name or field names are not valid Python identifiers.
            sqlite3.Error: If there is an error executing the SQL command.
        """
        if (not all(f.isidentifier() for f in data_dict.keys()) or
            not pk_field.isidentifier()
        ):
            raise ValueError("Invalid table name or field names")

        # Separate M2M data from the main data if handling M2M relationships
        m2m_data = {}
        if handle_m2m:
            for track_field_name in self.get_many_to_many_field_names():
                if track_field_name not in data_dict:
                    continue
                m2m_data[track_field_name] = data_dict.pop(track_field_name)

        if data_dict:
            # Update the main record
            set_clause = ', '.join([f"{field} = ?" for field in data_dict.keys()])
            sql = f"UPDATE {self.name} SET {set_clause} WHERE {pk_field} = ?"
            self._database.execute_raw(sql, list(data_dict.values()) + [pk_value])

        # Update M2M data in the junction table(s) if handling M2M relationships
        if handle_m2m:
            for track_field_name, selected_values in m2m_data.items():
                self._update_junction_table(track_field_name, pk_value, selected_values)

    def get_possible_values(self, field: Optional[str] = None) -> List[str]:
        """Get possible values from a related table using a display field.

        Args:
            table_name (str): The name of the related table.
            field (Optional[str]): The field to display. Defaults to the primary key.

        Returns:
            List[str]: A list of possible values from the specified display field.
        """
        # Determine the display field: use the provided display field or default to the primary key
        field = field or self.get_primary_keys()[0]

        # Ensure the display field exists in the table
        if field not in self.get_field_names():
            raise ValueError(f"Field '{field}' does not exist in table '{self.name}'")

        # Execute query to get the unique values for the display field
        rows = self._database.query_raw(f"SELECT DISTINCT {field} FROM {self.name} ORDER BY {field}")
        return [row[0] for row in rows]

    def add_display_field(self, field_name: str, display_field_name: str, display_format: str = None):
        """Add a display field entry to the meta table.
        """
        self._create_meta_display_field_table()
        self._database.execute_raw('''
            INSERT OR REPLACE INTO _meta_display_field (table_name, field_name, display_foreign_field_name, display_format)
            VALUES (?, ?, ?, ?);
        ''', (self.name, field_name, display_field_name, display_format))

    def get_display_field(self, field_name: str) -> Optional[Tuple[str, str]]:
        """Retrieve the display field name and format for a specific field.
        """
        return self._database.query_one(
            model_name='_meta_display_field',
            fields='display_foreign_field_name',
            conditions={
                'table_name': self.name,
                'field_name': field_name,
            },
            as_dict=False
        )

    # Private Methods
    # ---------------
    def _create_meta_enum_field_table(self):
        """Create the meta table to store enum field information.
        """
        self._database.execute_raw('''
            CREATE TABLE IF NOT EXISTS _meta_enum_field (
                table_name TEXT,
                field_name TEXT,
                enum_table_name TEXT,
                description TEXT,
                PRIMARY KEY (table_name, field_name)
            );
        ''')

    def _update_junction_table(self, track_field_name: str, from_value: Union[int, str, float], 
                            selected_values: List[Union[int, str, float]], is_rowid: bool = False):
        """Update the junction table for a many-to-many relationship.

        Args:
            track_field_name (str): The field name that tracks the many-to-many relationship.
            from_value (Union[int, str, float]): The value in the from_table to match, either a rowid or an existing key.
            selected_values (List[Union[int, str, float]]): The list of values to insert into the junction table.
            is_rowid (bool): Indicates if `from_value` is a rowid that needs to be translated into the corresponding foreign key value.
        """
        m2m = self.get_many_to_many_field(track_field_name)
        cursor = self._database.cursor()

        if is_rowid:
            # Translate the rowid into the corresponding foreign key value
            from_value = self.query_one(
                fields=m2m.local_fk.related_field,
                conditions={
                    'rowid': from_value,
                }
            )

        # Clear existing junction table entries for this record
        cursor.execute(f'''
            DELETE FROM {m2m.junction_table}
            WHERE {m2m.local_fk.local_field} = ?
        ''', (from_value,))

        # Insert new entries into the junction table
        for value in selected_values:
            cursor.execute(f'''
                INSERT INTO {m2m.junction_table} ({m2m.local_fk.local_field}, {m2m.related_fk.local_field})
                VALUES (?, ?)
            ''', (from_value, value))
        
        self._connection.commit()

    def _add_enum_metadata(self, table_name: str, field_name: str, enum_table_name: str, description: str = ""):
        self._create_meta_enum_field_table()
        self._database.execute_raw('''
            INSERT INTO _meta_enum_field (table_name, field_name, enum_table_name, description)
            VALUES (?, ?, ?, ?);
        ''', (table_name, field_name, enum_table_name, description))

    def _remove_display_field(self, field_name: str):
        """Remove a display field entry from the meta table.
        """
        self._database.execute_raw(
            '''
            DELETE FROM _meta_display_field
            WHERE table_name = ? AND field_name = ?;
            ''',
            (self.name, field_name)
        )

    def _create_meta_display_field_table(self):
        """Create the meta table to store display field information.
        """
        fields = {
            'table_name': 'TEXT',
            'field_name': 'TEXT',
            'display_foreign_field_name': 'TEXT',
            'display_format': 'TEXT',
            'PRIMARY KEY': '(table_name, field_name)'
        }
        self._database.create_table('_meta_display_field', fields)


class Entity:

    def __init__(self, database: SQLiteDatabase, model_name: str, entity_id: Any):
        self._database = database
        self._id = entity_id

        self._model = self._database.get_model(model_name)

    @property
    def database(self):
        return self._database

    @property
    def model(self):
        return self._model

    @property
    def id(self):
        return self._id

    def get_field_names(self) -> List[str]:
        return self._model.get_field_names()

    def get(self, fields: List[str] | str = None, as_dict: bool = True):
        return self._model.query_one(
            fields=fields,
            conditions={'rowids': self._id},
            as_dict=as_dict
        )

    def __getitem__(self, fields):
        return self.get(fields, as_dict=False)
