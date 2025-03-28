# Third Party Imports
# -------------------
from qtpy import QtCore, QtGui, QtWidgets

# Local Imports
# -------------
from blackboard.widgets.scalable_view import ScalableView
from blackboard.utils.key_binder import KeyBinder


# Class Definitions
# -----------------
class DockTitleBar(QtWidgets.QWidget):
    def __init__(self, title: str = 'Title', icon: QtGui.QIcon = None, parent=None):
        super().__init__(parent)

        self.icon_button = QtWidgets.QToolButton(icon=icon, parent=self)
        self.title_label = QtWidgets.QLabel(title, self)

        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.icon_button)
        layout.addWidget(self.title_label)

        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # Set the background color to match the WindowTitle color role
        palette = self.palette()
        color = palette.color(QtGui.QPalette.ColorRole.Base)
        self.setAutoFillBackground(True)
        palette.setColor(self.backgroundRole(), color)
        self.setPalette(palette)
        
    def set_icon(self, icon: QtGui.QIcon):
        self.icon_button.setIcon(icon)

    def set_title(self, title):
        self.title_label.setText(title)

class DockWidget(QtWidgets.QDockWidget):
    def __init__(self, widget: QtWidgets.QWidget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setParent(widget.parent())

        window_title = widget.windowTitle()
        self.setWindowTitle(window_title)

        title_bar = DockTitleBar(window_title, widget.windowIcon(), self)

        self.setTitleBarWidget(title_bar)
        self.setWidget(widget)

class MainWindow(QtWidgets.QMainWindow):

    # Class Constants
    # ---------------
    WINDOW_TITLE = 'Main Window'

    # Initialization and Setup
    # ------------------------
    def __init__(self, widget: QtWidgets.QWidget = None, parent: QtWidgets.QWidget = None, use_scalable_view: bool = True):
        super().__init__(parent)

        # Store the arguments
        self.widget = widget
        self.use_scalable_view = use_scalable_view

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        self.settings = QtCore.QSettings()

    def __init_ui(self):
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setDockNestingEnabled(True)

        if self.widget is not None:
            if self.use_scalable_view:
                self.widget_view = ScalableView(parent=self, widget=self.widget)
                self.setCentralWidget(self.widget_view)
            else:
                self.setCentralWidget(self.widget)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        KeyBinder.bind_key('F11', self, self.toggle_full_screen)

    def add_dock(self, widget: QtWidgets.QWidget) -> QtWidgets.QDockWidget:
        """Add a dock widget with the given widget and title.
        
        Args:
            widget (QtWidgets.QWidget): The widget to be added to the dock.
        
        Returns:
            QtWidgets.QDockWidget: The created dock widget.
        """
        dock_widget = DockWidget(widget, self)
        
        self.addDockWidget(QtCore.Qt.DockWidgetArea.TopDockWidgetArea, dock_widget)
        return dock_widget

    def toggle_full_screen(self):

        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def save_state(self):
        self.settings.setValue('geometry', self.geometry())
        self.settings.setValue('state', self.saveState())

        if hasattr(self.widget, 'save_state'):
            self.widget.save_state(self.settings)

        if self.use_scalable_view:
            self.widget_view.save_state(self.settings)

    def load_state(self):
        geometry = self.settings.value('geometry', QtCore.QRect())
        state = self.settings.value('state', QtCore.QByteArray())
        if geometry:
            self.setGeometry(geometry)
        self.restoreState(state)

        if hasattr(self.widget, 'load_state'):
            self.widget.load_state(self.settings)

        if self.use_scalable_view:
            self.widget_view.load_state(self.settings)

    # Override Methods
    # ----------------
    def show(self):
        super().show()
        self.load_state()

    def closeEvent(self, event):
        self.save_state()
        super().closeEvent(event)
