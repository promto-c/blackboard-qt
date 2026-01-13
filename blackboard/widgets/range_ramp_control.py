# Third Party Imports
# -------------------
import cv2
import numpy as np

from qtpy import QtCore, QtGui, QtWidgets


# Utility Functions
# -----------------
def clamp01(v):
    """Clamp a float value to [0, 1]."""
    return max(0.0, min(1.0, float(v)))


def wrap01(v):
    """Wrap a float value into [0, 1)."""
    v = float(v) % 1.0
    if v < 0.0:
        v += 1.0
    return v


def smoothstep(edge0, edge1, x):
    """Return smoothstep interpolation in [0, 1]."""
    if edge0 == edge1:
        return np.zeros_like(x, dtype=np.float32)
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def soft_band_mask_linear(values, low, high, soft_low, soft_high):
    """Compute a soft range mask for linear domain values in [0, 1].

    Inside [low, high] => 1
    Outside with softness => smooth falloff
    """
    low = float(low)
    high = float(high)
    soft_low = float(soft_low)
    soft_high = float(soft_high)

    if low > high:
        low, high = high, low

    m = np.ones_like(values, dtype=np.float32)

    # Left falloff: [low - soft_low, low]
    if soft_low > 0.0:
        left0 = low - soft_low
        left1 = low
        left = smoothstep(left0, left1, values)
    else:
        left = (values >= low).astype(np.float32)

    # Right falloff: [high, high + soft_high]
    if soft_high > 0.0:
        right0 = high
        right1 = high + soft_high
        right = 1.0 - smoothstep(right0, right1, values)
    else:
        right = (values <= high).astype(np.float32)

    m = np.minimum(left, right)
    return np.clip(m, 0.0, 1.0)


def circ_band_mask(h, low, high, soft_low, soft_high):
    """Compute a soft range mask for hue in circular domain [0, 1)."""
    low = wrap01(low)
    high = wrap01(high)
    soft_low = float(soft_low)
    soft_high = float(soft_high)

    # If not wrapping, treat like linear.
    if low <= high:
        return soft_band_mask_linear(h, low, high, soft_low, soft_high)

    # Wrapping range: [low..1] U [0..high]
    # Create mask from two segments and combine as max.
    m1 = soft_band_mask_linear(h, low, 1.0, soft_low, 0.0)
    m2 = soft_band_mask_linear(h, 0.0, high, 0.0, soft_high)
    return np.maximum(m1, m2)


def bgr_to_qimage(bgr):
    """Convert BGR uint8 image to QImage (RGB)."""
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    bytes_per_line = 3 * w
    return QtGui.QImage(
        rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888
    ).copy()


def gray_to_qimage(gray_u8):
    """Convert grayscale uint8 image to QImage."""
    h, w = gray_u8.shape
    bytes_per_line = w
    return QtGui.QImage(
        gray_u8.data, w, h, bytes_per_line, QtGui.QImage.Format_Grayscale8
    ).copy()


def overlay_mask_on_bgr(bgr, mask_u8, alpha=0.55):
    """Overlay mask on BGR image (green tint) for preview."""
    alpha = float(alpha)
    mask_f = (mask_u8.astype(np.float32) / 255.0)[:, :, None]
    tint = np.zeros_like(bgr, dtype=np.float32)
    tint[:, :, 1] = 255.0  # green channel
    out = bgr.astype(np.float32) * (1.0 - alpha * mask_f) + tint * (alpha * mask_f)
    return np.clip(out, 0, 255).astype(np.uint8)


# Widgets
# -------
class RangeRampControl(QtWidgets.QWidget):
    """Draw a ramp bar with draggable low/high and softness handles.

    Signals:
        rangeChanged(float, float, float, float): Emit low, high, soft_low, soft_high in 0..1.
    """
    rangeChanged = QtCore.Signal(float, float, float, float)

    _HANDLE_NONE = 0
    _HANDLE_MOVE = 5
    _HANDLE_LOW = 1
    _HANDLE_HIGH = 2
    _HANDLE_SOFT_LOW = 3
    _HANDLE_SOFT_HIGH = 4

    def __init__(
            self,
            parent: QtWidgets.QWidget = None,
            ramp_kind: str = 'hue',
            wrap_enabled: bool = False,
            show_softness: bool = True,
            ):
        """Initialize the widget.

        Args:
            parent: Parent widget.
            ramp_kind: One of {'hue', 'sat', 'luma', 'custom'}.
            wrap_enabled: Enable circular range behavior (recommended for Hue).
            show_softness: Draw and allow softness handles.
        """
        super().__init__(parent)

        self._ramp_kind = ramp_kind
        self._wrap_enabled = wrap_enabled
        self._show_softness = show_softness

        self._low = 0.30
        self._high = 0.55
        self._soft_low = 0.05
        self._soft_high = 0.05

        self._bar_height = 16
        self._handle_width = 10
        self._soft_handle_width = 8
        self._padding = 10

        self._active_handle = self._HANDLE_NONE
        self._drag_offset_px = 0
        self._hover_handle = self._HANDLE_NONE

        self._drag_start_t = 0.0
        self._drag_start_low = 0.0
        self._drag_start_high = 0.0
        self._drag_start_soft_low = 0.0
        self._drag_start_soft_high = 0.0
        self._drag_start_center = 0.0

        self.setMouseTracking(True)
        self.setMinimumHeight(36)

    def set_range(self, low, high, soft_low, soft_high):
        """Set the selection range and softness."""
        self._low = clamp01(low)
        self._high = clamp01(high)
        self._soft_low = clamp01(soft_low)
        self._soft_high = clamp01(soft_high)
        self.update()

    def get_range(self):
        """Return low, high, soft_low, soft_high."""
        return self._low, self._high, self._soft_low, self._soft_high

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        rect = self.rect()
        bar_rect = self._bar_rect(rect)

        painter.fillRect(rect, QtGui.QColor(24, 24, 28))

        ramp_brush = self._create_ramp_brush(bar_rect)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(ramp_brush)
        painter.drawRoundedRect(bar_rect, 6, 6)

        rim_pen = QtGui.QPen(QtGui.QColor(80, 80, 90))
        rim_pen.setWidth(1)
        painter.setPen(rim_pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(bar_rect, 6, 6)

        self._draw_selection(painter, bar_rect)
        self._draw_handles(painter, bar_rect)

    def _bar_rect(self, outer_rect):
        x = outer_rect.x() + self._padding
        y = outer_rect.center().y() - self._bar_height / 2
        w = outer_rect.width() - (self._padding * 2)
        h = self._bar_height
        return QtCore.QRectF(x, y, w, h)

    def _create_ramp_brush(self, bar_rect):
        grad = QtGui.QLinearGradient(bar_rect.left(), 0, bar_rect.right(), 0)

        if self._ramp_kind == 'hue':
            steps = 12
            for i in range(steps + 1):
                t = i / float(steps)
                c = QtGui.QColor.fromHsvF(t, 1.0, 1.0)
                grad.setColorAt(t, c)
        elif self._ramp_kind == 'sat':
            grad.setColorAt(0.0, QtGui.QColor(120, 120, 120))
            grad.setColorAt(1.0, QtGui.QColor(160, 220, 110))
        elif self._ramp_kind == 'luma':
            grad.setColorAt(0.0, QtGui.QColor(0, 0, 0))
            grad.setColorAt(1.0, QtGui.QColor(255, 255, 255))
        else:
            grad.setColorAt(0.0, QtGui.QColor(90, 90, 95))
            grad.setColorAt(1.0, QtGui.QColor(140, 140, 150))

        return QtGui.QBrush(grad)

    def _is_pos_inside_selection(self, pos, bar_rect):
        """Return True if mouse pos is inside the selected region (for move-drag)."""
        if not bar_rect.contains(pos):
            return False

        t = self._x_to_norm(bar_rect, pos.x())
        segments = self._selection_segments()
        for seg_low, seg_high in segments:
            if seg_low <= t <= seg_high:
                return True
        return False

    def _selection_segments(self):
        if not self._wrap_enabled:
            low, high = self._low, self._high
            if low > high:
                low, high = high, low
            return [(low, high)]

        low = wrap01(self._low)
        high = wrap01(self._high)
        if low <= high:
            return [(low, high)]
        return [(low, 1.0), (0.0, high)]

    def _draw_selection(self, painter, bar_rect):
        sel_color = QtGui.QColor(255, 255, 255, 30)
        soft_color = QtGui.QColor(255, 255, 255, 18)

        for seg_low, seg_high in self._selection_segments():
            x0 = self._norm_to_x(bar_rect, seg_low)
            x1 = self._norm_to_x(bar_rect, seg_high)

            sel_rect = QtCore.QRectF(x0, bar_rect.y(), x1 - x0, bar_rect.height())
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(sel_color)
            painter.drawRoundedRect(sel_rect, 6, 6)

            if self._show_softness:
                soft_low = clamp01(seg_low - self._soft_low)
                soft_high = clamp01(seg_high + self._soft_high)

                xsl0 = self._norm_to_x(bar_rect, soft_low)
                xsl1 = self._norm_to_x(bar_rect, seg_low)
                if xsl1 > xsl0:
                    r = QtCore.QRectF(xsl0, bar_rect.y(), xsl1 - xsl0, bar_rect.height())
                    painter.setBrush(soft_color)
                    painter.drawRoundedRect(r, 6, 6)

                xsr0 = self._norm_to_x(bar_rect, seg_high)
                xsr1 = self._norm_to_x(bar_rect, soft_high)
                if xsr1 > xsr0:
                    r = QtCore.QRectF(xsr0, bar_rect.y(), xsr1 - xsr0, bar_rect.height())
                    painter.setBrush(soft_color)
                    painter.drawRoundedRect(r, 6, 6)

    def _draw_handles(self, painter, bar_rect):
        low_x = self._norm_to_x(bar_rect, self._low)
        high_x = self._norm_to_x(bar_rect, self._high)

        self._draw_handle(painter, bar_rect, low_x, self._HANDLE_LOW)
        self._draw_handle(painter, bar_rect, high_x, self._HANDLE_HIGH)

        if not self._show_softness:
            return

        soft_low_pos = self._low - self._soft_low
        soft_high_pos = self._high + self._soft_high
        if self._wrap_enabled:
            soft_low_pos = wrap01(soft_low_pos)
            soft_high_pos = wrap01(soft_high_pos)
        else:
            soft_low_pos = clamp01(soft_low_pos)
            soft_high_pos = clamp01(soft_high_pos)

        self._draw_soft_handle(painter, bar_rect, self._norm_to_x(bar_rect, soft_low_pos), self._HANDLE_SOFT_LOW)
        self._draw_soft_handle(painter, bar_rect, self._norm_to_x(bar_rect, soft_high_pos), self._HANDLE_SOFT_HIGH)

    def _draw_handle(self, painter, bar_rect, x, handle_id):
        w = self._handle_width
        h = bar_rect.height() + 10
        y = bar_rect.center().y() - h / 2.0
        r = QtCore.QRectF(x - w / 2.0, y, w, h)

        is_active = (self._active_handle == handle_id)
        is_hover = (self._hover_handle == handle_id)

        base = QtGui.QColor(220, 220, 230) if (is_active or is_hover) else QtGui.QColor(170, 170, 185)
        edge = QtGui.QColor(20, 20, 22)

        painter.setPen(QtGui.QPen(edge, 1))
        painter.setBrush(base)
        painter.drawRoundedRect(r, 3, 3)

        painter.setPen(QtGui.QPen(QtGui.QColor(30, 30, 36), 2))
        painter.drawLine(
            QtCore.QPointF(r.center().x(), r.top() + 6),
            QtCore.QPointF(r.center().x(), r.bottom() - 6),
        )

    def _draw_soft_handle(self, painter, bar_rect, x, handle_id):
        w = self._soft_handle_width
        h = bar_rect.height() + 6
        y = bar_rect.center().y() - h / 2.0
        r = QtCore.QRectF(x - w / 2.0, y, w, h)

        is_active = (self._active_handle == handle_id)
        is_hover = (self._hover_handle == handle_id)

        base = QtGui.QColor(255, 255, 255, 170) if (is_active or is_hover) else QtGui.QColor(255, 255, 255, 110)
        edge = QtGui.QColor(20, 20, 22)

        painter.setPen(QtGui.QPen(edge, 1))
        painter.setBrush(base)
        painter.drawRoundedRect(r, 3, 3)

    def _compute_center(self, low, high):
        """Compute center; in wrap mode this is approximate but stable for drag start."""
        if not self._wrap_enabled:
            return (low + high) * 0.5
        d = (high - low) % 1.0
        return wrap01(low + d * 0.5)

    def _drag_move_range(self, current_t):
        """Move low/high together based on drag delta."""
        if self._wrap_enabled:
            # Circular delta in [-0.5, 0.5]
            d = current_t - self._drag_start_t
            if d > 0.5:
                d -= 1.0
            elif d < -0.5:
                d += 1.0

            self._low = wrap01(self._drag_start_low + d)
            self._high = wrap01(self._drag_start_high + d)
            return

        # Linear mode: clamp movement at edges
        d = current_t - self._drag_start_t
        low = self._drag_start_low + d
        high = self._drag_start_high + d

        width = (self._drag_start_high - self._drag_start_low)
        if width < 0.0:
            width = -width

        # clamp by pushing back when out of bounds
        if low < 0.0:
            low = 0.0
            high = low + width
        if high > 1.0:
            high = 1.0
            low = high - width

        self._low = clamp01(low)
        self._high = clamp01(high)

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return

        bar_rect = self._bar_rect(self.rect())
        hit = self._hit_test_handles(event.pos(), bar_rect)
        self._active_handle = hit

        if self._active_handle != self._HANDLE_NONE:
            self._drag_start_low = self._low
            self._drag_start_high = self._high
            self._drag_start_soft_low = self._soft_low
            self._drag_start_soft_high = self._soft_high
            self._drag_start_center = self._compute_center(self._low, self._high)

            handle_x = self._handle_x_for_handle_id(bar_rect, self._active_handle)
            self._drag_offset_px = event.pos().x() - handle_x
            self._emit()
            self.update()
            return

        # If clicking inside selection, start move-drag
        if self._is_pos_inside_selection(event.pos(), bar_rect):
            self._active_handle = self._HANDLE_MOVE
            self._drag_start_t = self._x_to_norm(bar_rect, event.pos().x())
            self._drag_start_low = self._low
            self._drag_start_high = self._high
            self._emit()
            self.update()
            return

        # Click-to-move: move nearest edge
        t = self._x_to_norm(bar_rect, event.pos().x())
        self._move_nearest_edge(t)
        self._emit()
        self.update()

    def mouseMoveEvent(self, event):
        bar_rect = self._bar_rect(self.rect())

        if self._active_handle == self._HANDLE_NONE:
            self._hover_handle = self._hit_test_handles(event.pos(), bar_rect)
            self._update_cursor()
            self.update()
            return

        if self._active_handle == self._HANDLE_MOVE:
            t = self._x_to_norm(bar_rect, event.pos().x())
            self._drag_move_range(t)
            self._emit()
            self.update()
            return

        x = event.pos().x() - self._drag_offset_px
        t = self._x_to_norm(bar_rect, x)
        mods = event.modifiers()
        ctrl = bool(mods & QtCore.Qt.ControlModifier)
        self._drag_handle(self._active_handle, t, ctrl=ctrl)
        self._emit()
        self.update()

    def mouseReleaseEvent(self, event):
        if self._active_handle != self._HANDLE_NONE:
            self._active_handle = self._HANDLE_NONE
            self._drag_offset_px = 0
            self._emit()
            self.update()

    def leaveEvent(self, event):
        self._hover_handle = self._HANDLE_NONE
        self._update_cursor()
        self.update()

    def _update_cursor(self):
        if self._hover_handle in (
                self._HANDLE_LOW,
                self._HANDLE_HIGH,
                self._HANDLE_SOFT_LOW,
                self._HANDLE_SOFT_HIGH,
                ):
            self.setCursor(QtCore.Qt.SizeHorCursor)
        else:
            self.setCursor(QtCore.Qt.ArrowCursor)

    def _hit_test_handles(self, pos, bar_rect):
        handles = [self._HANDLE_LOW, self._HANDLE_HIGH]
        if self._show_softness:
            handles = [self._HANDLE_SOFT_LOW, self._HANDLE_SOFT_HIGH] + handles

        for handle_id in handles:
            hx = self._handle_x_for_handle_id(bar_rect, handle_id)
            r = QtCore.QRectF(hx - 8, bar_rect.y() - 10, 16, bar_rect.height() + 20)
            if r.contains(pos):
                return handle_id
        return self._HANDLE_NONE

    def _handle_x_for_handle_id(self, bar_rect, handle_id):
        low, high, soft_low, soft_high = self.get_range()

        if handle_id == self._HANDLE_LOW:
            return self._norm_to_x(bar_rect, low)
        if handle_id == self._HANDLE_HIGH:
            return self._norm_to_x(bar_rect, high)
        if handle_id == self._HANDLE_SOFT_LOW:
            t = low - soft_low
            t = wrap01(t) if self._wrap_enabled else clamp01(t)
            return self._norm_to_x(bar_rect, t)
        if handle_id == self._HANDLE_SOFT_HIGH:
            t = high + soft_high
            t = wrap01(t) if self._wrap_enabled else clamp01(t)
            return self._norm_to_x(bar_rect, t)
        return int(bar_rect.left())

    def _drag_handle(self, handle_id, t, ctrl=False):
        if self._wrap_enabled:
            t = wrap01(t)
        else:
            t = clamp01(t)

        if handle_id in (self._HANDLE_SOFT_LOW, self._HANDLE_SOFT_HIGH) and ctrl:
            if handle_id == self._HANDLE_SOFT_LOW:
                d = (self._low - t) % 1.0 if self._wrap_enabled else max(0.0, self._low - t)
            else:
                d = (t - self._high) % 1.0 if self._wrap_enabled else max(0.0, t - self._high)
            d = clamp01(d)
            self._soft_low = d
            self._soft_high = d
            return

        if handle_id in (self._HANDLE_LOW, self._HANDLE_HIGH) and ctrl:
            self._drag_main_preserve_center(handle_id, t)
            return

        if handle_id == self._HANDLE_LOW:
            self._low = t
        elif handle_id == self._HANDLE_HIGH:
            self._high = t
        elif handle_id == self._HANDLE_SOFT_LOW:
            d = (self._low - t) % 1.0 if self._wrap_enabled else max(0.0, self._low - t)
            self._soft_low = clamp01(d)
        elif handle_id == self._HANDLE_SOFT_HIGH:
            d = (t - self._high) % 1.0 if self._wrap_enabled else max(0.0, t - self._high)
            self._soft_high = clamp01(d)

        if not self._wrap_enabled and self._low > self._high:
            self._low, self._high = self._high, self._low

    def _drag_main_preserve_center(self, handle_id, t):
        c = self._drag_start_center

        if not self._wrap_enabled:
            if handle_id == self._HANDLE_LOW:
                new_low = clamp01(t)
                new_high = 2.0 * c - new_low
                if new_high < 0.0:
                    new_high = 0.0
                    new_low = clamp01(2.0 * c - new_high)
                elif new_high > 1.0:
                    new_high = 1.0
                    new_low = clamp01(2.0 * c - new_high)
            else:
                new_high = clamp01(t)
                new_low = 2.0 * c - new_high
                if new_low < 0.0:
                    new_low = 0.0
                    new_high = clamp01(2.0 * c - new_low)
                elif new_low > 1.0:
                    new_low = 1.0
                    new_high = clamp01(2.0 * c - new_low)

            if new_low > new_high:
                new_low, new_high = new_high, new_low

            self._low = clamp01(new_low)
            self._high = clamp01(new_high)
            return

        self._drag_main_preserve_center_wrap(handle_id, t)

    def _drag_main_preserve_center_wrap(self, handle_id, t):
        c = self._drag_start_center

        def signed_from_center(p):
            d = (p - c) % 1.0
            if d > 0.5:
                d -= 1.0
            return d

        d = signed_from_center(t)
        if handle_id == self._HANDLE_LOW:
            new_low = wrap01(c + d)
            new_high = wrap01(c - d)
        else:
            new_high = wrap01(c + d)
            new_low = wrap01(c - d)

        self._low = new_low
        self._high = new_high

    def _move_nearest_edge(self, t):
        if self._wrap_enabled:
            t = wrap01(t)
            dl = min(abs(t - self._low), 1.0 - abs(t - self._low))
            dh = min(abs(t - self._high), 1.0 - abs(t - self._high))
            if dl <= dh:
                self._low = t
            else:
                self._high = t
        else:
            t = clamp01(t)
            if abs(t - self._low) <= abs(t - self._high):
                self._low = t
            else:
                self._high = t
            if self._low > self._high:
                self._low, self._high = self._high, self._low

    def _norm_to_x(self, bar_rect, t):
        t = clamp01(t)
        return int(bar_rect.left() + t * bar_rect.width())

    def _x_to_norm(self, bar_rect, x):
        if bar_rect.width() <= 1:
            return 0.0
        t = (x - bar_rect.left()) / float(bar_rect.width())
        return clamp01(t)

    def _emit(self):
        self.rangeChanged.emit(float(self._low), float(self._high), float(self._soft_low), float(self._soft_high))


class ImageView(QtWidgets.QLabel):
    """Image viewport that supports click-to-pick a pixel color.

    Signals:
        picked(int, int): Emit pixel coordinates in image space.
    """
    picked = QtCore.Signal(int, int)

    def __init__(self, parent: QtWidgets.QWidget = None):
        """Initialize the viewport label."""
        super().__init__(parent)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMinimumSize(320, 200)
        self.setStyleSheet("QLabel { background: #111114; border: 1px solid #2b2b33; }")

        self._image_bgr = None
        self._pixmap = None
        self._scale = 1.0
        self._offset = QtCore.QPoint(0, 0)

    def set_image_bgr(self, bgr):
        """Set the displayed image."""
        self._image_bgr = bgr
        self._update_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_pixmap()

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return
        if self._image_bgr is None or self._pixmap is None:
            return

        pos = event.pos()
        x = pos.x() - self._offset.x()
        y = pos.y() - self._offset.y()

        if self._scale <= 0.0:
            return

        ix = int(x / self._scale)
        iy = int(y / self._scale)

        h, w = self._image_bgr.shape[:2]
        if 0 <= ix < w and 0 <= iy < h:
            self.picked.emit(ix, iy)

    def _update_pixmap(self):
        if self._image_bgr is None:
            self.setPixmap(QtGui.QPixmap())
            self._pixmap = None
            return

        qimg = bgr_to_qimage(self._image_bgr)
        pm = QtGui.QPixmap.fromImage(qimg)

        # Fit to label
        target = self.size()
        if pm.isNull() or target.width() <= 1 or target.height() <= 1:
            self.setPixmap(pm)
            self._pixmap = pm
            return

        scaled = pm.scaled(target, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

        self._pixmap = scaled
        self.setPixmap(scaled)

        # Track scale + offset for picking
        sw = scaled.width()
        sh = scaled.height()
        ow = pm.width()
        oh = pm.height()

        self._scale = min(sw / float(ow), sh / float(oh))
        self._offset = QtCore.QPoint(
            int((target.width() - sw) / 2),
            int((target.height() - sh) / 2),
        )


# Main Window
# -----------
class QualifierTestWindow(QtWidgets.QMainWindow):
    """Test app: load image, pick color, adjust H/S/V qualifiers, preview matte."""
    def __init__(self, parent: QtWidgets.QWidget = None):
        """Initialize the window."""
        super().__init__(parent)

        self.setWindowTitle('Qualifier Test (PyQt)')
        self._image_bgr = None
        self._picked_hsv = None

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        root = QtWidgets.QHBoxLayout(central)

        # Left: controls
        ctrl = QtWidgets.QVBoxLayout()
        root.addLayout(ctrl, 0)

        btn_row = QtWidgets.QHBoxLayout()
        ctrl.addLayout(btn_row)

        self._load_btn = QtWidgets.QPushButton('Load Image...')
        btn_row.addWidget(self._load_btn)

        self._mode_combo = QtWidgets.QComboBox()
        self._mode_combo.addItems(['Overlay', 'Mask Only', 'Original'])
        btn_row.addWidget(self._mode_combo)

        self._info = QtWidgets.QLabel('Pick: -')
        self._info.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        ctrl.addWidget(self._info)

        ctrl.addWidget(QtWidgets.QLabel('Hue (wrap)'))
        self._hue = RangeRampControl(ramp_kind='hue', wrap_enabled=True, show_softness=True)
        ctrl.addWidget(self._hue)

        ctrl.addWidget(QtWidgets.QLabel('Saturation'))
        self._sat = RangeRampControl(ramp_kind='sat', wrap_enabled=False, show_softness=True)
        ctrl.addWidget(self._sat)

        ctrl.addWidget(QtWidgets.QLabel('Value (as Luma proxy)'))
        self._val = RangeRampControl(ramp_kind='luma', wrap_enabled=False, show_softness=True)
        ctrl.addWidget(self._val)

        self._auto_btn = QtWidgets.QPushButton('Auto-range from pick')
        ctrl.addWidget(self._auto_btn)

        ctrl.addStretch(1)

        # Right: viewports
        views = QtWidgets.QVBoxLayout()
        root.addLayout(views, 1)

        self._view = ImageView()
        views.addWidget(self._view, 1)

        self._mask_view = QtWidgets.QLabel()
        self._mask_view.setAlignment(QtCore.Qt.AlignCenter)
        self._mask_view.setMinimumHeight(180)
        self._mask_view.setStyleSheet("QLabel { background: #0c0c0f; border: 1px solid #2b2b33; }")
        views.addWidget(self._mask_view, 0)

        # Signals
        self._load_btn.clicked.connect(self._on_load_clicked)
        self._view.picked.connect(self._on_picked)
        self._auto_btn.clicked.connect(self._on_auto_range)

        self._hue.rangeChanged.connect(self._on_controls_changed)
        self._sat.rangeChanged.connect(self._on_controls_changed)
        self._val.rangeChanged.connect(self._on_controls_changed)
        self._mode_combo.currentIndexChanged.connect(self._on_controls_changed)

    def _on_load_clicked(self):
        """Open a file dialog and load an image."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Open Image',
            '',
            'Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.exr);;All Files (*.*)',
        )
        if not path:
            return

        # OpenCV EXR needs built with OpenEXR; if not, it will fail.
        bgr = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if bgr is None:
            QtWidgets.QMessageBox.warning(self, 'Load Failed', 'Could not load image.')
            return

        # Normalize to 8-bit BGR for this demo
        if bgr.dtype != np.uint8:
            # Scale float/16-bit to 0..255 for preview
            bgr = self._to_u8_bgr(bgr)

        if bgr.ndim == 2:
            bgr = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)
        if bgr.shape[2] == 4:
            bgr = bgr[:, :, :3]

        self._image_bgr = bgr
        self._view.set_image_bgr(self._image_bgr)
        self._picked_hsv = None
        self._info.setText('Pick: -')
        self._update_outputs()

    def _to_u8_bgr(self, img):
        """Convert various image formats to uint8 BGR for preview."""
        img = np.asarray(img)

        if img.ndim == 2:
            mn = float(np.min(img))
            mx = float(np.max(img))
            if mx <= mn:
                out = np.zeros_like(img, dtype=np.uint8)
            else:
                out = ((img - mn) / (mx - mn) * 255.0).astype(np.uint8)
            return cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)

        # If float or 16-bit
        mn = float(np.min(img))
        mx = float(np.max(img))
        if mx <= mn:
            return np.zeros_like(img, dtype=np.uint8)

        out = ((img - mn) / (mx - mn) * 255.0).astype(np.uint8)
        if out.shape[2] == 4:
            out = out[:, :, :3]
        return out

    def _on_picked(self, x, y):
        """Pick the pixel and store HSV."""
        if self._image_bgr is None:
            return

        bgr = self._image_bgr[y, x, :].astype(np.uint8)[None, None, :]
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)

        # OpenCV HSV: H in [0..179], S/V in [0..255]
        h = float(hsv[0, 0, 0]) / 179.0
        s = float(hsv[0, 0, 1]) / 255.0
        v = float(hsv[0, 0, 2]) / 255.0

        self._picked_hsv = (h, s, v)
        self._info.setText(f'Pick HSV: h={h:.3f} s={s:.3f} v={v:.3f}  (x={x}, y={y})')
        self._update_outputs()

    def _on_auto_range(self):
        """Set ranges around the picked color (basic defaults)."""
        if self._picked_hsv is None:
            return

        h, s, v = self._picked_hsv

        # Defaults (tweak as you like)
        hue_w = 0.08
        sat_w = 0.25
        val_w = 0.25

        soft = 0.04

        self._hue.set_range(wrap01(h - hue_w), wrap01(h + hue_w), soft, soft)
        self._sat.set_range(clamp01(s - sat_w), clamp01(s + sat_w), 0.08, 0.08)
        self._val.set_range(clamp01(v - val_w), clamp01(v + val_w), 0.08, 0.08)

        self._update_outputs()

    def _on_controls_changed(self, *args):
        """Update output when controls change."""
        self._update_outputs()

    def _update_outputs(self):
        """Recompute the mask and refresh viewports."""
        if self._image_bgr is None:
            self._mask_view.setPixmap(QtGui.QPixmap())
            return

        mask_u8 = self._compute_mask_u8(self._image_bgr)

        mode = self._mode_combo.currentText()
        if mode == 'Original':
            disp = self._image_bgr
        elif mode == 'Mask Only':
            disp = cv2.cvtColor(mask_u8, cv2.COLOR_GRAY2BGR)
        else:
            disp = overlay_mask_on_bgr(self._image_bgr, mask_u8, alpha=0.55)

        self._view.set_image_bgr(disp)

        # Also show mask alone in the bottom preview
        mask_qimg = gray_to_qimage(mask_u8)
        pm = QtGui.QPixmap.fromImage(mask_qimg)
        pm = pm.scaled(self._mask_view.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self._mask_view.setPixmap(pm)

    def _compute_mask_u8(self, bgr_u8):
        """Compute qualifier mask from H/S/V controls."""
        hsv = cv2.cvtColor(bgr_u8, cv2.COLOR_BGR2HSV).astype(np.float32)

        h = hsv[:, :, 0] / 179.0
        s = hsv[:, :, 1] / 255.0
        v = hsv[:, :, 2] / 255.0

        h_low, h_high, h_soft_l, h_soft_h = self._hue.get_range()
        s_low, s_high, s_soft_l, s_soft_h = self._sat.get_range()
        v_low, v_high, v_soft_l, v_soft_h = self._val.get_range()

        mh = circ_band_mask(h, h_low, h_high, h_soft_l, h_soft_h)
        ms = soft_band_mask_linear(s, s_low, s_high, s_soft_l, s_soft_h)
        mv = soft_band_mask_linear(v, v_low, v_high, v_soft_l, v_soft_h)

        m = mh * ms * mv
        m = np.clip(m, 0.0, 1.0)

        return (m * 255.0).astype(np.uint8)


# Example Usages
# --------------
if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication(sys.argv)

    w = QualifierTestWindow()
    w.resize(1200, 700)
    w.show()

    sys.exit(app.exec_())
