from abc import ABC, abstractmethod
from collections import defaultdict
from typing import List, Dict, Any, Callable
from enum import Enum
from qtpy import QtCore, QtWidgets

from blackboard.enums.view_enum import FieldType


# NOTE: WIP
# Base grouping strategy with registry support
class GroupingStrategy:
    # Registry mapping FieldType to a factory function that returns a GroupingStrategy instance.
    _registry: Dict[FieldType, Callable[..., "GroupingStrategy"]] = {}

    def __init__(self, field: int, func: Callable[[Any], Any], default: str = 'uncategorized'):
        self.field = field
        self.func = func
        self.default = default

    def get_key(self, item: QtWidgets.QTreeWidgetItem) -> Any:
        value = item.data(self.field, QtCore.Qt.ItemDataRole.UserRole)
        if value is None:
            return self.default
        return self.func(value)

    @classmethod
    def register_strategy(cls, field_type: FieldType, factory: Callable[..., "GroupingStrategy"]) -> None:
        """
        Register a factory for a specific field type.
        
        Args:
            field_type (FieldType): The field type.
            factory (Callable[..., GroupingStrategy]): A callable that returns a GroupingStrategy instance.
        """
        cls._registry[field_type] = factory

    @classmethod
    def create_strategy(cls, field_type: FieldType, **kwargs) -> "GroupingStrategy":
        """
        Create or get a grouping strategy instance based on the field type.
        
        Args:
            field_type (FieldType): The field type.
            **kwargs: Additional parameters needed by the strategy's factory.
            
        Returns:
            GroupingStrategy: An instance of the appropriate strategy.
            
        Raises:
            ValueError: If no strategy is registered for the field type.
        """
        if field_type not in cls._registry:
            raise ValueError(f"No grouping strategy registered for field type: {field_type}")
        return cls._registry[field_type](**kwargs)


# 1. Exact Value Grouping Strategy
class ExactValueStrategy(GroupingStrategy):
    def __init__(self, field: int, default: str = 'uncategorized'):
        self.field = field
        self.default = default

    def get_key(self, item: QtWidgets.QTreeWidgetItem) -> Any:
        return item.data(self.field, QtCore.Qt.ItemDataRole.UserRole) or self.default

# 2. Range (Binning) Grouping Strategy for numeric fields
class RangeGroupingStrategy(GroupingStrategy):
    def __init__(self, field: int, ranges: List[tuple], default: str = 'uncategorized'):
        """
        ranges: List of tuples (min, max) defining bins.
        """
        self.field = field
        self.ranges = ranges
        self.default = default

    def get_key(self, item: QtWidgets.QTreeWidgetItem) -> Any:
        value = item.data(self.field, QtCore.Qt.ItemDataRole.UserRole)
        if value is None:
            return self.default
        for r in self.ranges:
            if r[0] <= value <= r[1]:
                return f"{r[0]}-{r[1]}"
        return self.default

class DateComponent(Enum):
    YEAR = 'year'
    MONTH = 'month'
    DAY = 'day'

# 3. Date/Time Component Grouping Strategy
class DateGroupingStrategy(GroupingStrategy):
    def __init__(self, field: int, component: DateComponent = DateComponent.YEAR, default: str = 'uncategorized'):
        """
        Args:
            field (int): The column index to extract the date value.
            component (DateComponent, optional): The date component to group by (year, month, or day).
                Defaults to DateComponent.YEAR.
            default (str, optional): The fallback group if no date value is present. Defaults to 'uncategorized'.
        """
        self.field = field
        self.component = component
        self.default = default

    def get_key(self, item: Any) -> Any:
        date_value = item.data(self.field, QtCore.Qt.ItemDataRole.UserRole)
        if not date_value:
            return self.default

        if self.component == DateComponent.YEAR:
            return date_value.year()
        elif self.component == DateComponent.MONTH:
            return date_value.month()
        elif self.component == DateComponent.DAY:
            return date_value.day()

        return self.default


# Register strategies for each FieldType
GroupingStrategy.register_strategy(FieldType.TEXT, lambda field, default='uncategorized': ExactValueStrategy(field, default))
GroupingStrategy.register_strategy(FieldType.NUMERIC, lambda field, ranges, default='uncategorized': RangeGroupingStrategy(field, ranges, default))
GroupingStrategy.register_strategy(FieldType.DATE, lambda field, component=DateComponent.DAY, default='uncategorized': DateGroupingStrategy(field, component, default))
