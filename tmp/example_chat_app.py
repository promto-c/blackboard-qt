# Standard Library Imports
import sys
import re
from difflib import SequenceMatcher

# Third Party Imports
from PyQt5 import QtCore, QtGui, QtWidgets


def apply_dark_theme(app: QtWidgets.QApplication):
    """Apply a dark Fusion palette to the application."""
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    # Base colors
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(30, 30, 30))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(25, 25, 25))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(35, 35, 35))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(50, 50, 50))
    palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(220, 220, 220))
    # Text
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(45, 45, 45))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor(255, 0, 0))
    # Links
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    # Highlights
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(30, 30, 30))
    app.setPalette(palette)


class ContactItem(QtWidgets.QWidget):
    """Custom widget for contacts list items."""
    def __init__(self, avatar: QtGui.QPixmap, name: str, snippet: str, timestamp: str):
        super().__init__()
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        # Avatar
        label_avatar = QtWidgets.QLabel()
        label_avatar.setPixmap(avatar.scaled(40, 40, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        layout.addWidget(label_avatar)
        # Name & snippet
        text_container = QtWidgets.QVBoxLayout()
        lbl_name = QtWidgets.QLabel(name)
        lbl_name.setStyleSheet("font-weight:bold; color:white;")
        text_container.addWidget(lbl_name)
        lbl_snip = QtWidgets.QLabel(snippet)
        lbl_snip.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        text_container.addWidget(lbl_snip)
        layout.addLayout(text_container)
        layout.addStretch()
        # Timestamp
        lbl_time = QtWidgets.QLabel(timestamp)
        lbl_time.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(lbl_time)


class ChatBubble(QtWidgets.QWidget):
    """Widget representing a chat bubble with highlight capability."""
    def __init__(self, text: str, is_sender: bool = False):
        super().__init__()
        self.original_text = text
        self.is_sender = is_sender
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        self.bubble_label = QtWidgets.QLabel()
        self.bubble_label.setWordWrap(True)
        self.bubble_label.setMaximumWidth(400)
        self.bubble_label.setTextFormat(QtCore.Qt.RichText)
        self.set_unhighlighted()
        if is_sender:
            layout.addStretch()
            layout.addWidget(self.bubble_label)
        else:
            layout.addWidget(self.bubble_label)
            layout.addStretch()

    def set_unhighlighted(self):
        # Set the bubble text without highlights
        style = "background-color: #2E5ACC; color: white; padding:8px; border-radius:12px;" if self.is_sender else \
                "background-color: #3A3A3A; color: white; padding:8px; border-radius:12px;"
        self.bubble_label.setStyleSheet(style)
        # Escape HTML to avoid injection
        safe_text = QtCore.QCoreApplication.translate("", self.original_text)
        self.bubble_label.setText(safe_text)

    def highlight_exact(self, pattern: str):
        # Highlight all case-insensitive occurrences of pattern
        def repl(match): return f"<span style='background-color: #FFF475; color:black;'>{match.group(0)}</span>"
        regex = re.compile(re.escape(pattern), re.IGNORECASE)
        highlighted = regex.sub(repl, self.original_text)
        style = "background-color: #2E5ACC; color: white; padding:8px; border-radius:12px;" if self.is_sender else \
                "background-color: #3A3A3A; color: white; padding:8px; border-radius:12px;"
        self.bubble_label.setStyleSheet(style)
        self.bubble_label.setText(highlighted)

    def highlight_fuzzy(self, pattern: str):
        text = self.original_text
        m = len(pattern)
        best_ratio = 0
        best_start = 0
        # If pattern longer than text, compare whole strings
        if m >= len(text):
            ratio = SequenceMatcher(None, pattern.lower(), text.lower()).ratio()
            if ratio > 0.5:
                best_ratio = ratio
                best_start = 0
                best_len = len(text)
            else:
                return  # no sufficient match
        else:
            # Slide a window of length m over text
            for i in range(len(text) - m + 1):
                substring = text[i:i+m]
                ratio = SequenceMatcher(None, pattern.lower(), substring.lower()).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_start = i
            best_len = m
        # Highlight if above threshold
        if best_ratio < 0.6:
            return
        # Construct highlighted HTML
        start = best_start
        end = start + best_len
        before = QtCore.QCoreApplication.translate("", text[:start])
        match = QtCore.QCoreApplication.translate("", text[start:end])
        after = QtCore.QCoreApplication.translate("", text[end:])
        highlighted = (
            f"{before}<span style='background-color: #FFB347; color:black;'>{match}</span>{after}"
        )
        style = "background-color: #2E5ACC; color: white; padding:8px; border-radius:12px;" if self.is_sender else \
                "background-color: #3A3A3A; color: white; padding:8px; border-radius:12px;"
        self.bubble_label.setStyleSheet(style)
        self.bubble_label.setText(highlighted)


def load_avatar(path: str) -> QtGui.QPixmap:
    try:
        pix = QtGui.QPixmap(path)
        if pix.isNull():
            raise Exception
        return pix
    except Exception:
        placeholder = QtGui.QPixmap(40, 40)
        placeholder.fill(QtGui.QColor(100, 100, 100))
        return placeholder


class ChatWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dark Chat")
        self.resize(1000, 600)
        # State
        self.current_contact = None
        self.messages = {
            "Alice": [("Alice", "Hey, are we on for tomorrow?", "11:10"),
                      ("Me", "Yes, 10 AM works.", "11:12"),
                      ("Alice", "Let me know if anything changes.", "11:15")],
            "Bob": [("Bob", "Did you see the update?", "10:30"),
                    ("Me", "Not yet, send me the link.", "10:32"),
                    ("Bob", "Sure, it's on slack.", "10:35")],
        }
        self.contacts = ["Alice", "Bob"]
        # UI
        self.__init_ui()
        self.__init_signals()

    def __init_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        # Left panel
        self.left_panel = QtWidgets.QFrame()
        self.left_panel.setFixedWidth(280)
        self.left_panel.setStyleSheet("background-color: #2A2A2A;")
        left_layout = QtWidgets.QVBoxLayout(self.left_panel)
        # Header
        lbl_header = QtWidgets.QLabel("Chats")
        lbl_header.setStyleSheet("font-size:18px; font-weight:bold; color:white;")
        left_layout.addWidget(lbl_header)
        # Search in contacts (optional, not implemented)
        search_contacts = QtWidgets.QLineEdit()
        search_contacts.setPlaceholderText("Search…")
        search_contacts.setStyleSheet(
            "background-color:#1E1E1E; border-radius:6px; padding:6px; color:white;"
        )
        left_layout.addWidget(search_contacts)
        # Contacts list
        self.contact_list = QtWidgets.QListWidget()
        self.contact_list.setFrameShape(QtWidgets.QFrame.NoFrame)
        left_layout.addWidget(self.contact_list)
        main_layout.addWidget(self.left_panel)

        # Right panel
        self.right_panel = QtWidgets.QFrame()
        self.right_panel.setStyleSheet("background-color: #1E1E1E;")
        right_layout = QtWidgets.QVBoxLayout(self.right_panel)
        # Chat header
        header_layout = QtWidgets.QHBoxLayout()
        self.btn_back = QtWidgets.QPushButton("←")
        self.btn_back.setStyleSheet("color:white; background:none; border:none; font-size:18px;")
        self.btn_back.setVisible(False)
        self.lbl_contact = QtWidgets.QLabel("")
        self.lbl_contact.setStyleSheet("font-size:16px; color:white;")
        header_layout.addWidget(self.btn_back)
        header_layout.addWidget(self.lbl_contact)
        header_layout.addStretch()
        self.btn_settings = QtWidgets.QPushButton()
        self.btn_settings.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView))
        self.btn_settings.setStyleSheet("color:white; background:none; border:none;")
        header_layout.addWidget(self.btn_settings)
        right_layout.addLayout(header_layout)
        # Search bar for chat
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search chat…")
        self.search_bar.setStyleSheet(
            "background-color:#3A3A3A; color:white; border-radius:6px; padding:6px;"
        )
        self.search_bar.setVisible(False)
        right_layout.addWidget(self.search_bar)
        # Messages area
        self.message_area = QtWidgets.QScrollArea()
        self.message_area.setWidgetResizable(True)
        self.message_container = QtWidgets.QWidget()
        self.message_layout = QtWidgets.QVBoxLayout(self.message_container)
        self.message_layout.addStretch()
        self.message_area.setWidget(self.message_container)
        right_layout.addWidget(self.message_area)
        # Input
        input_layout = QtWidgets.QHBoxLayout()
        self.input_field = QtWidgets.QLineEdit()
        self.input_field.setPlaceholderText("Type a message…")
        self.input_field.setStyleSheet("background-color:#2A2A2A; color:white; border-radius:6px; padding:8px;")
        self.btn_send = QtWidgets.QPushButton("▶")
        self.btn_send.setStyleSheet("background-color:#2E5ACC; color:white; border:none; padding:8px; border-radius:6px;")
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.btn_send)
        right_layout.addLayout(input_layout)
        main_layout.addWidget(self.right_panel)

        # Populate contacts with stored data
        for name in self.contacts:
            avatar = load_avatar("/path/to/avatar.png")
            last_msg = self.messages[name][-1][1]
            last_time = self.messages[name][-1][2]
            item = QtWidgets.QListWidgetItem()
            # store name in item for easy retrieval
            item.setData(QtCore.Qt.UserRole, name)
            widget = ContactItem(avatar, name, last_msg, last_time)
            item.setSizeHint(widget.sizeHint())
            self.contact_list.addItem(item)
            self.contact_list.setItemWidget(item, widget)

    def __init_signals(self):
        self.contact_list.itemClicked.connect(self.open_chat)
        self.btn_back.clicked.connect(self.close_chat)
        self.search_bar.textChanged.connect(self.perform_search)
        self.btn_send.clicked.connect(self.send_message)
        shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+F"), self)
        shortcut.activated.connect(self.toggle_search)

    def toggle_search(self):
        # Show or hide search bar and clear highlights when hiding
        visible = self.search_bar.isVisible()
        if visible:
            self.search_bar.clear()
            self.search_bar.setVisible(False)
            self.clear_highlights()
        else:
            self.search_bar.setVisible(True)
            self.search_bar.setFocus()

    def perform_search(self, text: str):
        if not self.current_contact:
            return
        # Clear previous highlights
        self.clear_highlights()
        if text.strip() == "":
            return
        # Apply fuzzy highlight for each bubble
        for i in range(self.message_layout.count() - 1):
            widget = self.message_layout.itemAt(i).widget()
            if isinstance(widget, ChatBubble):
                widget.highlight_fuzzy(text)

    def clear_highlights(self):
        # Reset all bubbles to original text
        for i in range(self.message_layout.count() - 1):
            widget = self.message_layout.itemAt(i).widget()
            if isinstance(widget, ChatBubble):
                widget.set_unhighlighted()

    def send_message(self):
        if not self.current_contact:
            return
        text = self.input_field.text().strip()
        if not text:
            return
        # Append to data
        self.messages.setdefault(self.current_contact, []).append(("Me", text, QtCore.QTime.currentTime().toString("HH:mm")))
        # Add bubble
        bubble = ChatBubble(text, is_sender=True)
        self.message_layout.insertWidget(self.message_layout.count() - 1, bubble)
        self.input_field.clear()
        QtCore.QTimer.singleShot(0, lambda: self.message_area.verticalScrollBar().setValue(
            self.message_area.verticalScrollBar().maximum()))

    def open_chat(self, item: QtWidgets.QListWidgetItem):
        name = item.data(QtCore.Qt.UserRole)
        self.current_contact = name
        self.lbl_contact.setText(name)
        # Show back button in narrow view
        if self.width() < 600:
            self.btn_back.setVisible(True)
            self.left_panel.setVisible(False)
        # Hide search bar and clear input
        self.search_bar.setVisible(False)
        self.search_bar.clear()
        # Clear previous messages
        for i in reversed(range(self.message_layout.count() - 1)):
            widget = self.message_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        # Add chat bubbles
        for sender, text, _ in self.messages.get(name, []):
            bubble = ChatBubble(text, is_sender=(sender == "Me"))
            self.message_layout.insertWidget(self.message_layout.count() - 1, bubble)
        # Scroll down
        QtCore.QTimer.singleShot(0, lambda: self.message_area.verticalScrollBar().setValue(
            self.message_area.verticalScrollBar().maximum()))

    def close_chat(self):
        self.current_contact = None
        self.lbl_contact.clear()
        self.btn_back.setVisible(False)
        self.left_panel.setVisible(True)
        # hide search
        self.search_bar.setVisible(False)
        self.search_bar.clear()
        # clear messages
        for i in reversed(range(self.message_layout.count() - 1)):
            widget = self.message_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        # Ensure shortcut works even if focus is elsewhere
        if event.matches(QtGui.QKeySequence.Find):
            self.toggle_search()
        else:
            super().keyPressEvent(event)


def main():
    app = QtWidgets.QApplication(sys.argv)
    apply_dark_theme(app)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
