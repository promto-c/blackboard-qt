# Relation Query DSL

This document defines the **relation-aware query DSL** used by `SQLQueryBuilder`, `QueryContext`, and `QuerySpec` for building SQL queries **without writing explicit joins**.

The goals are:

* Express cross-table queries using **field paths**, not raw SQL.
* Support **indirect (to-many) relations** such as “all Assets for this Project” via a short, readable syntax (`@Assets[project]`).
* Cleanly separate **relation traversal** from **value operations**.
* Provide a consistent mental model for **fields**, **relations**, **filters**, **sorting**, **grouping**, and **subqueries**.

This DSL is implemented by:

* `QuerySpec` / `QueryOneSpec`
* `QueryContext`
* `SQLQueryBuilder`
* Enums: `GroupOperator`, `SortOrder`, `FilterOperation`

## Table of Contents

- [1. Design Principles (Summary)](#1-design-principles-summary)
- [2. Quick Start](#2-quick-start)
- [3. Core Concepts](#3-core-concepts)
  - [3.1 Base model](#31-base-model)
  - [3.2 Relationship mapping](#32-relationship-mapping)
- [4. Field Path Syntax](#4-field-path-syntax)
  - [4.1 Chain separator](#41-chain-separator)
  - [4.2 Forward (simple) relations](#42-forward-simple-relations)
  - [4.3 Field selection and aliasing](#43-field-selection-and-aliasing)
- [5. Indirect Relation Segments (`@Model[field]`)](#5-indirect-relation-segments-modelfield)
  - [5.1 Syntax](#51-syntax)
  - [5.2 Semantics](#52-semantics)
  - [5.3 Mixed paths](#53-mixed-paths)
  - [5.4 Indirect chain extraction](#54-indirect-chain-extraction)
- [6. Value Operations](#6-value-operations)
  - [6.1 Design rule](#61-design-rule)
  - [6.2 Modifiers vs aggregators](#62-modifiers-vs-aggregators)
  - [6.3 `.distinct()` behavior](#63-distinct-behavior)
  - [6.4 Examples](#64-examples)
- [7. Filters DSL](#7-filters-dsl)
  - [7.1 Simple equality](#71-simple-equality)
  - [7.2 Explicit operators](#72-explicit-operators)
  - [7.3 AND / OR grouping](#73-and--or-grouping)
  - [7.4 Indirect fields in filters](#74-indirect-fields-in-filters)
- [8. Sorting (`order_by`)](#8-sorting-order_by)
- [9. Grouping Rules](#9-grouping-rules)
  - [9.1 When a field is considered “grouped”](#91-when-a-field-is-considered-grouped)
  - [9.2 SELECT behavior for grouped fields](#92-select-behavior-for-grouped-fields)
  - [9.3 GROUP BY behavior](#93-group-by-behavior)
- [10. Subqueries (`QuerySpec`)](#10-subqueries-queryspec)
- [11. Putting It All Together](#11-putting-it-all-together)

---

## 1. Design Principles (Summary)

* **Paths over joins** — users never write SQL joins.
* **Explicit relationship metadata** — all join logic comes from `relationships`.
* **Indirect relations as first-class** — `@Model[field]` segments encode reverse / one-to-many hops.
* **Alias-first selection** — fields are expressed as **alias → field**, matching `SELECT expr AS alias`.
* **Composable**: the same path syntax is used in:

  * `fields` (SELECT)
  * `filters` (WHERE)
  * `order_by` (ORDER BY)
  * grouping inference (GROUP BY)

This DSL is intentionally **implementation-agnostic**: you can point it at SQLite, Postgres, or any SQL backend as long as the generated SQL and relationship mappings match your schema.

---

## 2. Quick Start

Here is the smallest end-to-end slice: declare relationships, pick a base model, and use field paths (including indirect hops) to read or aggregate related data.

```python
relationships = {
    "Tasks.shot": "Shots.id",
    "Shots.project": "Projects.id",
    "Tasks.assigned_to": "Users.id",
    "Assets.task": "Tasks.id",
    "Assets.owner": "Users.id",
}

ctx = SQLQueryBuilder.build_context(
    model="Tasks",
    fields=[
        "name",
        ("unique_owner_count", "@Assets[task].owner.email.distinct().count()"),
        {"project_name": "shot.project.name"},
    ],
    filters={"status": "active"},
    relationships=relationships,
    order_by={"shot.project.name": "asc"},
    limit=10,
)

print(ctx.query)
print(ctx.parameters)
```

Key takeaways:

* Field paths traverse relations; indirect segments hop backward via FKs.
* Fields are declared as **alias → field**.
* Aggregators apply to the final scalar in the path; indirect hops imply grouping.
* You never hand-write joins; relationships drive them.

---

## 3. Core Concepts

### 3.1 Base model

Each query starts from **a single base model** (table):

```python
ctx = QuerySpec(
    model="Tasks",
    fields=[...],
    filters={...},
    relationships=relationships,
)
```

Internally:

* The base model is aliased as `_` in SQL
* Simple fields map directly to `_.field`

Example:

```python
fields = ["id", "name"]
```

```sql
SELECT _.id, _.name
FROM Tasks AS _
```

---

### 3.2 Relationship mapping

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

**Format**

* **Key**: `LeftModel.left_field`
* **Value**: `RightModel.right_field`

Semantics:

* `"Tasks.shot": "Shots.id"` means: `Tasks.shot` is a FK pointing to `Shots.id`.

This mapping is used by:

* `resolve_model` – follow a chain of relations and return the final model.
* `resolve_model_field` – return the final `Model.field`.
* `build_join_clause` – generate all required `LEFT JOIN`s.
* `build_group_by_clause` – deduce grouping columns for one-to-many relations.

---

## 4. Field Path Syntax

### 4.1 Chain separator

Field paths use `.` as the chain separator:

```text
shot.sequence.project.name
```

A path is a sequence of **segments**, resolved left → right.

* `"name"` → field on the base model
* `"shot.name"` → field `name` on the related model `shot`
* `"shot.sequence.project.name"` → multi-hop relation

### 4.2 Forward (simple) relations

Segments **without `@`** are resolved using `relationships`:

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

### 4.3 Field Selection and Aliasing

`fields` may be provided in three equivalent forms:

#### String

```python
fields = ["name"]
```

Alias defaults to the same value.

#### Tuple

```python
fields = [("task_name", "name")]
```

#### Dict

```python
fields = [{"task_name": "name"}]
```

All forms normalize to:

```sql
SELECT <field_expr> AS <alias>
```

---

## 5. Indirect Relation Segments (`@Model[field]`)

### 5.1 Syntax

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

### 5.2 Semantics

Informally:

> “From the current context, hop to `Model` using the relationship `Model.ref_field` pointing back to the current model.”

Given:

```python
relationships = {
    "Assets.task": "Tasks.id",
    "Assets.project": "Projects.id",
}
```

Then:

* From **Tasks**:

  * `@Assets[task]` → all Assets where `Assets.task = Tasks.id`

* From **Projects**:

  * `@Assets[project]` → all Assets where `Assets.project = Projects.id`

You never write the join condition manually — it is inferred.

---

### 5.3 Mixed paths

Forward and indirect segments can be mixed freely:

```text
project.@Assets[project].owner.email
shot.sequence.project.@Assets[project].created_at
```

Resolution pattern:

1. Resolve the **forward chain** `project` from the base model.
2. At `@Assets[project]`, treat this as a hop from the current model (here `Projects`) to `Assets` using `Assets.project`.
3. Continue with normal segments (`owner`, `created_by`, `name`) from the `Assets` side, using `relationships`.

---

### 5.4 Indirect chain extraction

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

## 6. Value Operations

### 6.1 Design rule

* Indirect relations (`@Model[field]`) always yield a **value stream**.
* Value operations apply **only to the terminal scalar**.
* Relation traversal and value operations are strictly separated.

Correct usage:

```text
@Assets[project].name.distinct()
@Assets[project].created_at.min()
@Assets[project].owner.email.distinct().count()
```

---

### 6.2 Modifiers vs aggregators

**Value modifiers (do not consume the stream):**

| DSL           | Meaning                           |
| ------------- | --------------------------------- |
| `.distinct()` | Apply `DISTINCT` to the value set |

**Scalar aggregators (consume values → scalar):**

| DSL        | SQL            | Result |
| ---------- | -------------- | ------ |
| `.count()` | `COUNT(value)` | scalar |
| `.sum()`   | `SUM(value)`   | scalar |
| `.min()`   | `MIN(value)`   | scalar |
| `.max()`   | `MAX(value)`   | scalar |
| `.avg()`   | `AVG(value)`   | scalar |

---

### 6.3 `.distinct()` behavior

`.distinct()` is a **value modifier**, not an aggregator.

#### With scalar aggregator

```text
value.distinct().count()
```

```sql
COUNT(DISTINCT value)
```

Other examples:

```text
value.distinct().sum()  → SUM(DISTINCT value)
value.distinct().avg()  → AVG(DISTINCT value)
```

#### Case B — terminal (no scalar aggregator)

```text
value.distinct()
```

Materializes a list:

```sql
JSON_GROUP_ARRAY(DISTINCT value)
  FILTER (WHERE value IS NOT NULL)
```

---

### 6.4 Examples

```text
# All unique asset owner emails per project
project.@Assets[project].owner.email.distinct()

# Count of unique tags across all assets in a shot
task.shot.@AssetShot[shot].tag.name.distinct().count()

# Earliest asset creation time
shot.@Assets[shot].created_at.min()
```

---

## 7. Filters DSL

Filters are expressed as nested dictionaries, using:

* **field paths** (simple or indirect) as keys
* `FilterOperation` or string operators as inner keys
* `GroupOperator` (or `"AND"`, `"OR"`) for grouping

### 7.1 Simple equality

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

---

### 7.2 Explicit operators

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

---

### 7.3 AND / OR grouping

```python
filters = {
    "OR": {
        "shot.sequence.project.name": {"contains": "Forest"},
        "shot.status": "Completed",
        "assigned_to.role": "Artist",
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

### 7.4 Indirect fields in filters

You can filter using indirect paths:

```python
filters = {
    "project.@Assets[project].name": {"contains": "tree"},
}
```

This is resolved to the correct alias using `_build_inner_alias` and `resolve_model_field`.

---

## 8. Sorting (`order_by`)

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

## 9. Grouping Rules

### 9.1 When a field is considered “grouped”

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

### 9.2 SELECT behavior for grouped fields

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

### 9.3 GROUP BY behavior

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

## 10. Subqueries (`QuerySpec`)

Subqueries reuse the same DSL.

```python
ctx = QuerySpec(
    model="Shots",
    fields=[
        "id",
        "name",
        (
            "earliest_work_ts",
            (
                QuerySpec(
                    model="TaskStartLog",
                    fields={"v": "started_at"},
                    filters={"task.shot": OuterRef("id")},
                )
                |
                QuerySpec(
                    model="TimesheetEntry",
                    fields={"v": "start_time"},
                    filters={"shot": OuterRef("id")},
                )
            ).min(),
        ),
    ],
)
```

Rules:

* `QuerySpec` → returns **array** by default
* `QueryOneSpec` → returns **scalar row**
* Applying a value aggregator (`min`, `count`, etc.) forces a scalar
* Subqueries inherit outer relationships unless overridden

---

## 11. Putting It All Together

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
