# UI Architecture Guidelines (PyQt)

This document defines the **mandatory UI architecture and coding conventions** for all PyQt-based code in this repository.

The goals are to ensure:

* Predictable and consistent UI structure
* Clear separation between UI, feature logic, core engines, and external services
* Long-term maintainability and easy refactoring
* Alignment with Google Python Style and project-wide naming conventions

These rules apply to all `QWidget`/`QMainWindow` subclasses, feature views, reusable widgets, and controller-level code.

---

# 1. High-Level Architecture

A PyQt application must follow the same layered architecture used in the React/Next.js codebase for cross-project consistency.

```
views/         ← Layout & screen composition
widgets/       ← Reusable UI widgets (pure UI)
features/      ← Domain state, actions, controllers
core/          ← Engines (timeline, nodegraph, undo, selection)
services/      ← IO, HTTP, storage, metadata access
utils/         ← Pure helper functions (domain-agnostic)
```

## 1.1 Folder Purposes

### **views/**

Top-level composition of UI widgets. Equivalent to pages/screens.

* No business logic
* Assemblies of widgets + calls into feature controllers
* Contains `MainWindow`, `TimelineView`, `AssetBrowserView`, etc.

### **widgets/**

Reusable Qt widgets. These are like React components.

* UI behavior only
* No domain logic
* Example: `SegmentedControl`, `SearchBar`, `IconButton`, `NodeCanvasWidget`

### **features/**

Feature-specific domain logic + state + controllers.
Equivalent of React feature slices.

Each feature folder typically includes:

```
features/<feature_name>/
  controller.py       # high-level behavior
  store.py            # state models (Qt or pure Python)
  actions.py          # domain operations
  adapters.py         # conversion helpers, if needed
```

### **core/**

Framework-independent engines.
These contain rules for how systems behave.

Examples:

```
core/timeline_engine.py
core/nodegraph_engine.py
core/selection_model.py
core/undo_redo.py
core/path_rules.py
```

**Rules:**

* Must be pure Python or minimal Qt
* No UI references allowed
* Used by `features/` layers

### **services/**

Modules that talk to the outside world:

* MinIO/S3
* Postgres

### **utils/**

Only general, domain-agnostic helpers:

```
utils/math_utils.py
utils/format_utils.py
utils/path_utils.py
```

---

# 2. Google Python Style & Docstrings

All UI code **must follow Google Python Style Guide**, including:

* Google-style docstrings
* Summary line on its own line
* Blank line before extended description
* Do **not** repeat class names in docstrings

### Examples

```python
class AssetBrowserView(QtWidgets.QWidget):
    """Main view for browsing project assets.

    Composes the asset list, filters, and preview panels.
    """
    ...

    def save_changes(self):
        """Save current changes for the active project.
        """
        ...
```

---

# 3. Class Section Order & Header Style

Every class must use the following section ordering.

### 3.1 Header Format

```
# Section Name
# ------------
```

### 3.2 Preferred Section Order

```
# Initialization and Setup
# Public Methods
# Class Properties
# Utility Methods
# Private Methods
# Overridden Methods
```

Sections may be omitted if empty. This order is preferred for consistency but not strictly required.

---

# 4. Initialization Pattern (Mandatory)

All widgets follow the same structure using **double underscore for init-like internals**.

```python
class ExampleWidget(QtWidgets.QWidget):
    """A demonstration widget following the architecture rules.
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        """Set up the widget, build the UI, and connect signals.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        # Store the arguments
        # -------------------
        ...

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize attributes.
        """
        # Public Attributes
        # -----------------
        ...

        # Private Attributes
        # ------------------
        ...

    def __init_ui(self):
        """Initialize the UI.
        """
        # Initial UI State
        # ----------------
        ...

        # Create Widgets
        # --------------
        self.title_label = QtWidgets.QLabel("Title")
        self.search_edit = QtWidgets.QLineEdit()
        self.list_view = QtWidgets.QListView()
        self.ok_button = QtWidgets.QPushButton("OK")
        self.cancel_button = QtWidgets.QPushButton("Cancel")

        # Add Widgets to Layouts
        # ----------------------
        # Header
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.search_edit)

        # Content
        content_layout = QtWidgets.QVBoxLayout()
        content_layout.addWidget(self.list_view)

        # Footer
        footer_layout = QtWidgets.QHBoxLayout()
        footer_layout.addStretch()
        footer_layout.addWidget(self.ok_button)
        footer_layout.addWidget(self.cancel_button)

        # Assemble main
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addLayout(header_layout)
        main_layout.addLayout(content_layout)
        main_layout.addLayout(footer_layout)

    def __init_signal_connections(self):
        """Initialize signal–slot connections.
        """
        self.ok_button.clicked.connect(self.save_changes)
        self.cancel_button.clicked.connect(self.close)

    # Public Methods
    # --------------
    def save_changes(self):
        """Save changes and refresh the UI.
        """
        ...

    # Utility Methods
    # ---------------
    ...
```

---

# 5. UI Construction Rules

* Widgets must be created **before** layouts.
* Layouts must be assembled **bottom-up**.
* Inline widget creation inside layouts is **forbidden**.

Example anti-pattern:

```python
layout.addWidget(QtWidgets.QLabel("Bad"))  # ❌
```

---

# 6. Action-Reflective Method Naming

Signal-connected methods describe **what they do**, not **what triggered them**.

Correct:

```python
def save_changes(self):
    ...

def update_results(self):
    ...

def apply_filter(self):
    ...

def toggle_sidebar(self):
    ...
```

Incorrect:

```python
def on_save_clicked(self):
    ...

def handle_filter_changed(self):
    ...
```
Example signal Connections:

```python
self.save_button.clicked.connect(self.save_changes)  # ✅
self.search_edit.textChanged.connect(self.update_results)  # ✅
```

---

# 7. Boolean Naming Rules

Booleans and boolean-returning methods must use:

```
is_, has_, can_, should_, will_, does_, was_
```

Examples:

```
self.is_dirty
self.has_selection
self.can_undo
self.should_show_metadata
```

---

# 8. Separating UI and Domain Logic

## 8.1 Where UI logic goes

* UI composition → `views/`
* Reusable UI → `widgets/`
* Action methods → inside UI class, but small

## 8.2 Where domain logic goes

* Feature state & controllers → `features/`
* Engine-level rules → `core/`
* IO & external systems → `services/`

### Example

```python
def __init_signal_connections(self):
    self.save_button.clicked.connect(self.save_changes)

def save_changes(self):
    self._project_service.save()
    self.refresh_view()
```

---

# 9. Enforcement

Reviewers must ensure:

* UI code respects folder separation (`views/`, `widgets/`, `features/`, `core/`, `services/`, `utils/`)
* All widgets follow `__init_attributes()`, `__init_ui()`, and `__init_signal_connections()` patterns
* Class sections follow required structure
* Widgets-first and bottom-up layouts
* Action-reflective naming (no `on_*`, no `handle_*`)
* Google docstring format
* No generic `utils/` dumping; domain logic goes to `core/` or `features/`

If any part of this architecture is unclear or ambiguous, propose an update to this document.
