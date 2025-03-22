# Third Party Imports
# -------------------
from PyQt5 import QtCore, QtGui, QtWidgets

import keyboard
from pynput import mouse


# Class Definitions
# -----------------
# TODO: Handle keyboard and mouse events simultaneously.
# TODO: Keep displayed while the event is still pressed.
class OverlayWidget(QtWidgets.QWidget):
    """A transparent overlay widget to display input events (keyboard, mouse) in real-time.
    """
    # Signal to update the overlay from global hook threads
    update_signal = QtCore.pyqtSignal(str)

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent: QtWidgets.QWidget = None, fade_duration: int = 800):
        """Initialize the widget and set up the UI, signal connections, and icons.
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
            QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        screen = QtWidgets.QApplication.primaryScreen()
        self.setGeometry(screen.availableGeometry())

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Create Widgets
        # --------------
        # Label for displaying messages (key pressed, mouse button, scroll, etc.)
        self.label = QtWidgets.QLabel(self)
        self.label.setFont(QtGui.QFont("Segoe UI", 26, QtGui.QFont.Weight.Bold))
        self.label.setStyleSheet("""
            QLabel {
                background-color: rgba(60, 60, 60, 180);
                color: rgba(255, 255, 255, 180);
                border-radius: 15px;
                padding: 20px;
            }
        """)

        # Set up an opacity effect for fade-out animation.
        self.opacity_effect = QtWidgets.QGraphicsOpacityEffect(self.label)
        self.label.setGraphicsEffect(self.opacity_effect)
        self.fade_animation = QtCore.QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(self.fade_duration)

        # Timer to clear the message and trigger fade-out.
        self.clear_timer = QtCore.QTimer(self, singleShot=True)
        self.clear_timer.timeout.connect(self.start_fade_out)

        # Add Widgets to Layouts
        # ----------------------
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 80)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.label)

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect update signal to the display method
        self.update_signal.connect(self.show_message)

    # Public Methods
    # --------------
    def show_message(self, text: str, duration: int = 1500):
        """Display a new message immediately at full opacity and restart the clear timer.
        
        Args:
            text (str): The message to display.
            duration (int): The duration in milliseconds to keep the message visible.
        """
        self.fade_animation.stop()
        self.opacity_effect.setOpacity(1.0)
        self.label.setText(text)
        # Restart clear timer (message stays visible for 1.5 seconds)
        self.clear_timer.start(duration)

    def start_fade_out(self):
        """Animate the fade-out effect from full opacity to transparent.
        """
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()


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
        self.overlay = overlay
        self.pressed_keys: set[str] = set()

    # Public Methods
    # --------------
    def keyboard_callback(self, event: keyboard.KeyboardEvent):
        """Callback for keyboard events.
        
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
        sorted_keys = sorted(self.pressed_keys, key=self.__sort_key)
        message = " + ".join(sorted_keys)
        self.overlay.update_signal.emit(f"⌨️ {message}")

    def on_click(self, x: int, y: int, button: mouse.Button, pressed: bool):
        """Callback for mouse click events.
        
        Args:
            x (int): The x-coordinate of the click.
            y (int): The y-coordinate of the click.
            button (mouse.Button): The mouse button clicked.
            pressed (bool): True if the button is pressed.
        """
        if pressed:
            message = f"🖱️ {button.name.capitalize()}"
            self.overlay.update_signal.emit(message)

    def on_scroll(self, x: int, y: int, dx: int, dy: int):
        """Callback for mouse scroll events.
        
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
        self.overlay.update_signal.emit(message)

    # Private Methods
    # ---------------
    def __sort_key(self, key: str):
        """Sorting logic: Ensure modifiers are sorted based on MODIFIER_KEYS, others alphabetically.
        """
        try:
            return (0, self.MODIFIER_KEYS.index(key))  # Modifier keys by predefined order
        except ValueError:
            return (1, key)  # Non-modifier keys sorted alphabetically


class KeyboardHookThread(QtCore.QThread):
    """QThread to run the keyboard hook in a separate thread.
    """
    def __init__(self, event_handler: InputEventHandler, parent: QtCore.QObject = None):
        super().__init__(parent)
        self.event_handler = event_handler

    def run(self):
        # Register the keyboard hook; this will run indefinitely.
        keyboard.hook(self.event_handler.keyboard_callback)
        keyboard.wait()  # Keeps the thread alive


class MouseHookThread(QtCore.QThread):
    """QThread to run the mouse listener in a separate thread.
    """
    def __init__(self, event_handler: InputEventHandler, parent: QtCore.QObject = None):
        super().__init__(parent)
        self.event_handler = event_handler

    def run(self):
        # Use pynput's mouse listener to handle click and scroll events.
        with mouse.Listener(
            on_click=self.event_handler.on_click,
            on_scroll=self.event_handler.on_scroll
        ) as listener:
            listener.join()


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    overlay_widget = OverlayWidget()
    overlay_widget.show()

    # Create an event handler instance with a reference to the overlay widget.
    event_handler = InputEventHandler(overlay_widget)

    # Start the keyboard hook in a QThread.
    keyboard_thread = KeyboardHookThread(event_handler)
    keyboard_thread.start()

    # Start the mouse listener in a QThread.
    mouse_thread = MouseHookThread(event_handler)
    mouse_thread.start()

    sys.exit(app.exec_())
