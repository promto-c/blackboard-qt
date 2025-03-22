# Third Party Imports
# -------------------
from qtpy import QtCore, QtGui, QtWidgets


# Class Definitions
# -----------------
class AdaptivePaddedDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    """A QDoubleSpinBox with adaptive padding and stepping based on cursor position.

    This class extends QDoubleSpinBox to allow dynamic adjustment of display padding
    and step size based on the cursor's position within the spin box.

    Attributes:
        integer_padding (int): The number of characters to display before the decimal.
        fraction_padding (int): The number of characters to display after the decimal.
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, integer_padding: int = 1, fraction_padding: int = 2, 
                 default_value: float = 0.0, min_value: float = 0.0, 
                 max_value: float = 99.99, step_size: float = 0.1, 
                 parent: QtWidgets.QWidget = None):
        """Initialize the spin box with specific padding lengths.

        Args:
            integer_padding (int): Initial padding length for the integer part.
            fraction_padding (int): Initial padding length for the fractional part.
            default_value (float): The initial value of the spin box.
            min_value (float): The minimum value allowed.
            max_value (float): The maximum value allowed.
            step_size (float): The increment or decrement step size.
            parent (QWidget, optional): The parent widget of the spin box.
        """
        super().__init__(parent=parent)

        # Store the arguments
        self.integer_padding = integer_padding
        self.fraction_padding = fraction_padding

        self._mouse_press_pos = None
        self._mouse_press_value = None

        self.setRange(min_value, max_value)
        self.setValue(default_value)
        self.setSingleStep(step_size)
        self.lineEdit().installEventFilter(self)

        # Hide the + and - buttons
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)

        # Set the maximum number of decimal places
        self.setDecimals(10)

        # Set up signal connections
        self.__init_signal_connections()

    def __init_signal_connections(self):
        """Set up signal connections between widgets and slots.
        """
        self.lineEdit().cursorPositionChanged.connect(self._adjust_step)
        self.lineEdit().textChanged.connect(self._adjust_padding)

    # Private Methods
    # ---------------
    def _adjust_step(self, old_pos: int, new_pos: int):
        """Adjust the step size based on the cursor position.

        Args:
            old_pos (int): The previous position of the cursor (not currently used).
            new_pos (int): The current position of the cursor.
        """
        # Get the current text from the line edit
        text = self.lineEdit().text()

        # Find the position of the decimal point, or use text length if no decimal point
        decimal_pos = text.find('.') if '.' in text else len(text)

        # Adjust the new cursor position if it's not at the selection start
        if self.lineEdit().selectionStart() != new_pos:
            new_pos -= 1

        # Calculate the distance from the new cursor position to the decimal point
        distance_to_decimal = new_pos - decimal_pos
        distance_to_decimal += 1 if distance_to_decimal < 0 else 0

        # Set the step size based on the distance to the decimal point
        self.setSingleStep(10 ** (-distance_to_decimal))

    def _adjust_padding(self, text: str):
        """Adjust the padding lengths based on the current text.

        This method updates the padding lengths for both the integer part (before the decimal point)
        and the fractional part (after the decimal point) based on the input text.

        Args:
            text (str): The current text from the line edit.

        Doctests:
            >>> app = QtWidgets.QApplication(sys.argv)
            >>> spinbox = AdaptivePaddedDoubleSpinBox()

            >>> spinbox._adjust_padding('123')
            >>> spinbox.padding_length_before
            3
            >>> spinbox.padding_length_after
            0
            >>> spinbox._adjust_padding('00123.456')
            >>> spinbox.padding_length_before
            5
            >>> spinbox.padding_length_after
            3
            >>> spinbox._adjust_padding('00123.')
            >>> spinbox.padding_length_before
            5
            >>> spinbox.padding_length_after
            0
        """
        # Split the text at the decimal point to extract integer and decimal parts
        integer_part, _, fraction_part = text.removeprefix(self.prefix()).removesuffix(self.suffix()).partition('.')

        # Update padding lengths based on the lengths of integer and decimal parts
        self.integer_padding = len(integer_part)
        self.fraction_padding = len(fraction_part) if fraction_part else 0

    # Overridden Methods
    # ------------------
    def setValue(self, value: float):
        """Set the value of the spinbox, adjusting the padding if necessary.

        Args:
            value (float): The new value to be set for the spinbox. The value should be within the range of the spinbox.
        """
        # Extracts the decimal part of the float value.
        fraction_length = len(str(value).split('.')[1]) if '.' in str(value) else 0

        # Update padding to match or exceed the length of the decimal part.
        self.fraction_padding = max(self.fraction_padding, fraction_length)

        # Set the value using the superclass method
        super().setValue(value)

    def textFromValue(self, value: float) -> str:
        """Convert the numeric value to text with proper padding.

        The method formats the given float value to a string that includes leading zeros
        and a fixed number of decimal places. It respects the current padding settings
        for both the integer and fractional parts of the number.

        Args:
            value (float): The numeric value to convert to a padded string.

        Returns:
            str: A string representation of the value with leading zeros and fixed decimal places.

        Examples:
            >>> app = QtWidgets.QApplication(sys.argv)
            >>> spinbox = AdaptivePaddedDoubleSpinBox()

            >>> spinbox.lineEdit().setText('12.')
            >>> spinbox.textFromValue(12.0)
            '12.'
            >>> spinbox.lineEdit().setText('123')
            >>> spinbox.textFromValue(123.0)
            '123'
            >>> spinbox.lineEdit().setText('0123.460')
            >>> spinbox.textFromValue(123.46)
            '0123.460'
        """
        # Determine the offset for padding, which includes the decimal point if any decimal places are specified.
        offset = self.fraction_padding + 1 if self.fraction_padding else 0

        # Format the value to a string with leading zeros and a fixed number of decimal places.
        # The total length includes padding before and after the decimal point, plus the decimal point itself.
        text = f'{value:0{self.integer_padding + offset}.{self.fraction_padding}f}'

        # Append a decimal point to the text if the current text in the line edit ends with a decimal point.
        # This maintains the user's input style.
        if self.lineEdit().text().endswith('.'):
            text += '.'

        return text

    def stepBy(self, steps: int):
        """Step the value, maintaining proper cursor and selection positioning.

        Args:
            steps (int): The number of steps to increment or decrement the value.
        """
        # Capture current cursor position and selection range
        cursor_position = self.lineEdit().cursorPosition()
        selection_start = self.lineEdit().selectionStart()
        selection_end = self.lineEdit().selectionEnd()
        selection_length = selection_end - selection_start

        # Record the text length before the step to detect changes
        text_length_before = len(self.lineEdit().text())

        # Perform the step operation using the superclass method
        super().stepBy(steps)
        
        # Determine the text length after the step to calculate the adjustment needed
        text_length_after = len(self.lineEdit().text())

        # Calculate the length difference due to the step operation
        length_difference = text_length_after - text_length_before

        # Determine the new cursor position and selection start
        new_cursor_position = cursor_position + length_difference
        new_selection_start = selection_start + length_difference

        # Set the new cursor position and selection
        if selection_length > 0:
            self.lineEdit().setSelection(new_selection_start, selection_length)
        else:
            self.lineEdit().setCursorPosition(new_cursor_position)

    def eventFilter(self, source: QtWidgets.QLineEdit, event: QtCore.QEvent):
        """Filters events for the line edit of the spin box, handling both middle mouse and Alt+left button drag interactions.
        """
        # Check if the event source is the line edit of the spin box
        if source == self.lineEdit():
            # Alt+Left Mouse Button or Middle Mouse Button press to start drag
            if event.type() == QtCore.QEvent.Type.MouseButtonPress and (
                    (event.buttons() == QtCore.Qt.MouseButton.LeftButton and QtWidgets.QApplication.keyboardModifiers() == QtCore.Qt.KeyboardModifier.AltModifier) or
                    (event.buttons() == QtCore.Qt.MouseButton.MiddleButton)):
                self._mouse_press_pos = event.globalPos()
                self._mouse_press_value = self.value()
                return True

            # Alt+Left Drag or Middle Mouse Drag adjustment
            elif event.type() == QtCore.QEvent.Type.MouseMove and self._mouse_press_pos is not None:
                # Calculate the horizontal movement from the initial mouse press position, 
                # apply a sensitivity factor, and adjust the spin box's value accordingly
                delta = event.globalPos() - self._mouse_press_pos
                delta_x = delta.x() / 10.0  # Sensitivity factor
                new_value = self._mouse_press_value + delta_x * self.singleStep()
                self.setValue(new_value)
                return True

            # Release mouse button to end drag
            elif event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                self._mouse_press_pos = None
                return True

        return super().eventFilter(source, event)

class DoubleSpinBoxWidget(QtWidgets.QWidget):
    """A widget that combines a QPushButton and a customized AdaptivePaddedDoubleSpinBox.

    This widget provides controlled number input with toggling functionality.
    The QPushButton toggles the spin box value between a default value and the last modified value.

    Attributes:
        default_value (float): Default value of the spin box.
        min_value (float): Minimum allowed value.
        max_value (float): Maximum allowed value.
        step_size (float): Step size for the spin box.
        icon (QtGui.QIcon): Icon displayed on the button.
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, default_value: float = 0.0, min_value: float = 0.0, max_value: float = 99.99, step_size: float = 0.1, 
                 icon: QtGui.QIcon = None, parent: QtWidgets.QWidget = None, *args, **kwargs):
        """Initialize the widget with the given default value, min/max range, step size, and icon.

        Args:
            default_value (float): The initial default value of the spin box.
            min_value (float): Minimum allowed value for the spin box.
            max_value (float): Maximum allowed value for the spin box.
            step_size (float): Increment/decrement step size for the spin box.
            icon (QtGui.QIcon, optional): Icon to display on the button.
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super().__init__(parent, *args, **kwargs)

        # Store the arguments
        self._default_value = default_value
        self._recent_value = default_value
        self._icon = icon
        self.min_value = min_value
        self.max_value = max_value
        self.step_size = step_size

        # Initialize setup
        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        self.setMaximumHeight(22)

        # Create Layouts
        # --------------
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create Widgets
        # --------------
        # Create button
        self.button = QtWidgets.QPushButton(self._icon, '', self) if self._icon else QtWidgets.QPushButton(self)
        self.button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))

        # Create spin box
        self.spin_box = AdaptivePaddedDoubleSpinBox(
            default_value=self._default_value, 
            min_value=self.min_value, max_value=self.max_value, 
            step_size=self.step_size, parent=self)

        # Add Widgets to Layouts
        # ----------------------
        layout.addWidget(self.button)
        layout.addWidget(self.spin_box)

    def __init_signal_connections(self):
        """Set up signal connections between widgets and slots.
        """
        # Connects valueChanged signal of spin box to this widget
        self.valueChanged = self.spin_box.valueChanged

        # Connect signals to slots
        self.spin_box.valueChanged.connect(self._update_button_and_last_value)
        self.button.clicked.connect(self.toggle_value)

    # Public Methods
    # --------------
    def set_default_value(self, value: float):
        """Set the default value with validation.

        Args:
            value (float): New default value.

        Raises:
            TypeError: If the provided value is not a float.
        """
        if not isinstance(value, float):
            raise TypeError("default_value must be a float")
        self._default_value = value

    def toggle_value(self):
        """Toggle between the default value and the most recent non-default value in the spin box.
        """
        if self.spin_box.value() == self._default_value:
            self.spin_box.setValue(self._recent_value)
        else:
            self.spin_box.setValue(self._default_value)

    # Class Properties
    # ----------------
    @property
    def default_value(self) -> float:
        """Getter method for default_value."""
        return self._default_value

    @default_value.setter
    def default_value(self, value: float):
        """Setter method for default_value, utilizing the dedicated set_default_value method."""
        self.set_default_value(value)

    # Private Methods
    # ---------------
    def _update_button_and_last_value(self, value: float):
        """Update the recent value when the spin box value changes, keeping track of the last set value.
        """
        if value == self._default_value:
            return
        self._recent_value = value

    # Overridden Methods
    # ------------------
    def icon(self) -> QtGui.QIcon:
        """Return the icon currently set on the button.
        """
        return self.button.icon()

    def setIcon(self, icon: QtGui.QIcon):
        """Set the icon for the button.
        """
        self.button.setIcon(icon)

    def setEnabled(self, enabled: bool):
        """Enable or disable the button and spin box simultaneously.

        Args:
            enabled (bool): Whether to enable or disable the widget components.
        """
        self.button.setEnabled(enabled)
        self.spin_box.setEnabled(enabled)

    def setDisabled(self, disabled: bool):
        """Disable or enable the button and spin box simultaneously.

        Args:
            disabled (bool): Whether to disable or enable the widget components.
        """
        self.setEnabled(not disabled)

    def setValue(self, value: float):
        self.spin_box.setValue(value)


# Example Usage
# -------------
def main():
    """Run a PyQt application demonstrating the custom spin box widgets."""
    import sys

    app = QtWidgets.QApplication(sys.argv)

    # Create a main window
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("Spin Box Widgets Example")
    main_window.resize(400, 200)

    # Create a central widget
    central_widget = QtWidgets.QWidget(main_window)
    main_window.setCentralWidget(central_widget)

    # Create a layout for the central widget
    layout = QtWidgets.QVBoxLayout(central_widget)

    # Add AdaptivePaddedDoubleSpinBox
    adaptive_spinbox = AdaptivePaddedDoubleSpinBox(
        integer_padding=3, 
        fraction_padding=4, 
        default_value=12.34, 
        min_value=0.0, 
        max_value=999.9999, 
        step_size=0.01, 
        parent=central_widget
    )
    adaptive_spinbox.setPrefix("Value: ")
    adaptive_spinbox.setSuffix(" units")
    layout.addWidget(adaptive_spinbox)

    # Add DoubleSpinBoxWidget
    toggle_spinbox_widget = DoubleSpinBoxWidget(
        default_value=10.0, 
        min_value=0.0, 
        max_value=100.0, 
        step_size=1.0, 
        icon=QtGui.QIcon.fromTheme("edit-undo"), 
        parent=central_widget
    )
    layout.addWidget(toggle_spinbox_widget)

    # Show the main window
    main_window.show()

    # Start the application event loop
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
