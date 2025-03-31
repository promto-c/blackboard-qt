import sys
from PyQt5 import QtWidgets, QtCore, QtGui

from blackboard.widgets.momentum_scroll_widget import MomentumScrollListWidget


class FadingOverlay(QtWidgets.QWidget):
    """
    This overlay is used only to draw fading gradients on the left and right
    edges of the list. It no longer handles auto‐scroll events.
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
        list_widget = self.parent()
        h_scroll = list_widget.horizontalScrollBar()
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


class ListWidgetWithAutoScroll(MomentumScrollListWidget):
    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        # Define the trigger zone width for auto-scrolling.
        self.auto_scroll_width = 16  
        self.scroll_direction = 0
        self.scroll_timer = QtCore.QTimer(self)
        self.scroll_timer.timeout.connect(self.autoScroll)

        # Create arrow buttons as children of the list widget.
        self.leftButton = QtWidgets.QToolButton(self)
        self.leftButton.setFixedWidth(self.auto_scroll_width)
        self.leftButton.setArrowType(QtCore.Qt.LeftArrow)
        self.leftButton.hide()

        self.rightButton = QtWidgets.QToolButton(self)
        self.rightButton.setFixedWidth(self.auto_scroll_width)
        self.rightButton.setArrowType(QtCore.Qt.RightArrow)
        self.rightButton.hide()

        self.init_ui()

        # Create the fading overlay (for visual effect) and connect it to scrollbar updates.
        self.overlay = FadingOverlay(self)
        # Ensure the overlay is drawn behind the arrow buttons.
        self.overlay.lower()
        self.horizontalScrollBar().valueChanged.connect(self.overlay.update)

    def init_ui(self):
        # Configure the list widget for a horizontal (icon) layout.
        self.setViewMode(QtWidgets.QListView.IconMode)
        self.setFlow(QtWidgets.QListView.LeftToRight)
        self.setResizeMode(QtWidgets.QListView.Adjust)
        self.setWrapping(False)
        self.setSpacing(5)

        # Populate the list with initial items.
        for i in range(20):
            item = QtWidgets.QListWidgetItem(f"Item {i+1}")
            self.addItem(item)

        # Hide the native scroll bars.
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

    def mouseMoveEvent(self, event):
        pos = event.pos()
        width = self.width()

        h_scroll = self.horizontalScrollBar()
        scroll_value = h_scroll.value()
        max_scroll = h_scroll.maximum()

        # Check if the cursor is in the left trigger zone.
        if pos.x() < self.auto_scroll_width and scroll_value > 0:
            self.scroll_direction = -1
            self.leftButton.show()
            self.rightButton.hide()
            self.leftButton.raise_()  # Ensure the button appears above the overlay.
        # Check if the cursor is in the right trigger zone.
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

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        # Stop auto scrolling and hide buttons when the mouse leaves.
        self.scroll_timer.stop()
        self.scroll_direction = 0
        self.leftButton.hide()
        self.rightButton.hide()
        super().leaveEvent(event)

    def autoScroll(self):
        # Scroll 5 pixels per tick in the set direction.
        h_scroll = self.horizontalScrollBar()
        new_value = h_scroll.value() + self.scroll_direction * 5
        new_value = max(0, min(new_value, h_scroll.maximum()))
        h_scroll.setValue(new_value)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Reposition the arrow buttons along the left/right edges, vertically centered.
        self.leftButton.move(0, (self.height() - self.leftButton.height()) // 2)
        self.rightButton.move(self.width() - self.rightButton.width(),
                              (self.height() - self.rightButton.height()) // 2)


if __name__ == "__main__":
    from blackboard import theme
    app = QtWidgets.QApplication(sys.argv)
    theme.set_theme(app, 'dark')

    # Create a main window with a vertical layout that contains the list widget
    # and an external button to add items.
    main_window = QtWidgets.QWidget()
    main_layout = QtWidgets.QVBoxLayout(main_window)

    list_widget = ListWidgetWithAutoScroll()
    list_widget.setStyleSheet("""
                              QListWidget {
                              background-color: #333;
                              border: none;
                              }""")
    main_layout.addWidget(list_widget)

    add_button = QtWidgets.QPushButton("Add Item")
    main_layout.addWidget(add_button)

    # Use a mutable container to hold the external item counter.
    external_count = [21]  # Starting after the 20 initial items

    def on_add():
        item_text = f"External Item {external_count[0]}"
        list_widget.addItem(QtWidgets.QListWidgetItem(item_text))
        external_count[0] += 1

    add_button.clicked.connect(on_add)

    main_window.setWindowTitle("ListWidget with Auto-Scrolling, Fading Edges, and External Item Addition")
    main_window.resize(400, 300)
    main_window.show()
    sys.exit(app.exec_())
