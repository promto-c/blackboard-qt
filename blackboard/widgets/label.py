# Third Party Imports
# -------------------
from qtpy import QtCore, QtGui, QtWidgets


# Class Definitions
# -----------------
class LabelEmbedderWidget(QtWidgets.QWidget):

    # Initialization and Setup
    # ------------------------
    def __init__(self, widget: QtWidgets.QWidget, text: str = '', parent: QtWidgets.QWidget = None):
        """Initializes the LabelEmbedderWidget with a label and a widget.

        Args:
            widget: The widget to be embedded below the label.
            text: The text to be displayed in the label.
            parent: The parent widget, if any.
        """
        super().__init__(parent)

        # Store the arguments
        self._widget = widget
        self._text = text

        # Initialize setup
        self.__init_ui()

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Apply the custom property and style to the new widget
        self._apply_embedded_widget_style()

        # Create Layouts
        # --------------
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.top_label_layout = QtWidgets.QHBoxLayout()
        
        self.action_layout = QtWidgets.QHBoxLayout()
        self.action_layout.setContentsMargins(0, 4, 0, 4)
        self.action_layout.setSpacing(6)
        layout.addLayout(self.top_label_layout)

        # Create Widgets
        # --------------
        self._label = QtWidgets.QLabel(self._text)
        self._label.setObjectName("embedder_label")
        # Set size policy to ensure the label uses its minimum height
        self._label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Maximum)

        # Add Widgets to Layouts
        # ----------------------
        self.top_label_layout.addWidget(self._label)
        self.top_label_layout.setAlignment(self._label, QtCore.Qt.AlignmentFlag.AlignBottom)
        self.top_label_layout.addStretch()
        self.top_label_layout.addLayout(self.action_layout)
        layout.addWidget(self._widget)

    def _apply_embedded_widget_style(self) -> None:
        """Applies the custom property and style to the embedded widget."""
        # Set a custom property for the widget
        self._widget.setProperty('is_embedded', True)

    # Public Methods
    # --------------
    def set_label_text(self, text: str):
        """Sets the text of the label.

        Args:
            text: The new text for the label.
        """
        self._label.setText(text)

    def add_actions(self, *widgets: QtWidgets.QWidget):
        """Adds one or more widgets to the top label layout.

        Args:
            *widgets: The widgets to add next to the label in the top label layout.
        """
        for widget in widgets:
            self.action_layout.addWidget(widget)

    def get_label_text(self) -> str:
        """Returns the current text of the label.

        Returns:
            The text displayed in the label.
        """
        return self._label.text()

    def set_label_alignment(self, alignment: QtCore.Qt.Alignment):
        """Sets the alignment of the label.

        Args:
            alignment: The alignment flag for the label (e.g., QtCore.Qt.AlignLeft).
        """
        self._label.setAlignment(alignment)

    def set_widget(self, widget: QtWidgets.QWidget):
        """Replaces the current embedded widget with a new one.

        Args:
            widget: The new widget to embed.
        """
        layout = self.layout()
        layout.removeWidget(self._widget)
        self._widget.deleteLater()
        self._widget = widget
        self._apply_embedded_widget_style()
        layout.addWidget(self._widget)

    def get_widget(self) -> QtWidgets.QWidget:
        """Returns the currently embedded widget.

        Returns:
            The currently embedded widget.
        """
        return self._widget

    @property
    def label_text(self) -> str:
        """str: Gets or sets the text of the label."""
        return self._label.text()

    @label_text.setter
    def label_text(self, text: str):
        self.set_label_text(text)

    @property
    def label_alignment(self) -> QtCore.Qt.Alignment:
        """QtCore.Qt.Alignment: Gets or sets the alignment of the label."""
        return self._label.alignment()

    @label_alignment.setter
    def label_alignment(self, alignment: QtCore.Qt.Alignment):
        self.set_label_alignment(alignment)

    @property
    def widget(self) -> QtWidgets.QWidget:
        """QtWidgets.QWidget: Gets or sets the currently embedded widget."""
        return self._widget

    @widget.setter
    def widget(self, widget: QtWidgets.QWidget):
        self.set_widget(widget)


if __name__ == '__main__':
    import sys
    from blackboard.theme import set_theme

    app = QtWidgets.QApplication(sys.argv)
    set_theme(app, 'dark')

    combo_box = QtWidgets.QComboBox()
    window = LabelEmbedderWidget(combo_box, 'Label')
    window.show()
    sys.exit(app.exec_())
