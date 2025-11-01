from typing import Dict, Tuple, List
from enum import Enum

from PyQt5 import QtWidgets, QtGui, QtCore
import sqlite3

# Constants for colors, sizes, etc.
BACKGROUND_COLOR = QtGui.QColor(30, 30, 30)
TABLE_COLOR = QtGui.QColor(40, 40, 40)
TABLE_BORDER_COLOR = QtGui.QColor(200, 200, 200)
HIGHLIGHT_COLOR = QtGui.QColor(60, 60, 60)
LINE_COLOR = QtGui.QColor(0, 128, 255)
HIGHLIGHT_LINE_COLOR = QtGui.QColor(255, 165, 0)
TEXT_COLOR = QtGui.QColor(255, 255, 255)

TABLE_WIDTH = 200
ROW_HEIGHT = 20
HEADER_HEIGHT = 30
MARGIN = 80
COLUMN_WIDTH = 240

def get_db_schema(db_path: str) -> Tuple[Dict[str, Tuple], Dict[str, str]]:
    """Fetch schema information and foreign keys from the SQLite database.
    """
    schema = {}
    relationships = {}

    # Open database in read-only mode
    conn = sqlite3.connect(f"file:///{db_path}?mode=ro", uri=True)

    with conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            schema[table_name] = columns

            cursor.execute(f"PRAGMA foreign_key_list({table_name});")
            fks = cursor.fetchall()
            for fk in fks:
                from_table, from_column, to_table, to_column = table_name, fk[3], fk[2], fk[4]
                relationships[f'{from_table}.{from_column}'] = f'{to_table}.{to_column}'
    
    return schema, relationships


# TODO: Design more appropriate colors
class ConnectionDirection(Enum):
    FROM = ("From", QtGui.QColor(255, 165, 0))  # Blue for outgoing
    TO = ("To", QtGui.QColor(255, 69, 0))     # Green for incoming
    SELF = ("Self", QtGui.QColor(0, 255, 128)) # Orange for self-relation

    def __init__(self, label: str, color: QtGui.QColor):
        self.label = label
        self.color = color

    @property
    def get_color(self):
        return self.color


class TableItem(QtWidgets.QGraphicsRectItem):
    """Custom QGraphicsRectItem to represent a database table."""

    def __init__(self, table_name: str, columns: list, position: tuple):
        super().__init__(0, 0, TABLE_WIDTH, HEADER_HEIGHT + len(columns) * ROW_HEIGHT)
        self.setPos(*position)

        # Enable hover events
        self.setAcceptHoverEvents(True)

        # Set pen and brush for dark theme
        self.setPen(QtGui.QPen(TABLE_BORDER_COLOR))  # Light gray border
        self.setBrush(QtGui.QBrush(TABLE_COLOR))

        # Table header
        self.header = QtWidgets.QGraphicsTextItem(table_name, self)
        self.header.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Weight.Bold))
        self.header.setDefaultTextColor(TEXT_COLOR)
        self.header.setPos(5, 5)

        # Add column names
        self.columns: List[QtWidgets.QGraphicsTextItem] = []
        for i, column in enumerate(columns):
            column_text = QtWidgets.QGraphicsTextItem(f"{'* ' if column[5] else ''}{column[1]} ({column[2]})", self)
            column_text.setDefaultTextColor(QtGui.QColor(180, 180, 180))  # Light gray text
            column_text.setPos(5, HEADER_HEIGHT + i * ROW_HEIGHT)
            self.columns.append(column_text)

        # Store connections associated with this table
        self.connections: Tuple[ConnectionItem, ConnectionDirection] = []

    def add_connection(self, connection_item):
        """Add a connection item associated with this table."""
        self.connections.append(connection_item)

    def get_column_edge_position(self, column_name: str, side: str) -> QtCore.QPointF:
        """Get the edge position of a specific column within the table."""
        for column in self.columns:
            if column_name in column.toPlainText():
                column_rect = column.sceneBoundingRect()
                if side == 'left':
                    return QtCore.QPointF(column_rect.left(), column_rect.center().y())
                else:
                    return QtCore.QPointF(column_rect.right(), column_rect.center().y())
        return self.sceneBoundingRect().center()

    def hoverEnterEvent(self, event):
        """Change appearance on hover and highlight connections."""
        self.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), 2))  # Yellow border on hover
        self.setBrush(QtGui.QBrush(HIGHLIGHT_COLOR))           # Lighter fill on hover

        # Highlight associated connections
        for connection_item, direction in self.connections:
            connection_item.highlight(True, direction)

        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Revert appearance on hover leave and reset connection highlights.
        """
        self.setPen(QtGui.QPen(TABLE_BORDER_COLOR))
        self.setBrush(QtGui.QBrush(TABLE_COLOR))

        # Reset associated connections
        for connection_item, _ in self.connections:
            connection_item.highlight(False)

        super().hoverLeaveEvent(event)


class ConnectionItem(QtWidgets.QGraphicsPathItem):
    """Custom QGraphicsPathItem to represent a connection between tables."""

    def __init__(self, path: QtGui.QPainterPath, from_table: str, to_table: str, from_column: str, to_column: str):
        super().__init__(path)

        # Enable hover events
        self.setAcceptHoverEvents(True)

        # Set default and highlight pens
        self.default_pen = QtGui.QPen(LINE_COLOR, 2)  # Light blue line

        self.setPen(self.default_pen)

        # Store connection details
        self.from_table = from_table
        self.to_table = to_table
        self.from_column = from_column
        self.to_column = to_column

        # Set tooltip with connection details
        self.setToolTip(f"{from_table}.{from_column} -> {to_table}.{to_column}")

    def hoverEnterEvent(self, event):
        """Change line appearance on hover."""
        self.setPen(QtGui.QPen(HIGHLIGHT_LINE_COLOR, 3))  # Red dashed line on hover
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Revert line appearance on hover leave."""
        self.setPen(self.default_pen)  # Revert to default line
        super().hoverLeaveEvent(event)

    def highlight(self, should_highlight: bool, direction: 'ConnectionDirection' = None):
        """Highlight or unhighlight the line."""
        if should_highlight:
            self.setPen(QtGui.QPen(direction.color, 3))
        else:
            self.setPen(self.default_pen)


class ERDiagramView(QtWidgets.QGraphicsView):
    """Custom QGraphicsView to display the ER diagram."""

    # Initialization and Setup
    # ------------------------
    def __init__(self, schema: Dict[str, Tuple], relationships: Dict[str, str], parent=None):
        super().__init__(parent)

        # Store the arguments
        self.schema = schema
        self.relationships = relationships

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        self.table_items: Dict[str, TableItem] = {}
        self.last_drag_pos = None

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Enable zooming and panning
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        # Hide scrollbars
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scene = QtWidgets.QGraphicsScene(self, backgroundBrush=QtGui.QBrush(BACKGROUND_COLOR))
        self.setScene(scene)

        self.draw_schema(self.schema)
        self.draw_relationships(self.relationships)

    # Public Methods
    # --------------
    def draw_schema(self, schema: dict):
        """Draw tables and their columns on the scene."""
        x, y = 0, 0
        max_height = 0

        for table_name, columns in schema.items():
            table_item = TableItem(table_name, columns, (x, y))
            self.scene().addItem(table_item)
            self.table_items[table_name] = table_item

            y += table_item.boundingRect().height() + MARGIN
            max_height = max(max_height, table_item.boundingRect().height())

            if y > 600:  # If y position exceeds 600, move to the next column
                y = 0
                x += COLUMN_WIDTH + MARGIN

    def draw_relationships(self, relationships: Dict[str, str]):
        """Draw lines representing foreign key relationships between tables.
        """
        for from_chain, to_chain in relationships.items():
            from_table, from_column = from_chain.rsplit('.', 1)
            to_table, to_column = to_chain.rsplit('.', 1)

            from_item = self.table_items[from_table]
            to_item = self.table_items[to_table]

            # Positions of table centers
            from_pos = from_item.sceneBoundingRect().center()
            to_pos = to_item.sceneBoundingRect().center()

            # Determine explicit edge positions
            start_pos, end_pos = self.determine_connection_sides(
                from_item, to_item, from_pos, to_pos, from_column, to_column
            )

            # Create the painter path
            path = QtGui.QPainterPath()
            path.moveTo(start_pos)

            # Check if they're approximately in the same column
            same_column_threshold = 10  # adjust as needed
            if abs(from_pos.x() - to_pos.x()) < same_column_threshold:
                # Route around the right side of the tables
                # This ensures the line is always visible and not behind the table
                route_x = max(from_item.sceneBoundingRect().right(),
                            to_item.sceneBoundingRect().right()) + 50
                path.lineTo(route_x, start_pos.y())  # Move horizontally to the right
                path.lineTo(route_x, end_pos.y())    # Move vertically to target's height
                path.lineTo(end_pos)                 # Move horizontally to the target
            else:
                # Default midpoint-based path
                horizontal_midpoint = (start_pos.x() + end_pos.x()) / 2
                path.lineTo(horizontal_midpoint, start_pos.y())
                path.lineTo(horizontal_midpoint, end_pos.y())
                path.lineTo(end_pos)

            # Add the connection item with hover effects
            connection_item = ConnectionItem(path, from_table, to_table, from_column, to_column)
            connection_item.setZValue(-1000)  # Place behind table items
            self.scene().addItem(connection_item)

            # Associate connection with both tables for hover highlighting
            if from_item == to_item:
                from_item.add_connection((connection_item, ConnectionDirection.SELF))  # Mark as 'from'
                to_item.add_connection((connection_item, ConnectionDirection.SELF))   # Mark as 'to'
            else:
                from_item.add_connection((connection_item, ConnectionDirection.FROM))  # Mark as 'from'
                to_item.add_connection((connection_item, ConnectionDirection.TO))   # Mark as 'to'

    def determine_connection_sides(self, from_item, to_item, from_pos, to_pos, from_column, to_column):
        """Determine which sides of the tables to connect based on their positions."""
        if from_pos.x() < to_pos.x():
            # Connect from right of source to left of destination
            start_pos = from_item.get_column_edge_position(from_column, 'right')
            end_pos = to_item.get_column_edge_position(to_column, 'left')
        elif from_pos.x() > to_pos.x():
            # Connect from left of source to right of destination
            start_pos = from_item.get_column_edge_position(from_column, 'left')
            end_pos = to_item.get_column_edge_position(to_column, 'right')
        else:
            # If same vertical alignment, connect from right to left
            start_pos = from_item.get_column_edge_position(from_column, 'right')
            end_pos = to_item.get_column_edge_position(to_column, 'right')
        return start_pos, end_pos

    # Overridden Methods
    # ------------------
    def wheelEvent(self, event):
        """Zoom in or out with mouse wheel.
        """
        # Tell the view to treat the mouse cursor as the zoom anchor.
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        # Determine zoom factor.
        factor = 1.15 if event.angleDelta().y() > 0 else 0.85
        
        # Perform the scale around the cursor.
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        """Start panning with middle mouse button.
        """
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            self.last_drag_pos = event.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        """Handle panning."""
        if self.last_drag_pos is not None:
            # Calculate delta movement and account for zoom level
            delta = self.mapToScene(event.pos()) - self.mapToScene(self.last_drag_pos)
            # Invert the delta to drag in the correct direction
            self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.NoAnchor)
            self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.NoAnchor)
            self.translate(delta.x(), delta.y())
            self.last_drag_pos = event.pos()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """End panning."""
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            self.last_drag_pos = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class MainWindow(QtWidgets.QWidget):
    """Main application window for displaying the ER diagram."""

    def __init__(self, db_path: str):
        super().__init__(windowTitle="ER Diagram Viewer")
        self.setGeometry(100, 100, 1200, 800)

        schema, relationships = get_db_schema(db_path)

        layout = QtWidgets.QVBoxLayout(self)

        # Search bar
        search_layout = QtWidgets.QHBoxLayout()
        self.search_bar = QtWidgets.QLineEdit(self)
        self.search_bar.setPlaceholderText("Search tables...")
        self.search_bar.textChanged.connect(self.search_tables)
        search_layout.addWidget(self.search_bar)
        layout.addLayout(search_layout)

        # Diagram view
        self.diagram_view = ERDiagramView(schema, relationships)
        layout.addWidget(self.diagram_view)

    def search_tables(self):
        """Adjust opacity of tables based on search input.
        """
        search_text = self.search_bar.text().lower()
        for table_name, table_item in self.diagram_view.table_items.items():
            if search_text in table_name.lower():
                table_item.setOpacity(1.0)  # Full opacity for matching tables
            else:
                table_item.setOpacity(0.3)  # Lower opacity for non-matching tables


def main():
    import sys
    app = QtWidgets.QApplication(sys.argv)

    # Load your database path here
    db_path = "chinook.db"  # Adjust the path to your database file

    main_window = MainWindow(db_path)
    main_window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
