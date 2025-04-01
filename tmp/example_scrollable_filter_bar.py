from PyQt5 import QtWidgets, QtCore

class FilterBarWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.filter_count = 0
        self._filter_buttons = []

        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(6)

        # Scrollable filter area
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.container = QtWidgets.QWidget()
        self.h_layout = QtWidgets.QHBoxLayout(self.container)
        self.h_layout.setAlignment(QtCore.Qt.AlignLeft)
        self.h_layout.setContentsMargins(0, 0, 0, 0)
        self.h_layout.setSpacing(6)

        self.filter_layout = QtWidgets.QHBoxLayout()
        self.filter_layout.setAlignment(QtCore.Qt.AlignLeft)
        self.filter_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_layout.setSpacing(6)

        self.h_layout.addLayout(self.filter_layout)

        self.scroll_area.setWidget(self.container)
        self.main_layout.addWidget(self.scroll_area)

        # [+] Add Filter Button (initially inside scroll area)
        self.add_button = QtWidgets.QToolButton()
        self.add_button.setText("+")
        self.add_button.setToolTip("Add Filter")
        self.add_button.setFixedSize(24, 24)
        self.add_button.clicked.connect(self.__handle_add_filter)

        # Container for button outside when overflow occurs
        self.add_button_outside_container = QtWidgets.QWidget()
        self.outside_layout = QtWidgets.QHBoxLayout(self.add_button_outside_container)
        self.outside_layout.setContentsMargins(0, 0, 0, 0)
        self.outside_layout.setSpacing(0)
        self.outside_layout.addWidget(self.add_button)
        self.add_button_outside_container.setVisible(False)

        # Initially button is inside
        self.h_layout.addWidget(self.add_button)

        self.main_layout.addWidget(self.add_button_outside_container)

        # Timer to continuously monitor layout
        self.resize_timer = QtCore.QTimer(self, interval=100, timeout=self.__adjust_add_button_position)
        self.resize_timer.start()

    def __handle_add_filter(self):
        self.filter_count += 1
        filter_button = QtWidgets.QPushButton(f"Filter {self.filter_count}")
        filter_button.setFixedHeight(24)
        filter_button.setMaximumWidth(120)
        filter_button.clicked.connect(lambda: self.__remove_filter(filter_button))
        self.filter_layout.addWidget(filter_button)
        self._filter_buttons.append(filter_button)

        # Schedule execution after current events to animate scrolling
        QtCore.QTimer.singleShot(2, lambda: self.__animate_scroll_to_widget(filter_button))

    def __animate_scroll_to_widget(self, widget):
        """Animate scrolling so that the new filter button is smoothly scrolled into view."""
        scroll_bar = self.scroll_area.horizontalScrollBar()
        # Calculate the widget's x-position relative to the filter_container
        widget_pos = widget.mapTo(self.container, QtCore.QPoint(0, 0)).x()
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
        content_width = self.container.sizeHint().width()
        available_width = self.scroll_area.viewport().width()

        if content_width > available_width:
            # Overflow, move add button outside
            if self.add_button.parent() != self.add_button_outside_container:
                self.h_layout.removeWidget(self.add_button)
                self.add_button.setParent(None)
                self.outside_layout.addWidget(self.add_button)
                self.add_button_outside_container.setVisible(True)
        else:
            # No overflow, keep add button inside
            if self.add_button.parent() != self.container:
                self.outside_layout.removeWidget(self.add_button)
                self.add_button.setParent(None)
                self.h_layout.addWidget(self.add_button)
                self.add_button_outside_container.setVisible(False)


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
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("Dynamic Filter Bar with Add Button")

    main = MainWidget()
    window.setCentralWidget(main)
    window.resize(600, 400)
    window.show()
    sys.exit(app.exec_())
