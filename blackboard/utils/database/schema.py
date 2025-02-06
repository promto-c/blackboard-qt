# Type Checking Imports
# ---------------------
from typing import TYPE_CHECKING, List, Optional, Dict, Any
if TYPE_CHECKING:
    from .database_manager import DatabaseManager

# Standard Library Imports
# ------------------------
from dataclasses import dataclass, field


# Class Definitions
# -----------------
@dataclass
class ForeignKey:
    """Represents a foreign key constraint in a database table.
    """
    constraint_id: int           # Foreign key constraint ID
    sequence: int                # Sequence number within the foreign key
    local_table: str             # The local table name (the table containing the foreign key)
    local_field: str             # The field in the local table (foreign key column)
    related_table: str           # The referenced table name
    related_field: str           # The field in the referenced table (primary key column)
    on_update: str               # Action on update (e.g., "CASCADE", "RESTRICT", "SET NULL")
    on_delete: str               # Action on delete (e.g., "CASCADE", "RESTRICT", "SET NULL")
    match: str                   # The match type (e.g., "NONE", "PARTIAL", "FULL")

    @classmethod
    def from_dict(cls, data: Dict[str, Any], local_table: str) -> "ForeignKey":
        """Create a ForeignKey instance from a dictionary of PRAGMA output.

        Args:
            data: A dictionary with keys matching SQLite PRAGMA output.
            local_table: The name of the local table (since PRAGMA output does not include it).

        Returns:
            An instance of ForeignKey with fields populated from the dictionary.
        """
        return cls(
            constraint_id = data["id"],
            sequence = data["seq"],
            local_table = local_table,
            local_field = data["from"],      # 'from' in SQLite output becomes local_field here.
            related_table = data["table"],
            related_field = data["to"],        # 'to' in SQLite output becomes related_field.
            on_update = data["on_update"],
            on_delete = data["on_delete"],
            match = data["match"]
        )

    def get_field_definition(self) -> str:
        """Generate the SQL definition string for this foreign key.
        """
        definition = (f"FOREIGN KEY({self.local_field}) REFERENCES {self.related_table}({self.related_field}) "
                      f"ON UPDATE {self.on_update} ON DELETE {self.on_delete}")
        if self.match and self.match != 'NONE':
            definition += f" MATCH {self.match}"
        return definition

@dataclass
class ManyToManyField:
    """Represents a many-to-many relationship field.
    """
    track_field_name: str                   # The field name used for display purposes
    local_table: str                        # The originating table name
    related_table: str                      # The related table name
    junction_table: str                     # The name of the junction table
    local_fk: ForeignKey                    # ForeignKeyInfo for the local table
    related_fk: ForeignKey                  # ForeignKeyInfo for the remote table

@dataclass
class FieldInfo:
    cid: int = -1
    name: str = ''
    type: str = 'NULL'
    notnull: int = 0
    dflt_value: Optional[str] = None
    pk: int = 0
    is_unique: bool = False
    fk: Optional[ForeignKey] = None
    m2m: Optional[ManyToManyField] = None

    def get_field_definition(self) -> str:
        """Generate the SQL definition string for this field.
        """
        definition = f"{self.name} {self.type}"
        if self.is_not_null:
            definition += " NOT NULL"
        if self.is_primary_key:
            definition += " PRIMARY KEY"
        if self.is_unique:
            definition += " UNIQUE"
        # if self.is_foreign_key:
        #     definition += f", {self.fk.get_field_definition()}"
        return definition

    @property
    def is_not_null(self) -> bool:
        return bool(self.notnull)

    @property
    def is_primary_key(self) -> bool:
        return bool(self.pk)

    @property
    def is_foreign_key(self) -> bool:
        return self.fk is not None

    @property
    def is_many_to_many(self) -> bool:
        """Check if the field is part of a many-to-many relationship.
        """
        return self.m2m is not None

# NOTE: WIP
@dataclass
class RelationStep:
    local_table: str
    foreign_key: str
    related_table: str
    related_field: str

@dataclass
class RelationChain:
    root_table: str
    steps: List[RelationStep] = field(default_factory=list)
    select_fields: List[str] = field(default_factory=list)  # Fields to select from the final table

    @staticmethod
    def parse(chain: str, db_manager: 'DatabaseManager') -> 'RelationChain':
        parts = chain.split('.')
        if len(parts) < 2:
            raise ValueError("Relation chain must include at least one relationship and one field.")

        root_table = parts[0]
        current_table = root_table
        current_model = db_manager.get_model(current_table)
        relation_chain = RelationChain(root_table=root_table)

        for i in range(1, len(parts) - 1):
            fk_column = parts[i]

            try:
                field_info = current_model.get_field(fk_column)
            except ValueError as e:
                raise ValueError(f"Error parsing relation chain: {e}")

            if not field_info.fk:
                raise ValueError(f"Field '{fk_column}' in table '{current_table}' is not a foreign key.")

            step = RelationStep(
                local_table=current_table,
                foreign_key=fk_column,
                related_table=field_info.fk.related_table,
                related_field=field_info.fk.related_field
            )
            relation_chain.steps.append(step)
            current_table = step.related_table
            current_model = db_manager.get_model(current_table)

        # The last part is the field to select from the final table
        select_field = parts[-1]
        if select_field not in current_model.get_field_names():
            raise ValueError(f"Field '{select_field}' does not exist in table '{current_table}'.")

        # Add the final field to select_fields
        relation_chain.select_fields.append(f"{current_table}.{select_field} AS {select_field}")

        return relation_chain
