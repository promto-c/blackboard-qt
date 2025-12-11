# Relation Query DSL

This document defines the **relation-aware query DSL** used by `SQLQueryBuilder` and `QueryContext` for building SQL queries without writing explicit joins.

The goals are:

* Express cross-table queries using **field paths**, not raw SQL.
* Support **indirect relations** such as “all Assets for this Task’s project” via a short, readable syntax (`@Assets[project]`).
* Provide a consistent mental model for **fields**, **relations**, **filters**, **sorting**, and **grouping**.

This DSL is implemented by:

* `QueryContext`
* `SQLQueryBuilder`
* Enums: `GroupOperator`, `SortOrder`, `FilterOperation`

---

## 1. Core Concepts

### 1.1 Base model

Each query is built **from a single base model** (table), usually a string:

```python
base_model = "Tasks"

context = SQLQueryBuilder.build_context(
    model=base_model,
    fields=[...],
    filters={...},
    relationships={...},
)
```

Internally:

* Base model is aliased as `_` in SQL:

  * `Tasks` → `'Tasks' AS _`
* Simple fields like `"name"` map to `_.name` in SQL.

---

### 1.2 Relationship mapping

Relationships between models are declared in a flat dictionary:

```python
relationships = {
    "Tasks.shot": "Shots.id",
    "Shots.sequence": "Sequences.id",
    "Sequences.project": "Projects.id",
    "Tasks.assigned_to": "Users.id",
    "Tasks.parent_task": "Tasks.id",
    "Assets.project": "Projects.id",
    "Assets.task": "Tasks.id",
}
```

**Format:**

* Key: `"LeftModel.left_field"`
* Value: `"RightModel.right_field"`

Semantics:

* `"Tasks.shot": "Shots.id"` means: `Tasks.shot` is a FK pointing to `Shots.id`.

This mapping is used by:

* `resolve_model` – follow a chain of relations and return the final model.
* `resolve_model_field` – return the final `Model.field`.
* `build_join_clause` – generate all required `LEFT JOIN`s.
* `build_group_by_clause` – deduce grouping columns for one-to-many relations.

---

## 2. Field Path Syntax

### 2.1 Chain separator

The **chain separator** is a dot:

```python
SQLQueryBuilder.CHAIN_SEPARATOR = "."
```

A path is a sequence of **segments**:

* `"name"` → field on the base model
* `"shot.name"` → field `name` on the related model `shot`
* `"shot.sequence.project.name"` → multi-hop relation

### 2.2 Simple paths (forward relations)

Simple paths **do not start with `@`** and are resolved using `relationships`:

```python
fields = [
    "name",                        # Tasks.name   (base model)
    "shot.name",                   # Shots.name   via Tasks.shot → Shots.id
    "shot.sequence.project.name",  # Projects.name via Shots.sequence → Sequences.project → Projects.id
]
```

In SQL, these are turned into:

* `_.name`
* `'shot'.name`
* `'shot.sequence.project'.name`

**How it works:**

1. `resolve_model` walks through the path:

   * `Tasks` ―(shot)→ `Shots` ―(sequence)→ `Sequences` ―(project)→ `Projects`
2. `build_join_clause` emits `LEFT JOIN` statements for each prefix:

   * `"shot"`
   * `"shot.sequence"`
   * `"shot.sequence.project"`

---

## 3. Indirect Relation Segments (`@Model[field]`)

### 3.1 Syntax

An **indirect relation segment** has the form:

```text
@Model[ref_field]
```

Examples:

* `@Assets[task]`
* `@Assets[project]`
* `@Tasks[parent_task]`

These are treated as a **special path segment** inside a field chain:

```python
"@Assets[task].name"
"shot.sequence.project.@Assets[project].name"
"project.@Assets[project].owner.name"
```

### 3.2 Semantics

Informally:

> “From the current context, hop to `Model` using the relationship `Model.ref_field` pointing back to the current model.”

Given:

```python
relationships = {
    "Assets.task": "Tasks.id",
    "Assets.project": "Projects.id",
}
```

then:

* From base model **Tasks**:

  * `@Assets[task]` means:

    * “All `Assets` where `Assets.task = Tasks.id`”.
* From context **Projects**:

  * `@Assets[project]` means:

    * “All `Assets` where `Assets.project = Projects.id`”.

The DSL does **not** require you to specify `Assets.task = Tasks.id` manually in the query. It only requires the relationship mapping.

### 3.3 Mixed paths with indirect segments

You can mix forward and indirect hops:

```python
"project.@Assets[project].owner.name"
"shot.sequence.project.@Assets[project].name"
"shot.sequence.project.@Assets[project].created_by.name"
```

Resolution pattern:

1. Resolve the **forward chain** `project` from the base model.
2. At `@Assets[project]`, treat this as a hop from the current model (here `Projects`) to `Assets` using `Assets.project`.
3. Continue with normal segments (`owner`, `created_by`, `name`) from the `Assets` side, using `relationships`.

### 3.4 Indirect chain extraction

A helper like:

```python
SQLQueryBuilder._extract_indirect_chain("shot.sequence.project.@Assets[project].created_by.name")
# -> "shot.sequence.project.@Assets[project]"
```

is used to:

* detect **one-to-many chains**,
* drive `GROUP BY` behavior,
* decide which side to group on.

---

## 4. Relation & Value Aggregators

These apply to relation segments (`@Model[field]`) or scalar values.

### 4.1 Aggregators Overview

Aggregators can operate either at the **relation level** (on `@Model[field]` segments)
or at the **value level** (on scalar fields at the end of the chain).

| Aggregator   | Level    | SQL Mapping / Purpose                             | Result Type           |
| ------------ | -------- | ------------------------------------------------- | --------------------- |
| `.one()`     | Relation | Treat relation as 1-to-1 (`SELECT .. LIMIT 1`)    | Scalar entity or NULL |
| `distinct()` | Value    | `JSON_GROUP_ARRAY(DISTINCT field ORDER BY field)` | Array                 |
| `count()`    | Value    | `COUNT(*)` or `COUNT(field)`                      | Scalar                |
| `sum()`      | Value    | `SUM(field)`                                      | Scalar                |
| `min()`      | Value    | `MIN(field)`                                      | Scalar                |
| `max()`      | Value    | `MAX(field)`                                      | Scalar                |
| `avg()`      | Value    | `AVG(field)`                                      | Scalar                |

### 4.2 Aggregator Examples

**Relation-level (`.one()`) examples**

```text
# Task → Assignments (logically one primary assignment)
task.@Assignments[task].one().user.name

# Asset → Versions (pick latest / canonical version)
asset.@Versions[asset].one().file_path
```

**Value-level (`distinct`, `count`, `sum`, `avg`, ...) examples**

```text
# Unique emails of all owners of assets in a project
project.@Assets[project].owner.email.distinct()

# Unique tag names across all assets linked to shots under a task
task.shot.@AssetShot[shot].tag.name.distinct()

# Aggregated numeric examples
project.@Assets[project].duration.sum()
project.@Assets[project].owner_id.count()
project.@Assets[project].amount.avg()
```

### 4.3 Grammar & Precedence

(kept concise to fit DSL)

* Relation resolves first.
* Relation aggregators attach only to relation segment.
* Value aggregators attach only to terminal scalar fields.
* Only one relation aggregator allowed.
* Default relation return type = array.

---

## 5. Filters DSL

Filters are expressed as nested dictionaries, using:

* **field paths** (simple or indirect) as keys
* **`FilterOperation`** or string operators as inner keys
* `GroupOperator` (or `"AND"`, `"OR"`) for grouping

### 4.1 Simple equality

```python
filters = {
    "status": "active",  # shorthand for {"status": {"eq": "active"}}
}
```

Generated WHERE:

```sql
_.status = ?
-- params: ["active"]
```

### 4.2 Explicit operations

Supported operations come from `FilterOperation` (e.g. `eq`, `lt`, `lte`, `gt`, `gte`, `contains`, `in`, `not_in`, etc.):

```python
filters = {
    "age": {"gte": 18},
    "name": {"contains": "John"},
}
```

Generated WHERE:

```sql
_.age >= ? AND _.name LIKE '%' || ? || '%'
-- params: [18, "John"]
```

### 4.3 Grouping with AND / OR

```python
filters = {
    "OR": {
        "shot.sequence.project.name": {"contains": "Forest"},
        "shot.status": {"eq": "Completed"},
        "assigned_to.role": {"eq": "Artist"},
    }
}
```

Generated WHERE (simplified):

```sql
(
  'shot.sequence.project'.name LIKE '%' || ? || '%'
  OR 'shot'.status = ?
  OR 'assigned_to'.role = ?
)
```

### 4.4 Indirect fields in filters

You can filter using indirect paths:

```python
filters = {
    "project.@Assets[project].name": {"contains": "tree"},
}
```

This is resolved to the correct alias using `_build_inner_alias` and `resolve_model_field`.

---

## 5. Sorting DSL (`order_by`)

Sorting is specified as:

```python
order_by = {
    "shot.name": "desc",
    "name": "asc",
}
```

or using `SortOrder` enum:

```python
order_by = {
    "shot.name": SortOrder.DESC,
    "name": SortOrder.ASC,
}
```

`SQLQueryBuilder.build_order_by_clause` normalizes all values via `_normalize_sort_order`:

* `"asc"`, `"ASC"` → `ASC`
* `"desc"`, `"DESC"` → `DESC`
* `SortOrder.ASC` → `ASC`
* `SortOrder.DESC` → `DESC`
* `0` / `1` (from Qt sort order) → `ASC` / `DESC`

Generated ORDER BY:

```sql
'shot'.name DESC, _.name ASC
```

Indirect or deep paths can also be used as keys:

```python
order_by = {
    "shot.sequence.project.@Assets[project].created_date": "desc",
}
```

---

## 6. Grouping and Aggregation

### 6.1 When a field is considered “grouped”

A field is considered to represent a **one-to-many/indirect relation** if it includes at least one **indirect relation segment**:

```python
SQLQueryBuilder._is_group_field(
    "shot.sequence.project.@Assets[project].created_by.name"
)
# → True
```

`_resolve_grouped_fields` collects such fields; they are then:

* Aggregated in `SELECT` via `JSON_GROUP_ARRAY(...)`.
* Grouped in `GROUP BY` using the **left side** of the relation.

### 6.2 SELECT behavior for grouped fields

If a field is in `grouped_fields`, its inner alias is wrapped:

```sql
JSON_GROUP_ARRAY(field_alias) FILTER (WHERE field_alias IS NOT NULL) AS 'field_name'
```

Example:

```python
fields = [
    "shot.sequence.project.@Assets[project].name",
]
```

SELECT might contain:

```sql
JSON_GROUP_ARRAY('shot.sequence.project.@Assets[project]'.name)
  FILTER (WHERE 'shot.sequence.project.@Assets[project]'.name IS NOT NULL)
  AS 'shot.sequence.project.@Assets[project].name'
```

### 6.3 GROUP BY behavior

`build_group_by_clause`:

* Looks at each grouped field.
* Extracts parent chain through the last indirect segment:

  * `"shot.sequence.project.@Assets[project].created_by.name"`
  * → `"shot.sequence.project.@Assets[project]"`
* Uses the relationships map to determine **which column on the left side** defines uniqueness.

Example:

```python
group_fields = {
    "shot.@Assets[shot].created_by.name",
    "shot.sequence.project.@Assets[project].name",
    "shot.sequence.project.@Assets[project].created_by.name",
}

relationships = {
    "Tasks.shot": "Shots.id",
    "Shots.sequence": "Sequences.id",
    "Sequences.project": "Projects.id",
    "Assets.project": "Projects.id",
    "Assets.shot": "Shots.id",
    "Shots.assets_shot": "Assets.shot",
    "Projects.assets_project": "Assets.project",
    "Assets.created_by": "Users.id",
}
```

Generated GROUP BY:

```sql
'shot'.id, 'shot.sequence.project'.id
```

---

## 7. Putting It All Together (End-to-End Example)

```python
base_model = "Tasks"

fields = [
    "shot.sequence.project.name",
    "shot.sequence.project.@Assets[project].name",  # indirect: assets per project
    "shot.name",
    "name",
    "status",
    "parent_task.name",
    "start_date",
    "due_date",
    "assigned_to.email",
    "@Assets[task].name",                           # indirect: assets per task
    "@Tasks[parent_task].name",                     # indirect: child tasks
]

filters = {
    "OR": {
        "shot.sequence.project.name": {"contains": "Forest"},
        "shot.status": {"eq": "Completed"},
        "assigned_to.role": {"eq": "Artist"},
    }
}

relationships = {
    "Tasks.shot": "Shots.id",
    "Shots.sequence": "Sequences.id",
    "Sequences.project": "Projects.id",
    "Tasks.assigned_to": "Users.id",
    "Tasks.parent_task": "Tasks.id",
    "Assets.project": "Projects.id",
    "Assets.task": "Tasks.id",
}

order_by = {
    "shot.name": "desc",
    "name": "asc",
}

context = SQLQueryBuilder.build_context(
    model=base_model,
    fields=fields,
    filters=filters,
    relationships=relationships,
    order_by=order_by,
    limit=5,
)

print(context.query)
print(context.parameters)
```

Conceptually, this means:

* **FROM**: `Tasks`
* **JOIN**:

  * `Tasks → Shots → Sequences → Projects`
  * `Tasks ← Assets` (via `Assets.task`)
  * `Projects ← Assets` (via `Assets.project`)
  * `Tasks ← Tasks` (for `parent_task` / child tasks)
  * `Tasks.assigned_to → Users`
* **SELECT**:

  * Simple scalar fields from base and related models.
  * Aggregated JSON arrays for one-to-many indirect fields.
* **WHERE**:

  * Filter tasks where:

    * project name contains `"Forest"`, OR
    * shot status is `"Completed"`, OR
    * assigned user role is `"Artist"`.
* **ORDER BY**:

  * Shot name descending, then task name ascending.
* **LIMIT**:

  * 5 rows.

---

## 8. Design Principles

* **Low ceremony**: the user writes paths like `"shot.sequence.project.name"` and `"@Assets[project].name"`; `SQLQueryBuilder` generates all joins.
* **Explicit relationship metadata**: all join logic comes from `relationships`.
* **Indirect relations as first-class**: `@Model[field]` segments encode reverse/one-to-many hops cleanly.
* **Composable**: the same path syntax is used in:

  * `fields` (SELECT)
  * `filters` (WHERE)
  * `order_by` (ORDER BY)
  * grouping inference (GROUP BY)

This DSL is intentionally **implementation-agnostic**: you can point it at SQLite, Postgres, or any SQL backend as long as the generated SQL and relationship mappings match your schema.
