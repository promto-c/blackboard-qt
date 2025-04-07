from PyQt5 import QtWidgets, QtCore
from blackboard.widgets.scroll_area import EdgeAwareScrollArea
class FilterBarWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._filter_buttons = []

        # Scrollable filter area
        self.scroll_area = EdgeAwareScrollArea(self, widgetResizable=True)

        # [+] Add Filter Button (initially inside scroll area)
        self.add_button = QtWidgets.QToolButton()
        self.add_button.setText("+")
        self.add_button.setToolTip("Add Filter")
        self.add_button.setFixedSize(24, 24)
        self.add_button.clicked.connect(self.__handle_add_filter)

        # Add Widgets to Layouts
        # ----------------------
        self.main_layout = QtWidgets.QHBoxLayout(self, spacing=6)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.filter_layout = QtWidgets.QHBoxLayout()
        self.filter_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area.container_layout.addLayout(self.filter_layout)
        self.scroll_area.container_layout.addWidget(self.add_button)

        # Container for button outside when overflow occurs
        self.outside_container = QtWidgets.QWidget(visible=False)
        self.outside_layout = QtWidgets.QHBoxLayout(self.outside_container, spacing=0)
        self.outside_layout.setContentsMargins(0, 0, 0, 0)

        self.main_layout.addWidget(self.scroll_area)
        self.main_layout.addWidget(self.outside_container)

        self.__adjust_add_button_position()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.__adjust_add_button_position()

    def __handle_add_filter(self):
        filter_button = QtWidgets.QPushButton(f"Filter")
        filter_button.setFixedHeight(24)
        filter_button.setMaximumWidth(120)
        filter_button.clicked.connect(lambda: self.__remove_filter(filter_button))
        self.filter_layout.addWidget(filter_button)
        self._filter_buttons.append(filter_button)

        # Adjust the button position immediately after adding a filter
        self.__adjust_add_button_position()

        # Schedule execution after current events to animate scrolling
        QtCore.QTimer.singleShot(2, lambda: self.__animate_scroll_to_widget(filter_button))

    def __animate_scroll_to_widget(self, widget):
        """Animate scrolling so that the new filter button is smoothly scrolled into view."""
        scroll_bar = self.scroll_area.horizontalScrollBar()
        # Calculate the widget's x-position relative to the filter_container
        widget_pos = widget.mapTo(self.scroll_area.container, QtCore.QPoint(0, 0)).x()
        widget_width = widget.width()
        viewport_width = self.scroll_area.viewport().width()
        # The target value is set so that the right edge of the widget aligns with the viewport's right edge
        target_value = widget_pos + widget_width - viewport_width
        if target_value < 0:
            target_value = 0

        animation = QtCore.QPropertyAnimation(scroll_bar, b"value", self)
        animation.setDuration(250)  # Duration in milliseconds (adjust as needed)
        animation.setStartValue(scroll_bar.value())
        animation.setEndValue(target_value)
        # Set easing curve to OutCubic for a smooth ease-out effect
        animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        animation.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def __remove_filter(self, button):
        self.filter_layout.removeWidget(button)
        button.setParent(None)
        self._filter_buttons.remove(button)

    def __adjust_add_button_position(self):
        """Check if overflow happens; move button outside when necessary."""
        content_width = self.scroll_area.container.sizeHint().width()
        available_width = self.scroll_area.viewport().width()

        if content_width > available_width:
            # Overflow, move add button outside
            if self.add_button.parent() != self.outside_container:
                self.scroll_area.container_layout.removeWidget(self.add_button)
                self.add_button.setParent(None)
                self.outside_layout.addWidget(self.add_button)
                self.outside_container.setVisible(True)
        else:
            # No overflow, keep add button inside
            if self.add_button.parent() != self.scroll_area.container:
                self.outside_layout.removeWidget(self.add_button)
                self.add_button.setParent(None)
                self.scroll_area.container_layout.addWidget(self.add_button)
                self.outside_container.setVisible(False)


class MainWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Top bar: Filter Bar + Search Bar
        top_bar = QtWidgets.QHBoxLayout()
        top_bar.setSpacing(12)

        self.filter_bar = FilterBarWidget()
        top_bar.addWidget(self.filter_bar, stretch=3)

        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.setFixedHeight(28)
        top_bar.addWidget(self.search_bar, stretch=2)

        main_layout.addLayout(top_bar)

        # Data View (QTableWidget as a placeholder)
        self.data_view = QtWidgets.QTableWidget(10, 3)
        self.data_view.setHorizontalHeaderLabels(["Name", "Type", "Status"])
        main_layout.addWidget(self.data_view)


if __name__ == '__main__':
    import sys
    import blackboard

    app = QtWidgets.QApplication(sys.argv)
    blackboard.theme.set_theme(app, 'dark')
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("Dynamic Filter Bar with Add Button")

    main = MainWidget()
    window.setCentralWidget(main)
    window.resize(600, 400)
    window.show()
    sys.exit(app.exec_())
