# Type Checking Imports
# ---------------------
from typing import List, Optional

# Standard Library Imports
# ------------------------
from enum import Enum, auto

# Third Party Imports
# -------------------
from qtpy import QtCore


# Class Definitions
# -----------------
class SortOrder(Enum):

    ASC = "Ascending"
    DESC = "Descending"

    @property
    def display_name(self):
        return self.value

    def __str__(self) -> str:
        """Convert enum to a string (supports .upper() for query generation)."""
        return self.name


class FilterOperation(Enum):
    # Display name, SQL operator, number of parameters
    LT = ("Less Than", "< ?", 1)
    GT = ("Greater Than", "> ?", 1)
    LTE = ("Less Than or Equal", "<= ?", 1)
    GTE = ("Greater Than or Equal", ">= ?", 1)
    BEFORE = ("Before", "< ?", 1)
    AFTER = ("After", "> ?", 1)
    EQ = ("Equals", "= ?", 1)
    NEQ = ("Not Equals", "!= ?", 1)
    CONTAINS = ("Contains", "LIKE '%' || ? || '%'", 1)                  # Special LIKE operator for string matching
    NOT_CONTAINS = ("Does Not Contain", "NOT LIKE '%' || ? || '%'", 1)
    STARTS_WITH = ("Starts With", "LIKE ? || '%'", 1)                   # Start with pattern matching
    ENDS_WITH = ("Ends With", "LIKE '%' || ?", 1)                       # End with pattern matching
    NOT_STARTS_WITH = ("Not Starts With", "NOT LIKE ? || '%'", 1)
    NOT_ENDS_WITH = ("Not Ends With", "NOT LIKE '%' || ?", 1)
    IS_NULL = ("Is Null", "IS NULL", 0)                                 # Checks for NULL values
    IS_NOT_NULL = ("Is Not Null", "IS NOT NULL", 0)                     # Checks for NOT NULL values
    IN = ("In", "IN", -1)                                               # Special case for IN query, variable number of arguments
    NOT_IN = ("Not In", "NOT IN", -1)                                   # Special case for NOT IN query, variable number of arguments
    BETWEEN = ("Between", "BETWEEN ? AND ?", 2)                         # Special case for BETWEEN operator, requires two values
    NOT_BETWEEN = ("Not Between", "NOT BETWEEN ? AND ?", 2)             # Special case for NOT BETWEEN operator, requires two values

    # Initialization and Setup
    # ------------------------
    def __init__(self, display_name: str, sql_operator: str, num_params: int):
        """Initialize the enum with its display name, SQL operator, and number of values.
        """
        self._display_name = display_name
        self._sql_operator = sql_operator
        self._num_params = num_params

    @property
    def display_name(self) -> str:
        """Return the display name of the filter operation.
        """
        return self._display_name

    @property
    def sql_operator(self) -> str:
        """Return the SQL operator for the filter operation.
        """
        return self._sql_operator

    @property
    def num_params(self) -> int:
        """Return the number of values required for the filter operation.
        """
        return self._num_params

    def requires_param(self) -> bool:
        """Determine if the filter condition requires input values.

        Returns:
            bool: True if values are required, False otherwise.
        """
        return self._num_params != 0

    def is_multi_param(self) -> bool:
        """Return True if the operation supports multiple values."""
        return self._num_params == -1

    @classmethod
    def from_string(cls, name: str) -> 'FilterOperation':
        name = name.upper()
        mapping = {
            "<": cls.LT,
            ">": cls.GT,
            "<=": cls.LTE,
            ">=": cls.GTE,
            "EQUALS": cls.EQ,
            "=": cls.EQ,
            "NOT_EQUALS": cls.NEQ,
            "!=": cls.NEQ,
        }

        return mapping.get(name, cls[name])

    def __str__(self):
        """Return the string representation of the filter operation.
        """
        return self._display_name


class FieldType(Enum):
    """Enum representing user-friendly column types and their associated filter widgets.
    """
    NULL = 'Null'
    TEXT = 'Text'
    NUMERIC = 'Numeric'
    DATE = 'Date'
    DATETIME = 'Date & Time'
    BOOLEAN = 'True/False'
    ENUM = 'Single Select'
    LIST = 'Multiple Select'
    UUID = 'UUID'

    @property
    def display_name(self):
        """Return the user-friendly display type of the column.
        """
        return self.value

    @property
    def supported_operations(self) -> List['FilterOperation']:
        return FieldTypeMapping.TO_SUPPORTED_OPERATIONS.get(self, [])

    def __str__(self):
        """Return a string representation of the FieldType enum.
        """
        return self.name

    @staticmethod
    def from_sql(sql_type: str) -> 'FieldType':
        """Map SQL column type to the corresponding FieldType enum.

        Args:
            sql_type (str): The SQL type of the column.

        Returns:
            FieldType: The corresponding FieldType enum instance.
        """
        sql_type = sql_type.upper()

        # Map common SQL types to FieldType enum
        if any(keyword in sql_type for keyword in ['CHAR', 'VARCHAR', 'TEXT', 'CLOB']):
            return FieldType.TEXT
        # Combine integer and floating point SQL types into NUMERIC.
        elif any(keyword in sql_type for keyword in [
            'INT', 'INTEGER', 'TINYINT', 'SMALLINT', 'BIGINT', 'SERIAL',
            'REAL', 'DOUBLE', 'FLOAT', 'DECIMAL', 'NUMERIC', 'MONEY'
        ]):
            return FieldType.NUMERIC
        elif 'DATETIME' in sql_type or 'TIMESTAMP' in sql_type:
            return FieldType.DATETIME  # Support DATETIME types
        elif 'DATE' in sql_type:
            return FieldType.DATE
        elif any(keyword in sql_type for keyword in ['BOOLEAN', 'BOOL']):
            return FieldType.BOOLEAN
        elif 'ENUM' in sql_type:  # Assumption: custom enum or select types include 'ENUM' keyword
            return FieldType.ENUM
        elif 'LIST' in sql_type or 'ARRAY' in sql_type:  # Use 'LIST' for PostgreSQL array types
            return FieldType.LIST

        # PostgreSQL-Specific Types and others
        elif 'UUID' in sql_type:
            return FieldType.UUID
        elif 'JSON' in sql_type or 'JSONB' in sql_type:
            return FieldType.TEXT
        elif 'TSVECTOR' in sql_type or 'TSQUERY' in sql_type:
            return FieldType.TEXT
        elif 'HSTORE' in sql_type:
            return FieldType.TEXT
        elif any(keyword in sql_type for keyword in ['CIDR', 'INET', 'MACADDR']):
            return FieldType.TEXT
        elif 'BIT' in sql_type:
            return FieldType.NUMERIC
        elif 'INTERVAL' in sql_type:
            return FieldType.TEXT
        elif 'BYTEA' in sql_type:
            return FieldType.TEXT

        else:
            raise ValueError(f"Unsupported SQL type: {sql_type}")


class FieldTypeMapping:

    STANDARD_OPERATIONS = [
        FilterOperation.EQ,
        FilterOperation.NEQ,
        FilterOperation.IS_NULL,
        FilterOperation.IS_NOT_NULL,
    ]

    TO_SUPPORTED_OPERATIONS = {
        FieldType.TEXT: [
            FilterOperation.CONTAINS,
            FilterOperation.NOT_CONTAINS,
            FilterOperation.STARTS_WITH,
            FilterOperation.ENDS_WITH,
            *STANDARD_OPERATIONS,
        ],
        FieldType.NUMERIC: [
            FilterOperation.GT,
            FilterOperation.LT,
            FilterOperation.GTE,
            FilterOperation.LTE,
            FilterOperation.BETWEEN,
            FilterOperation.NOT_BETWEEN,
            *STANDARD_OPERATIONS,
        ],
        FieldType.DATE: [
            FilterOperation.BEFORE,
            FilterOperation.AFTER,
            FilterOperation.BETWEEN,
            FilterOperation.NOT_BETWEEN,
            *STANDARD_OPERATIONS,
        ],
        FieldType.DATETIME: [
            FilterOperation.BEFORE,
            FilterOperation.AFTER,
            FilterOperation.BETWEEN,
            FilterOperation.NOT_BETWEEN,
            *STANDARD_OPERATIONS,
        ],
        FieldType.ENUM: [
            FilterOperation.IN,
            FilterOperation.NOT_IN,
            FilterOperation.CONTAINS,
            FilterOperation.NOT_CONTAINS,
            *STANDARD_OPERATIONS,
        ],
        FieldType.LIST: [
            # FilterOperation.CONTAINS_ANY,    # The list contains at least one element of a provided set
            # FilterOperation.NOT_CONTAINS_ANY,
            # FilterOperation.CONTAINS_ALL,    # The list contains all elements of a provided set
            # FilterOperation.NOT_CONTAINS_ALL,
            FilterOperation.IN,              # At least one element in the list is in a given set
            FilterOperation.NOT_IN,          # None of the elements in the list are in a given set
            *STANDARD_OPERATIONS,
        ],
        FieldType.BOOLEAN: STANDARD_OPERATIONS.copy(),
        FieldType.UUID: STANDARD_OPERATIONS.copy(),
    }


# Enum for logical operators (AND, OR) used for grouping
class GroupOperator(Enum):

    AND = auto()
    OR = auto()

    @property
    def display_name(self) -> str:
        return self.name.lower()

    @property
    def sql_operator(self) -> str:
        return self.name

    @classmethod
    def is_valid(cls, key: str) -> bool:
        try:
            cls[key.upper()]  # Try to access the enum by the string value
            return True
        except KeyError:
            return False

    def __str__(self):
        return self.name


class FilterMode(Enum):
    """Enum representing the different filter modes available.
    
    - STANDARD: The default filtering behavior.
    - TOGGLE: A mode where filters can be toggled on/off.
    - ADVANCED: A mode for more complex filtering options.
    """
    STANDARD = auto()
    TOGGLE = auto()
    ADVANCED = auto()

    def __str__(self):
        return self.name.capitalize()


class DateRange(Enum):
    """Enum representing various date ranges.
    """

    SELECTED_DATE_RANGE = "Selected Date Range"
    TODAY = "Today"
    YESTERDAY = "Yesterday"
    PAST_7_DAYS = "Past 7 Days"
    PAST_15_DAYS = "Past 15 Days"
    PAST_MONTH = "Past Month"
    PAST_2_MONTHS = "Past 2 Months"
    PAST_YEAR = "Past Year"

    def get_date_range(self):
        today = QtCore.QDate.currentDate()

        match self:
            case DateRange.TODAY:
                return today, today
            case DateRange.YESTERDAY:
                return today.addDays(-1), today.addDays(-1)
            case DateRange.PAST_7_DAYS:
                return today.addDays(-7), today
            case DateRange.PAST_15_DAYS:
                return today.addDays(-15), today
            case DateRange.PAST_MONTH:
                return today.addMonths(-1), today
            case DateRange.PAST_2_MONTHS:
                return today.addMonths(-2), today
            case DateRange.PAST_YEAR:
                return today.addYears(-1), today
            case _:
                return None, None

    def __str__(self):
        return self.value
