from PyQt5 import QtCore, QtGui, QtWidgets


class AnimatedToggleDelegate(QtWidgets.QStyledItemDelegate):
    """Delegate for rendering an animated toggle in a tree widget."""

    DEFAULT_ON_COLOR = QtGui.QColor('#4D6')
    DEFAULT_OFF_COLOR = QtGui.QColor('#CCC')

    def __init__(self, parent=None):
        """Initialize the delegate and set up animation parameters."""
        super().__init__(parent)
        self.animations = {}
        self.animation_duration = 200  # Duration in milliseconds

    # Constants for toggle dimensions relative to item height.
        self._toggle_width_ratio = 0.6
        self._toggle_height_ratio = 0.4
        self._toggle_padding = 10
        self._circle_scale = 0.9

    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex):
        """Custom paint method to render the toggle and shift text right."""
        # Calculate text shift based on toggle width.
        text_shift = option.rect.height() * self._toggle_width_ratio + self._toggle_padding
        adjusted_rect = option.rect.adjusted(int(text_shift), 0, 0, 0)
        option.rect = adjusted_rect

        # Call the base class to draw item text and default visuals.
        super().paint(painter, option, index)

        # Retrieve colors from the widget's custom properties.
        toggle_on_color = self.parent().property('toggle_on_color') or self.DEFAULT_ON_COLOR
        toggle_off_color = self.parent().property('toggle_off_color') or self.DEFAULT_OFF_COLOR

        # Retrieve the animation progress.
        progress = index.data(QtCore.Qt.ItemDataRole.UserRole) or 0.0

        # Save the painter state.
        painter.save()
        rect = option.rect

        # Define toggle dimensions.
        toggle_width = rect.height() * self._toggle_width_ratio
        toggle_height = rect.height() * self._toggle_height_ratio
        toggle_radius = toggle_height / 2

        # Calculate positions for the toggle track.
        x = option.rect.left() - text_shift + 4  # Adjust based on padding.
        y = rect.top() + (rect.height() - toggle_height) / 2

        # Draw the background track.
        track_rect = QtCore.QRectF(x, y, toggle_width, toggle_height)
        track_color = toggle_off_color if progress < 0.5 else toggle_on_color
        painter.setBrush(track_color)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(track_rect, toggle_radius, toggle_radius)

        # Draw the toggle circle.
        circle_diameter = toggle_height * self._circle_scale
        circle_x = x + (progress * (toggle_width - circle_diameter))
        circle_y = y + (toggle_height - circle_diameter) / 2
        circle_rect = QtCore.QRectF(circle_x, circle_y, circle_diameter, circle_diameter)
        painter.setBrush(QtGui.QColor('#fff'))
        painter.drawEllipse(circle_rect)

        # Restore painter state.
        painter.restore()

    def start_animation(self, index: QtCore.QModelIndex, start_value: float, end_value: float):
        """Start the animation to transition the toggle state."""
        # Stop an existing animation on the same index, if any.
        if index in self.animations:
            self.animations[index].stop()

        animation = QtCore.QVariantAnimation()
        animation.setDuration(self.animation_duration)
        animation.setStartValue(start_value)
        animation.setEndValue(end_value)
        animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

        def on_value_changed(value: float):
            """Update the progress and redraw the item during animation."""
            self.parent().model().setData(index, value, QtCore.Qt.ItemDataRole.UserRole)
            self.parent().viewport().update(self.parent().visualRect(index))

        def on_finished():
            """Clean up the finished animation."""
            del self.animations[index]

        animation.valueChanged.connect(on_value_changed)
        animation.finished.connect(on_finished)
        animation.start()
        self.animations[index] = animation


class ToggleTreeWidget(QtWidgets.QTreeWidget):
    """Tree widget with toggle color properties and integrated selection handling."""

    def __init__(self, 
                 parent: QtWidgets.QWidget = None,
                 selectionMode: QtWidgets.QAbstractItemView.SelectionMode = QtWidgets.QAbstractItemView.SelectionMode.MultiSelection,
                 *args, **kwargs
                 ):
        """Initialize the tree widget and set up delegate and selection mode."""
        super().__init__(parent=parent, selectionMode=selectionMode, *args, **kwargs)

        self._toggle_on_color = AnimatedToggleDelegate.DEFAULT_ON_COLOR
        self._toggle_off_color = AnimatedToggleDelegate.DEFAULT_OFF_COLOR

        # Set the custom delegate.
        self.delegate = AnimatedToggleDelegate(self)
        self.setItemDelegate(self.delegate)

        # Connect the selection changed signal.
        self.itemSelectionChanged.connect(self.on_item_selection_changed)

    @QtCore.pyqtProperty(QtGui.QColor)
    def toggle_on_color(self) -> QtGui.QColor:
        """Get the toggle 'on' color."""
        return self._toggle_on_color

    @toggle_on_color.setter
    def toggle_on_color(self, color):
        """Set the toggle 'on' color."""
        self._toggle_on_color = QtGui.QColor(color)

    @QtCore.pyqtProperty(QtGui.QColor)
    def toggle_off_color(self) -> QtGui.QColor:
        """Get the toggle 'off' color."""
        return self._toggle_off_color

    @toggle_off_color.setter
    def toggle_off_color(self, color):
        """Set the toggle 'off' color."""
        self._toggle_off_color = QtGui.QColor(color)

    def on_item_selection_changed(self):
        """Animate toggle states based on item selection."""
        selected_indexes = set(self.selectionModel().selectedIndexes())
        all_indexes = [
            self.indexFromItem(item)
            for item in self.findItems('', QtCore.Qt.MatchFlag.MatchContains | QtCore.Qt.MatchFlag.MatchRecursive)
        ]

        for index in all_indexes:
            progress = index.data(QtCore.Qt.ItemDataRole.UserRole) or 0.0
            if index in selected_indexes and progress < 1.0:
                self.delegate.start_animation(index, progress, 1.0)
            elif index not in selected_indexes and progress > 0.0:
                self.delegate.start_animation(index, progress, 0.0)


def main():
    """Main entry point for the application."""
    app = QtWidgets.QApplication([])

    # Create an instance of CustomTreeWidget.
    tree_widget = ToggleTreeWidget(headerHidden=True)

    # Apply stylesheet for custom properties.
    app.setStyleSheet('''
    ToggleTreeWidget {
        qproperty-toggle_on_color: #4D6;  /* Green color for "on" state */
        qproperty-toggle_off_color: #F33; /* Red color for "off" state */
    }
    ''')

    # Add items to the tree widget.
    for i in range(5):
        item = QtWidgets.QTreeWidgetItem(tree_widget)
        item.setText(0, f'Item {i + 1}')

    tree_widget.expandAll()
    tree_widget.show()
    app.exec_()


if __name__ == '__main__':
    main()
