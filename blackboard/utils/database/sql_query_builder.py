# Type Checking Imports
# ---------------------
from __future__ import annotations
from typing import Any, Callable, Generator, Iterable

# Standard Imports
# ----------------
import re
from dataclasses import dataclass, field, InitVar

# Local Imports
# -------------
from blackboard.enums.view_enum import GroupOperator, SortOrder, FilterOperation, SetOperator


# Class Definitions
# -----------------
# NOTE: WIP
class DataSerializer:
    """Serializes and deserializes data for storage.

    This class encapsulates functions that convert Python values to a storage-compatible
    format (serialization) and convert stored values back into Python values (deserialization).

    Attributes:
        serialize (Callable[[Any], Any]): Function to serialize a Python value for storage.
        deserialize (Callable[[Any], Any]): Function to deserialize a stored value back to Python.
    """

    def __init__(self,
                 serialize: Callable[[Any], Any],
                 deserialize: Callable[[Any], Any]) -> None:
        """Initializes the DataSerializer with serialization functions.

        Args:
            serialize (Callable[[Any], Any]): Function to serialize a Python value for storage.
            deserialize (Callable[[Any], Any]): Function to deserialize a stored value back to Python.
        """
        self.serialize = serialize
        self.deserialize = deserialize


@dataclass(frozen=True)
class OuterRef:
    field: str


class SetOpsMixin:
    def union(self: QuerySpecBase, other: QuerySpecBase) -> CompoundQuerySpec:
        return CompoundQuerySpec(left=self, op=SetOperator.UNION, right=other)

    def union_all(self: QuerySpecBase, other: QuerySpecBase) -> CompoundQuerySpec:
        return CompoundQuerySpec(left=self, op=SetOperator.UNION_ALL, right=other)

    def intersect(self: QuerySpecBase, other: QuerySpecBase) -> CompoundQuerySpec:
        return CompoundQuerySpec(left=self, op=SetOperator.INTERSECT, right=other)

    def except_(self: QuerySpecBase, other: QuerySpecBase) -> CompoundQuerySpec:
        return CompoundQuerySpec(left=self, op=SetOperator.EXCEPT, right=other)

    def __or__(self: QuerySpecBase, other: QuerySpecBase) -> CompoundQuerySpec:
        return self.union_all(other)

    def __and__(self: QuerySpecBase, other: QuerySpecBase) -> CompoundQuerySpec:
        return self.intersect(other)

    def __sub__(self: QuerySpecBase, other: QuerySpecBase) -> CompoundQuerySpec:
        return self.except_(other)


@dataclass(frozen=True, kw_only=True)
class QuerySpecBase(SetOpsMixin):
    """Base type for all query nodes.
    """
    # Global (outer) modifiers for the compound result
    distinct: bool = False
    order_by: dict[str, Any] | None = None
    limit: int | None = None


@dataclass(frozen=True)
class QuerySpec(QuerySpecBase):
    model: str
    fields: Any = None
    filters: dict[Any, Any] | None = None


@dataclass(frozen=True)
class QueryOneSpec(QuerySpec):
    """Represent a query that expects at most one row (0..1).
    """

    def __post_init__(self):
        object.__setattr__(self, "limit", 1)


@dataclass(frozen=True)
class CompoundQuerySpec(QuerySpecBase):
    left: QuerySpecBase
    op: SetOperator
    right: QuerySpecBase


@dataclass
class QueryContext:
    """Holds context for building a query, including fields, filters, and relationships.
    """
    model: str
    query: str = field(default_factory=str)
    parameters: list[Any] = field(default_factory=list)

    relationships: dict[str, str] = field(default_factory=dict)
    serializers: dict[str, DataSerializer] = field(default_factory=dict)

    # Actual field/alias maps
    field_to_alias: dict[str, str] = field(default_factory=dict)
    alias_to_field: dict[str, str] = field(default_factory=dict)
    grouped_fields: set[str] = field(default_factory=set)

    # Init-only data used inside __post_init__
    field_to_alias_pairs: InitVar[list[tuple[str, str]] | None] = None

    def __post_init__(self, field_to_alias_pairs: list[tuple[str, str]] | None):
        """Populate alias maps from init-only pairs, and/or normalize provided maps.
        """
        self._add_field_alias_pairs(field_to_alias_pairs or [])

    def _add_field_alias_pairs(self, pairs: list[tuple[str, str]]):
        """Add field-alias pairs and maintain a reversible mapping.

        This method updates both `field_aliases` (field → alias) and 
        `alias_to_field` (alias → field) mappings.

        Args:
            pairs (list[tuple[str, str]]): A list of tuples where the first value is 
                the field name and the second is the alias.

        Example:
            >>> result = QueryContext(model="tasks", query="SELECT id FROM tasks", parameters=[])
            >>> result._add_field_alias_pairs([("tasks.id", "task_id"), ("tasks.name", "task_name")])
            >>> print(result.field_to_alias)
            {'tasks.id': 'task_id', 'tasks.name': 'task_name'}
            >>> print(result.alias_to_field)
            {'task_id': 'tasks.id', 'task_name': 'tasks.name'}
        """
        for field, alias in pairs:
            # Ensure no duplicate alias is assigned to different fields
            if alias in self.alias_to_field and self.alias_to_field[alias] != field:
                raise ValueError(f"Alias '{alias}' is already mapped to '{self.alias_to_field[alias]}'.")

            # Store mappings
            self.field_to_alias[field] = alias
            self.alias_to_field[alias] = field

    def get_field_by_alias(self, alias: str) -> str:
        """Retrieve the field name using its alias.

        Args:
            alias (str): The alias to search for.

        Returns:
            str: The field name corresponding to the alias.
        """
        return self.alias_to_field.get(alias)
    
    def get_field_by_index(self, index: int) -> str:
        """Retrieve the field name using its index.

        Args:
            index (int): The index of the field to retrieve.

        Returns:
            str: The field name at the specified index.
        """
        return list(self.field_to_alias.keys())[index]

    def resolve_model(self, relation_chain: str) -> str:
        """Resolve a chain of relationships to determine the final model.

        Args:
            relation_chain (str): A separator-delimited string representing the chain of relationships (e.g., "name.account").
            sep (str, optional): The separator used in both the relationship chain and the dictionary keys.
                 Defaults to CHAIN_SEPARATOR.

        Returns:
            str: The final model reached after resolving the relationship chain. Returns None if the chain cannot be fully resolved.

        Example:
            >>> relationships = {
            ...     'Tasks.name': 'Users.id',
            ...     'Users.profile': 'Profiles.id',
            ...     'Profiles.account': 'Accounts.id'
            ... }
            >>> result = QueryContext(model='Tasks', query="SELECT id FROM Tasks", parameters=[], relationships=relationships)
            >>> result.resolve_model('name.profile.account')
            'Accounts'
        """
        return SQLQueryBuilder.resolve_model(self.model, relation_chain, self.relationships)
    
    def resolve_model_field(self, field_chain: str, as_tuple: bool = False) -> tuple[str, str]:
        """Resolve a field to determine the final model it belongs to.

        Args:
            field_chain (str): The field to resolve to a model.

        Returns:
            tuple[str, str]: A tuple containing the final model and field name.

        Example:
            >>> relationships = {
            ...     'User.name': 'Profile.id',
            ...     'Profile.account': 'Account.id'
            ... }
            >>> result = QueryContext(model='User', relationships=relationships)
            >>> result.resolve_model_field('name.account', as_tuple=True)
            ('Profile', 'account')
        """
        return SQLQueryBuilder.resolve_model_field(self.model, field_chain, self.relationships, as_tuple=as_tuple)


class SQLQueryBuilder:

    CHAIN_SEPARATOR = '.'

    # Matches segments like @Assets[project] or @Task[parent_task]
    _INDIRECT_RELATION_SEGMENT_RE = re.compile(r'@[^.\[\]]+\[[^\]]+\]')

    # Utility Methods
    # ---------------
    @classmethod
    def resolve_model(
            cls,
            base_model: str,
            relation_chain: str,
            relationships: dict[str, str],
            sep: str = CHAIN_SEPARATOR
        ) -> str:
        """Resolve a chain of relationships to determine the final model.

        Starting from a base model, this method iteratively follows the relationship chain defined by
        the `relation_chain` string. At each step, it uses the `relationships` dictionary to map the current
        model and field (formatted as "Model{sep}field") to a new model. If the chain is invalid or incomplete,
        the function returns None.

        This also supports indirect relation segments of the form '@Model[field]', which represent
        context-dependent cross-model hops (e.g. reverse/indirect relations).

        Args:
            base_model (str): The initial model from which to start the resolution.
            relation_chain (str): A separator-delimited string representing the chain of relationships
                (e.g., "name.account" or "project.@Assets[project].owner").
            relationships (dict[str, str]): A dictionary mapping "Model{sep}field" to
                "RelatedModel{sep}related_field".
            sep (str, optional): The separator used in both the relationship chain and the dictionary keys.
                 Defaults to CHAIN_SEPARATOR.

        Returns:
            str: The final model reached after resolving the relationship chain. Returns None if the chain
                cannot be fully resolved.

        Examples:
            >>> relationships = {
            ...     'Users.name': 'Profiles.id',
            ...     'Profiles.account': 'Accounts.id',
            ...     'Assets.project': 'Projects.id',
            ...     'Tasks.project': 'Projects.id',
            ...     'Assets.owner': 'Users.id',
            ... }
            >>> SQLQueryBuilder.resolve_model('Users', 'name.account', relationships)
            'Accounts'
            >>> SQLQueryBuilder.resolve_model('Users', 'name', relationships)
            'Profiles'
            >>> SQLQueryBuilder.resolve_model('Tasks', 'project.@Assets[project].owner', relationships)
            'Users'
            >>> SQLQueryBuilder.resolve_model('Tasks', 'project.@Assets[project]', relationships)
            'Assets'
            >>> SQLQueryBuilder.resolve_model('Projects', '@Assets[project]', relationships)
            'Assets'
        """
        if not relationships:
            return

        for field in cls._tokenize_field(relation_chain):
            # Handle indirect relational fields like "@Assets[project]"
            if field.startswith('@'):
                base_model, field = cls._parse_relationship(cls._normalize_indirect_relation(field))
                continue
            if (left_model_field := f'{base_model}{sep}{field}') not in relationships:
                return
            base_model, _right_field = cls._parse_relationship(relationships[left_model_field])

        return base_model

    @classmethod
    def resolve_model_field(
            cls,
            base_model: str,
            field_chain: str,
            relationships: dict[str, str],
            sep: str = CHAIN_SEPARATOR,
            as_tuple: bool = False,
        ) -> str | tuple[str, str]:
        """Resolve a field chain to its final model and field.

        This method takes a starting model and a field chain (which may include relationship
        navigations and indirect relation segments such as '@Assets[project]') and determines
        the final model associated with the target field.

        Behaviour:
        - If the chain does not contain the separator, the field is assumed to belong to the base model,
          unless it is an indirect relation segment ('@Model[field]').
        - If the chain contains the separator, the part before the last separator is treated as the
          parent relation chain and resolved to a model, and the last segment is resolved as:
            * a normal field on that model, or
            * an indirect relation segment '@Model[field]'.

        Args:
            base_model (str): The initial model name from which to begin resolution.
            field_chain (str): The field or chain of fields to resolve
                (e.g., "name", "name.account", "project.@Assets[project].owner").
            relationships (dict[str, str]): A mapping where each key is in the format
                "Model{sep}field" and each value is in the format "RelatedModel{sep}related_field".
            sep (str, optional): The separator used in the field chain and relationship keys.
                Defaults to CHAIN_SEPARATOR.
            as_tuple (bool): If True, return a (model, field) tuple instead of "Model.field".

        Returns:
            str | tuple[str, str]: Either a string "FinalModel{sep}field" or a (model, field) tuple.

        Examples:
            >>> relationships = {
            ...     'Users.name': 'Profiles.id',
            ...     'Profiles.account': 'Accounts.id',
            ...     'Assets.project': 'Projects.id',
            ...     'Tasks.project': 'Projects.id',
            ...     'Assets.owner': 'Users.id',
            ... }
            >>> SQLQueryBuilder.resolve_model_field('Users', 'name', relationships)
            'Users.name'
            >>> SQLQueryBuilder.resolve_model_field('Users', 'name.account', relationships)
            'Profiles.account'
            >>> SQLQueryBuilder.resolve_model_field('Tasks', 'project.@Assets[project].owner.name', relationships)
            'Users.name'
            >>> SQLQueryBuilder.resolve_model_field('Tasks', 'project.@Assets[project].owner', relationships)
            'Assets.owner'
            >>> SQLQueryBuilder.resolve_model_field('Tasks', 'project.@Assets[project]', relationships)
            'Assets.project'
            >>> SQLQueryBuilder.resolve_model_field('Projects', '@Assets[project]', relationships)
            'Assets.project'
        """
        if not cls._is_relation_chain(field_chain) or not relationships:
            # Simple field or a single indirect relation segment
            if field_chain.startswith('@'):
                model, field = cls._parse_relationship(cls._normalize_indirect_relation(field_chain))
            else:
                model, field = base_model, field_chain
        else:
            parent_chain, field = cls._parse_relationship(field_chain)
            # Last segment may itself be an indirect relation segment "@Model[field]"
            if field.startswith('@'):
                model, field = cls._parse_relationship(cls._normalize_indirect_relation(field))
            else:
                model = cls.resolve_model(base_model, parent_chain, relationships)

        if as_tuple:
            return model, field
        else:
            return f"{model}{sep}{field}"

    @classmethod
    def propagate_hierarchies(
            cls,
            fields: list[str],
            sep: str = CHAIN_SEPARATOR,
            prune_leaves: int = 0
        ) -> list[str]:
        """Propagate and ensure all levels of hierarchy are referenced, with an option to prune levels from the leaves.

        Indirect relation segments ('@Model[field]') are treated as normal tokens for the
        purposes of hierarchy propagation.

        Args:
            fields (list[str]): List of hierarchical strings.
            sep (str): Separator used to split the hierarchy strings. Default is '.'.
            prune_leaves (int): Number of levels to prune from the end of each hierarchy. Default is 0.

        Returns:
            list[str]: Unique propagated hierarchy references (sorted lexicographically).

        Examples:
            >>> SQLQueryBuilder.propagate_hierarchies([
            ...     "shot.sequence.project.name",
            ...     "shot.name",
            ...     "name",
            ...     "status",
            ...     "user.name"
            ... ], prune_leaves=1)
            ['shot', 'shot.sequence', 'shot.sequence.project', 'user']

            >>> SQLQueryBuilder.propagate_hierarchies([
            ...     "department.team.lead.name",
            ...     "department.team.project.status",
            ...     "company.department.team.lead",
            ...     "company.department",
            ...     "team.member.task"
            ... ], prune_leaves=1)
            ['company', 'company.department', 'company.department.team', 'department', 'department.team', 'department.team.lead', 'department.team.project', 'team', 'team.member']

            >>> SQLQueryBuilder.propagate_hierarchies(["a.b.c.d", "a.b.c", "x.y.z"], prune_leaves=2)
            ['a', 'a.b', 'x']

            >>> SQLQueryBuilder.propagate_hierarchies(["level1/level2", "level1/level2/level3"], sep='/')
            ['level1', 'level1/level2', 'level1/level2/level3']

            >>> SQLQueryBuilder.propagate_hierarchies(["root.branch.leaf"], prune_leaves=1)
            ['root', 'root.branch']
        """
        unique_hierarchies = set()

        # Iterate over the flattened fields and process the hierarchical tokens.
        for field in fields:
            base_field, _ops = cls._strip_value_ops(field)
            tokens = cls._tokenize_field(base_field, sep=sep)

            # Generate all prefix levels
            for i in range(len(tokens) - prune_leaves):
                prefix = sep.join(tokens[:i+1])
                unique_hierarchies.add(prefix)

        # Return a lexicographically sorted list
        return sorted(unique_hierarchies)

    @classmethod
    def build_select_clause(
            cls,
            field_to_alias_pairs: list[tuple[str, str]] | None = None,
        ) -> str:
        """Build the SELECT part of the query.

        Arguments:
            field_to_alias_pairs: A list containing field names as strings or dictionaries mapping a field to an alias,
                or a dictionary mapping multiple fields to aliases.

        Returns:
            str: The SELECT clause in SQL format.

        Examples:
            # Basic: no aliases
            >>> SQLQueryBuilder.build_select_clause([
            ...     ("shot.sequence.project.name", ""),
            ...     ("shot.name", ""),
            ...     ("name", ""),
            ...     ("status", ""),
            ... ])
            "'shot.sequence.project'.name AS 'shot.sequence.project.name',\\n\\t'shot'.name AS 'shot.name',\\n\\t_.name AS 'name',\\n\\t_.status AS 'status'"

            # Basic: explicit aliases
            >>> SQLQueryBuilder.build_select_clause([
            ...     ("shot.sequence.project.name", "project_name"),
            ...     ("shot.name", "shot_name"),
            ... ])
            "'shot.sequence.project'.name AS 'project_name',\\n\\t'shot'.name AS 'shot_name'"

            # Mixed: some aliased, some default-to-field-name
            >>> SQLQueryBuilder.build_select_clause([
            ...     ("shot.sequence.project.name", ""),
            ...     ("shot.name", "my_shot_name"),
            ...     ("status", ""),
            ... ])
            "'shot.sequence.project'.name AS 'shot.sequence.project.name',\\n\\t'shot'.name AS 'my_shot_name',\\n\\t_.status AS 'status'"

            # Value stream default aggregation (to-many / indirect) => JSON_GROUP_ARRAY(...)
            >>> SQLQueryBuilder.build_select_clause(
            ...     [("shot.@Assets[shot].name", "")],
            ... )
            "JSON_GROUP_ARRAY('shot.@Assets[shot]'.name) FILTER (WHERE 'shot.@Assets[shot]'.name IS NOT NULL) AS 'shot.@Assets[shot].name'"

            # Value modifier: distinct() applies to the value stream
            >>> SQLQueryBuilder.build_select_clause(
            ...     [("shot.@Assets[shot].name.distinct()", "shot_asset_names")],
            ... )
            "JSON_GROUP_ARRAY(DISTINCT 'shot.@Assets[shot]'.name) FILTER (WHERE 'shot.@Assets[shot]'.name IS NOT NULL) AS 'shot_asset_names'"

            # Scalar aggregator: count() consumes the stream and returns a scalar
            >>> SQLQueryBuilder.build_select_clause(
            ...     [("shot.@Assets[shot].id.count()", "")],
            ... )
            "COUNT('shot.@Assets[shot]'.id) AS 'shot.@Assets[shot].id.count()'"

            # Scalar aggregator + distinct modifier: count distinct values
            >>> SQLQueryBuilder.build_select_clause(
            ...     [("shot.@Assets[shot].owner.username.count().distinct()", "")],
            ... )
            "COUNT(DISTINCT 'shot.@Assets[shot].owner'.username) AS 'shot.@Assets[shot].owner.username.count().distinct()'"

            # Scalar aggregator with explicit alias
            >>> SQLQueryBuilder.build_select_clause(
            ...     [("shot.@Assets[shot].id.count()", "asset_count")],
            ... )
            "COUNT('shot.@Assets[shot]'.id) AS 'asset_count'"
        """
        if not field_to_alias_pairs:
            return "*"

        def _build(field, alias):
            alias = alias or field
            base_field, ops = cls._strip_value_ops(field)
            field_inner_alias = cls._build_inner_alias(base_field)
            if cls._is_group_field(field):
                field_inner_alias = cls._compile_value_expr(field_inner_alias, ops)

            return f"{field_inner_alias} AS '{alias}'"

        # Handle both list of tuples (field, alias)
        select_parts = [
            _build(field, alias)
            for field, alias in field_to_alias_pairs
        ]

        return ",\n\t".join(select_parts)

    @classmethod
    def build_join_clause(
            cls,
            base_model: str,
            fields: list[str],
            relationships: dict[str, str]
        ) -> str:
        """Build the complete JOIN clause of the query by iterating over the required relation chains.

        This method derives joinable prefixes from the requested fields (e.g.,
        "shot.sequence.project.name" → "shot", "shot.sequence", "shot.sequence.project")
        and builds one LEFT JOIN per chain. Indirect relation chains
        (e.g., "@Assets[task]" or "shot.sequence.project.@Assets[project]") are also supported.

        Args:
            base_model (str): The base table/model for the query (e.g. "Tasks").
            fields (list[str]): A list of hierarchical field strings.
            relationships (dict[str, str]): A dictionary mapping relationships between tables.

        Returns:
            str: The JOIN clause in SQL format.

        Example:
            >>> SQLQueryBuilder.build_join_clause(
            ...     base_model="Tasks",
            ...     fields=["shot.sequence.project.name", "shot.name", "name", "status", "@Assets[task].name"],
            ...     relationships={
            ...         "Tasks.shot": "Shots.id",
            ...         "Shots.sequence": "Sequences.id",
            ...         "Sequences.project": "Projects.id",
            ...         "Assets.task": "Tasks.id",
            ...     }
            ... )
            "LEFT JOIN\\n\\tAssets AS '@Assets[task]' ON _.id = '@Assets[task]'.task\\nLEFT JOIN\\n\\tShots AS 'shot' ON _.shot = 'shot'.id\\n\
LEFT JOIN\\n\\tSequences AS 'shot.sequence' ON 'shot'.sequence = 'shot.sequence'.id\\n\
LEFT JOIN\\n\\tProjects AS 'shot.sequence.project' ON 'shot.sequence'.project = 'shot.sequence.project'.id"
        """
        # Derive joinable prefixes (e.g., "shot.sequence.project.name" → ["shot", "shot.sequence", "shot.sequence.project"]);
        # prune_leaves=1 skips the last field, then build one LEFT JOIN per chain.
        join_clauses = [
            cls._build_join_clause_for_chain(base_model, chain, relationships)
            for chain in cls.propagate_hierarchies(fields, prune_leaves=1)
        ]

        # Return the JOIN clauses as a single multi-line string.
        return "\n".join(join_clauses)

    @classmethod
    def build_where_clause(
            cls,
            base_model: str = None,
            filters: dict[GroupOperator | str, Any] = None,
            group_operator: GroupOperator | str = GroupOperator.AND,
            relationships: dict[str, str] | None = None,
            serializers: dict[str, DataSerializer] | None = None,
        ) -> tuple[str, set[str], list[Any]]:
        """Build the WHERE clause of the query.

        Indirect relation fields (e.g. "project.@Assets[project].name") can be used as filter keys;
        they are resolved to inner aliases by `_build_inner_alias`.

        Examples:
            >>> SQLQueryBuilder.build_where_clause(filters={"name": "John"})
            ('_.name = ?', {'name'}, ['John'])

            >>> where_clauses, fields, parameters = SQLQueryBuilder.build_where_clause(filters={
            ...     "age": {"gte": 18},
            ...     "name": {"contains": "John"}
            ... })
            >>> where_clauses, parameters
            ("_.age >= ? AND _.name LIKE '%' || ? || '%'", [18, 'John'])
            >>> fields == {'name', 'age'}
            True

            >>> SQLQueryBuilder.build_where_clause(filters={
            ...     "status": {"in": ["active", "pending", "suspended"]}
            ... })
            ('_.status IN (?, ?, ?)', {'status'}, ['active', 'pending', 'suspended'])

            >>> SQLQueryBuilder.build_where_clause(filters={
            ...     "status": {"not_in": ["inactive", "deleted"]}
            ... })
            ('_.status NOT IN (?, ?)', {'status'}, ['inactive', 'deleted'])

            >>> where_clauses, fields, parameters = SQLQueryBuilder.build_where_clause(filters={
            ...     "age": {"lt": 25},
            ...     "name": {"contains": "John"}
            ... })
            >>> where_clauses, parameters
            ("_.age < ? AND _.name LIKE '%' || ? || '%'", [25, 'John'])
            >>> fields == {'name', 'age'}
            True

            >>> SQLQueryBuilder.build_where_clause(filters={
            ...     "id": 123
            ... })
            ('_.id = ?', {'id'}, [123])

            >>> where_clauses, fields, parameters = SQLQueryBuilder.build_where_clause(filters={
            ...    "OR": {
            ...        "shot.sequence.project.name": {"contains": "Forest"},
            ...        "shot.status": {"eq": "Completed"},
            ...        "assigned_to.role": {"eq": "Artist"}
            ...    }
            ... })
            >>> where_clauses, parameters
            ("('shot.sequence.project'.name LIKE '%' || ? || '%' OR 'shot'.status = ? OR 'assigned_to'.role = ?)", ['Forest', 'Completed', 'Artist'])
            >>> fields == {'shot.sequence.project.name', 'assigned_to.role', 'shot.status'}
            True

            >>> where_clauses, fields, parameters = SQLQueryBuilder.build_where_clause(filters={
            ...     "OR": {
            ...         "age": {"lt": 18},
            ...         "AND": {
            ...             "status": {"eq": "inactive"},
            ...             "id": {"gte": 100}
            ...         }
            ...     }
            ... })
            >>> where_clauses, parameters
            ('(_.age < ? OR (_.status = ? AND _.id >= ?))', [18, 'inactive', 100])
            >>> fields == {'id', 'age', 'status'}
            True
        """
        if not filters:
            return None, set(), None

        where_clauses = []
        parameters = []
        fields = set()

        for key, value in cls._flatten_pairs(filters):
            # Handle group operators by recursively building sub-clauses.
            if isinstance(key, GroupOperator) or GroupOperator.is_valid(key):
                sub_where_clause, sub_fields, sub_parameters = cls.build_where_clause(
                    base_model, value, group_operator=key,
                    relationships=relationships, serializers=serializers,
                )
                where_clauses.append(f"({sub_where_clause})")
                fields.update(sub_fields)
                parameters.extend(sub_parameters)
                continue

            # If value is not a dict, assume equality.
            if not isinstance(value, dict):
                operator = FilterOperation.EQ
            else:
                operator, value = next(iter(value.items()))

            if not isinstance(operator, FilterOperation):
                operator = FilterOperation.from_string(operator)

            if operator.is_multi_param():
                if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
                    raise ValueError(
                        f"For '{operator}' operation, value should be an iterable (but not a string or bytes)"
                    )
                placeholders = ', '.join(['?'] * len(value))
                sql_operator = f"{operator.sql_operator} ({placeholders})"
            else:
                sql_operator = operator.sql_operator

            fields.add(key)
            where_clause = f"{cls._build_inner_alias(key)} {sql_operator}"
            where_clauses.append(where_clause)

            if serializers:
                model_field_name = cls.resolve_model_field(base_model, key, relationships)
                serializer = serializers.get(model_field_name)
            else:
                serializer = None

            # Process the value(s) with a serializer if provided.
            if operator.is_multi_param() or operator.num_params > 1:
                if serializer:
                    parameters.extend([serializer.serialize(v) for v in value])
                else:
                    parameters.extend(value)
            elif operator.requires_param():
                if serializer:
                    parameters.append(serializer.serialize(value))
                else:
                    parameters.append(value)

        where_clauses_str = cls._join_where_clauses(where_clauses, group_operator)

        return where_clauses_str, fields, parameters

    @classmethod
    def build_group_by_clause(
            cls,
            group_fields: set[str],
            relationships: dict[str, str],
            sep: str = CHAIN_SEPARATOR
        ) -> str:
        """Build the GROUP BY clause for the query.

        Args:
            group_fields (Set[str]): A set of fields to group by.
            base_model (str): The base model for the query.
            relationships (Dict[str, str]): A dictionary mapping relationships between models.
            sep (str): The separator used in the hierarchical field names.

        Returns:
            str: The GROUP BY clause in SQL format.

        Examples:
            >>> SQLQueryBuilder.build_group_by_clause(
            ...     group_fields={"shot.@Assets[shot].created_by.name", "shot.sequence.project.@Assets[project].name", "shot.sequence.project.@Assets[project].created_by.name"},
            ...     relationships={
            ...         "Tasks.shot": "Shots.id",
            ...         "Shots.sequence": "Sequences.id",
            ...         "Sequences.project": "Projects.id",
            ...         "Assets.project": "Projects.id",
            ...         "Assets.shot": "Shots.id",
            ...         "Shots.assets_shot": "Assets.shot",
            ...         "Projects.assets_project": "Assets.project",
            ...         "Assets.created_by": "Users.id",
            ...     }
            ... )
            "'shot'.id, 'shot.sequence.project'.id"
        """
        # Build GROUP BY aliases for each field:
        # follow to-many chain → resolve LHS → map to RHS → derive "alias_prefix.sep.related_field".
        group_by_clauses = set()
        for field in group_fields:
            parent_chain = cls._extract_indirect_chain(field)
            alias_prefix, field = cls._parse_relationship(cls._build_inner_alias(parent_chain))

            # "@Assets[shot]" -> "Assets.shot"
            _, related_field = cls._parse_relationship(relationships[cls._normalize_indirect_relation(field)])

            # Add left field alias to the GROUP BY clauses set
            group_by_clauses.add(f'{alias_prefix}{sep}{related_field}')

        return ', '.join(sorted(group_by_clauses))

    @classmethod
    def build_order_by_clause(cls, order_by: dict[str, SortOrder]) -> str:
        """Build the ORDER BY clause of the query.

        Args:
            order_by (dict[str, SortOrder | str]): A dictionary specifying the fields to sort by and the sort order.

        Returns:
            str: The ORDER BY clause in SQL format.

        Examples:
            >>> SQLQueryBuilder.build_order_by_clause({
            ...     "shot.name": SortOrder.DESC,
            ...     "name": SortOrder.ASC
            ... })
            "'shot'.name DESC, _.name ASC"
            
            >>> SQLQueryBuilder.build_order_by_clause({
            ...     "shot.name": "desc",
            ...     "name": "asc"
            ... })
            "'shot'.name DESC, _.name ASC"
        """
        if not order_by:
            return

        return ", ".join(
            f"{cls._build_inner_alias(field)} {cls._normalize_sort_order(direction)}"
            for field, direction in order_by.items()
        )

    @classmethod
    def build_context(cls, model: str, fields=None, filters=None, relationships=None,
                      order_by: dict[str, SortOrder] | None = None, limit: int = None,
                      serializers: dict[str, DataSerializer] | None = None,
                      distinct: bool = False) -> QueryContext:
        """Construct a SQL query dynamically based on the given parameters.

        This method builds a `SELECT` query by handling fields, filters, relationships,
        ordering, and limit constraints. It also processes indirect relational fields, such as
        one-to-many or reverse-like relationships expressed via '@Model[field]'.

        Args:
            model (str): The base model (table) from which to query data.
            fields (Optional[List[str]]): A list of fields to retrieve in the `SELECT` clause.
            filters (Optional[Dict[str, Any]]): A dictionary of filters for the `WHERE` clause.
            relationships (Optional[Dict[str, str]]): A dictionary defining relationships between models.
            order_by (Optional[Dict[str, SortOrder]]): A dictionary specifying sorting order for fields.
            limit (Optional[int]): The maximum number of records to retrieve.
            distinct (Optional[bool]): Whether to add the DISTINCT keyword to the SELECT clause.

        Returns:
            QueryContext: An instance of QueryContext.

        Examples:
            >>> context = SQLQueryBuilder.build_context(
            ...     model="Tasks",
            ...     fields=["id", "name", "status"],
            ...     filters={"status": "active"},
            ...     relationships={"Tasks.assigned_to": "Users.id"},
            ...     order_by={"created_at": "DESC"},
            ...     limit=10,
            ...     distinct=True
            ... )
            >>> context.query
            "SELECT DISTINCT\\n\\t_.id AS 'id',\\n\\t_.name AS 'name',\\n\\t_.status AS 'status'\\nFROM\\n\\t'Tasks' AS _\\nWHERE\\n\\t_.status = ?\\nORDER BY\\n\\t_.created_at DESC\\nLIMIT\\n\\t10"
            >>> context.parameters
            ['active']

            >>> context = SQLQueryBuilder.build_context(
            ...     model="Users",
            ...     fields=["id", "email"],
            ...     filters={"role": "admin"},
            ...     limit=5
            ... )
            >>> context.query
            "SELECT\\n\\t_.id AS 'id',\\n\\t_.email AS 'email'\\nFROM\\n\\t'Users' AS _\\nWHERE\\n\\t_.role = ?\\nLIMIT\\n\\t5"
            >>> context.parameters
            ['admin']
        """
        # 1) Derive alias maps & group info
        field_to_alias_pairs = list(cls._flatten_pairs(fields))
        grouped_fields = cls._resolve_grouped_fields(field_to_alias_pairs)

        # 2) Compile SQL + params
        sql, parameters = cls._build_sql(
            model=model,
            field_to_alias_pairs=field_to_alias_pairs,
            grouped_fields=grouped_fields,
            filters=filters,
            relationships=relationships,
            order_by=order_by,
            limit=limit,
            serializers=serializers,
            distinct=distinct,
        )

        return QueryContext(
            model=model,
            query=sql,
            parameters=parameters,
            relationships=relationships,
            serializers=serializers,
            grouped_fields=grouped_fields,
            field_to_alias_pairs=field_to_alias_pairs,
        )

    @classmethod
    def _build_sql(
            cls,
            model: str,
            field_to_alias_pairs: list[tuple[str, str]],
            grouped_fields: set[str],
            filters: dict[GroupOperator | str, Any] = None,
            relationships: dict[str, str] | None = None,
            order_by: dict[str, SortOrder] | None = None,
            limit: int | None = None,
            serializers: dict[str, 'DataSerializer'] | None = None,
            distinct: bool = False,
        ) -> tuple[str, list[Any]]:
        """Build the complete SQL query string along with its parameters.
        """
        select_clause = cls.build_select_clause(field_to_alias_pairs)
        where_clause, fields, parameters = cls.build_where_clause(model, filters, relationships=relationships, serializers=serializers)
        fields.update(cls._flatten_pairs(field_to_alias_pairs, keys_only=True))
        join_clause = cls.build_join_clause(model, fields, relationships)
        group_by_clause = cls.build_group_by_clause(grouped_fields, relationships)
        order_by_clause = cls.build_order_by_clause(order_by)

        query_clauses = [
            f"SELECT{' DISTINCT' if distinct else ''}\n\t{select_clause}",
            f"FROM\n\t'{model}' AS _",
        ]
        if join_clause:
            query_clauses.append(join_clause)
        if where_clause:
            query_clauses.append(f'WHERE\n\t{where_clause}')
        if group_by_clause:
            query_clauses.append(f'GROUP BY\n\t{group_by_clause}')
        if order_by_clause:
            query_clauses.append(f'ORDER BY\n\t{order_by_clause}')
        if limit:
            query_clauses.append(f'LIMIT\n\t{limit}')

        query_clauses_str = '\n'.join(query_clauses)

        return query_clauses_str, parameters

    @classmethod
    def _resolve_grouped_fields(cls, field_to_alias_pairs: list[tuple[str, str]]) -> set[str]:
        """Determine which fields should be grouped based on indirect relations.

        Args:
            field_to_alias_pairs (list[tuple[str, str]]): A list of tuples containing field names and their corresponding aliases.

        Returns:
            set[str]: A set of fields that should be grouped.
        """
        return {
            field
            for field, _alias in field_to_alias_pairs
            if cls._is_group_field(field)
        }

    @classmethod
    def _is_indirect_relation_chain(cls, field: str) -> bool:
        """Check if the given field string ends with an indirect relation segment.

        An indirect relation segment is of the form '@Model[field]', and this method
        returns True if the last segment in the chain matches that pattern.

        Args:
            field (str): The field string to check.

        Returns:
            bool: True if the field ends in an indirect relation segment, False otherwise.
        """
        match = cls._INDIRECT_RELATION_SEGMENT_RE.search(field)
        return bool(match and match.end() == len(field))

    @classmethod
    def _build_join_clause_for_chain(
            cls,
            base_model: str,
            chain: str,
            relationships: dict[str, str],
            sep: str = CHAIN_SEPARATOR,
        ) -> str:
        """Build a LEFT JOIN clause for a single relation chain.

        Handles both:
        - forward relations: "shot.sequence.project"
        - indirect relations: "@Assets[task]" or "shot.sequence.@Assets[project]"

        Args:
            base_model (str): The base table/model name.
            chain (str): The relation chain prefix (e.g. "shot" or "shot.sequence").
            relationships (dict[str, str]): Mapping of relationships.
            sep (str): The separator used in the chain.

        Returns:
            str: The LEFT JOIN clause for this chain.
        """
        # Resolve model-field relationships: left model-field → mapped right model-field → parsed (model, field)
        if cls._is_indirect_relation_chain(chain):
            # Handle indirect relation chains (e.g., "@Assets[task]").
            right_model_field = cls.resolve_model_field(base_model, chain, relationships)
            right_model, right_field = cls._parse_relationship(right_model_field)

            # Determine the left side alias from the inverse relationship.
            left_model, _right_reverse_form = cls._parse_relationship(cls._build_inner_alias(chain))
            _left_model, left_field = cls._parse_relationship(relationships[right_model_field])
            left_field_alias = f'{left_model}{sep}{left_field}'

        else:
            left_model_field = cls.resolve_model_field(base_model, chain, relationships)
            right_model_field = relationships[left_model_field]
            right_model, right_field = cls._parse_relationship(right_model_field)

            # Determine the left side alias.
            left_field_alias = cls._build_inner_alias(chain)

        # Build the right side alias for the join table using the chain.
        right_model_alias = f"'{chain}'"
        right_field_alias = f"{right_model_alias}{sep}{right_field}"

        # Construct the LEFT JOIN clause.
        return (
            f"LEFT JOIN\n\t{right_model} AS {right_model_alias} "
            f"ON {left_field_alias} = {right_field_alias}"
        )

    @classmethod
    def _normalize_indirect_relation(cls, field: str) -> str:
        """Transform an indirect relation segment into a standard 'Model.field' format.

        Examples:
            >>> SQLQueryBuilder._normalize_indirect_relation("@Assets[project]")
            'Assets.project'
            >>> SQLQueryBuilder._normalize_indirect_relation("@Users[assigned_tasks]")
            'Users.assigned_tasks'
        """
        return field[1:-1].replace('[', '.', 1)

    @staticmethod
    def _normalize_sort_order(sort_order: SortOrder | str | int) -> str:
        if isinstance(sort_order, int):
            # In PyQt, 0 is AscendingOrder and 1 is DescendingOrder
            return "DESC" if sort_order else "ASC"
        return str(sort_order).upper()

    @classmethod
    def _flatten_pairs(
            cls,
            data: str | tuple[str, Any] | dict[str, Any] | Iterable[Any],
            keys_only: bool = False
        ) -> Generator[tuple[str, Any] | str, None, None]:
        """Recursively flattens key-value pairs from various data structures.

        This method supports:
        - Strings (yields the string as both key and value)
        - Tuples of length 2 (yields them as-is)
        - Dictionaries (yields items as key-value pairs)
        - Iterables containing any of the above (recursively processes each element)
        - Optionally, only the keys from the data structures

        Args:
            data: The input data, which can be a string, tuple of two elements,
                dictionary, or an iterable containing any of these.
            keys_only: If True, only keys will be yielded (ignoring values).

        Yields:
            Tuple[str, Any] | str: Tuples of (key, value) extracted from the input,
                or just (key) if keys_only is True.

        Examples:
            >>> list(SQLQueryBuilder._flatten_pairs("status"))
            [('status', 'status')]

            >>> list(SQLQueryBuilder._flatten_pairs(("priority", 1)))
            [('priority', 1)]

            >>> list(SQLQueryBuilder._flatten_pairs({"name": "Alice", "age": 30}))
            [('name', 'Alice'), ('age', 30)]

            >>> list(SQLQueryBuilder._flatten_pairs([("id", 42), {"role": "admin"}]))
            [('id', 42), ('role', 'admin')]

            >>> list(SQLQueryBuilder._flatten_pairs([
            ...     "category",
            ...     ("level", "high"),
            ...     {"status": "active", "rank": 5}
            ... ], keys_only=True))
            ['category', 'level', 'status', 'rank']
        """
        # Handle the simple case where data is a string.
        if isinstance(data, str):
            yield data if keys_only else (data, data)

        # Check early if data is a tuple of length 2.
        elif isinstance(data, tuple) and len(data) == 2:
            yield data[0] if keys_only else data

        # Handle the case where data is a dict.
        elif isinstance(data, dict):
            yield from data.keys() if keys_only else data.items()

        # Otherwise, if it's an iterable (but not a string), recursively process each element.
        elif isinstance(data, Iterable):
            for item in data:
                yield from cls._flatten_pairs(item, keys_only)

    @staticmethod
    def _tokenize_field(chain: str, sep: str = CHAIN_SEPARATOR) -> list[str]:
        return chain.split(sep)

    @staticmethod
    def _parse_relationship(relationship: str, sep: str = CHAIN_SEPARATOR) -> tuple[str, str]:
        """Parse a simplified relationship string into (model, field).
        """
        return relationship.rsplit(sep, 1)

    @classmethod
    def _is_group_field(cls, field: str) -> bool:
        """Checks if a hierarchical field implies a one-to-many/indirect relationship.

        Any field that contains at least one indirect relation segment
        ('@Model[field]') is considered groupable.

        Args:
            field (str): The hierarchical field string to check.

        Returns:
            bool: True if the field implies a one-to-many relationship, False otherwise.
        """
        return bool(cls._extract_indirect_chain(field))

    @classmethod
    def _is_relation_chain(cls, field: str, sep: str = CHAIN_SEPARATOR) -> bool:
        """Determines if the given field string represents a relation chain.
        """
        return sep in field

    @classmethod
    def _extract_indirect_chain(cls, field: str) -> str | None:
        """Return substring through the last '@Model[field]' match.

        A indirect relation represents an inverted foreign-key reference, where
        the relation points from the related model back to the base model.
        Such relations are denoted by an at-sign followed by the related model
        name and the referencing field in brackets, e.g. '@Assets[project]'.

        Examples:
            >>> SQLQueryBuilder._extract_indirect_chain("shot.sequence.project.@Assets[project].created_by.name")
            'shot.sequence.project.@Assets[project]'
            >>> SQLQueryBuilder._extract_indirect_chain("@Task[parent_task].project.@Assets[project].name")
            '@Task[parent_task].project.@Assets[project]'
            >>> SQLQueryBuilder._extract_indirect_chain("shot.sequence.project.name") is None
            True
        """
        last_match = None
        for match in cls._INDIRECT_RELATION_SEGMENT_RE.finditer(field):
            last_match = match
        if not last_match:
            return

        # Return the substring up to and including the matched to-many segment.
        return field[: last_match.end()]

    @staticmethod
    def _join_where_clauses(where_clauses: list[str], group_operator: GroupOperator | str) -> str:
        if isinstance(group_operator, GroupOperator):
            group_operator_str = group_operator.sql_operator
        else:
            group_operator_str = group_operator.upper()

        return f" {group_operator_str} ".join(where_clauses)

    @classmethod
    def _build_inner_alias(cls, field: str, base_alias: str = '_') -> str:
        """Builds the inner alias for a given field.

        Args:
            field (str): The hierarchical field name (e.g. "shot.sequence.name").
            base_alias (str): The base alias to use for non-relational fields.

        Returns:
            str: The inner alias in SQL format.

        Examples:
            >>> SQLQueryBuilder._build_inner_alias("shot.sequence.name")
            "'shot.sequence'.name"
            >>> SQLQueryBuilder._build_inner_alias("shot")
            '_.shot'
        """
        if cls._is_relation_chain(field):
            # e.g. "shot.sequence" => "'shot'.sequence"
            relation_chain, relation_field = cls._parse_relationship(field)
            return f"'{relation_chain}'.{relation_field}"
        else:
            # e.g. "shot" => '_.shot'
            return f'{base_alias}.{field}'

    @staticmethod
    def _strip_value_ops(field: str) -> tuple[str, list[str]]:
        """Strip trailing '.op()' value operations and return (base_field, ops)."""
        ops: list[str] = []
        while True:
            match = re.search(r"\.([a-z_]+)\(\)$", field)
            if not match:
                break
            ops.append(match.group(1))
            field = field[: match.start()]
        ops.reverse()  # keep left-to-right order as written
        return field, ops

    @staticmethod
    def _compile_value_expr(field_inner_alias: str, ops: list[str]) -> str:
        """Compile a value stream + ops to a SQL select expression (no AS).
        """
        # classify
        distinct_sql = "DISTINCT " if "distinct" in ops else ""
        scalar_aggs = [op for op in ops if op in {"count", "sum", "avg", "min", "max"}]

        # If a scalar aggregator exists, it consumes the stream into a scalar.
        if scalar_aggs:
            # If multiple scalar aggs are chained, use the last one as the effective aggregator.
            agg = scalar_aggs[-1].upper()

            # COUNT(*) support can be added later; for now we count the expression.
            return f"{agg}({distinct_sql}{field_inner_alias})"

        # No scalar aggregator => this is a stream result.
        return (
            f"JSON_GROUP_ARRAY({distinct_sql}{field_inner_alias}) "
            f"FILTER (WHERE {field_inner_alias} IS NOT NULL)"
        )


# Example usage
if __name__ == "__main__":
    import doctest
    doctest.testmod()

    context = SQLQueryBuilder.build_context(
        model='Tasks',
        fields=[
            "shot.sequence.project.name",
            ("shot.sequence.project.@Assets[project].name.distinct().count()", "project_name_count"),
            "shot.name",
            "name",
            "status",
            "parent_task.name",
            "start_date",
            "due_date",
            "assigned_to.email",
            "@Assets[task].name",
            ("@Tasks[parent_task].name", "child_task_names"),
        ],
        filters={
            "OR": {
                "shot.sequence.project.name": {"contains": "Forest"},
                "shot.status": {"eq": "Completed"},
                "assigned_to.role": {"eq": "Artist"}
            }
        },
        # subqueries={
        #     ...
        # },
        relationships={
            "Tasks.shot": "Shots.id",
            "Shots.sequence": "Sequences.id",
            "Sequences.project": "Projects.id",
            "Tasks.assigned_to": "Users.id",
            "Tasks.parent_task": "Tasks.id",
            "Assets.project": "Projects.id",
            "Assets.task": "Tasks.id",
        },
        order_by={
            "shot.name": "desc",
            "name": "asc"
        },
        limit=5
    )
    print(context.query)
    print(context.parameters)
    # NOTE: Example outputs
    # SELECT
    #         'shot.sequence.project'.name AS 'shot.sequence.project.name',
    #         COUNT(DISTINCT 'shot.sequence.project.@Assets[project]'.name) AS 'project_name_count',
    #         'shot'.name AS 'shot.name',
    #         _.name AS 'name',
    #         _.status AS 'status',
    #         'parent_task'.name AS 'parent_task.name',
    #         _.start_date AS 'start_date',
    #         _.due_date AS 'due_date',
    #         'assigned_to'.email AS 'assigned_to.email',
    #         JSON_GROUP_ARRAY('@Assets[task]'.name) FILTER (WHERE '@Assets[task]'.name IS NOT NULL) AS '@Assets[task].name',
    #         JSON_GROUP_ARRAY('@Tasks[parent_task]'.name) FILTER (WHERE '@Tasks[parent_task]'.name IS NOT NULL) AS 'child_task_names'
    # FROM
    #         'Tasks' AS _
    # LEFT JOIN
    #         Assets AS '@Assets[task]' ON _.id = '@Assets[task]'.task
    # LEFT JOIN
    #         Tasks AS '@Tasks[parent_task]' ON _.id = '@Tasks[parent_task]'.parent_task
    # LEFT JOIN
    #         Users AS 'assigned_to' ON _.assigned_to = 'assigned_to'.id
    # LEFT JOIN
    #         Tasks AS 'parent_task' ON _.parent_task = 'parent_task'.id
    # LEFT JOIN
    #         Shots AS 'shot' ON _.shot = 'shot'.id
    # LEFT JOIN
    #         Sequences AS 'shot.sequence' ON 'shot'.sequence = 'shot.sequence'.id
    # LEFT JOIN
    #         Projects AS 'shot.sequence.project' ON 'shot.sequence'.project = 'shot.sequence.project'.id
    # LEFT JOIN
    #         Assets AS 'shot.sequence.project.@Assets[project]' ON 'shot.sequence.project'.id = 'shot.sequence.project.@Assets[project]'.project
    # WHERE
    #         ('shot.sequence.project'.name LIKE '%' || ? || '%' OR 'shot'.status = ? OR 'assigned_to'.role = ?)
    # GROUP BY
    #         'shot.sequence.project'.id, _.id
    # ORDER BY
    #         'shot'.name DESC, _.name ASC
    # LIMIT
    #         5
    # ['Forest', 'Completed', 'Artist']
