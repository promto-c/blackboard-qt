# Type Checking Imports
# ---------------------
from typing import Tuple, Union

# Third Party Imports
# -------------------
from PyQt5 import QtCore, QtGui, QtWidgets

import keyboard
from pynput import mouse

from tablerqicon import TablerQIcon


# Class Definitions
# -----------------
class FadeLabel(QtWidgets.QLabel):
    """A QLabel subclass that supports fade-in, fade-out animation and easy message display.
    """
    def __init__(self, parent: QtWidgets.QWidget = None, fade_duration: int = 800):
        super().__init__(parent, visible=False)
        self.fade_duration = fade_duration

        # Setup the label appearance
        self.setFont(QtGui.QFont("Segoe UI", 26, QtGui.QFont.Weight.Bold))
        self.setStyleSheet("""
            QLabel {
                background-color: rgba(60, 60, 60, 180);
                color: rgba(255, 255, 255, 180);
                border-radius: 15px;
                padding: 20px;
            }
        """)
        self.setVisible(False)

        # Setup opacity effect and fade animation
        self.opacity_effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_animation = QtCore.QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(self.fade_duration)
        # Connect finished signal to hide the label once the fade-out completes
        self.fade_animation.finished.connect(self.hide)

        # Timer to start fade out after the message duration
        self.clear_timer = QtCore.QTimer(self, singleShot=True)
        self.clear_timer.timeout.connect(self.start_fade_out)

    def display_message(self, text: str, duration: int = 1500):
        """Display a message with full opacity, then fade out after a delay.

        Args:
            text (str): The message to display.
            duration (int, optional): Duration (in ms) to keep the message before fading out.
                                      Defaults to 1500.
        """
        self.fade_animation.stop()
        self.opacity_effect.setOpacity(1.0)
        self.setText(text)
        self.setVisible(True)
        self.clear_timer.start(duration)

    def start_fade_out(self):
        """Trigger the fade-out animation.
        """
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()


class OverlayWidget(QtWidgets.QWidget):
    """A transparent overlay widget to display input events (keyboard, mouse, scroll) in real-time.
    """
    # Define separate signals for each event type
    keyboard_update_signal = QtCore.pyqtSignal(str)
    mouse_update_signal = QtCore.pyqtSignal(str)
    scroll_update_signal = QtCore.pyqtSignal(str)

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent: QtWidgets.QWidget = None, fade_duration: int = 800):
        """Initialize the overlay widget, set up UI, signal connections, and effects.

        Args:
            parent (QtWidgets.QWidget, optional): Parent widget. Defaults to None.
            fade_duration (int, optional): Duration of fade-out animation in ms. Defaults to 800.
        """
        super().__init__(parent)

        # Store the arguments
        self.fade_duration = fade_duration

        # Initialize setup
        self.__init_attributes()
        self.__init_ui()
        self.__init_signal_connections()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        # Set window flags for a frameless, always-on-top, transparent overlay
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.WindowStaysOnTopHint |
            QtCore.Qt.WindowType.Tool |
            QtCore.Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

        screen = QtWidgets.QApplication.primaryScreen()
        self.setGeometry(screen.availableGeometry())

        self.event_handler = InputEventHandler(self)

    def __init_ui(self):
        """Initialize the UI components.
        """
        # Create Widgets
        # --------------
        # Create a FadeLabel instance for each event type
        self.keyboard_label = FadeLabel(self, fade_duration=self.fade_duration)
        self.mouse_label = FadeLabel(self, fade_duration=self.fade_duration)
        self.scroll_label = FadeLabel(self, fade_duration=self.fade_duration)

        # Add Widgets to Layouts
        # ----------------------
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 80)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.keyboard_label)
        layout.addWidget(self.mouse_label)
        layout.addWidget(self.scroll_label)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        self.keyboard_update_signal.connect(self.keyboard_label.display_message)
        self.mouse_update_signal.connect(self.mouse_label.display_message)
        self.scroll_update_signal.connect(self.scroll_label.display_message)

    # Overridden Methods
    # ------------------
    def show(self):
        """Show the overlay widget and start the event handler.
        """
        self.event_handler.start()
        super().show()

    def close(self):
        """Stop the event handler and close the overlay widget.
        """
        self.event_handler.stop()
        super().close()


class InputEventHandler:
    """Handles keyboard and mouse events and updates the overlay widget accordingly.
    """
    MODIFIER_KEYS = [
        "Ctrl", "Right ctrl",
        "Alt", "Right alt",
        "Shift", "Right shift",
        "Meta",
        "Left windows",
        "Space",
    ]

    # Initialization and Setup
    # ------------------------
    def __init__(self, overlay: OverlayWidget):
        # Store the arguments
        self.overlay = overlay

        # Store the pressed keys and mouse buttons
        self.pressed_keys: set[str] = set()
        self.pressed_mouse_buttons: set[str] = set()

    # Public Methods
    # --------------
    def start(self):
        """Start listening to keyboard and mouse events.
        """
        # Start the keyboard hook
        keyboard.hook(self._keyboard_callback)

        # Start the mouse listener
        self.mouse_listener = mouse.Listener(on_click=self._on_click, on_scroll=self._on_scroll)
        self.mouse_listener.start()

    def stop(self):
        """Stop listening to keyboard and mouse events.
        """
        # Stop the keyboard hook
        keyboard.unhook_all()

        # Stop the mouse listener
        self.mouse_listener.stop()

    # Private Methods
    # ---------------
    def _sort_key(self, key: str) -> Tuple[int, Union[int, str]]:
        """Sort modifier keys by a predefined order and non-modifiers alphabetically.

        Args:
            key (str): The key name.

        Returns:
            Tuple[int, Union[int, str]]: Sorting key tuple.
        """
        try:
            return (0, self.MODIFIER_KEYS.index(key))
        except ValueError:
            return (1, key)

    def _keyboard_callback(self, event: keyboard.KeyboardEvent):
        """Handle keyboard events, updating the pressed keys and the overlay display.

        Args:
            event (keyboard.KeyboardEvent): The keyboard event.
        """
        # Normalize key names
        key_name = event.name.capitalize()

        if event.event_type == keyboard.KEY_UP:
            self.pressed_keys.discard(key_name)
            return

        self.pressed_keys.add(key_name)

        # Sort: modifiers first, then regular keys alphabetically
        sorted_keys = sorted(self.pressed_keys, key=self._sort_key)
        message = " + ".join(sorted_keys)
        self.overlay.keyboard_update_signal.emit(f"⌨️ {message}")

    def _on_click(self, x: int, y: int, button: mouse.Button, pressed: bool):
        """Handle mouse click events and update the overlay.

        Args:
            x (int): The x-coordinate of the click.
            y (int): The y-coordinate of the click.
            button (mouse.Button): The mouse button clicked.
            pressed (bool): True if the button is pressed.
        """
        button_name = button.name.capitalize()

        if not pressed:
            self.pressed_mouse_buttons.discard(button_name)
            return

        self.pressed_mouse_buttons.add(button_name)

        # Update the overlay only if there's any pressed button
        message = " + ".join(sorted(self.pressed_mouse_buttons))
        self.overlay.mouse_update_signal.emit(f"🖱️ {message}")

    def _on_scroll(self, x: int, y: int, dx: int, dy: int):
        """Handle mouse scroll events and update the overlay.

        Args:
            x (int): The x-coordinate during the scroll.
            y (int): The y-coordinate during the scroll.
            dx (int): Horizontal scroll delta.
            dy (int): Vertical scroll delta.
        """
        event_texts = []
        if dx:
            event_texts.append("→" if dx > 0 else "←")
        if dy:
            event_texts.append("↑" if dy > 0 else "↓")
        message = f"🖲️ {', '.join(event_texts)}"
        self.overlay.scroll_update_signal.emit(message)


class Tray(QtWidgets.QSystemTrayIcon):
    """A system tray icon with a context menu to quit the application.
    """

    # Initialization and Setup
    # ------------------------
    def __init__(self, widget: QtWidgets.QWidget, parent: QtWidgets.QWidget = None):
        super().__init__(TablerQIcon.mouse, parent)

        # Store the arguments
        self.widget = widget

        # Initialize setup
        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        """Initialize the UI components.
        """
        # Create Widgets
        # --------------
        self.menu = QtWidgets.QMenu()
        # Add a Quit/Exit action        
        self.exit_action = self.menu.addAction("Exit")
        self.setContextMenu(self.menu)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Show the menu on single or double click
        self.activated.connect(lambda: self.contextMenu().exec_(QtGui.QCursor.pos()))
        self.exit_action.triggered.connect(self.widget.close)
        self.exit_action.triggered.connect(QtWidgets.qApp.quit)


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)

    # Create and show the overlay widget
    overlay_widget = OverlayWidget()
    overlay_widget.show()

    # Create and show the system tray icon with exit functionality
    tray = Tray(overlay_widget)
    tray.show()

    sys.exit(app.exec_())
