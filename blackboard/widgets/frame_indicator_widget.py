# Standard Library Imports
# ------------------------
from enum import Enum

# Third-Party Imports
# -------------------
from qtpy import QtCore, QtGui, QtWidgets


# Class Definitions
# -----------------
class FrameStatus(Enum):
    """Cache-status flag per frame.
    """

    DEFAULT = 'default'
    CACHING = 'caching'
    CACHED = 'cached'

class FrameIndicatorBar(QtWidgets.QWidget):
    """Tiny strip that visualises per-frame cache status **plus** In/Out overlay.
    """

    GRAY_COLOR = QtGui.QColor(29, 29, 29)
    BLUE_COLOR = QtGui.QColor(65, 102, 144)
    GREEN_COLOR = QtGui.QColor(65, 144, 65)

    MARK_COLOR = QtGui.QColor(65, 144, 65, 120)  # translucent overlay
    HANDLE_COLOR = QtGui.QColor(220, 220, 220)
    HANDLE_SIZE_PX = 6

    STATUS_TO_COLOR = {
        FrameStatus.DEFAULT: GRAY_COLOR,
        FrameStatus.CACHING: BLUE_COLOR,
        FrameStatus.CACHED: GREEN_COLOR,
    }

    in_out_dragged = QtCore.Signal(int, int)   # (in_frame, out_frame)

    # Initialization and Setup
    # ------------------------
    def __init__(self, first_frame: int = 0, last_frame: int = 1, parent=None, *args, **kwargs):
        """Initialize the frame indicator bar with a specified range of frames.

        Args:
            first_frame: Index of the first frame.
            last_frame: Index of the last frame.
            parent: Parent widget.
        """
        super().__init__(parent, *args, **kwargs)
        self.first_frame = first_frame
        self.last_frame = last_frame
        self.total_frames = last_frame - first_frame + 1
        # Initialize all frames to default
        self.frame_status = [FrameStatus.DEFAULT] * self.total_frames

        self.in_frame: int | None = None
        self.out_frame: int | None = None
        self._dragging_handle: str | None = None  # "in", "out", or None
        self.setMinimumHeight(6)

    # Public Methods
    # --------------
    def set_frame_range(self, first_frame: int, last_frame: int):
        """Reset the bar to a new absolute range.

        Args:
            first_frame: Index of the first frame.
            last_frame: Index of the last frame.
        """
        self.first_frame = first_frame
        self.last_frame = last_frame
        self.total_frames = last_frame - first_frame + 1
        # Reset frame status to default
        self.frame_status = [FrameStatus.DEFAULT] * self.total_frames
        self.in_frame = self.out_frame = None
        self.update()

    def update_frame_status(self, frame_index: int, status: FrameStatus = FrameStatus.DEFAULT):
        """Update the status of a specific frame.

        Args:
            frame_index: The index of the frame to update.
            status: A FrameStatus enum indicating the new status of the frame.
        """
        if self.first_frame <= frame_index <= self.last_frame:
            self.frame_status[frame_index - self.first_frame] = status
            self.update()

    def set_in_out_frames(self, in_frame: int | None, out_frame: int | None):
        """Update trim overlay."""
        self.in_frame, self.out_frame = in_frame, out_frame
        self.update()

    # Overridden Methods
    # ------------------
    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        """Handle the paint event to draw the frame indicators.

        Args:
            event: The QPaintEvent.
        """
        painter = QtGui.QPainter(self)
        rect = self.rect()

        # Fill the background with the default color
        painter.fillRect(rect, self.GRAY_COLOR)

        if self.total_frames <= 0:
            return

        frame_width = rect.width() / self.total_frames

        for frame_index, status in enumerate(self.frame_status):
            color = self.STATUS_TO_COLOR.get(status, self.GRAY_COLOR)
            painter.fillRect(
                QtCore.QRectF(frame_index * frame_width, 0, frame_width, rect.height()),
                color,
            )

        # WIP:
        # Trim overlay + handles
        if self.in_frame is not None and self.out_frame is not None:
            left = (self.in_frame - self.first_frame) * frame_width
            right = (self.out_frame - self.first_frame + 1) * frame_width
            painter.fillRect(
                QtCore.QRectF(left, 0, right - left, rect.height()), self.MARK_COLOR
            )

            # Diamond handles
            half = self.HANDLE_SIZE_PX / 2
            for x in (left, right - frame_width):
                path = QtGui.QPainterPath()
                cx = x + frame_width / 2
                path.moveTo(cx, 0)
                path.lineTo(cx + half, half)
                path.lineTo(cx, self.HANDLE_SIZE_PX)
                path.lineTo(cx - half, half)
                path.closeSubpath()
                painter.fillPath(path, self.HANDLE_COLOR)

    # Mouse handling for draggable handles
    # ------------------------------------
    def _frame_at_pos(self, pos: QtCore.QPointF) -> int:
        return int(self.first_frame + pos.x() / self.width() * self.total_frames)

    def mousePressEvent(self, e: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.in_frame is None or self.out_frame is None:
            return super().mousePressEvent(e)

        hit = self._frame_at_pos(e.position())
        if abs(hit - self.in_frame) <= 1:
            self._dragging_handle = "in"
        elif abs(hit - self.out_frame) <= 1:
            self._dragging_handle = "out"

    def mouseMoveEvent(self, e: QtGui.QMouseEvent) -> None:  # noqa: N802
        if not self._dragging_handle:
            return super().mouseMoveEvent(e)

        frame = max(self.first_frame, min(self._frame_at_pos(e.position()), self.last_frame))
        if self._dragging_handle == "in":
            self.in_frame = min(frame, self.out_frame)
        else:
            self.out_frame = max(frame, self.in_frame)
        self.update()
        # Let parent react
        self.in_out_dragged.emit(self.in_frame, self.out_frame)

        # if hasattr(self.parent(), "in_out_dragged"):
        #     self.parent().in_out_dragged(self.in_frame, self.out_frame)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent) -> None:  # noqa: N802
        super().mouseReleaseEvent(e)
        self._dragging_handle = None


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.frame_indicator = FrameIndicatorBar(1001, 1022)
        self.setCentralWidget(self.frame_indicator)

        # Example updating frame status
        self.frame_indicator.update_frame_status(5, FrameStatus.CACHING)  # Frame 5 is caching
        self.frame_indicator.update_frame_status(6, FrameStatus.CACHED)  # Frame 6 is cached

        self.frame_indicator.set_in_out_frames(1005, 1020)

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
