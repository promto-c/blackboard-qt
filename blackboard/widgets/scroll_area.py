# Standard Library Imports
# ------------------------
import sys
from qtpy import QtWidgets, QtCore, QtGui

# Local Imports
# -------------
from blackboard.widgets.momentum_scroll_widget import MomentumScrollArea


# Class Definitions
# -----------------
# TODO: Implement to reuable to any scroll able widgets (QListWidget, QTreeWidget, ...)
class FadingOverlay(QtWidgets.QWidget):
    """Overlay widget that draws fading gradients at the scrollable edges.

    The overlay is transparent to mouse events and dynamically adapts based on
    the scroll area's orientation and scroll position.

    Attributes:
        MAX_OPACITY (int): Maximum opacity for gradient fades.
        FADE_SIZE (int): The size (in pixels) of the fade region.
    """

    MAX_OPACITY = 200
    FADE_SIZE = 30

    def __init__(self, scroll_area: QtWidgets.QScrollArea, parent):
        """Initialize the FadingOverlay.

        Args:
            scroll_area (QtWidgets.QScrollArea): The scroll area using this overlay.
            parent (QWidget): The parent widget, typically the viewport.
        """
        super().__init__(parent)

        self._scroll_area = scroll_area
        # Enable transparency and ensure the widget doesn't block mouse events.
        # self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.resize(self.parent().size())
        # Listen for resize events on the parent.
        self.parent().installEventFilter(self)

    def eventFilter(self, obj, event):
        """Filter events to adjust the overlay size on parent resize.
        """
        if event.type() == QtCore.QEvent.Type.Resize:
            self.resize(self.parent().size())
        return super().eventFilter(obj, event)

    def paintEvent(self, event: QtGui.QPaintEvent | None):
        """Draw fading gradients based on scroll position and orientation.
        """
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)
        width = self.width()
        height = self.height()
  
        # Get scroll bars to determine if there's off-screen content.
        vbar = self._scroll_area.verticalScrollBar()
        hbar = self._scroll_area.horizontalScrollBar()

        # Determine if more content exists in any direction.
        has_more_up   = vbar.value() > vbar.minimum()
        has_more_down = vbar.value() < vbar.maximum()
        has_more_left  = hbar.value() > hbar.minimum()
        has_more_right = hbar.value() < hbar.maximum()

        # Use the parent's background color.
        bg_color = self.parent().palette().color(self.parent().backgroundRole())

        # Top gradient
        if has_more_up:
            top_opacity = int(self.MAX_OPACITY * min(1.0, vbar.value() / self.FADE_SIZE))
            top_color = QtGui.QColor(bg_color.red(), bg_color.green(), bg_color.blue(), top_opacity)
            transparent = QtGui.QColor(bg_color.red(), bg_color.green(), bg_color.blue(), 0)
            grad_top = QtGui.QLinearGradient(0, 0, 0, self.FADE_SIZE)
            grad_top.setColorAt(0.0, top_color)
            grad_top.setColorAt(1.0, transparent)
            painter.fillRect(0, 0, width, self.FADE_SIZE, grad_top)
        # Bottom gradient
        if has_more_down:
            bottom_distance = vbar.maximum() - vbar.value()
            bottom_opacity = int(self.MAX_OPACITY * min(1.0, bottom_distance / self.FADE_SIZE))
            bottom_color = QtGui.QColor(bg_color.red(), bg_color.green(), bg_color.blue(), bottom_opacity)
            transparent = QtGui.QColor(bg_color.red(), bg_color.green(), bg_color.blue(), 0)
            grad_bot = QtGui.QLinearGradient(0, height - self.FADE_SIZE, 0, height)
            grad_bot.setColorAt(0.0, transparent)
            grad_bot.setColorAt(1.0, bottom_color)
            painter.fillRect(0, height - self.FADE_SIZE, width, self.FADE_SIZE, grad_bot)
        # Left gradient
        if has_more_left:
            left_opacity = int(self.MAX_OPACITY * min(1.0, hbar.value() / self.FADE_SIZE))
            left_color = QtGui.QColor(bg_color.red(), bg_color.green(), bg_color.blue(), left_opacity)
            transparent = QtGui.QColor(bg_color.red(), bg_color.green(), bg_color.blue(), 0)
            grad_left = QtGui.QLinearGradient(0, 0, self.FADE_SIZE, 0)
            grad_left.setColorAt(0.0, left_color)
            grad_left.setColorAt(1.0, transparent)
            painter.fillRect(0, 0, self.FADE_SIZE, height, grad_left)
        # Right gradient
        if has_more_right:
            right_distance = hbar.maximum() - hbar.value()
            right_opacity = int(self.MAX_OPACITY * min(1.0, right_distance / self.FADE_SIZE))
            right_color = QtGui.QColor(bg_color.red(), bg_color.green(), bg_color.blue(), right_opacity)
            transparent = QtGui.QColor(bg_color.red(), bg_color.green(), bg_color.blue(), 0)
            grad_right = QtGui.QLinearGradient(width - self.FADE_SIZE, 0, width, 0)
            grad_right.setColorAt(0.0, transparent)
            grad_right.setColorAt(1.0, right_color)
            painter.fillRect(width - self.FADE_SIZE, 0, self.FADE_SIZE, height, grad_right)


class EdgeAwareScrollArea(MomentumScrollArea):
    """Scroll area that auto-scrolls when the mouse hovers near its edges.

    This scroll area contains an internal container and a fading overlay.
    It ensures that mouse events on child widgets still trigger auto-scroll.
    The widget is designed to be reusable with any scrollable widget.
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent=None, orientation=QtCore.Qt.Orientation.Horizontal, widgetResizable=True):
        """Initialize the EdgeAwareScrollArea.

        Args:
            parent (QWidget, optional): The parent widget.
            orientation (QtCore.Qt.Orientation, optional): The scroll orientation.
                Defaults to horizontal.
        """
        super().__init__(
            parent,
            horizontalScrollBarPolicy=QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
            verticalScrollBarPolicy=QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
            widgetResizable=widgetResizable,
        )

        # Store the arguments
        self.orientation = orientation

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        # Auto-scroll properties.
        self.trigger_size = 16
        self.scroll_direction = 0
        self.scroll_timer = QtCore.QTimer(self)

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Create an internal container with a layout based on orientation.
        self.container = QtWidgets.QWidget()
        if self.orientation == QtCore.Qt.Orientation.Horizontal:
            self.container_layout = QtWidgets.QHBoxLayout(self.container)
            self.container_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        else:
            self.container_layout = QtWidgets.QVBoxLayout(self.container)
            self.container_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.setWidget(self.container)

        # Enable mouse tracking and install event filters.
        self.viewport().setMouseTracking(True)
        self.viewport().installEventFilter(self)
        self.container.installEventFilter(self)

        # Create arrow buttons as children of the viewport.
        if self.orientation == QtCore.Qt.Orientation.Horizontal:
            self.left_button = QtWidgets.QToolButton(self)
            self.left_button.setFixedWidth(self.trigger_size)
            self.left_button.setArrowType(QtCore.Qt.ArrowType.LeftArrow)
            self.left_button.hide()

            self.right_button = QtWidgets.QToolButton(self)
            self.right_button.setFixedWidth(self.trigger_size)
            self.right_button.setArrowType(QtCore.Qt.ArrowType.RightArrow)
            self.right_button.hide()

            overlay_layout = QtWidgets.QHBoxLayout(self)
            overlay_layout.setContentsMargins(0, 0, 0, 0)
            overlay_layout.addWidget(self.left_button, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
            overlay_layout.addWidget(self.right_button, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        else:
            self.up_button = QtWidgets.QToolButton(self)
            self.up_button.setFixedHeight(self.trigger_size)
            self.up_button.setArrowType(QtCore.Qt.ArrowType.UpArrow)
            self.up_button.hide()

            self.down_button = QtWidgets.QToolButton(self)
            self.down_button.setFixedHeight(self.trigger_size)
            self.down_button.setArrowType(QtCore.Qt.ArrowType.DownArrow)
            self.down_button.hide()

            overlay_layout = QtWidgets.QVBoxLayout(self)
            overlay_layout.setContentsMargins(0, 0, 0, 0)
            overlay_layout.addWidget(self.up_button, alignment=QtCore.Qt.AlignmentFlag.AlignTop)
            overlay_layout.addWidget(self.down_button, alignment=QtCore.Qt.AlignmentFlag.AlignBottom)

        # Integrate the fading overlay within the scroll area.
        self.overlay = FadingOverlay(scroll_area=self, parent=self.viewport())
        self.overlay.show()

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        self.scroll_timer.timeout.connect(self._auto_scroll)
        if self.orientation == QtCore.Qt.Orientation.Horizontal:
            self.horizontalScrollBar().valueChanged.connect(self.overlay.update)
        else:
            self.verticalScrollBar().valueChanged.connect(self.overlay.update)

    # Private Methods
    # ---------------
    def _auto_scroll(self):
        """Perform auto-scroll by a fixed number of pixels based on the current direction.
        """
        if self.orientation == QtCore.Qt.Orientation.Horizontal:
            h_scroll = self.horizontalScrollBar()
            new_value = h_scroll.value() + self.scroll_direction * 5  # 5px per tick.
            new_value = max(0, min(new_value, h_scroll.maximum()))
            h_scroll.setValue(new_value)
        else:
            v_scroll = self.verticalScrollBar()
            new_value = v_scroll.value() + self.scroll_direction * 5  # 5px per tick.
            new_value = max(0, min(new_value, v_scroll.maximum()))
            v_scroll.setValue(new_value)

    # Overridden Methods
    # ------------------
    def addWidget(self, widget: QtWidgets.QWidget, adjust_size: bool = True):
        """Add a widget to the internal container.

        Args:
            widget (QWidget): The widget to add.
            adjust_size (bool, optional): If True, adjust the container size after adding.
                Defaults to True.
        """
        self.container_layout.addWidget(widget)
        widget.installEventFilter(self)
        if adjust_size:
            self.container.adjustSize()

    def addLayout(self, layout: QtWidgets.QLayout, adjust_size: bool = True):
        """Add a layout to the internal container.

        Args:
            layout (QLayout): The layout to add.
            adjust_size (bool, optional): If True, adjust the container size after adding.
                Defaults to True.
        """
        self.container_layout.addLayout(layout)
        if adjust_size:
            self.container.adjustSize()

    def removeWidget(self, widget: QtWidgets.QWidget, adjust_size: bool = True):
        """Remove a widget from the internal container.

        This method removes the specified widget from the container layout,
        uninstalls its event filter, and resets its parent to None. Optionally,
        it adjusts the container size after removal.

        Args:
            widget (QWidget): The widget to remove.
            adjust_size (bool, optional): If True, adjust the container size after removal.
                Defaults to True.
        """
        index = self.container_layout.indexOf(widget)
        if index == -1:
            return

        # Remove widget from layout and uninstall event filter
        self.container_layout.removeWidget(widget)
        widget.removeEventFilter(self)

        if adjust_size:
            self.container.adjustSize()

    def eventFilter(self, obj, event):
        """Filter events to trigger auto-scroll based on mouse movement.

        Args:
            obj (QObject): The object sending the event.
            event (QEvent): The event to filter.

        Returns:
            bool: True if the event is filtered; otherwise, False.
        """
        if event.type() == QtCore.QEvent.Type.MouseMove:
            # Convert event coordinates to viewport's coordinate system if needed.
            if obj is not self.viewport():
                pos = obj.mapTo(self.viewport(), event.pos())
            else:
                pos = event.pos()

            # Skip auto-scroll if the middle mouse button is pressed.
            if event.buttons() & QtCore.Qt.MiddleButton:
                return super().eventFilter(obj, event)

            if self.orientation == QtCore.Qt.Orientation.Horizontal:
                width = self.viewport().width()
                h_scroll = self.horizontalScrollBar()
                scroll_value = h_scroll.value()
                max_scroll = h_scroll.maximum()

                if pos.x() < self.trigger_size and scroll_value > 0:
                    self.scroll_direction = -1
                    self.left_button.show()
                    self.right_button.hide()
                    self.left_button.raise_()
                elif pos.x() > width - self.trigger_size and scroll_value < max_scroll:
                    self.scroll_direction = 1
                    self.right_button.show()
                    self.left_button.hide()
                    self.right_button.raise_()
                else:
                    self.scroll_direction = 0
                    self.left_button.hide()
                    self.right_button.hide()

                if self.scroll_direction != 0 and not self.scroll_timer.isActive():
                    self.scroll_timer.start(20)
                elif self.scroll_direction == 0 and self.scroll_timer.isActive():
                    self.scroll_timer.stop()
            else:
                height = self.viewport().height()
                v_scroll = self.verticalScrollBar()
                scroll_value = v_scroll.value()
                max_scroll = v_scroll.maximum()

                if pos.y() < self.trigger_size and scroll_value > 0:
                    self.scroll_direction = -1
                    self.up_button.show()
                    self.down_button.hide()
                    self.up_button.raise_()
                elif pos.y() > height - self.trigger_size and scroll_value < max_scroll:
                    self.scroll_direction = 1
                    self.down_button.show()
                    self.up_button.hide()
                    self.down_button.raise_()
                else:
                    self.scroll_direction = 0
                    self.up_button.hide()
                    self.down_button.hide()

                if self.scroll_direction != 0 and not self.scroll_timer.isActive():
                    self.scroll_timer.start(20)
                elif self.scroll_direction == 0 and self.scroll_timer.isActive():
                    self.scroll_timer.stop()
        elif event.type() == QtCore.QEvent.Type.Leave:
            self.scroll_timer.stop()
            if self.orientation == QtCore.Qt.Orientation.Horizontal:
                self.left_button.hide()
                self.right_button.hide()
            else:
                self.up_button.hide()
                self.down_button.hide()

        return super().eventFilter(obj, event)


if __name__ == '__main__':
    from blackboard import theme
    app = QtWidgets.QApplication(sys.argv)
    theme.set_theme(app, 'dark')

    # Create our custom scroll area with internal container and fading overlay.
    scroll_area = EdgeAwareScrollArea(orientation=QtCore.Qt.Orientation.Horizontal)

    # Add buttons using the addWidget() method.
    for i in range(15):
        btn = QtWidgets.QPushButton(f'Button {i + 1}')
        scroll_area.addWidget(btn)

    scroll_area.show()
    sys.exit(app.exec_())
