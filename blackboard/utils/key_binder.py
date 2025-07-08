# Type Checking Imports
# ---------------------
from typing import Callable, Union, List, Dict, DefaultDict, Tuple, Set

# Standard Imports
# ----------------
from collections import defaultdict

# Third Party Imports
# -------------------
from qtpy import QtCore, QtGui, QtWidgets

# Class Definitions
# -----------------
# TODO: Add support for any QtCore.Qt.ShortcutContext
class Shortcut(QtWidgets.QShortcut):

    _shortcuts: DefaultDict[str, Set[Tuple[QtWidgets.QWidget, Callable]]] = defaultdict(set)

    def __init__(self, key_sequence: QtGui.QKeySequence, parent_widget: QtWidgets.QWidget, callback: Callable,
                 context: QtCore.Qt.ShortcutContext = QtCore.Qt.ShortcutContext.WindowShortcut):
        # NOTE: ambiguousMember, to handle when multiple widgets binding on same key (when used with ScalableView)
        try:
            super().__init__(key_sequence, parent_widget, self.activate, self.activate, QtCore.Qt.ShortcutContext.WindowShortcut)
        except TypeError:
            super().__init__(key_sequence, parent_widget, self.activate, QtCore.Qt.ShortcutContext.WindowShortcut)

        self.key_sequence_str = key_sequence.toString()
        Shortcut._shortcuts[self.key_sequence_str].add((parent_widget, callback, context))

        # TODO: Check if not wrapped by ScalableView
        # # Connect the activated signal of the shortcut to the given function
        # self.activated.connect(self.callback)
        # self.activated.connect(self.check_focus_and_activate)

    # NOTE: Use activate() to handle focused_widget instead of original app.focusWidget()
    #       because it will get only ScalableView that wrapped all inside widgets
    def activate(self):
        for widget, callback, context in Shortcut._shortcuts[self.key_sequence_str]:
            if (
                context == QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut and
                widget.focusWidget() and
                widget.isAncestorOf(QtWidgets.QApplication.instance().focusWidget())
            ):
                callback()
                break
            elif widget.hasFocus():
                callback()
                break


class KeyBinder(QtWidgets.QWidget):

    shortcuts: Dict[str, Shortcut] = {}

    @classmethod
    def bind_key(cls, key_sequence: Union[str, QtGui.QKeySequence], parent_widget: QtWidgets.QWidget, callback: Callable, 
                 context: QtCore.Qt.ShortcutContext = QtCore.Qt.ShortcutContext.WidgetShortcut) -> Shortcut:
        """Bind a given key sequence to a function.

        Args:
            key_sequence (Union[str, QtGui.QKeySequence]): The key sequence as a string or QKeySequence, e.g., "Ctrl+F".
            callback (Callable): The function to be called when the key sequence is activated.
            context (QtCore.Qt.ShortcutContext, optional): The context in which the shortcut is active.
        """
        key_sequence = QtGui.QKeySequence(key_sequence)

        # Create a shortcut with the specified key sequence
        if context in (QtCore.Qt.ShortcutContext.WidgetShortcut, QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut):
            shortcut = Shortcut(key_sequence, parent_widget, callback, context)
        else:
            shortcut = QtWidgets.QShortcut(key_sequence, parent_widget, callback, context=context)

        # Store the shortcut object
        cls.shortcuts[key_sequence.toString()] = shortcut

        return shortcut

    @classmethod
    def unbind_key(cls, key_sequence: Union[str, QtGui.QKeySequence]):
        """Remove a binding for a given key sequence."""
        key = str(key_sequence)
        if key in cls.shortcuts:
            shortcut = cls.shortcuts[key]
            shortcut.activated.disconnect()
            del cls.shortcuts[key]

    @classmethod
    def disable_key(cls, key_sequence: Union[str, QtGui.QKeySequence]):
        """Disable a binding without removing it completely."""
        key = str(key_sequence)
        if key in cls.shortcuts:
            cls.shortcuts[key].setEnabled(False)

    @classmethod
    def enable_key(cls, key_sequence: Union[str, QtGui.QKeySequence]):
        """Enable a previously disabled binding."""
        key = str(key_sequence)
        if key in cls.shortcuts:
            cls.shortcuts[key].setEnabled(True)

    @classmethod
    def get_bound_keys(cls) -> List[str]:
        """List all key sequences that are currently bound."""
        return list(cls.shortcuts.keys())
    
    @classmethod
    def get_bound_keys_detail(cls):
        """Return detailed information about all bound keys."""
        details = []
        for key, shortcut in cls.shortcuts.items():
            detail = {
                'key_sequence': key,
                'callback': shortcut.callback.__name__,
                'context': shortcut.context(),
                'target_widget': shortcut.target_widget
            }
            details.append(detail)

        return details
