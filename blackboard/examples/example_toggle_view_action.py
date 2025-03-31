from PyQt5 import QtWidgets, QtCore


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Toggle View Action Example")
        self.resize(600, 400)

        # Create a dockable widget
        self.dock = QtWidgets.QDockWidget("Dockable Panel", self)
        self.dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        self.dock.setWidget(QtWidgets.QLabel("Content inside the dock widget"))
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock)

        # Add the toggle view action to the menu
        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.dock.toggleViewAction())

        # Optional: Add the toggle view action to a toolbar
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.addAction(self.dock.toggleViewAction())


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
