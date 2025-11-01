import os
import re

from qtpy import QtCore, QtGui, QtWidgets

from tablerqicon import TablerQIcon

from blackboard.widgets.filter_widget import FilterSelectionBar
from blackboard.widgets.momentum_scroll_widget import MomentumScrollArea


STATUS_COLOR = {
    "To Do": "#C74",        # Orange
    "In Progress": "#DB3",  # Yellow
    "Done": "#6B5",         # Green
    "Completed": "#299",    # Teal
}

DEFAULT_STATUS_COLOR = "#333"

STATUS_ORDER = ["To Do", "In Progress", "Done", "Completed"]


class ResizeHandler(QtWidgets.QWidget):

    WINDOW_FLAGS = QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint
    MARGIN = 10  # Size for resize handles

    def __init__(self, widget: QtWidgets.QWidget, allowed_edges=None):
        super().__init__(widget, self.WINDOW_FLAGS)
        self.widget = widget
        self.is_resizing = False
        self.current_edge = QtCore.Qt.Edge(0)
        self.mouse_pos = None

        # Store the allowed edges (default: all edges enabled)
        self.allowed_edges = allowed_edges or (
            QtCore.Qt.Edge.LeftEdge | QtCore.Qt.Edge.RightEdge |
            QtCore.Qt.Edge.TopEdge | QtCore.Qt.Edge.BottomEdge
        )

        self.widget.setMouseTracking(True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

        # Install event filter on the widget
        self.widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Intercept events for the widget."""
        if obj is self.widget:
            if event.type() == QtCore.QEvent.Type.MouseButtonPress:
                self.mouse_press_event(event)
            elif event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                self.mouse_release_event(event)
            elif event.type() == QtCore.QEvent.Type.MouseMove:
                self.mouse_move_event(event)
            elif event.type() == QtCore.QEvent.Type.Resize:
                pass  # Handle is updated when needed
        return super().eventFilter(obj, event)

    def mouse_press_event(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.mouse_pos = event.globalPos()
            if self.current_edge:
                self.is_resizing = True
                self.starting_geometry = self.widget.geometry()

    def mouse_release_event(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.is_resizing = False
            self.current_edge = None
            self.hide()
            self.widget.unsetCursor()

    def mouse_move_event(self, event):
        if self.is_resizing:
            self.resize_window(event.globalPos())
        else:
            self.update_cursor_and_handle(event.pos())

    def paintEvent(self, event):
        """Custom paint to draw handles with round line caps and rounded corners."""
        if not self.current_edge:
            return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        m = self.MARGIN // 2
        rect = self.rect()

        # Set up the pen with round cap
        pen = QtGui.QPen()
        pen.setWidth(self.MARGIN)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)

        # Create gradient based on the edge or corner
        gradient = self._create_gradient(rect)

        if gradient:
            gradient.setColorAt(0, QtGui.QColor(255, 255, 255, 60))
            gradient.setColorAt(1, QtGui.QColor(255, 255, 255, 0))
            pen.setBrush(gradient)
        else:
            pen.setBrush(QtGui.QColor(255, 255, 255, 60))

        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        # Check if the edge is an edge or a corner
        if self.current_edge in (
            QtCore.Qt.Edge.LeftEdge,
            QtCore.Qt.Edge.RightEdge,
            QtCore.Qt.Edge.TopEdge,
            QtCore.Qt.Edge.BottomEdge,
        ):
            path = self._generate_edge_path(rect, m)
        else:
            path = self._generate_corner_path(rect, m)

        # Draw the cached path
        painter.drawPath(path)

    def _create_gradient(self, rect):
        """Create gradient based on the edge or corner."""
        gradient = None
        if self.current_edge == (QtCore.Qt.Edge.LeftEdge | QtCore.Qt.Edge.TopEdge):
            gradient = QtGui.QLinearGradient(0, 0, rect.width(), rect.height())
        elif self.current_edge == (QtCore.Qt.Edge.RightEdge | QtCore.Qt.Edge.TopEdge):
            gradient = QtGui.QLinearGradient(rect.width(), 0, 0, rect.height())
        elif self.current_edge == (QtCore.Qt.Edge.LeftEdge | QtCore.Qt.Edge.BottomEdge):
            gradient = QtGui.QLinearGradient(0, rect.height(), rect.width(), 0)
        elif self.current_edge == (QtCore.Qt.Edge.RightEdge | QtCore.Qt.Edge.BottomEdge):
            gradient = QtGui.QLinearGradient(rect.width(), rect.height(), 0, 0)
        return gradient

    def _generate_edge_path(self, rect, m):
        """Generate and return the path for an edge."""
        path = QtGui.QPainterPath()
        if self.current_edge == QtCore.Qt.Edge.LeftEdge:
            path.moveTo(rect.width() - m, m)
            path.lineTo(rect.width() - m, rect.height() - m)
        elif self.current_edge == QtCore.Qt.Edge.RightEdge:
            path.moveTo(m, m)
            path.lineTo(m, rect.height() - m)
        elif self.current_edge == QtCore.Qt.Edge.TopEdge:
            path.moveTo(m, rect.height() - m)
            path.lineTo(rect.width() - m, rect.height() - m)
        elif self.current_edge == QtCore.Qt.Edge.BottomEdge:
            path.moveTo(m, m)
            path.lineTo(rect.width() - m, m)

        return path

    def _generate_corner_path(self, rect, m):
        """Generate and return the path for a corner."""
        path = QtGui.QPainterPath()
        radius = self.MARGIN * 2  # Adjust the radius for the rounded corner

        if self.current_edge == (QtCore.Qt.Edge.LeftEdge | QtCore.Qt.Edge.TopEdge):
            # Top-left corner
            path.moveTo(m, rect.height() - m)
            path.lineTo(m, m + radius)
            path.quadTo(m, m, m + radius, m)
            path.lineTo(rect.width() - m, m)
        elif self.current_edge == (QtCore.Qt.Edge.RightEdge | QtCore.Qt.Edge.TopEdge):
            # Top-right corner
            path.moveTo(rect.width() - m, rect.height() - m)
            path.lineTo(rect.width() - m, m + radius)
            path.quadTo(rect.width() - m, m, rect.width() - m - radius, m)
            path.lineTo(m, m)
        elif self.current_edge == (QtCore.Qt.Edge.LeftEdge | QtCore.Qt.Edge.BottomEdge):
            # Bottom-left corner
            path.moveTo(m, m)
            path.lineTo(m, rect.height() - m - radius)
            path.quadTo(m, rect.height() - m, m + radius, rect.height() - m)
            path.lineTo(rect.width() - m, rect.height() - m)
        elif self.current_edge == (QtCore.Qt.Edge.RightEdge | QtCore.Qt.Edge.BottomEdge):
            # Bottom-right corner
            path.moveTo(rect.width() - m, m)
            path.lineTo(rect.width() - m, rect.height() - m - radius)
            path.quadTo(
                rect.width() - m, rect.height() - m, rect.width() - m - radius, rect.height() - m
            )
            path.lineTo(m, rect.height() - m)

        return path

    def resize_window(self, global_pos):
        dx = global_pos.x() - self.mouse_pos.x()
        dy = global_pos.y() - self.mouse_pos.y()

        geom = self.starting_geometry
        x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()

        if self.current_edge & QtCore.Qt.Edge.LeftEdge:
            x += dx
            w -= dx

        if self.current_edge & QtCore.Qt.Edge.RightEdge:
            w += dx

        if self.current_edge & QtCore.Qt.Edge.TopEdge:
            y += dy
            h -= dy

        if self.current_edge & QtCore.Qt.Edge.BottomEdge:
            h += dy

        self.widget.setGeometry(x, y, max(w, self.widget.minimumWidth()), max(h, self.widget.minimumHeight()))

        # Update handle position during resizing
        if self.isVisible():
            self.update_position()

    def update_cursor_and_handle(self, pos):
        self.current_edge = self.detect_edge(pos)

        if self.current_edge:
            self.update_position()
            self.show()
            self.update_cursor_shape()
        else:
            self.hide()
            self.widget.unsetCursor()

    def update_position(self):
        """Update position and appearance based on the edge, incorporating sizing logic."""
        w, h = self.widget.width(), self.widget.height()
        m = self.MARGIN

        # Calculate sizes using the same logic
        corner_size = min(w // 4, h // 4, 100)
        handle_size_w = w // 3
        handle_size_h = h // 3

        if self.current_edge == QtCore.Qt.Edge.LeftEdge:
            self.setGeometry(0, handle_size_h, m, handle_size_h)
        elif self.current_edge == QtCore.Qt.Edge.RightEdge:
            self.setGeometry(w - m, handle_size_h, m, handle_size_h)
        elif self.current_edge == QtCore.Qt.Edge.TopEdge:
            self.setGeometry(handle_size_w, 0, handle_size_w, m)
        elif self.current_edge == QtCore.Qt.Edge.BottomEdge:
            self.setGeometry(handle_size_w, h - m, handle_size_w, m)
        elif self.current_edge == (QtCore.Qt.Edge.LeftEdge | QtCore.Qt.Edge.TopEdge):
            self.setGeometry(0, 0, corner_size, corner_size)
        elif self.current_edge == (QtCore.Qt.Edge.RightEdge | QtCore.Qt.Edge.TopEdge):
            self.setGeometry(w - corner_size, 0, corner_size, corner_size)
        elif self.current_edge == (QtCore.Qt.Edge.LeftEdge | QtCore.Qt.Edge.BottomEdge):
            self.setGeometry(0, h - corner_size, corner_size, corner_size)
        elif self.current_edge == (QtCore.Qt.Edge.RightEdge | QtCore.Qt.Edge.BottomEdge):
            self.setGeometry(w - corner_size, h - corner_size, corner_size, corner_size)
        else:
            self.hide()

    def update_cursor_shape(self):
        """Set the cursor shape based on the edge."""
        if self.current_edge == (QtCore.Qt.Edge.LeftEdge | QtCore.Qt.Edge.TopEdge) or \
           self.current_edge == (QtCore.Qt.Edge.RightEdge | QtCore.Qt.Edge.BottomEdge):
            self.widget.setCursor(QtCore.Qt.CursorShape.SizeFDiagCursor)
        elif self.current_edge == (QtCore.Qt.Edge.RightEdge | QtCore.Qt.Edge.TopEdge) or \
             self.current_edge == (QtCore.Qt.Edge.LeftEdge | QtCore.Qt.Edge.BottomEdge):
            self.widget.setCursor(QtCore.Qt.CursorShape.SizeBDiagCursor)
        elif self.current_edge & QtCore.Qt.Edge.LeftEdge or self.current_edge & QtCore.Qt.Edge.RightEdge:
            self.widget.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
        elif self.current_edge & QtCore.Qt.Edge.TopEdge or self.current_edge & QtCore.Qt.Edge.BottomEdge:
            self.widget.setCursor(QtCore.Qt.CursorShape.SizeVerCursor)

    def detect_edge(self, pos: QtCore.QPoint) -> QtCore.Qt.Edge:
        """Detect which edge or corner the mouse is hovering over.

        Args:
            pos (QtCore.QPoint): The current mouse position relative to the widget.

        Returns:
            QtCore.Qt.Edge: The edge or corner flag.
        """
        rect = self.widget.rect()
        margin = self.MARGIN
        edge = QtCore.Qt.Edge(0)

        if pos.x() <= margin and self.allowed_edges & QtCore.Qt.Edge.LeftEdge:
            edge |= QtCore.Qt.Edge.LeftEdge
        elif pos.x() >= rect.width() - margin and self.allowed_edges & QtCore.Qt.Edge.RightEdge:
            edge |= QtCore.Qt.Edge.RightEdge

        if pos.y() <= margin and self.allowed_edges & QtCore.Qt.Edge.TopEdge:
            edge |= QtCore.Qt.Edge.TopEdge
        elif pos.y() >= rect.height() - margin and self.allowed_edges & QtCore.Qt.Edge.BottomEdge:
            edge |= QtCore.Qt.Edge.BottomEdge

        return edge

def process_markdown(content):
    """
    Processes the markdown content by removing leading/trailing spaces from
    non-markdown lines and appending two spaces for line breaks, while preserving
    code blocks and skipping markdown-specific lines.

    Args:
        content (str): The markdown content to process.

    Returns:
        str: Processed markdown content with line breaks.

    Examples:
        >>> content = '''
        ... # Header
        ... Plain text
        ... ```code block```
        ... - List item
        ... More plain text
        ... '''
        >>> process_markdown(content)
        '# Header\\nPlain text  \\n```code block```  \\n- List item\\nMore plain text'
        
        >>> content = '''
        ... Simple text
        ... with newlines
        ... ```
        ... multiline code block
        ... ```
        ... '''
        >>> process_markdown(content)
        'Simple text  \\nwith newlines  \\n```\\nmultiline code block\\n```'
    """
    # Regular expression to find code blocks (multiline or inline)
    code_block_pattern = r'```.*?```|`.*?`'
    
    # Find all code blocks (both multiline and inline)
    code_blocks = re.findall(code_block_pattern, content, re.DOTALL)
    
    # Replace code blocks with placeholders
    for i, block in enumerate(code_blocks):
        content = content.replace(block, f"CODE_BLOCK_{i}")
    
    # Process lines outside of code blocks, skipping markdown-specific lines
    def process_lines_outside_codeblocks(text):
        lines = text.split("\n")
        processed_lines = []
        
        # Define regex patterns to match markdown lines (headers, lists, blockquotes)
        markdown_line_pattern = re.compile(r'^\s*(#|\*|\-|\d+\.)|^\s*>')
        
        for line in lines:
            # Skip markdown lines like headers, lists, blockquotes
            if markdown_line_pattern.match(line):
                processed_lines.append(line)
            else:
                # For plain text, strip leading/trailing spaces and add   
                stripped_line = line.strip()
                if stripped_line:
                    processed_lines.append(stripped_line + "  ")
                else:
                    processed_lines.append("\n")  # Preserve empty lines
        
        return "\n".join(processed_lines)

    # Apply the line processing
    content_with_line_breaks = process_lines_outside_codeblocks(content)
    
    # Reinsert the code blocks
    for i, block in enumerate(code_blocks):
        content_with_line_breaks = content_with_line_breaks.replace(f"CODE_BLOCK_{i}", block)

    return content_with_line_breaks.strip()

def format_user_mentions(text):
    """Convert @username mentions to clickable links in markdown."""
    def replace_mention(match):
        username = match.group(1)
        return f"[ @{username} ](user:{username})"
    return re.sub(r'@(\w+)', replace_mention, text)

class PlaceholderCard(QtWidgets.QWidget):
    """Placeholder card shown when no cards match the current filter criteria."""

    def __init__(self, parent=None, message="No cards to display"):
        super().__init__(parent)

        # Setup placeholder card UI
        self.setStyleSheet(f"""
            background-color: rgba(60, 60, 60, 150);
            border: 2px dashed #555;
            border-radius: 15px;
            color: #AAA;
            font-size: 14px;
            padding: 20px;
        """)

        # Main layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Message label
        self.message_label = QtWidgets.QLabel(message, self)
        self.main_layout.addWidget(self.message_label)

class StatusFilterWidget(QtWidgets.QFrame):

    DEFAULT_ACTIVE_STATUSES = ["To Do", "In Progress"]
    STYLE_SHEET = """
        QFrame {
            background-color: #333;
            border-radius: 10px;
        }
        QToolButton {
            background-color: #333;
            border-radius: 10px;
            border: 1px solid gray;
            padding: 1 6;
        }
        QToolButton:hover {
            background-color: rgba(90, 90, 90, 200);
        }
        QToolButton:checked {
            background-color: rgba(100, 100, 100, 200);
            border: 1px solid cyan;
        }
        QPushButton#clear_button {
            border: none;
            background: transparent;
            border-radius: 10px;
            padding: 2px 0px;
        }
        QPushButton#clear_button:hover {
            background-color: #D54;
        }
        QPushButton#clear_button:pressed {
            background-color: #222;
        }
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent=None):
        super().__init__(parent)

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setFixedHeight(40)
        self.setStyleSheet(self.STYLE_SHEET)

        # Create Layouts
        # --------------
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Create Widgets
        # --------------
        # Add a filter bar
        self.filter_selection_bar = FilterSelectionBar(self)
        self.filter_selection_bar.setFixedHeight(20)
        self.filter_changed = self.filter_selection_bar.filter_changed
        self.filters_cleared = self.filter_selection_bar.filters_cleared
        self.set_filter_checked = self.filter_selection_bar.set_filter_checked

        self.filter_selection_bar.add_filters(STATUS_ORDER)
        for status in self.DEFAULT_ACTIVE_STATUSES:
            self.filter_selection_bar.set_filter_checked(status)

        # Add a clear filters button
        self.clear_button = QtWidgets.QPushButton(TablerQIcon.filter_x, '', self)
        self.clear_button.setFixedWidth(32)
        self.clear_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.clear_button.setToolTip("Clear Filters")
        self.clear_button.setObjectName('clear_button')

        # Add Widgets to Layouts
        # ----------------------
        layout.addWidget(self.filter_selection_bar)
        layout.addWidget(self.clear_button)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        self.clear_button.clicked.connect(self.filter_selection_bar.clear_filters)

    @property
    def active_filters(self):
        return self.filter_selection_bar.get_active_filters()

class StatusNextStepWidget(QtWidgets.QWidget):
    status_changed = QtCore.Signal(str)  # Signal emitted when status changes

    def __init__(self, current_status="To Do", container: 'TransparentFloatingLayout' = None):
        super().__init__(container)


        self.container = container
        
        self.current_status = current_status
        self.clicked = False  # Track the clicked state

        # Setup parallel animation group for synchronized animations
        self.parallel_animation_group = QtCore.QParallelAnimationGroup()

        # Main layout
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(5)

        self.setStyleSheet('''
            QComboBox {
                border: none;
                border-radius: 10;
                padding-left: 10px;
            }

            QPushButton#next_step_button {
                background-color: #299;
                border: none;
                border-radius: 10;
            }
            QPushButton#next_step_button:disabled {
                background-color: #555;
                color: gray;
            }
        ''')

        # Create the status combobox
        self.status_combobox = QtWidgets.QComboBox()
        self.status_combobox.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.status_combobox.addItems(STATUS_ORDER)
        self.status_combobox.setCurrentText(self.current_status)
        self.status_combobox.setFixedHeight(20)
        self.status_combobox.setStyleSheet(self.get_combobox_style(self.current_status))
        self.status_combobox.currentTextChanged.connect(self.on_status_changed)
        self.status_combobox.wheelEvent = self.wheelEvent
        self.main_layout.addWidget(self.status_combobox)

        # Create the next step button
        self.next_step_button = QtWidgets.QPushButton(self)
        self.next_step_button.setObjectName('next_step_button')
        self.next_step_button.setFixedHeight(20)
        self.next_step_button.setFixedWidth(30)
        self.next_step_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.next_step_button.clicked.connect(self.mark_as_next_status)
        self.main_layout.addWidget(self.next_step_button)

        # Set hover event handlers
        self.next_step_button.installEventFilter(self)

        # Active animations list to manage animation lifetimes
        self.active_animations = []
        self.update_button()  # Initialize button state

    def get_next_status(self):
        """Get the next status based on the current status."""
        current_index = STATUS_ORDER.index(self.current_status)
        if current_index < len(STATUS_ORDER) - 1:
            return STATUS_ORDER[current_index + 1]
        return None

    def get_combobox_style(self, status):
        """Return the stylesheet for the combobox based on the status."""
        return f"""
            QComboBox {{
                background-color: {STATUS_COLOR.get(status, DEFAULT_STATUS_COLOR)};
                color: #FFF;
            }}
        """

    def update_button(self):
        """Update the button icon and tooltip."""
        next_status = self.get_next_status()
        if next_status:
            self.next_step_button.setEnabled(True)
            self.next_step_button.setToolTip(f"Mark as '{next_status}'")
            self.next_step_button.setIcon(TablerQIcon.chevron_right)
        else:
            self.next_step_button.setEnabled(False)
            self.next_step_button.setToolTip("No further status")
            self.next_step_button.setIcon(TablerQIcon.check)

    def on_status_changed(self, status_text):
        """Handle changes in the combobox selection."""
        self.current_status = status_text
        self.status_combobox.setStyleSheet(self.get_combobox_style(status_text))
        self.update_button()
        self.status_changed.emit(self.current_status)

    def mark_as_next_status(self):
        """Advance the task to the next status with a transition color animation."""
        self.clicked = True  # Set clicked state to True
        next_status = self.get_next_status()
        if next_status:
            # Check if the next status is in the currently active statuses in the parent
            active_statuses = self.container.status_filter_widget.active_filters or STATUS_ORDER

            # Otherwise, animate the transition
            self.status_combobox.setCurrentText(next_status)

            if next_status in active_statuses:
                self.animate_back()
            else:
                self.next_step_button.setText("")

            gradient_animation = QtCore.QVariantAnimation()
            gradient_animation.setDuration(300)
            gradient_animation.setStartValue(QtGui.QColor(STATUS_COLOR.get(self.current_status, DEFAULT_STATUS_COLOR)))
            gradient_animation.setEndValue(QtGui.QColor(STATUS_COLOR.get(next_status, DEFAULT_STATUS_COLOR)))
            gradient_animation.valueChanged.connect(self.apply_gradient_color)
            gradient_animation.start()

    def apply_gradient_color(self, color):
        """Apply the gradient color to the combobox background."""
        # self.status_combobox.setBackgroundRole(color)
        self.status_combobox.setStyleSheet(f"""
            QComboBox {{
                background-color: {color.name()};
            }}
        """)

    def animate_back(self):
        """Animate the button back to its original size and clear hover state."""
        self.next_step_button.setText("")  # Clear button text
        self.parallel_animation_group.clear()  # Clear existing animations

        # Create animation to shrink the button width
        shrink_button_animation = UIUtil.apply_animation(
            widget=self.next_step_button,
            property_name="minimumWidth",
            start_value=self.next_step_button.width(),
            end_value=30,
            duration=300,
            easing_curve=QtCore.QEasingCurve.Type.InOutQuad
        )
        self.parallel_animation_group.addAnimation(shrink_button_animation)

        # Create animation to extend the combobox width back to original
        extend_combobox_animation = UIUtil.apply_animation(
            widget=self.status_combobox,
            property_name="minimumWidth",
            start_value=self.status_combobox.width(),
            end_value=120,
            duration=300,
            easing_curve=QtCore.QEasingCurve.Type.InOutQuad
        )
        self.parallel_animation_group.addAnimation(extend_combobox_animation)

        # Connect to the finished signal to reset hover state
        self.parallel_animation_group.finished.connect(self.reset_hover_state)

        # Start the parallel animation group
        self.parallel_animation_group.start()

    def reset_hover_state(self):
        """Reset hover state to allow animations when hovering again."""
        self.clicked = False  # Reset the clicked state

    def eventFilter(self, obj, event):
        """Handle hover events for the next step button.
        """
        if obj == self.next_step_button and not self.clicked:  # Only handle hover if not clicked
            if event.type() == QtCore.QEvent.Type.Enter and self.next_step_button.isEnabled():
                self.expand_button_on_hover()
            elif event.type() == QtCore.QEvent.Type.Leave and not self.clicked:
                self.animate_back()
        return super().eventFilter(obj, event)

    def expand_button_on_hover(self):
        """Expand the button and contract the combobox on hover."""
        # Update the button text to indicate the next status
        self.next_step_button.setText(f"Mark as '{self.get_next_status()}'")

        # Clear existing animations in the parallel group
        self.parallel_animation_group.clear()

        # Create animation to expand the button width
        expand_button_animation = UIUtil.apply_animation(
            widget=self.next_step_button,
            property_name="minimumWidth",
            start_value=self.next_step_button.width(),
            end_value=120,
            duration=300,
            easing_curve=QtCore.QEasingCurve.Type.InOutQuad
        )
        self.parallel_animation_group.addAnimation(expand_button_animation)

        # Create animation to shorten the combobox width
        shorten_combobox_animation = UIUtil.apply_animation(
            widget=self.status_combobox,
            property_name="minimumWidth",
            start_value=self.status_combobox.width(),
            end_value=30,
            duration=300,
            easing_curve=QtCore.QEasingCurve.Type.InOutQuad
        )
        self.parallel_animation_group.addAnimation(shorten_combobox_animation)

        # Start the parallel animation group
        self.parallel_animation_group.start()

    def showEvent(self, event):
        self.animate_back()
        super().showEvent(event)

# Define a utility class for UI-related common methods
class UIUtil:
    """Utility class for common UI methods."""

    @staticmethod
    def create_shadow_effect(blur_radius=15, x_offset=0, y_offset=4, color=QtGui.QColor(0, 0, 0, 150)):
        """Create and return a shadow effect for the floating card or any widget.

        Args:
            blur_radius (int): The blur radius of the shadow.
            x_offset (int): The horizontal offset of the shadow.
            y_offset (int): The vertical offset of the shadow.
            color (QColor): The color of the shadow effect.

        Returns:
            QGraphicsDropShadowEffect: Configured shadow effect.
        """
        shadow = QtWidgets.QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur_radius)
        shadow.setXOffset(x_offset)
        shadow.setYOffset(y_offset)
        shadow.setColor(color)
        return shadow

    @staticmethod
    def apply_animation(widget: QtWidgets.QWidget, property_name: str, start_value: QtCore.QVariant, end_value: QtCore.QVariant,
                        duration: int = 300, easing_curve: QtCore.QEasingCurve = None) -> QtCore.QPropertyAnimation:
        """Applies a simple property animation to a widget.

        Args:
            widget: The widget to animate.
            property_name: The property of the widget to animate.
            start_value: The starting value of the animation.
            end_value: The ending value of the animation.
            duration: The duration of the animation in milliseconds.
            easing_curve: The easing curve to apply to the animation.

        Returns:
            The QPropertyAnimation object created for the animation.
        """
        # Create the QPropertyAnimation object, set its duration, and configure
        # the start and end values for the given property of the widget.
        animation = QtCore.QPropertyAnimation(widget, property_name.encode())
        animation.setDuration(duration)
        animation.setStartValue(start_value)
        animation.setEndValue(end_value)

        # Set an easing curve if provided, which defines the rate of change during the animation.
        if easing_curve:
            animation.setEasingCurve(easing_curve)

        # Start the animation.
        animation.start()

        # Assign the animation to the widget to prevent it from being garbage collected.
        widget._animation = animation

        # Return the animation object.
        return animation

class FlexTextBrowser(QtWidgets.QTextBrowser):

    STYLE_SHEET = '''
        QTextBrowser {
            background-color: #333;
            border: 1px solid gray;
            border-bottom-left-radius: 15px;
            border-bottom-right-radius: 15px;
            padding: 10px;
        }
    '''

    def __init__(self, parent=None, max_height: int = 300):
        """Initialize the auto-resizing text browser.

        Args:
            parent (Optional[QWidget]): The parent widget.
            max_height (int): The maximum height the widget can expand to.
        """
        super().__init__(parent)
        self.max_height = max_height
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        self.document().contentsChanged.connect(self.adjust_height_to_content)
        self.setStyleSheet(self.STYLE_SHEET)
        self.setOpenLinks(False)

    # Public Methods
    # --------------
    def adjust_height_to_content(self):
        """Adjust the height of the widget to fit the document content, respecting the maximum height.
        """
        self.setFixedHeight(min(self._calculate_content_height(), self.max_height))

    # Private Methods
    # ---------------
    def _calculate_content_height(self):
        """Calculate the total height needed to display the document content.
        """
        # Get the document height, considering the current width of the QTextBrowser
        document_width = self.viewport().width()
        self.document().setTextWidth(document_width)  # Set text width to match the widget's width
        document_height = int(self.document().size().height())  # Convert to integer
        # Calculate additional margins if necessary
        vertical_margins = self.contentsMargins().top() + self.contentsMargins().bottom()

        return document_height + vertical_margins

    # Overridden Methods
    # ------------------
    def resizeEvent(self, event):
        """Handle the widget's resize event.
        """
        super().resizeEvent(event)
        # Adjust height when the width changes
        self.adjust_height_to_content()

    def sizeHint(self):
        """Override sizeHint to provide the height based on the document content.
        """
        document_height = self._calculate_content_height()
        return QtCore.QSize(self.viewport().width(), document_height)

class FlexPlainTextEdit(QtWidgets.QPlainTextEdit):

    STYLE_SHEET = '''
        QPlainTextEdit {
            background-color: #222;
            padding: 5px;
        }
    '''

    activated = QtCore.Signal()

    def __init__(self, parent=None, max_height: int = 300, tab_size: int = 4):
        """Initialize the flexible plain text edit.

        Args:
            parent (Optional[QWidget]): The parent widget.
            max_height (int): The maximum height the widget can expand to.
            tab_size (int): Number of spaces to insert for a tab.
        """
        super().__init__(parent)
        self.max_height = max_height
        self.tab_size = tab_size
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        self.document().contentsChanged.connect(self.adjust_height_to_content)
        self.setStyleSheet(self.STYLE_SHEET)

    # Public Methods
    # --------------
    def adjust_height_to_content(self):
        """Adjust the height of the widget to fit the document content, respecting the maximum height."""
        self.setFixedHeight(min(self._calculate_content_height(), self.max_height))

    # Private Methods
    # ---------------
    def _calculate_content_height(self):
        """Calculate the total height needed to display the document content."""
        block_count = self.document().blockCount()
        # Get line height using font metrics
        line_height = QtGui.QFontMetrics(self.font()).height()
        # Calculate the new height and set it
        document_height = block_count * line_height
        
        # vertical_margins = self.contentsMargins().top() + self.contentsMargins().bottom()
        vertical_margins = 20

        return document_height + vertical_margins

    # Overridden Methods
    # ------------------
    def resizeEvent(self, event):
        """Handle the widget's resize event."""
        super().resizeEvent(event)
        self.adjust_height_to_content()

    def sizeHint(self):
        """Override sizeHint to provide the height based on the document content."""
        document_height = self._calculate_content_height()
        return QtCore.QSize(self.viewport().width(), document_height)

    def keyPressEvent(self, event):
        """Override keyPressEvent to handle tab key and Ctrl+Enter/Return."""
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter) and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            self.activated.emit()
            event.accept()
        elif event.key() == QtCore.Qt.Key.Key_Tab:
            cursor = self.textCursor()
            # Get the text from the start of the line to the current cursor position
            cursor.select(QtGui.QTextCursor.SelectionType.LineUnderCursor)
            line_text = cursor.selectedText()

            # Count leading spaces in the current line
            leading_spaces = len(line_text) - len(line_text.lstrip(' '))

            # Calculate how many spaces to add to reach the next tab stop
            spaces_to_next_tab_stop = self.tab_size - (leading_spaces % self.tab_size)
            self.insertPlainText(' ' * spaces_to_next_tab_stop)
        else:
            super().keyPressEvent(event)

class FloatingCard(QtWidgets.QWidget):
    """Custom floating card widget designed for feedback or comments with support for multiple image attachments.
    """

    # Initialization and Setup
    # ------------------------

    # Signal emitted when the card's status changes
    status_changed = QtCore.Signal(object, str, str)  # Emits self, previous_status, new_status

    def __init__(self, parent=None, content="", attached_images=None):
        super().__init__(parent)

        # Store the arguments
        self.attached_images = attached_images or []  # Support multiple image paths
        self.content = content

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        self.current_status = "To Do"

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Set size policy to expand to the available width
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)

        # Apply shadow effect using utility method
        self.setGraphicsEffect(UIUtil.create_shadow_effect())

        # Set size policy to expand to the available width
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)

        # Create Layouts
        # --------------
        # Main layout of the card
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 0, 5, 0)
        self.main_layout.setSpacing(0)

        # Header layout containing the title and status widget
        header_widget = QtWidgets.QWidget(self)
        header_layout = QtWidgets.QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 5, 10, 5)
        header_widget.setFixedHeight(40)
        header_widget.setStyleSheet("""
            background-color: #222; 
            border-top-left-radius: 15px; 
            border-top-right-radius: 15px; 
        """)

        # Title label
        card_label = QtWidgets.QLabel("Task Note", header_widget)
        card_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(card_label)

        # Spacer
        header_layout.addStretch()

        # Status widget
        self.status_widget = StatusNextStepWidget(current_status=self.current_status, container=self.parent())
        header_layout.addWidget(self.status_widget)

        # Add header to main layout
        self.main_layout.addWidget(header_widget)

        # Add attached images if present
        if self.attached_images:
            self.image_layout = QtWidgets.QVBoxLayout()  # A layout to hold multiple images
            self.image_layout.setContentsMargins(0, 0, 0, 0)
            self.image_layout.setSpacing(0)

            # Display each attached image as a thumbnail
            for image_path in self.attached_images:
                self.add_image_thumbnail(image_path)

            # Add the image layout to the main layout
            self.main_layout.addLayout(self.image_layout)

        # Comment Text Area with markdown support
        self.comment_area = FlexTextBrowser(self)
        content = process_markdown(self.content)
        self.comment_area.setMarkdown(content)
        self.main_layout.addWidget(self.comment_area)

    def add_image_thumbnail(self, image_path):
        """Add a scaled image thumbnail to the card."""
        image_label = QtWidgets.QLabel(self)
        image_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        pixmap = QtGui.QPixmap(image_path)
        
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                340, 
                pixmap.height(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation
            )
            image_label.setPixmap(scaled_pixmap)
            image_label.setToolTip(os.path.basename(image_path))  # Tooltip with file name
            self.image_layout.addWidget(image_label)  # Add to image layout

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect the anchorClicked signal to handle user mentions
        self.comment_area.anchorClicked.connect(self._handle_user_mentions)

        # Connect the status_changed signal
        self.status_widget.status_changed.connect(self.on_status_changed)

    def on_status_changed(self, new_status):
        """Handle when status is changed."""
        previous_status = self.current_status
        self.current_status = new_status
        self.status_changed.emit(self, previous_status, new_status)

    def _handle_user_mentions(self, url):
        """Handle clicks on user mentions."""
        user = url.toString().lstrip("user:")
        QtWidgets.QMessageBox.information(self, "User Mention", f"You clicked on @{user}")

    def animate_out(self, direction='right'):
        """Animate the card sliding out in the specified direction and remove it from the layout.

        Args:
            direction (str): Direction to animate the card ('left' or 'right').
        """
        # Disable the card during animation
        self.setEnabled(False)

        if self.status_widget.parallel_animation_group.state() == QtCore.QAbstractAnimation.State.Running:
            # Stop the current animation and re-calculate based on new size
            self.status_widget.parallel_animation_group.stop()

        # Animation to slide the card out to the specified direction
        self.animation = QtCore.QPropertyAnimation(self, b"pos")
        self.animation.setDuration(300)
        start_pos = self.pos()

        # Determine the end position based on the direction
        offset = 500 if direction == 'right' else -500  # Move 500 pixels left or right
        end_pos = self.pos() + QtCore.QPoint(offset, 0)  # Slide left or right

        self.animation.setStartValue(start_pos)
        self.animation.setEndValue(end_pos)
        self.animation.setEasingCurve(QtCore.QEasingCurve.Type.InCubic)
        self.animation.finished.connect(self.on_animation_finished)
        self.animation.start()

    def on_animation_finished(self):
        """Handle the cleanup after the animation finishes."""
        # Remove the card from its parent layout
        self.hide()
        self.setEnabled(True)

    def get_status(self):
        """Retrieve the current status of the card.
        """
        return self.status_widget.status_combobox.currentText()

class FloatingHeaderWidget(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setFixedHeight(40)
        self.setStyleSheet("""
            background-color: #222; 
            border-radius: 15px;
        """)

        # Create layout
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Application title
        app_title = QtWidgets.QLabel("Feedback & Comments", self)
        app_title.setStyleSheet("font-size: 16px; color: #FFF;")
        layout.addWidget(app_title)

        # Spacer to push buttons to the right
        layout.addStretch()

        # Toggle background button
        self.toggle_bg_button = self._create_button(
            icon=TablerQIcon.background, 
            tooltip="Toggle Background"
        )

        # Collapse/Expand button
        self.collapse_button = self._create_button(
            text="−", tooltip="Collapse"
        )

        # Close button for the layout
        self.close_button = self._create_button(
            text="✕", tooltip="Close", hover_color="red"
        )

        # Add buttons to the layout
        layout.addWidget(self.toggle_bg_button)
        layout.addWidget(self.collapse_button)
        layout.addWidget(self.close_button)

    def _create_button(self, text='', icon=None, tooltip='', hover_color=None):
        button = QtWidgets.QPushButton(icon, text, self) if icon else QtWidgets.QPushButton(text, self)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.setFixedSize(20, 20)
        button.setToolTip(tooltip)
        style = """
            QPushButton {
                background-color: transparent;
                border: none;
            }
        """
        if hover_color:
            style += f"""
                QPushButton:hover {{
                    color: {hover_color};
                }}
            """
        button.setStyleSheet(style)
        return button

class TransparentFloatingLayout(QtWidgets.QWidget):
    """Main widget holding a transparent scrollable layout with feedback cards, drag functionality, and filter buttons."""

    WINDOW_FLAGS = QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint

    def __init__(self, window_title: str = "Feedback and Comment System", parent = None):
        super().__init__(parent, self.WINDOW_FLAGS, windowTitle=window_title)

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        # Enable dragging and closing on the entire layout
        self.is_dragging = False
        self._widget_position_offset = None
        self.visible_cards = []
        self.attached_images = []

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

        # Apply shadow effect using utility method
        self.setGraphicsEffect(UIUtil.create_shadow_effect())
        self.resize(400, 800)

        # Create Widgets
        # --------------
        self.header_widget = FloatingHeaderWidget(self)
        self.status_filter_widget = StatusFilterWidget(self)
        self.scroll_area = self._create_scroll_area()
        self.input_bar = self._create_input_bar()

        # Add Widgets to Layouts
        # ----------------------
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.main_layout.addWidget(self.header_widget)
        self.main_layout.addWidget(self.status_filter_widget)
        self.main_layout.addWidget(self.scroll_area)
        self.main_layout.addWidget(self.input_bar)

        # Store the allowed edges (default: all edges enabled)
        allowed_edges = QtCore.Qt.Edge.LeftEdge | QtCore.Qt.Edge.RightEdge | QtCore.Qt.Edge.BottomEdge

        # Attach the resize-move handler
        self._resize_handler = ResizeHandler(self, allowed_edges)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect signals to slots
        self.header_widget.collapse_button.clicked.connect(self.toggle_card_area)
        self.header_widget.close_button.clicked.connect(self.close)

        self.status_filter_widget.filter_changed.connect(self.filter_cards)
        self.status_filter_widget.filters_cleared.connect(self.filter_cards)

        self.attach_button.clicked.connect(self.attach_image)
        self.new_task_input.textChanged.connect(self.toggle_add_button_state)
        self.add_button.clicked.connect(self.add_new_task)

        # Add keyboard shortcuts for common actions
        QtWidgets.QShortcut("Ctrl+Return", self.new_task_input, self.add_new_task)
        QtWidgets.QShortcut("Ctrl+Enter", self.new_task_input, self.add_new_task)

    # TODO: Implement as class CardArea(QtWidgets.QScrollArea)
    def _create_scroll_area(self) -> QtWidgets.QScrollArea:
        # Scrollable area for feedback cards
        scroll_area = MomentumScrollArea(
            self,
            widgetResizable=True,
        )
        scroll_area.setStyleSheet("background: transparent; border: none;")  # Transparent scroll area background

        # Container for scrollable area
        self.scroll_content = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)  # Align cards to the top
        self.scroll_layout.setSpacing(20)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        # Set size policy to expand to the available width
        # scroll_area.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)

        # Placeholder card for when no cards match the current filter
        self.placeholder_card = PlaceholderCard(self, "No cards match the selected filters.")
        self.scroll_layout.addWidget(self.placeholder_card)

        scroll_area.setWidget(self.scroll_content)

        return scroll_area

    def _create_input_bar(self):
        # Input bar at the bottom for new task and attachment
        input_bar = QtWidgets.QFrame(self)
        sticky_layout = QtWidgets.QHBoxLayout(input_bar)
        sticky_layout.setContentsMargins(10, 5, 10, 5)
        input_bar.setStyleSheet("""
            QFrame {
                border-radius: 10px;
            }
        """)

        # Attachment preview layout for displaying attached images
        self.attachment_preview_layout = QtWidgets.QHBoxLayout(self.scroll_area)
        self.attachment_preview_layout.setContentsMargins(0, 0, 0, 0)
        self.attachment_preview_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignLeft)

        # Attach image button
        self.attach_button = QtWidgets.QToolButton(input_bar)
        self.attach_button.setIcon(TablerQIcon.image_in_picture)
        self.attach_button.setToolTip("Attach Image")

        self.screenshot_btn = QtWidgets.QToolButton(input_bar)
        self.screenshot_btn.setIcon(TablerQIcon.screenshot)
        self.screenshot_btn.setToolTip("Screen Shot")

        sticky_layout.addWidget(self.attach_button)
        sticky_layout.addWidget(self.screenshot_btn)

        # Input field for new task or comment
        self.new_task_input = FlexPlainTextEdit(input_bar)
        self.new_task_input.setPlaceholderText("Add a new task or comment... Use @username to mention someone.")

        sticky_layout.addWidget(self.new_task_input)

        # Add button for adding new task or comment with icon
        self.add_button = QtWidgets.QToolButton(input_bar)
        self.add_button.setIcon(TablerQIcon.plus)
        self.add_button.setToolTip("Add Task")
        self.add_button.setEnabled(False)  # Disable add button initially

        sticky_layout.addWidget(self.add_button)

        return input_bar

    def attach_image(self):
        file_dialog = QtWidgets.QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Attach Image", "", "Images (*.png *.jpg *.bmp)")
        if not file_path:
            return

        # Display thumbnail in attachment preview layout
        thumbnail_label = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap(file_path).scaled(50, 50, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
        thumbnail_label.setPixmap(pixmap)
        thumbnail_label.setToolTip(os.path.basename(file_path))

        # Add close button to remove thumbnail
        close_button = QtWidgets.QPushButton("×")
        close_button.setFixedSize(20, 20)
        close_button.clicked.connect(lambda: self.remove_attachment(thumbnail_label, file_path))

        thumbnail_layout = QtWidgets.QVBoxLayout()
        thumbnail_layout.addWidget(close_button, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        thumbnail_layout.addWidget(thumbnail_label)

        self.attachment_preview_layout.addLayout(thumbnail_layout)

        # Track attached image path
        self.attached_images.append(file_path)

        self.toggle_add_button_state()

    def remove_attachment(self, thumbnail_label, file_path):
        """Remove the attachment thumbnail and its associated file path.
        """
        # Find the thumbnail's parent layout (it contains the thumbnail and close button)
        for i in range(self.attachment_preview_layout.count()):
            item = self.attachment_preview_layout.itemAt(i)
            if item.layout() and thumbnail_label in [item.layout().itemAt(j).widget() for j in range(item.layout().count())]:
                # Clear all widgets in this sub-layout
                for j in reversed(range(item.layout().count())):
                    widget = item.layout().itemAt(j).widget()
                    if widget:
                        widget.deleteLater()
                # Remove the layout itself from attachment_preview_layout
                self.attachment_preview_layout.takeAt(i).layout().deleteLater()
                break

        # Remove the file path from attached_images if it exists
        if file_path in self.attached_images:
            self.attached_images.remove(file_path)

        # Update add button state after removal
        self.toggle_add_button_state()

    def toggle_add_button_state(self):
        """Enable or disable the Add button based on input field text or attached images."""
        has_text = bool(self.new_task_input.toPlainText().strip())
        has_images = bool(self.attached_images)
        self.add_button.setEnabled(has_text or has_images)

    def clear_layout(self, layout):
        """Remove all widgets from the given layout.
        """
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                # Handle nested layouts if necessary
                self.clear_layout(item.layout())

    def add_new_task(self, message: str = None):
        """Add a new task or comment as a floating card."""
        new_task_text = message or self.new_task_input.toPlainText().strip()

        # Proceed only if there's text or images to add
        if not new_task_text and not self.attached_images:
            return

        # Handle user mentions by converting @username to clickable links
        formatted_text = format_user_mentions(new_task_text)

        # Create a new FloatingCard with attachments
        new_card = FloatingCard(self, content=formatted_text, attached_images=self.attached_images)
        
        # Reset attachments for the next task
        self.clear_layout(self.attachment_preview_layout)  # Clear attachment previews
        self.attached_images.clear()

        # Ensure "To Do" status is visible in the filter
        self.ensure_status_visible("To Do")

        self.add_card(new_card)
        self.new_task_input.clear()  # Clear the input field after adding
        self.attached_image_path = None  # Reset the attached image path

        # Hide placeholder card since a new card is added
        self.placeholder_card.setVisible(False)

        # Scroll to the bottom of the scroll area
        QtCore.QTimer.singleShot(0, self.scroll_to_bottom)

    def ensure_status_visible(self, status):
        """Ensure that the given status is visible by modifying the filter if necessary.

        Args:
            status (str): The status to ensure visibility.
        """
        active_statuses = self.status_filter_widget.active_filters or STATUS_ORDER
        if status not in active_statuses:
            self.status_filter_widget.set_filter_checked(status)

    def scroll_to_bottom(self):
        """Smoothly animate scrolling to the bottom of the scroll area.
        """
        # Get the vertical scroll bar of the scroll area
        scroll_bar = self.scroll_area.verticalScrollBar()

        # Use UIUtil to create and start the scroll animation
        UIUtil.apply_animation(
            widget=scroll_bar,
            property_name="value",
            start_value=scroll_bar.value(),
            end_value=scroll_bar.maximum(),
            duration=500,
            easing_curve=QtCore.QEasingCurve.Type.OutCubic
        )

    def filter_cards(self):
        """Filter cards based on the selected filter button.
        """
        # Get the statuses of all checked filters
        selected_status = self.status_filter_widget.active_filters or STATUS_ORDER

        self.visible_cards.clear()

        # Iterate through all cards and update visibility based on the selected filters
        for i in range(self.scroll_layout.count()):
            card = self.scroll_layout.itemAt(i).widget()

            # Skip placeholder card when filtering
            if isinstance(card, PlaceholderCard):
                continue

            # Get the card's status and determine visibility
            card.setVisible(card.get_status() in selected_status)
            if card.isVisible():
                self.visible_cards.append(card)

        # Show placeholder card if no other cards are visible
        self.placeholder_card.setVisible(not self.visible_cards)

    def toggle_card_area(self):
        """Toggle the visibility of the card area (expand/collapse).
        """
        if self.scroll_area.isVisible():
            # Collapse the card area
            self.header_widget.collapse_button.setText("+")  # Change button to show expand icon

            # Animate the main window's geometry to collapse
            self.animate_window_geometry(collapse=True)
        else:
            # Expand the card area
            self.status_filter_widget.setVisible(True)
            self.scroll_area.setVisible(True)
            self.header_widget.collapse_button.setText("−")  # Change button to show collapse icon

            # Animate the main window's geometry to expand
            self.animate_window_geometry(collapse=False)

    def animate_window_geometry(self, collapse):
        """Animate the geometry of the main window to collapse or expand.
        """
        # Get the current geometry of the main window
        start_geometry = self.geometry()

        # Calculate the target geometry based on collapse or expand
        if collapse:
            # Calculate the height when collapsed (header + input bar)
            target_height = self.header_widget.height() + self.input_bar.height()
        else:
            # Make sure all widgets are visible to calculate the expanded height
            self.status_filter_widget.setVisible(True)
            self.scroll_area.setVisible(True)
            self.adjustSize()  # Adjust size to fit contents
            target_height = self.sizeHint().height()

        # Create the target geometry
        target_geometry = QtCore.QRect(
            start_geometry.x(),
            start_geometry.y(),
            start_geometry.width(),
            target_height
        )

        # Use UIUtil to apply the geometry animation
        self.geometry_animation = UIUtil.apply_animation(
            widget=self,
            property_name="geometry",
            start_value=start_geometry,
            end_value=target_geometry,
            duration=300,
            easing_curve=QtCore.QEasingCurve.Type.InOutQuad
        )

        # Connect to the animation's finished signal if collapsing
        if collapse:
            self.geometry_animation.finished.connect(self.collapse)

    def collapse(self):
        self.status_filter_widget.setVisible(False)
        self.scroll_area.setVisible(False)

    def add_card(self, card: 'FloatingCard'):
        """Add a card to the layout with a fade-in animation.
        """
        card.setGraphicsEffect(UIUtil.create_shadow_effect())
        card.setVisible(False)
        self.scroll_layout.addWidget(card)
        self.visible_cards.append(card)
        card.setVisible(True)
        # Connect to card's status_changed signal
        card.status_changed.connect(self.update_card_visibility)

    def update_card_visibility(self, card: 'FloatingCard', previous_status, new_status):
        """Handle when a card's status is changed.
        """
        selected_status = self.status_filter_widget.active_filters or STATUS_ORDER

        if card.isVisible() and new_status not in selected_status:
            # Card should be hidden, animate it out to left or right
            direction = "right" if STATUS_ORDER.index(new_status) > STATUS_ORDER.index(previous_status) else "left"
            card.animate_out(direction)
            self.visible_cards.remove(card)

        if not self.visible_cards:
            self.placeholder_card.setVisible(True)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """Start dragging the entire layout when the mouse is pressed on the layout drag area."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.header_widget.geometry().contains(event.pos()):
            self.is_dragging = True
            self._widget_position_offset = event.pos()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        """Handle dragging of the entire layout."""
        if self.is_dragging:
            self.move(self.mapToParent(event.pos() - self._widget_position_offset))

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        """End dragging when the mouse is released."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self._widget_position_offset = None


if __name__ == "__main__":
    import doctest
    doctest.testmod()

    from blackboard.theme import set_theme
    app = QtWidgets.QApplication([])
    set_theme(app)
    window = TransparentFloatingLayout()

    # NOTE: Example: Add a few floating cards below the header inside the scrollable area
    card_count = 4
    for i in range(card_count):
        content = f"This is a comment or feedback. Mentioning @user{i}."
        window.add_new_task(content)

    window.show()
    app.exec()
