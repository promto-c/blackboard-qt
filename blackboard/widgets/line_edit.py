# Third Party Imports
# -------------------
from qtpy import QtWidgets, QtGui
from tablerqicon import TablerQIcon


# Class Definitions
# -----------------
class LineEdit(QtWidgets.QLineEdit):

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent=None, validator: QtGui.QValidator = None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        if validator is not None:
            self.setValidator(validator)

        # Initialize setup
        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        # Add line edits for entering numeric values with placeholders
        self.setProperty('has-placeholder', True)

        # Create a clear action for the line edit
        clear_action = QtWidgets.QAction(self, icon=TablerQIcon.x, toolTip="Clear", triggered=self.clear)
        self.addAction(clear_action, QtWidgets.QLineEdit.ActionPosition.TrailingPosition)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        self.textChanged.connect(self._update_style)

    # Private Methods
    # ---------------
    def _update_style(self):
        """Update the style of the widget.
        """
        self.style().unpolish(self)
        self.style().polish(self)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])

    # Create a LineEdit instance with the validator
    validator = QtGui.QIntValidator(1, 100)
    line_edit = LineEdit(validator=validator)
    line_edit.setPlaceholderText("Enter a number between 1 and 100")
    line_edit.show()

    app.exec_()
