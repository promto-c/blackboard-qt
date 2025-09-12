from PyQt5 import QtCore, QtGui, QtWidgets


class SnackToast(QtWidgets.QWidget):
    """Glassmorphism notification toast (bottom-right) with fade+slide and lifeline."""

    closed = QtCore.pyqtSignal(object)  # emits self on close

    def __init__(self,
                 message: str = "Opening file…",
                 duration_ms: int = 3000,
                 action_text: str = "",
                 on_action=None,
                 margin: int = 16,
                 glass_enabled: bool = True,
                 glass_radius: int = 14,
                 glass_blur_radius: float = 24.0,
                 glass_tint: QtGui.QColor = QtGui.QColor(20, 22, 28, 120)):
        """Initialize the toast.

        Args:
            message: Text to display.
            duration_ms: Auto-dismiss duration (>= 800 ms).
            action_text: Optional action button label.
            on_action: Optional callable for action click.
            margin: Gap from screen edges in pixels.
            glass_enabled: Enable blurred backdrop (glassmorphism).
            glass_radius: Corner radius for the glass card.
            glass_blur_radius: Blur strength in device pixels.
            glass_tint: Overlay tint color on top of the blur.
        """
        super().__init__(None)
        self._duration_ms = max(800, duration_ms)
        self._on_action = on_action
        self._margin = max(0, margin)

        self._glass_enabled = glass_enabled
        self._glass_radius = max(0, glass_radius)
        self._glass_blur_radius = max(0.0, float(glass_blur_radius))
        self._glass_tint = glass_tint

        self._start_ts = 0
        self._end_ts = 0

        # Frameless, translucent, topmost, non-activating.
        self.setWindowFlags(
            QtCore.Qt.Tool
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.NoDropShadowWindowHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setWindowOpacity(0.0)

        # --- Background layer (holds blurred/tinted rounded image) ---
        self._bg = QtWidgets.QLabel(self)
        self._bg.setObjectName("bg")
        self._bg.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

        # --- Foreground card content ---
        self._card = QtWidgets.QWidget(self)
        self._card.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)

        icon_lbl = QtWidgets.QLabel(self._card)
        icon_lbl.setPixmap(self._make_icon_pixmap(20))
        icon_lbl.setFixedSize(24, 24)
        icon_lbl.setAlignment(QtCore.Qt.AlignCenter)

        msg_lbl = QtWidgets.QLabel(message, self._card)
        msg_lbl.setObjectName("msg")
        msg_lbl.setWordWrap(False)
        msg_lbl.setAlignment(QtCore.Qt.AlignVCenter)

        self._act_btn = QtWidgets.QPushButton(action_text, self._card)
        self._act_btn.setObjectName("act")
        self._act_btn.setVisible(bool(action_text))
        if action_text and on_action is not None:
            self._act_btn.clicked.connect(self._handle_action)

        # Lifeline bar.
        self._bar = QtWidgets.QProgressBar(self._card)
        self._bar.setRange(0, 1000)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(4)

        # Minimal styling (text + button); bg is painted as blurred image.
        self._card.setStyleSheet("""
            QLabel#msg { color: white; font-weight: 600; letter-spacing: .2px; }
            QPushButton#act {
                color: rgb(180,210,255); background: transparent; border: none;
                padding: 6px 10px; border-radius: 10px;
            }
            QPushButton#act:hover { background: rgba(255,255,255,0.06); }
            QPushButton#act:pressed { background: rgba(255,255,255,0.10); }
            QProgressBar { background: rgba(255,255,255,0.18); border: none; border-radius: 2px; }
            QProgressBar::chunk { background: white; border-radius: 2px; }
        """)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(icon_lbl, 0, QtCore.Qt.AlignVCenter)
        row.addWidget(msg_lbl, 1)
        row.addWidget(self._act_btn, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        v = QtWidgets.QVBoxLayout(self._card)
        v.setContentsMargins(14, 12, 14, 10)
        v.setSpacing(8)
        v.addLayout(row)
        v.addWidget(self._bar)

        # Root layout (bg under card).
        root = QtWidgets.QGridLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._bg, 0, 0)
        root.addWidget(self._card, 0, 0)

        # Animations (no QGraphicsOpacityEffect on live widget).
        self._anim_group = QtCore.QParallelAnimationGroup(self)
        self._fade = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setEasingCurve(QtCore.QEasingCurve.InOutQuad)
        self._slide = QtCore.QPropertyAnimation(self, b"pos", self)
        self._slide.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._anim_group.addAnimation(self._fade)
        self._anim_group.addAnimation(self._slide)

        # Timers.
        self._life_timer = QtCore.QTimer(self)
        self._life_timer.timeout.connect(self._update_bar)
        self._life_timer.setInterval(16)

        self._auto_timer = QtCore.QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self.dismiss)

        # Dismiss on click/Esc.
        self.installEventFilter(self)

    # ---------------- Public API ----------------
    def show_toast(self, at_point: QtCore.QPoint):
        """Show the toast at a target top-left; capture+blur the real background."""
        self._layout_to_natural_size()

        final_pos = QtCore.QPoint(at_point.x(), at_point.y())
        start_pos = QtCore.QPoint(final_pos.x(), final_pos.y() + 10)

        # Prepare glass background from screen under final rect.
        if self._glass_enabled:
            self._update_glass_backdrop(final_pos)

        self.setWindowOpacity(0.0)
        self.move(start_pos)
        self.show()
        self.raise_()

        self._fade.setDuration(160)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)

        self._slide.setDuration(220)
        self._slide.setStartValue(start_pos)
        self._slide.setEndValue(final_pos)

        self._anim_group.start()

        # Lifeline timers.
        self._start_ts = QtCore.QDateTime.currentMSecsSinceEpoch()
        self._end_ts = self._start_ts + self._duration_ms
        self._life_timer.start()
        self._auto_timer.start(self._duration_ms)

    def dismiss(self):
        """Dismiss with exit animation and emit closed(self)."""
        if self._anim_group.state() == QtCore.QAbstractAnimation.Running:
            self._anim_group.stop()
        self._life_timer.stop()

        end_pos = QtCore.QPoint(self.x(), self.y() + 12)
        self._fade.setDuration(160)
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._slide.setDuration(220)
        self._slide.setStartValue(self.pos())
        self._slide.setEndValue(end_pos)

        self._anim_group.finished.connect(self._final_close)
        self._anim_group.start()

    # ---------------- Internals ----------------
    def _final_close(self):
        try:
            self._anim_group.finished.disconnect(self._final_close)
        except TypeError:
            pass
        self.close()
        self.closed.emit(self)

    def _layout_to_natural_size(self):
        """Ensure background and card fill exactly with rounded mask intent."""
        self._card.adjustSize()
        # Give outer widget the same size as card (bg drawn under it).
        self.resize(self._card.size())
        self._bg.resize(self.size())

    def _update_glass_backdrop(self, final_pos: QtCore.QPoint):
        """Grab the pixels under the final rect, blur+tint, and round the corners."""
        screen = QtWidgets.QApplication.screenAt(final_pos) or QtWidgets.QApplication.primaryScreen()
        geo = QtCore.QRect(final_pos, self.size())
        # HiDPI: grab in device pixels, then set devicePixelRatio back.
        dpr = screen.devicePixelRatio()
        grab = screen.grabWindow(0,
                                 int(geo.x() * dpr),
                                 int(geo.y() * dpr),
                                 int(geo.width() * dpr),
                                 int(geo.height() * dpr))
        grab.setDevicePixelRatio(dpr)

        # Blur off-screen (not as a live effect on this widget).
        blurred = self._blur_pixmap(grab, self._glass_blur_radius)

        # Tint and rounded mask.
        final_pm = QtGui.QPixmap(blurred.size())
        final_pm.fill(QtCore.Qt.transparent)

        p = QtGui.QPainter(final_pm)
        p.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform, True)

        path = QtGui.QPainterPath()
        rect = QtCore.QRectF(0, 0, final_pm.width(), final_pm.height())
        radius = float(self._glass_radius)
        path.addRoundedRect(rect, radius, radius)
        p.setClipPath(path)

        # Draw blurred background.
        p.drawPixmap(0, 0, blurred)

        # Overlay tint.
        p.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
        p.fillRect(rect, self._glass_tint)
        p.end()

        self._bg.setPixmap(final_pm)

    def _blur_pixmap(self, pm: QtGui.QPixmap, radius: float) -> QtGui.QPixmap:
        """Blur a pixmap using a QGraphicsBlurEffect rendered off-screen."""
        if radius <= 0.0:
            return pm

        # Render pm into a QGraphicsScene with blur, then grab the result.
        scene = QtWidgets.QGraphicsScene()
        item = QtWidgets.QGraphicsPixmapItem(pm)
        blur = QtWidgets.QGraphicsBlurEffect()
        blur.setBlurRadius(radius)
        item.setGraphicsEffect(blur)
        scene.addItem(item)

        out = QtGui.QImage(pm.size(), QtGui.QImage.Format_ARGB32_Premultiplied)
        out.fill(0)
        painter = QtGui.QPainter(out)
        scene.render(painter, QtCore.QRectF(out.rect()), QtCore.QRectF(pm.rect()))
        painter.end()

        result = QtGui.QPixmap.fromImage(out)
        # Preserve HiDPI scale so it displays crisply.
        result.setDevicePixelRatio(pm.devicePixelRatio())
        return result

    def _update_bar(self):
        now = QtCore.QDateTime.currentMSecsSinceEpoch()
        if now >= self._end_ts:
            self._bar.setValue(1000)
            self._life_timer.stop()
            return
        t = (now - self._start_ts) / float(self._duration_ms)
        self._bar.setValue(int(1000 * max(0.0, min(1.0, t))))

    def _handle_action(self):
        if callable(self._on_action):
            try:
                self._on_action()
            except Exception:
                pass
        self.dismiss()

    def eventFilter(self, obj, event):
        et = event.type()
        if et in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease):
            self.dismiss()
            return True
        if et == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape:
            self.dismiss()
            return True
        return super().eventFilter(obj, event)

    # ---------------- Visual helper ----------------
    def _make_icon_pixmap(self, size: int) -> QtGui.QPixmap:
        pm = QtGui.QPixmap(size, size)
        pm.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(120, 160, 255))
        p.drawEllipse(0, 0, size, size)
        pen = QtGui.QPen(QtGui.QColor(20, 28, 40))
        pen.setWidthF(max(1.2, size * 0.08))
        p.setPen(pen)
        p.drawLine(int(size * 0.30), int(size * 0.55), int(size * 0.70), int(size * 0.45))
        p.end()
        return pm



# -----------------------------------------------------------
# NotificationCenter (manages stacking per active screen)
# -----------------------------------------------------------
class NotificationCenter(QtCore.QObject):
    """A manager that shows and auto-stacks SnackToast on the active display."""

    _instance = None

    def __init__(self,
                 margin: int = 16,
                 gap: int = 8):
        """Initialize the notification center.

        Args:
            margin: Margin from screen edges in pixels.
            gap: Vertical gap between stacked toasts in pixels.
        """
        super().__init__()
        self._margin = max(0, margin)
        self._gap = max(0, gap)
        # Map screen name -> list[SnackToast] (bottom-most is index 0).
        self._stacks = {}

        # React to screen changes (optional reflow safety).
        QtWidgets.QApplication.instance().screenAdded.connect(self._reflow_all)
        QtWidgets.QApplication.instance().screenRemoved.connect(self._reflow_all)

    # ---------------- Singleton ----------------
    @classmethod
    def instance(cls):
        """Return a shared NotificationCenter instance."""
        if cls._instance is None:
            cls._instance = NotificationCenter()
        return cls._instance

    # ---------------- Public API ----------------
    def show(self,
             message: str,
             duration_ms: int = 3000,
             action_text: str = "",
             on_action=None):
        """Show a toast on the active display and auto-stack it.

        Args:
            message: The message to display.
            duration_ms: Auto-dismiss duration in milliseconds.
            action_text: Optional action text.
            on_action: Optional callable for action.
        """
        screen = self._active_screen()
        if screen is None:
            screen = QtWidgets.QApplication.primaryScreen()
        key = screen.name()

        toast = SnackToast(
            message=message,
            duration_ms=duration_ms,
            action_text=action_text,
            on_action=on_action,
            margin=self._margin,
        )
        toast.closed.connect(self._on_toast_closed)

        # Append to the stack for this screen.
        stack = self._stacks.setdefault(key, [])
        stack.append(toast)

        # Compute positions and show all (reflow).
        self._reflow_stack(screen)

        # Show only the new one (others already visible).
        # (show_toast called by _reflow_stack for all to ensure correct geometry on DPI changes)

    # ---------------- Internals ----------------
    def _active_screen(self) -> QtGui.QScreen:
        """Determine the user's active screen (focused window > cursor > primary)."""
        app = QtWidgets.QApplication.instance()
        win = app.activeWindow() or app.focusWindow()
        if win is not None and win.screen() is not None:
            return win.screen()
        screen = QtWidgets.QApplication.screenAt(QtGui.QCursor.pos())
        if screen is not None:
            return screen
        return QtWidgets.QApplication.primaryScreen()

    def _br_slots(self, screen: QtGui.QScreen, count: int):
        """Yield top-left positions for bottom-right aligned toasts, stacked upward."""
        area = screen.availableGeometry()
        x = area.right() - self._margin  # right edge; we'll subtract toast width later
        # First slot sits just above bottom margin, others stack upward.
        for idx in range(count):
            yield (x, area.bottom() - self._margin, idx)

    def _reflow_stack(self, screen: QtGui.QScreen):
        """Position and (re)show all toasts for a given screen."""
        key = screen.name()
        stack = self._stacks.get(key, [])
        if not stack:
            return

        # Measure heights to compute vertical positions.
        # We place bottom-most = last item.
        total = len(stack)
        # Ensure all have correct size hints before positioning.
        for t in stack:
            t.adjustSize()

        # Build final positions (bottom-most last).
        y_cursor = screen.availableGeometry().bottom() - self._margin
        for t in reversed(stack):
            # Each toast's top-left X depends on its width; right-aligned.
            x = screen.availableGeometry().right() - self._margin - t.width()
            y = y_cursor - t.height()
            target = QtCore.QPoint(x, y)
            if not t.isVisible():
                t.show_toast(target)
            else:
                # Animate to new slot if needed.
                if t.pos() != target:
                    self._animate_move(t, target)
            y_cursor = y - self._gap  # move up for next toast

    def _animate_move(self, toast: SnackToast, target: QtCore.QPoint):
        """Animate a toast to a new position when the stack reflows."""
        anim = QtCore.QPropertyAnimation(toast, b"pos", toast)
        anim.setDuration(160)
        anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        anim.setStartValue(toast.pos())
        anim.setEndValue(target)
        # Keep a reference on the widget to prevent GC.
        toast._reflow_anim = anim  # noqa: SLF001 (simple stash)
        anim.start()

    def _on_toast_closed(self, toast: SnackToast):
        """Remove a closed toast and reflow remaining ones."""
        # Find which stack contains it.
        for key, items in list(self._stacks.items()):
            if toast in items:
                items.remove(toast)
                if not items:
                    del self._stacks[key]
                else:
                    # Reflow remaining on that screen.
                    screen = self._screen_by_name(key)
                    if screen is None:
                        screen = QtWidgets.QApplication.primaryScreen()
                    self._reflow_stack(screen)
                break

    def _screen_by_name(self, name: str) -> QtGui.QScreen:
        """Return a QScreen by its name (best effort)."""
        for s in QtWidgets.QApplication.screens():
            if s.name() == name:
                return s
        return None

    def _reflow_all(self, *unused):
        """Reflow all stacks (e.g., when screens change)."""
        for key, items in self._stacks.items():
            if not items:
                continue
            screen = self._screen_by_name(key) or QtWidgets.QApplication.primaryScreen()
            self._reflow_stack(screen)


# -----------------------------------------------------------
# Demo
# -----------------------------------------------------------
def main():
    """Show a simple window with buttons to trigger notifications."""
    import sys

    app = QtWidgets.QApplication(sys.argv)

    root = QtWidgets.QWidget()
    root.setWindowTitle("Active-Display Notifications Demo")
    root.resize(560, 340)

    btn1 = QtWidgets.QPushButton("Notify: Opening file…")
    btn2 = QtWidgets.QPushButton("Notify with Action")
    btn3 = QtWidgets.QPushButton("Burst x5")

    lay = QtWidgets.QVBoxLayout(root)
    lay.addStretch(1)
    lay.addWidget(btn1, 0, QtCore.Qt.AlignHCenter)
    lay.addWidget(btn2, 0, QtCore.Qt.AlignHCenter)
    lay.addWidget(btn3, 0, QtCore.Qt.AlignHCenter)
    lay.addStretch(1)

    center = NotificationCenter.instance()

    def do_basic():
        center.show("Opening file…", duration_ms=2800)

    def do_action():
        center.show(
            "Opening /shots/SH020/plates/…",
            duration_ms=4200,
            action_text="Open Folder",
            on_action=lambda: QtGui.QDesktopServices.openUrl(
                QtCore.QUrl.fromLocalFile("/shots/SH020/plates")
            ),
        )

    def do_burst():
        for i in range(5):
            center.show(f"Notification {i+1}", duration_ms=2000 + i * 300)

    btn1.clicked.connect(do_basic)
    btn2.clicked.connect(do_action)
    btn3.clicked.connect(do_burst)

    root.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
