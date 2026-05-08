import sys
import math
from qtpy import QtCore, QtGui, QtWidgets
from tablerqicon import TablerQIcon
import scipy
import numpy as np
from enum import Enum


class ScreenCaptureArea(QtWidgets.QWidget):
    closed = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.WindowType.WindowStaysOnTopHint | QtCore.Qt.WindowType.FramelessWindowHint)
        self.setWindowState(QtCore.Qt.WindowState.WindowFullScreen)
        self.setWindowOpacity(0.3)
        self.rubber_band = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Shape.Rectangle, self)
        self.origin: QtCore.QPoint = QtCore.QPoint()
        self.selected_rect: QtCore.QRect = QtCore.QRect()

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.origin = event.pos()
            self.rubber_band.setGeometry(QtCore.QRect(self.origin, QtCore.QSize()))
            self.rubber_band.show()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if self.rubber_band.isVisible():
            self.rubber_band.setGeometry(QtCore.QRect(self.origin, event.pos()).normalized())

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.selected_rect = self.rubber_band.geometry()
            self.rubber_band.hide()
            self.close()

    def closeEvent(self, event: QtGui.QCloseEvent):
        self.closed.emit()
        super().closeEvent(event)

    def get_selected_rect(self) -> QtCore.QRect:
        return self.selected_rect


class DrawingObject:
    def __init__(self, points, color, width):
        self.points = points
        self.color = color
        self.width = width


class ToolMode(Enum):
    NONE = 0
    SELECTION = 1
    FREEHAND = 2
    RECTANGLE = 3
    ERASER = 4
    TEXT = 5


class DrawingLabel(QtWidgets.QWidget):
    # Define the signal
    drawing_changed = QtCore.Signal()
    selection_changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image: QtGui.QPixmap = QtGui.QPixmap()
        self.last_point: QtCore.QPoint = QtCore.QPoint()
        self.current_tool: ToolMode = ToolMode.NONE
        self.rectangle_start: QtCore.QPoint = QtCore.QPoint()
        self.rectangle_end: QtCore.QPoint = QtCore.QPoint()
        self.rectangles: list[QtCore.QRect] = []
        self.control_points: list[QtCore.QPointF] = []
        self.drawing_objects: list[DrawingObject] = []
        self.text_items: list[tuple[QtCore.QPoint, str]] = []
        self.text_editor = None
        self.text_font = QtGui.QFont('Arial', 12)
        self.pen_color: QtGui.QColor = QtGui.QColor(QtCore.Qt.GlobalColor.red)
        self.pen_width: int = 3
        self.is_dragging: bool = False
        self.start_drag_position: QtCore.QPoint = QtCore.QPoint()
        self.initial_pen_width: int = self.pen_width
        self.cursor_visible: bool = False
        self.text_color: QtGui.QColor = QtGui.QColor(0, 0, 0)  # Text color
        self.hover_item: tuple[str, int] | None = None
        self.selected_item: tuple[str, int] | None = None
        self.hover_handle: tuple[str, int, str] | None = None
        self.rect_resize_handle: str | None = None
        self.rect_resize_initial_rect: QtCore.QRect | None = None
        self.selection_dragging: bool = False
        self.selection_drag_start: QtCore.QPoint = QtCore.QPoint()
        self.selection_initial_points: list[QtCore.QPointF] | None = None
        self.selection_initial_position: QtCore.QPoint | None = None
        self.editing_text_index: int | None = None
        self.handle_size: int = 10
        self.selection_modified: bool = False
        self.eraser_hover_item: tuple[str, int] | None = None
        self.eraser_cursor: QtGui.QCursor | None = self._create_eraser_cursor()

        self.setMouseTracking(True)  # Enable mouse tracking to get mouseMoveEvent even when no button is pressed

    def set_pixmap(self, pixmap: QtGui.QPixmap):
        self.image = pixmap.copy()
        self.setFixedSize(self.image.size())
        self._clear_selection_state()
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)
        if not self.image.isNull():
            self._draw_background(painter)
            self._draw_rectangles(painter)
            self._draw_drawing_objects(painter)
            self._draw_text_items(painter)
            self._draw_selection_overlay(painter)
            self._draw_eraser_overlay(painter)

        # Draw the preview cursor if it's visible
        if self.cursor_visible and self.current_tool == ToolMode.FREEHAND:
            painter.setPen(QtGui.QPen(self.pen_color, 1, QtCore.Qt.PenStyle.DashLine))
            cursor_size = self.pen_width
            cursor_center = self.start_drag_position if self.is_dragging else self.last_point
            cursor_rect = QtCore.QRect(cursor_center.x() - cursor_size // 2,
                                       cursor_center.y() - cursor_size // 2,
                                       cursor_size, cursor_size)
            painter.drawEllipse(cursor_rect)

    def _draw_background(self, painter: QtGui.QPainter):
        painter.drawPixmap(self.rect(), self.image)

    def _draw_rectangles(self, painter: QtGui.QPainter):
        pen = QtGui.QPen(self.pen_color, self.pen_width, QtCore.Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        for rect in self.rectangles:
            painter.drawRect(rect)
        if self.current_tool == ToolMode.RECTANGLE:
            painter.drawRect(QtCore.QRect(self.rectangle_start, self.rectangle_end))

    def _draw_drawing_objects(self, painter: QtGui.QPainter):
        for obj in self.drawing_objects:
            pen = QtGui.QPen(obj.color, obj.width, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap, QtCore.Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            for i in range(1, len(obj.points)):
                start_point = obj.points[i - 1]
                end_point = obj.points[i]
                painter.drawLine(start_point, end_point)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and not self.image.isNull():
            if self.current_tool == ToolMode.SELECTION:
                self._start_selection_interaction(event.pos())
                return

            if self.current_tool == ToolMode.FREEHAND and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
                self.is_dragging = True
                self.start_drag_position = event.pos()
                self.initial_pen_width = self.pen_width
            else:
                if self.current_tool == ToolMode.RECTANGLE:
                    self.rectangle_start = event.pos()
                    self.rectangle_end = self.rectangle_start
                elif self.current_tool == ToolMode.ERASER:
                    self.erase_drawing(event.pos())
                elif self.current_tool == ToolMode.FREEHAND:
                    self.last_point = event.pos()
                    self.control_points = [event.pos()]
                    # Add new drawing object
                    self.current_drawing = DrawingObject(self.control_points, self.pen_color, self.pen_width)
                    self.drawing_objects.append(self.current_drawing)
                elif self.current_tool == ToolMode.TEXT:
                    self.add_text(event.pos())

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        self.last_point = event.pos()  # Update the last point for cursor preview

        if self.current_tool == ToolMode.SELECTION:
            self._handle_selection_move(event)
            return

        if self.current_tool == ToolMode.ERASER:
            self._update_eraser_hover(event.pos())

        if self.current_tool == ToolMode.RECTANGLE and (event.buttons() & QtCore.Qt.MouseButton.LeftButton):
            self.rectangle_end = event.pos()
            self.update()
            return

        if self.is_dragging:
            # Adjust brush size based on horizontal drag distance from the start position
            delta_x = event.pos().x() - self.start_drag_position.x()
            new_width = max(1, self.initial_pen_width + delta_x)
            self.pen_width = new_width
            self.update()  # Refresh to update the preview cursor
        elif self.current_tool == ToolMode.ERASER and (event.buttons() & QtCore.Qt.MouseButton.LeftButton):
            self.erase_drawing(event.pos())
        elif self.current_tool == ToolMode.FREEHAND and (event.buttons() & QtCore.Qt.MouseButton.LeftButton) and not self.image.isNull():
            painter = QtGui.QPainter(self.image)
            pen = QtGui.QPen(self.pen_color, self.pen_width, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap, QtCore.Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(self.last_point, event.pos())
            self.last_point = event.pos()
            self.control_points.append(event.pos())
            self.update()
        else:
            self.update()  # Ensure the cursor preview is updated when moving

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.current_tool == ToolMode.SELECTION:
            if self.selection_dragging and self.selection_modified:
                self.drawing_changed.emit()
            self.selection_dragging = False
            self.selection_modified = False
            self.selection_initial_points = None
            self.selection_initial_position = None
            self.rect_resize_handle = None
            self.rect_resize_initial_rect = None
            self._update_hover_state(event.pos())
            self.update()
            return

        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False  # End brush size adjustment
        elif event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self.current_tool == ToolMode.RECTANGLE:
                rect = QtCore.QRect(self.rectangle_start, self.rectangle_end).normalized()
                if rect.width() > 0 and rect.height() > 0:
                    self.rectangles.append(rect)
            elif self.current_tool == ToolMode.FREEHAND:
                self.smooth_drawn_line()

            # Emit the signal when the drawing changes
            self.drawing_changed.emit()
        self.update()

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.current_tool == ToolMode.SELECTION:
            self._update_hover_state(event.pos())
            if self.hover_item and self.hover_item[0] == 'text':
                self.edit_text_item(self.hover_item[1])
                return
        super().mouseDoubleClickEvent(event)

    def enterEvent(self, event: QtCore.QEvent):
        self.cursor_visible = True
        self.update()

    def leaveEvent(self, event: QtCore.QEvent):
        self.cursor_visible = False
        if self.current_tool == ToolMode.ERASER and self.eraser_hover_item is not None:
            self.eraser_hover_item = None
        self.update()

    def erase_drawing(self, point: QtCore.QPoint):
        if self.text_editor is not None:
            self.commit_text()

        hit = self._hit_test_items(point)
        if not hit:
            return

        item_type, index = hit
        removed = False

        if item_type == 'line' and 0 <= index < len(self.drawing_objects):
            del self.drawing_objects[index]
            removed = True
        elif item_type == 'rectangle' and 0 <= index < len(self.rectangles):
            del self.rectangles[index]
            removed = True
        elif item_type == 'text' and 0 <= index < len(self.text_items):
            del self.text_items[index]
            removed = True

        if not removed:
            return

        previous_selected = self.selected_item
        self._clear_selection_state()
        if previous_selected is not None:
            self._emit_selection_changed(previous_selected)

        self.drawing_changed.emit()
        self._update_eraser_hover(point)
        self.update()

    def smooth_drawn_line(self):
        if len(self.control_points) < 4:  # Need at least 4 points for a cubic B-spline
            return

        # Convert control points to numpy array
        points = np.array([(pt.x(), pt.y()) for pt in self.control_points], dtype=float)

        # Generate B-spline representation
        tck, u = scipy.interpolate.splprep([points[:, 0], points[:, 1]], s=len(points) * 5)
        u_fine = np.linspace(0, 1, len(points) * 10)
        x_fine, y_fine = scipy.interpolate.splev(u_fine, tck)

        # Store the smoothed line as a DrawingObject
        smooth_points = [QtCore.QPointF(x, y) for x, y in zip(x_fine, y_fine)]
        # Update smooth points to current drawing object
        self.current_drawing.points = smooth_points

        self.update()

    def add_text(self, position: QtCore.QPoint):
        if self.text_editor is not None:
            return

        self.editing_text_index = None
        self._create_text_editor(position, '')

    def edit_text_item(self, index: int):
        if index < 0 or index >= len(self.text_items):
            return
        position, text = self.text_items[index]
        self.editing_text_index = index
        self._create_text_editor(position, text)
        if self.text_editor is not None:
            self.text_editor.selectAll()

    def _create_text_editor(self, position: QtCore.QPoint, text: str):
        if self.text_editor is not None:
            self.commit_text()

        editor = QtWidgets.QTextEdit(self)
        editor.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        editor.move(position)
        editor.setStyleSheet(f"background: transparent; color: {self.text_color.name()};")
        editor.setFont(self.text_font)
        editor.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        editor.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        editor.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Preferred)
        editor.setFixedSize(200, 50)
        editor.setPlainText(text)

        original_focus_out = editor.focusOutEvent
        original_key_press = editor.keyPressEvent

        editor.focusOutEvent = lambda event, orig=original_focus_out, ed=editor: self.finish_text_editing(event, orig, ed)
        editor.keyPressEvent = lambda event, orig=original_key_press, ed=editor: self.text_editor_key_press_event(event, orig, ed)

        editor.textChanged.connect(self.adjust_text_editor_size)
        editor.show()
        editor.setFocus()

        self.text_editor = editor
        self.adjust_text_editor_size()

    def text_editor_key_press_event(self, event: QtGui.QKeyEvent, original_handler, editor):
        if event.key() == QtCore.Qt.Key.Key_Return and not (event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier):
            if self.text_editor is editor:
                self.commit_text()
        else:
            original_handler(event)

    def finish_text_editing(self, event: QtGui.QFocusEvent, original_handler, editor):
        original_handler(event)
        if self.text_editor is editor:
            self.commit_text()

    def commit_text(self):
        if not self.text_editor:
            return

        text = self.text_editor.toPlainText()
        position = self.text_editor.pos()
        previous_selected = self.selected_item
        new_selected_item = self.selected_item
        editing_index = self.editing_text_index
        committed_index = None

        if text.strip():
            if editing_index is not None and 0 <= editing_index < len(self.text_items):
                self.text_items[editing_index] = (QtCore.QPoint(position), text)
                committed_index = editing_index
            else:
                self.text_items.append((QtCore.QPoint(position), text))
                committed_index = len(self.text_items) - 1
            if self.current_tool == ToolMode.SELECTION and committed_index is not None:
                new_selected_item = ('text', committed_index)
            self.drawing_changed.emit()
        elif editing_index is not None and 0 <= editing_index < len(self.text_items):
            del self.text_items[editing_index]
            if previous_selected and previous_selected[0] == 'text':
                if previous_selected[1] == editing_index:
                    new_selected_item = None
                elif previous_selected[1] > editing_index:
                    new_selected_item = ('text', previous_selected[1] - 1)
            self.drawing_changed.emit()

        editor = self.text_editor
        self.text_editor = None
        self.editing_text_index = None
        if editor:
            editor.deleteLater()

        self.selected_item = new_selected_item
        self._emit_selection_changed(previous_selected)
        self.update()

    def adjust_text_editor_size(self):
        if not self.text_editor:
            return
        doc = self.text_editor.document()
        doc.setTextWidth(200)
        height = doc.size().height() + 10
        self.text_editor.setFixedHeight(int(height))

    def _draw_text_items(self, painter: QtGui.QPainter):
        painter.setPen(QtGui.QPen(self.text_color))
        painter.setFont(self.text_font)
        for point, text in self.text_items:
            # Support multi-line text
            rect = QtCore.QRectF(point, QtCore.QSizeF(self.width() - point.x(), self.height() - point.y()))
            painter.drawText(rect, text)

    def _start_selection_interaction(self, pos: QtCore.QPoint):
        previous_selected = self.selected_item
        self.selection_modified = False
        if self.text_editor is not None:
            self.commit_text()

        self._update_hover_state(pos)
        if self.hover_handle:
            _, index, handle = self.hover_handle
            self.selected_item = ('rectangle', index)
            self.rect_resize_handle = handle
            self.rect_resize_initial_rect = QtCore.QRect(self.rectangles[index])
            self.selection_dragging = True
            self.selection_drag_start = QtCore.QPoint(pos)
            self.selection_initial_points = None
            self.selection_initial_position = None
            self._emit_selection_changed(previous_selected)
            self._update_cursor_for_selection()
            self.update()
            return

        if self.hover_item:
            self.selected_item = self.hover_item
            self.selection_dragging = True
            self.selection_drag_start = QtCore.QPoint(pos)
            item_type, index = self.selected_item
            if item_type == 'line':
                self.selection_initial_points = [QtCore.QPointF(pt) for pt in self.drawing_objects[index].points]
                self.rect_resize_initial_rect = None
                self.selection_initial_position = None
            elif item_type == 'rectangle':
                self.rect_resize_initial_rect = QtCore.QRect(self.rectangles[index])
                self.selection_initial_points = None
                self.selection_initial_position = None
            elif item_type == 'text':
                position, _ = self.text_items[index]
                self.selection_initial_position = QtCore.QPoint(position)
                self.selection_initial_points = None
                self.rect_resize_initial_rect = None
            self.rect_resize_handle = None
            self._emit_selection_changed(previous_selected)
        else:
            self.clear_selection()
            return
        self._update_cursor_for_selection()
        self.update()

    def _handle_selection_move(self, event: QtGui.QMouseEvent):
        pos = event.pos()
        if self.selection_dragging:
            if self.rect_resize_handle:
                self._resize_selected_rectangle(pos)
            elif self.selected_item:
                self._drag_selected_item(pos)
        else:
            self._update_hover_state(pos)

    def _update_hover_state(self, pos: QtCore.QPoint):
        previous_hover = self.hover_item
        previous_handle = self.hover_handle

        self.hover_handle = self._hit_test_rectangle_handles(pos)
        if self.hover_handle:
            self.hover_item = ('rectangle', self.hover_handle[1])
        else:
            self.hover_item = self._hit_test_items(pos)

        if previous_hover != self.hover_item or previous_handle != self.hover_handle:
            self._update_cursor_for_selection()
            self.update()

    def _drag_selected_item(self, pos: QtCore.QPoint):
        if not self.selected_item:
            return

        delta = pos - self.selection_drag_start
        if delta.manhattanLength() == 0:
            return

        item_type, index = self.selected_item
        if item_type == 'line' and self.selection_initial_points is not None:
            translated = [QtCore.QPointF(pt.x() + delta.x(), pt.y() + delta.y()) for pt in self.selection_initial_points]
            self.drawing_objects[index].points = translated
            self.selection_modified = True
            self.update()
        elif item_type == 'rectangle' and self.rect_resize_initial_rect is not None:
            rect = QtCore.QRect(self.rect_resize_initial_rect)
            rect.translate(delta)
            self.rectangles[index] = rect
            self.selection_modified = True
            self.update()
        elif item_type == 'text' and self.selection_initial_position is not None:
            base = QtCore.QPoint(self.selection_initial_position)
            new_pos = base + delta
            _, text = self.text_items[index]
            self.text_items[index] = (QtCore.QPoint(new_pos), text)
            self.selection_modified = True
            self.update()

    def _resize_selected_rectangle(self, pos: QtCore.QPoint):
        if not self.selected_item or self.rect_resize_initial_rect is None or not self.rect_resize_handle:
            return

        item_type, index = self.selected_item
        if item_type != 'rectangle':
            return

        delta = pos - self.selection_drag_start
        rectf = QtCore.QRectF(self.rect_resize_initial_rect)

        if 'left' in self.rect_resize_handle:
            rectf.setLeft(rectf.left() + delta.x())
        if 'right' in self.rect_resize_handle:
            rectf.setRight(rectf.right() + delta.x())
        if 'top' in self.rect_resize_handle:
            rectf.setTop(rectf.top() + delta.y())
        if 'bottom' in self.rect_resize_handle:
            rectf.setBottom(rectf.bottom() + delta.y())

        rectf = rectf.normalized()
        min_size = 6
        if rectf.width() < min_size or rectf.height() < min_size:
            return

        new_rect = QtCore.QRect(int(rectf.left()), int(rectf.top()), int(rectf.width()), int(rectf.height()))
        self.rectangles[index] = new_rect
        self.selection_modified = True
        self.update()

    def _hit_test_rectangle_handles(self, pos: QtCore.QPoint) -> tuple[str, int, str] | None:
        for index in reversed(range(len(self.rectangles))):
            rect = self.rectangles[index]
            handles = self._get_rect_handles(rect)
            for handle_name, handle_rect in handles.items():
                if handle_rect.contains(QtCore.QPointF(pos)):
                    return ('rectangle', index, handle_name)
        return None

    def _hit_test_items(self, pos: QtCore.QPoint) -> tuple[str, int] | None:
        candidates: list[tuple[str, int, float]] = []
        pointf = QtCore.QPointF(pos)

        for index in reversed(range(len(self.rectangles))):
            rect = self.rectangles[index]
            expanded = rect.adjusted(-6, -6, 6, 6)
            if expanded.contains(pos):
                distance = 0.0
            else:
                distance = self._distance_to_rect(rect, pointf)
            if distance is not None and distance <= 15:
                candidates.append(('rectangle', index, distance + 0.1))

        for index in reversed(range(len(self.text_items))):
            rectf = self._text_rect_from_item(index)
            if rectf is None:
                continue
            expanded = rectf.adjusted(-4, -4, 4, 4)
            if expanded.contains(pointf):
                distance = 0.0
            else:
                distance = self._distance_to_rectf(rectf, pointf)
            if distance is not None and distance <= 15:
                candidates.append(('text', index, distance))

        for index in reversed(range(len(self.drawing_objects))):
            obj = self.drawing_objects[index]
            distance = self._distance_to_polyline(obj.points, pointf)
            if distance is None:
                continue
            threshold = max(6, obj.width + 4)
            if distance <= threshold:
                candidates.append(('line', index, distance + 0.2))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[2])
        return (candidates[0][0], candidates[0][1])

    def _get_rect_handles(self, rect: QtCore.QRect) -> dict[str, QtCore.QRectF]:
        size = self.handle_size
        half = size / 2
        corners = {
            'top_left': QtCore.QPointF(rect.left(), rect.top()),
            'top_right': QtCore.QPointF(rect.right(), rect.top()),
            'bottom_left': QtCore.QPointF(rect.left(), rect.bottom()),
            'bottom_right': QtCore.QPointF(rect.right(), rect.bottom()),
        }
        handles: dict[str, QtCore.QRectF] = {}
        for name, corner in corners.items():
            handles[name] = QtCore.QRectF(corner.x() - half, corner.y() - half, size, size)
        return handles

    def _draw_selection_overlay(self, painter: QtGui.QPainter):
        if self.current_tool != ToolMode.SELECTION:
            return
        highlight_targets = []
        if self.hover_item and self.hover_item != self.selected_item:
            highlight_targets.append((self.hover_item, QtGui.QColor(255, 204, 0, 160)))
        if self.selected_item:
            highlight_targets.append((self.selected_item, QtGui.QColor(0, 153, 255, 180)))

        painter.save()
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        for item, color in highlight_targets:
            rectf = self._get_item_bounding_rect(item)
            if rectf is None:
                continue
            pen = QtGui.QPen(color, 1, QtCore.Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(rectf)

            if item[0] == 'rectangle' and self.selected_item == item:
                handles = self._get_rect_handles(self.rectangles[item[1]])
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
                for name, handle_rect in handles.items():
                    is_active = self.rect_resize_handle == name
                    is_hovered = self.hover_handle is not None and self.hover_handle[1] == item[1] and self.hover_handle[2] == name
                    if is_active or is_hovered:
                        painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 153, 255)))
                    else:
                        painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
                    painter.drawRect(handle_rect)
        painter.restore()

    def _draw_eraser_overlay(self, painter: QtGui.QPainter):
        if self.current_tool != ToolMode.ERASER or not self.eraser_hover_item:
            return

        rectf = self._get_item_bounding_rect(self.eraser_hover_item)
        if rectf is None:
            return

        painter.save()
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 130, 0, 180), 1, QtCore.Qt.PenStyle.DashLine))
        painter.drawRect(rectf)
        painter.restore()

    def _create_eraser_cursor(self) -> QtGui.QCursor:
        size = 32
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)

        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        body = QtGui.QPolygonF([
            QtCore.QPointF(7, 18),
            QtCore.QPointF(15, 10),
            QtCore.QPointF(27, 22),
            QtCore.QPointF(19, 30),
        ])
        painter.setPen(QtGui.QPen(QtGui.QColor(140, 140, 140), 1))
        painter.setBrush(QtGui.QBrush(QtGui.QColor(248, 248, 248)))
        painter.drawPolygon(body)

        rubber = QtGui.QPolygonF([
            QtCore.QPointF(7, 18),
            QtCore.QPointF(11, 14),
            QtCore.QPointF(23, 26),
            QtCore.QPointF(19, 30),
        ])
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 163, 102), 1))
        painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 163, 102)))
        painter.drawPolygon(rubber)

        painter.setPen(QtGui.QPen(QtGui.QColor(200, 200, 200), 1))
        painter.drawLine(QtCore.QPointF(11, 14), QtCore.QPointF(19, 22))

        painter.end()

        return QtGui.QCursor(pixmap, 26, 26)

    def _distance_to_polyline(self, points, pos: QtCore.QPointF) -> float | None:
        if len(points) < 2:
            return None
        px, py = pos.x(), pos.y()
        best = None
        for start, end in zip(points[:-1], points[1:]):
            sx, sy = start.x(), start.y()
            ex, ey = end.x(), end.y()
            dist = self._distance_to_segment(sx, sy, ex, ey, px, py)
            if best is None or dist < best:
                best = dist
        return best

    @staticmethod
    def _distance_to_segment(x1, y1, x2, y2, px, py) -> float:
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    @staticmethod
    def _distance_to_rect(rect: QtCore.QRect, point: QtCore.QPointF) -> float | None:
        rectf = QtCore.QRectF(rect)
        return DrawingLabel._distance_to_rectf(rectf, point)

    @staticmethod
    def _distance_to_rectf(rect: QtCore.QRectF, point: QtCore.QPointF) -> float | None:
        if rect.contains(point):
            return 0.0
        x = point.x()
        y = point.y()
        left = rect.left()
        right = rect.right()
        top = rect.top()
        bottom = rect.bottom()
        dx = max(left - x, 0, x - right)
        dy = max(top - y, 0, y - bottom)
        return math.hypot(dx, dy)

    def _text_rect_from_item(self, index: int) -> QtCore.QRectF | None:
        if index < 0 or index >= len(self.text_items):
            return None
        position, text = self.text_items[index]
        doc = QtGui.QTextDocument()
        doc.setDefaultFont(self.text_font)
        doc.setPlainText(text)
        doc.setTextWidth(doc.idealWidth())
        size = doc.size()
        width = max(10.0, size.width())
        layout = doc.documentLayout()
        layout_height = layout.documentSize().height() if layout is not None else 0.0
        height = max(layout_height, size.height())
        if height == 0:
            height = QtGui.QFontMetrics(self.text_font).lineSpacing()
        rectf = QtCore.QRectF(QtCore.QPointF(position), QtCore.QSizeF(width + 6, height + 6))
        return rectf

    def _get_item_bounding_rect(self, item: tuple[str, int]) -> QtCore.QRectF | None:
        item_type, index = item
        if item_type == 'rectangle':
            return QtCore.QRectF(self.rectangles[index]) if index < len(self.rectangles) else None
        if item_type == 'line':
            if index >= len(self.drawing_objects):
                return None
            points = self.drawing_objects[index].points
            if not points:
                return None
            xs = [pt.x() for pt in points]
            ys = [pt.y() for pt in points]
            rectf = QtCore.QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
            rectf = rectf.normalized().adjusted(-4, -4, 4, 4)
            return rectf
        if item_type == 'text':
            return self._text_rect_from_item(index)
        return None

    def _update_eraser_hover(self, pos: QtCore.QPoint):
        if self.current_tool != ToolMode.ERASER:
            if self.eraser_hover_item is not None:
                self.eraser_hover_item = None
                self.update()
            return

        hit = self._hit_test_items(pos)
        if hit != self.eraser_hover_item:
            self.eraser_hover_item = hit
            self.update()

    def _update_cursor_for_selection(self):
        if self.rect_resize_handle:
            handle = self.rect_resize_handle
        elif self.hover_handle:
            handle = self.hover_handle[2]
        else:
            handle = None

        if handle:
            if handle in ('top_left', 'bottom_right'):
                cursor = QtCore.Qt.CursorShape.SizeFDiagCursor
            elif handle in ('top_right', 'bottom_left'):
                cursor = QtCore.Qt.CursorShape.SizeBDiagCursor
            else:
                cursor = QtCore.Qt.CursorShape.SizeAllCursor
            self.setCursor(QtGui.QCursor(cursor))
        elif self.hover_item or (self.selected_item and self.selection_dragging):
            self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.SizeAllCursor))
        else:
            self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.ArrowCursor))

    def update_cursor_for_tool(self):
        if self.current_tool == ToolMode.SELECTION:
            self._update_cursor_for_selection()
        elif self.current_tool == ToolMode.FREEHAND:
            self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.CrossCursor))
        elif self.current_tool == ToolMode.RECTANGLE:
            self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.CrossCursor))
        elif self.current_tool == ToolMode.ERASER:
            if self.eraser_cursor is None:
                self.eraser_cursor = self._create_eraser_cursor()
            self.setCursor(self.eraser_cursor)
        elif self.current_tool == ToolMode.TEXT:
            self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.IBeamCursor))
        else:
            self.unsetCursor()

    def select_item(self, item_type: str, index: int):
        valid = False
        if item_type == 'line' and 0 <= index < len(self.drawing_objects):
            valid = True
        elif item_type == 'rectangle' and 0 <= index < len(self.rectangles):
            valid = True
        elif item_type == 'text' and 0 <= index < len(self.text_items):
            valid = True

        previous_item = self.selected_item
        if valid:
            self.selected_item = (item_type, index)
            self.hover_item = self.selected_item
        else:
            self.selected_item = None
            self.hover_item = None

        self.selection_dragging = False
        self.rect_resize_handle = None
        self.rect_resize_initial_rect = None
        self.selection_initial_points = None
        self.selection_initial_position = None
        self.selection_modified = False
        self.eraser_hover_item = None

        if self.current_tool == ToolMode.SELECTION:
            self._update_cursor_for_selection()
        self._emit_selection_changed(previous_item)
        self.update()

    def clear_selection(self):
        previous_item = self.selected_item
        self._clear_selection_state()
        self.update_cursor_for_tool()
        self.update()
        self._emit_selection_changed(previous_item)

    def _clear_selection_state(self):
        self.hover_item = None
        self.selected_item = None
        self.hover_handle = None
        self.rect_resize_handle = None
        self.rect_resize_initial_rect = None
        self.selection_dragging = False
        self.selection_initial_points = None
        self.selection_initial_position = None
        self.selection_modified = False
        self.eraser_hover_item = None

    def _emit_selection_changed(self, previous_item: tuple[str, int] | None):
        if previous_item != self.selected_item:
            self.selection_changed.emit()


class FloatingActionButton(QtWidgets.QToolButton):
    def __init__(self, icon, tooltip_text, parent=None):
        super().__init__(parent, icon=icon, toolTip=tooltip_text)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setIconSize(QtCore.QSize(40, 40))
        self.setStyleSheet('''
            QToolButton {
                border-radius: 20px;
                background-color: #888;
                color: white;
            }
            QToolButton:hover {
                background-color: #aaa;
            }
            QToolButton:pressed {
                background-color: #666;
            }
        ''')
        self.setFixedSize(50, 50)
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))


class ScreenshotWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__(
            windowTitle="Screenshot and Annotation Tool",
            flags=QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint,
            styleSheet="background-color: #444; border-radius: 30;",
            windowOpacity=0.8,
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        # Initialize dragging variables
        self.drag_start_position = None

        # Create an opacity animation for visual effects
        self._opacity_animation = QtCore.QPropertyAnimation(self, b'windowOpacity')
        self._opacity_animation.setDuration(200)

        self.tabler_qicon = TablerQIcon(color=QtGui.QColor(255, 255, 255))

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Create Widgets
        # --------------
        # Add grip_vertical button for drag area
        self.grip_vertical_btn = FloatingActionButton(TablerQIcon(color=QtGui.QColor(255, 255, 255), opacity=0.6).grip_vertical, "Drag Area")
        self.grip_vertical_btn.setStyleSheet('''
            QToolButton {
                background-color: transparent;
            }
        ''')
        
        self.grip_vertical_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.OpenHandCursor))

        # Add screen_share button for screenshot whole screen
        self.screen_share_btn = FloatingActionButton(self.tabler_qicon.screen_share, "Screenshot Whole Screen")
        # Add screenshot button for grab from screen shot
        self.screenshot_btn = FloatingActionButton(self.tabler_qicon.screenshot, "Grab Screenshot")
        # Add close button to close the window
        self.close_btn = FloatingActionButton(self.tabler_qicon.x, "Close")
        self.close_btn.setStyleSheet('''
            QToolButton {
                border-radius: 20px;
                background-color: #888;
            }
            QToolButton:hover {
                background-color: #F66;
            }
            QToolButton:pressed {
                background-color: #C44;
            }
        ''')

        # Add Widgets to Layouts
        # ----------------------
        self.widget = QtWidgets.QWidget(self, windowOpacity=0.8)

        self.tmp_layout = QtWidgets.QHBoxLayout(self)
        self.tmp_layout.addWidget(self.widget)

        # Layout to arrange the floating buttons horizontally
        self.fab_layout = QtWidgets.QHBoxLayout(
            self.widget,
            spacing=10,
        )
        self.fab_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignBottom)

        self.fab_layout.addWidget(self.grip_vertical_btn)
        self.fab_layout.addWidget(self.screen_share_btn)
        self.fab_layout.addWidget(self.screenshot_btn)
        self.fab_layout.addWidget(self.close_btn)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        self.close_btn.clicked.connect(self.close)

        # Install event filter
        self.grip_vertical_btn.installEventFilter(self)

        # Connect buttons to annotation mode
        self.screen_share_btn.clicked.connect(self.take_screenshot)
        self.screenshot_btn.clicked.connect(self.grab_screen_area)

    # Public Methods
    # --------------
    def start_drag(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.drag_start_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def perform_drag(self, event: QtGui.QMouseEvent):
        if event.buttons() == QtCore.Qt.MouseButton.LeftButton:
            new_pos = event.globalPos() - self.drag_start_position
            screen_geometry = QtGui.QGuiApplication.primaryScreen().availableGeometry()
            x = max(screen_geometry.left(), min(new_pos.x(), screen_geometry.right() - self.width()))
            y = max(screen_geometry.top(), min(new_pos.y(), screen_geometry.bottom() - self.height()))
            self.move(x, y)
            event.accept()

    def take_screenshot(self):
        screen = QtGui.QGuiApplication.primaryScreen()
        # Hide before capture
        self.hide()
        screenshot = screen.grabWindow(0)
        self.switch_to_annotation_mode(screenshot)

    def grab_screen_area(self):
        self.capture_window = ScreenCaptureArea()
        self.capture_window.closed.connect(self.on_capture_window_closed)
        self.capture_window.show()

    def on_capture_window_closed(self):
        QtCore.QTimer.singleShot(200, self.capture_selected_area)

    def capture_selected_area(self):
        selected_rect = self.capture_window.get_selected_rect()
        if selected_rect.isNull():
            return

        # Hide the widget before capturing
        self.hide()
        self._capture_area(selected_rect)

    def switch_to_annotation_mode(self, screenshot: QtGui.QPixmap):
        self.annotate_window = AnnotateWindow()
        self.annotate_window.drawing_label.set_pixmap(screenshot)
        self.annotate_window.update_object_list()
        self.close()
        self.annotate_window.show()

    # Private Methods
    # ---------------
    def _capture_area(self, selected_rect: QtCore.QRect):
        screen = QtGui.QGuiApplication.primaryScreen()
        screenshot = screen.grabWindow(
            0, selected_rect.x(), selected_rect.y(), selected_rect.width(), selected_rect.height()
        )
        self.switch_to_annotation_mode(screenshot)

    # Overridden Methods
    # ------------------
    def enterEvent(self, event: QtCore.QEvent):
        self._opacity_animation.setStartValue(self.windowOpacity())
        self._opacity_animation.setEndValue(1.0)
        self._opacity_animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent):
        self._opacity_animation.setStartValue(self.windowOpacity())
        self._opacity_animation.setEndValue(0.8)
        self._opacity_animation.start()
        super().leaveEvent(event)

    def eventFilter(self, obj, event):
        if obj == self.grip_vertical_btn:
            if event.type() == QtCore.QEvent.Type.MouseButtonPress and event.button() == QtCore.Qt.MouseButton.LeftButton:
                self.start_drag(event)
                return True
            elif event.type() == QtCore.QEvent.Type.MouseMove and event.buttons() == QtCore.Qt.MouseButton.LeftButton:
                self.perform_drag(event)
                return True
        return super().eventFilter(obj, event)


class AnnotateWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Screenshot Annotator with Tabler Icons')
        self.current_tool_action = None
        self.__init_ui()
        self.select_tool(ToolMode.FREEHAND)

    def __init_ui(self):
        # Toolbar setup
        toolbar = QtWidgets.QToolBar("Annotation Tools", self)
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, toolbar)

        # Add Selection Tool with TablerQIcon
        self.selection_action = QtWidgets.QAction(TablerQIcon.pointer, 'Selection Tool', self)
        self.selection_action.setCheckable(True)
        self.selection_action.triggered.connect(lambda: self.select_tool(ToolMode.SELECTION))

        # Add Freehand Tool with TablerQIcon
        self.freehand_action = QtWidgets.QAction(TablerQIcon.pencil, 'Freehand Tool', self)
        self.freehand_action.setCheckable(True)
        self.freehand_action.triggered.connect(lambda: self.select_tool(ToolMode.FREEHAND))

        # Add Rectangle Tool with TablerQIcon
        self.rectangle_action = QtWidgets.QAction(TablerQIcon.square, 'Rectangle Tool', self)
        self.rectangle_action.setCheckable(True)
        self.rectangle_action.triggered.connect(lambda: self.select_tool(ToolMode.RECTANGLE))

        # Add Eraser Tool with TablerQIcon
        self.eraser_action = QtWidgets.QAction(TablerQIcon.eraser, 'Eraser Tool', self)
        self.eraser_action.setCheckable(True)
        self.eraser_action.triggered.connect(lambda: self.select_tool(ToolMode.ERASER))

        # Add Text Tool with TablerQIcon
        self.text_action = QtWidgets.QAction(TablerQIcon.text_size, 'Text Tool', self)
        self.text_action.setCheckable(True)
        self.text_action.triggered.connect(lambda: self.select_tool(ToolMode.TEXT))

        toolbar.addActions([self.selection_action, self.freehand_action, self.rectangle_action, self.eraser_action, self.text_action])

        self.tool_actions = {
            ToolMode.SELECTION: self.selection_action,
            ToolMode.FREEHAND: self.freehand_action,
            ToolMode.RECTANGLE: self.rectangle_action,
            ToolMode.ERASER: self.eraser_action,
            ToolMode.TEXT: self.text_action,
        }

        # Color Picker Button
        color_action = QtWidgets.QAction(TablerQIcon.color_swatch, 'Select Color', self)
        color_action.triggered.connect(self.select_color)
        toolbar.addAction(color_action)

        # Save Button
        save_action = QtWidgets.QAction(TablerQIcon.device_floppy, 'Save Image', self)
        save_action.triggered.connect(self.save_image)
        toolbar.addAction(save_action)

        # Drawing Area
        self.drawing_label = DrawingLabel(self)
        self.setCentralWidget(self.drawing_label)

        # Connect the signal from DrawingLabel to update the object list
        self.drawing_label.drawing_changed.connect(self.update_object_list)
        self.drawing_label.selection_changed.connect(self.update_object_list)

        # Object List Widget
        self.object_list_widget = QtWidgets.QTreeWidget()
        self.object_list_widget.setHeaderLabels(["Object Type", "Details"])
        dock = QtWidgets.QDockWidget("Drawing Objects", self)
        dock.setWidget(self.object_list_widget)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.object_list_widget.itemClicked.connect(self.on_object_list_item_clicked)

    def update_object_list(self):
        self.object_list_widget.clear()
        selected_tree_item = None
        selected_descriptor = self.drawing_label.selected_item
        for i, obj in enumerate(self.drawing_label.drawing_objects):
            item = QtWidgets.QTreeWidgetItem(self.object_list_widget)
            item.setText(0, f"Smoothed Line {i+1}")
            item.setText(1, f"Points: {len(obj.points)}, Color: {obj.color.name()}, Width: {obj.width}")
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, ('line', i))
            if selected_descriptor == ('line', i):
                selected_tree_item = item
        for i, rect in enumerate(self.drawing_label.rectangles):
            item = QtWidgets.QTreeWidgetItem(self.object_list_widget)
            item.setText(0, f"Rectangle {i+1}")
            item.setText(1, f"Top-left: ({rect.topLeft().x()}, {rect.topLeft().y()}), Size: ({rect.width()}x{rect.height()})")
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, ('rectangle', i))
            if selected_descriptor == ('rectangle', i):
                selected_tree_item = item
        for i, (point, text) in enumerate(self.drawing_label.text_items):
            item = QtWidgets.QTreeWidgetItem(self.object_list_widget)
            item.setText(0, f"Text {i+1}")
            item.setText(1, f"Position: ({point.x()}, {point.y()}), Text: {text}")
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, ('text', i))
            if selected_descriptor == ('text', i):
                selected_tree_item = item

        if selected_tree_item is not None:
            self.object_list_widget.blockSignals(True)
            self.object_list_widget.setCurrentItem(selected_tree_item)
            self.object_list_widget.blockSignals(False)

    def on_object_list_item_clicked(self, item: QtWidgets.QTreeWidgetItem, column: int):
        data = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if not data:
            return
        item_type, index = data
        if self.current_tool != ToolMode.SELECTION:
            self.select_tool(ToolMode.SELECTION)
        self.drawing_label.select_item(item_type, index)

    def select_tool(self, tool: ToolMode):
        # Select the current tool action
        sender_action = self.sender()
        if sender_action in self.tool_actions.values():
            self.current_tool_action = sender_action
        else:
            self.current_tool_action = self.tool_actions.get(tool)
            if self.current_tool_action:
                self.current_tool_action.setChecked(True)

        for action in self.tool_actions.values():
            if action and action != self.current_tool_action:
                action.setChecked(False)

        # Set the tool for the drawing label
        self.current_tool = tool
        self.drawing_label.current_tool = tool
        if tool != ToolMode.SELECTION:
            self.drawing_label.clear_selection()
        self.drawing_label.update_cursor_for_tool()

    def select_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            self.drawing_label.pen_color = color

    def save_image(self):
        if not self.drawing_label.image.isNull():
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Image", "", "PNG(*.png);;JPEG(*.jpg *.jpeg)")
            if file_path:
                self.drawing_label.image.save(file_path)


if __name__ == '__main__':
    from blackboard.theme import set_theme
    app = QtWidgets.QApplication(sys.argv)
    set_theme(app, 'dark')
    main_window = ScreenshotWidget()
    main_window.show()
    sys.exit(app.exec_())
