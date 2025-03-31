import sys
from PyQt5 import QtWidgets, QtCore, QtGui

from blackboard.widgets.momentum_scroll_widget import MomentumScrollArea


class FadingOverlay(QtWidgets.QWidget):
    """
    This overlay is used only to draw fading gradients on the left and right
    edges of the viewport. It no longer handles auto‐scroll events.
    """
    def __init__(self, parent):
        super().__init__(parent)
        # Use a nonopaque background and ignore mouse events.
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.fade_width = 30  # Width for the fade effect.
        # Ensure the overlay always covers the parent.
        self.setGeometry(parent.rect())
        parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        # Update overlay geometry when the parent resizes.
        if event.type() == QtCore.QEvent.Resize:
            self.setGeometry(self.parent().rect())
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        rect = self.rect()
        # Use the parent's background color.
        bg_color = self.parent().palette().color(QtGui.QPalette.Window)
        scroll_area = self.parent().parent()
        h_scroll = scroll_area.horizontalScrollBar()
        scroll_value = h_scroll.value()
        max_scroll = h_scroll.maximum()
        max_opacity = 200

        # Left fade if not at the far left.
        if scroll_value > 0:
            left_opacity = int(max_opacity * min(1.0, scroll_value / self.fade_width))
            left_gradient = QtGui.QLinearGradient(0, 0, self.fade_width, 0)
            left_gradient.setColorAt(0, QtGui.QColor(bg_color.red(), bg_color.green(), bg_color.blue(), left_opacity))
            left_gradient.setColorAt(1, QtGui.QColor(bg_color.red(), bg_color.green(), bg_color.blue(), 0))
            painter.fillRect(0, 0, self.fade_width, rect.height(), left_gradient)

        # Right fade if not at the far right.
        if scroll_value < max_scroll:
            right_distance = max_scroll - scroll_value
            right_opacity = int(max_opacity * min(1.0, right_distance / self.fade_width))
            right_gradient = QtGui.QLinearGradient(rect.width() - self.fade_width, 0, rect.width(), 0)
            right_gradient.setColorAt(0, QtGui.QColor(bg_color.red(), bg_color.green(), bg_color.blue(), 0))
            right_gradient.setColorAt(1, QtGui.QColor(bg_color.red(), bg_color.green(), bg_color.blue(), right_opacity))
            painter.fillRect(rect.width() - self.fade_width, 0, self.fade_width, rect.height(), right_gradient)


class AutoScrollMomentumScrollArea(MomentumScrollArea):
    """
    Subclass of MomentumScrollArea that implements auto-scrolling based on
    mouse movement near the left/right edges of the viewport.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Enable mouse tracking on the viewport.
        self.viewport().setMouseTracking(True)
        self.viewport().installEventFilter(self)

        # Auto-scroll properties.
        self.auto_scroll_width = 16  # Trigger zone in pixels.
        self.scroll_direction = 0
        self.scroll_timer = QtCore.QTimer(self)
        self.scroll_timer.timeout.connect(self.autoScroll)

        # Create arrow buttons as children of the viewport.
        self.leftButton = QtWidgets.QToolButton(self.viewport())
        self.leftButton.setFixedWidth(self.auto_scroll_width)
        self.leftButton.setArrowType(QtCore.Qt.LeftArrow)
        self.leftButton.hide()

        self.rightButton = QtWidgets.QToolButton(self.viewport())
        self.rightButton.setFixedWidth(self.auto_scroll_width)
        self.rightButton.setArrowType(QtCore.Qt.RightArrow)
        self.rightButton.hide()

    def autoScroll(self):
        h_scroll = self.horizontalScrollBar()
        new_value = h_scroll.value() + self.scroll_direction * 5  # Scroll 5px per tick.
        new_value = max(0, min(new_value, h_scroll.maximum()))
        h_scroll.setValue(new_value)

    def eventFilter(self, obj, event):
        if obj is self.viewport():
            if event.type() == QtCore.QEvent.MouseMove:
                    # If middle mouse button is pressed, do nothing.
                if event.buttons() & QtCore.Qt.MiddleButton:
                    return super().eventFilter(obj, event)

                pos = event.pos()
                width = self.viewport().width()
                h_scroll = self.horizontalScrollBar()
                scroll_value = h_scroll.value()
                max_scroll = h_scroll.maximum()

                # Determine auto-scroll direction based on mouse x position.
                if pos.x() < self.auto_scroll_width and scroll_value > 0:
                    self.scroll_direction = -1
                    self.leftButton.show()
                    self.rightButton.hide()
                    self.leftButton.raise_()
                elif pos.x() > width - self.auto_scroll_width and scroll_value < max_scroll:
                    self.scroll_direction = 1
                    self.rightButton.show()
                    self.leftButton.hide()
                    self.rightButton.raise_()
                else:
                    self.scroll_direction = 0
                    self.leftButton.hide()
                    self.rightButton.hide()

                # Start or stop the auto-scroll timer as needed.
                if self.scroll_direction != 0 and not self.scroll_timer.isActive():
                    self.scroll_timer.start(20)
                elif self.scroll_direction == 0 and self.scroll_timer.isActive():
                    self.scroll_timer.stop()

            elif event.type() == QtCore.QEvent.Leave:
                self.scroll_timer.stop()
                self.scroll_direction = 0
                self.leftButton.hide()
                self.rightButton.hide()

        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Reposition the arrow buttons in the viewport, vertically centered.
        vp = self.viewport()
        self.leftButton.move(0, (vp.height() - self.leftButton.height()) // 2)
        self.rightButton.move(vp.width() - self.rightButton.width(),
                              (vp.height() - self.rightButton.height()) // 2)


class WidgetWithScrollableToolbar(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(24)
        self.init_ui()

    def init_ui(self):
        # Create a QToolBar and add many buttons to ensure overflow.
        toolbar = QtWidgets.QToolBar("My Toolbar", self)
        for i in range(15):
            btn = QtWidgets.QPushButton(f"Button {i+1}")
            toolbar.addWidget(btn)

        # Wrap the toolbar in our custom auto-scroll scroll area.
        scroll_area = AutoScrollMomentumScrollArea()
        scroll_area.setWidget(toolbar)

        # Hide native scroll bars.
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        # Add the fading overlay to the scroll area's viewport.
        overlay = FadingOverlay(scroll_area.viewport())
        overlay.show()
        scroll_area.horizontalScrollBar().valueChanged.connect(overlay.update)

        # Create the main layout and add the scroll area.
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(scroll_area)
        self.setLayout(layout)


if __name__ == "__main__":
    from blackboard import theme
    app = QtWidgets.QApplication(sys.argv)
    theme.set_theme(app, 'dark')
    widget = WidgetWithScrollableToolbar()
    widget.setWindowTitle("Scrollable QToolBar with Fading Edges")
    widget.resize(300, 200)
    widget.show()
    sys.exit(app.exec_())
