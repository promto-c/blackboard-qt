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
    """Widget to display a bar indicating the status of video frames.
    """
    # Define class-level constants for color representations.
    GRAY_COLOR = QtGui.QColor(29, 29, 29)
    BLUE_COLOR = QtGui.QColor(65, 102, 144)
    GREEN_COLOR = QtGui.QColor(65, 144, 65)

    STATUS_TO_COLOR = {
        FrameStatus.DEFAULT: GRAY_COLOR,
        FrameStatus.CACHING: BLUE_COLOR,
        FrameStatus.CACHED: GREEN_COLOR,
    }

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
        self.setMinimumHeight(2)

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
        # Redraw the widget
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

    # Overridden Methods
    # ------------------
    def paintEvent(self, event: QtGui.QPaintEvent):
        """Handle the paint event to draw the frame indicators.

        Args:
            event: The QPaintEvent.
        """
        painter = QtGui.QPainter(self)
        rect = self.rect()

        # Fill the background with the default color
        painter.fillRect(rect, self.GRAY_COLOR)

        frame_width = rect.width() / self.total_frames

        for frame_index, status in enumerate(self.frame_status):
            color = self.STATUS_TO_COLOR.get(status, self.GRAY_COLOR)
            painter.fillRect(QtCore.QRectF(frame_index * frame_width, 0, frame_width, rect.height()), color)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.frame_indicator = FrameIndicatorBar(1001, 1022)
        self.setCentralWidget(self.frame_indicator)

        # Example updating frame status
        self.frame_indicator.update_frame_status(5, FrameStatus.CACHING)  # Frame 5 is caching
        self.frame_indicator.update_frame_status(6, FrameStatus.CACHED)  # Frame 6 is cached


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
