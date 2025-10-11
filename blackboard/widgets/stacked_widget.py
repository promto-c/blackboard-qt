# Type Checking Imports
# ---------------------
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from typing import Optional

# Standard Library Imports
# ------------------------
from enum import Enum

# Third Party Imports
# -------------------
from qtpy import QtCore, QtGui, QtWidgets

# Local Imports
# -------------
from blackboard.utils.typed_prop import TypedProp


# Public Enums
# ------------
class TransitionMode(str, Enum):
    """Supported animation styles for TransitionStackedWidget transitions."""

    SLIDE = "slide"
    FADE = "fade"


class Direction(str, Enum):
    """Supported movement directions for slide transitions."""

    AUTO = "auto"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


# Class Definitions
# -----------------
class TransitionStackedWidget(QtWidgets.QStackedWidget):
    """A QStackedWidget with animated transitions.

    Supports:
      * Slide: left, right, up, down (or auto by index delta)
      * Fade: cross-fade between pages
      * Interrupt-safe: new transition cancels the previous one cleanly
      * Resizing: keeps overlays aligned during window resizes

    Public API:
      set_current_index_animated(index, *, mode="slide"|"fade",
                                 direction="auto"|"left"|"right"|"up"|"down",
                                 duration_ms=260, easing=QEasingCurve.OutCubic)
      set_current_widget_animated(widget, **same_kwargs)
      next_animated(mode="slide", duration_ms=260)
      previous_animated(mode="slide", duration_ms=260)
    """

    # Public API enums / aliases
    TransitionMode = TransitionMode
    Direction = Direction

    # Properties with type validation and defaults
    transition_mode: TransitionMode = TypedProp(default=TransitionMode.SLIDE)
    duration_ms: int = TypedProp(default=260, validator=lambda v: v >= 0)
    easing_curve: QtCore.QEasingCurve.Type | None = TypedProp(default=QtCore.QEasingCurve.OutCubic)

    # Initialization and Setup
    # ------------------------
    def __init__(
        self,
        parent: QtWidgets.QWidget = None,
        *,
        transition_mode: TransitionMode = transition_mode._default,
        duration_ms: int = duration_ms._default,
        easing_curve: QtCore.QEasingCurve | None = easing_curve._default,
    ):
        """Initialize the widget and internal state."""
        super().__init__(parent)
        self._anim_group: Optional[QtCore.QParallelAnimationGroup] = None

        self._prev_widget: Optional[QtWidgets.QWidget] = None
        self._next_widget: Optional[QtWidgets.QWidget] = None
        self._prev_effect: Optional[QtWidgets.QGraphicsOpacityEffect] = None
        self._next_effect: Optional[QtWidgets.QGraphicsOpacityEffect] = None
        self._pending_set_index = -1

        # Instance defaults for transition behaviour
        self.transition_mode = transition_mode
        self.duration_ms = duration_ms
        self.easing_curve = easing_curve

        # For geometry sync while animating
        self._needs_geom_sync = False

    # Public Methods
    # --------------
    def get_active_index(self) -> int:
        """Return the index that is currently considered active.

        If an animation is in progress and a target index is pending,
        treat the pending index as the active one. Otherwise, return the
        actual current index of the widget.
        """
        if self.is_animating and 0 <= self._pending_set_index < self.count():
            return self._pending_set_index
        return self.currentIndex()

    def set_current_index_animated(
        self,
        index: int,
        *,
        mode: TransitionMode | None = None,
        direction: Direction = Direction.AUTO,
    ):
        """Animate to the given page index.

        Args:
          index: Target page index.
          mode: Transition mode. Defaults to the widget's
            configured `transition_mode` when omitted.
          direction: Slide direction (AUTO/LEFT/RIGHT/UP/DOWN).
        """
        mode = mode or self.transition_mode

        # If a transition is running, stop it and clean up first.
        if self.is_animating:
            self._finalize_animation()

        self._prev_widget = self.currentWidget()
        self._next_widget = self.widget(index)
        self._pending_set_index = index

        if mode == TransitionMode.FADE:
            self._start_fade()
        elif mode == TransitionMode.SLIDE:
            if direction == Direction.AUTO:
                direction = self._auto_direction_for(index)
            self._start_slide(direction)

    def set_current_widget_animated(
        self,
        widget: QtWidgets.QWidget,
        *,
        mode: TransitionMode | None = None,
        direction: Direction = Direction.AUTO,
    ):
        """Animate to the given page widget.

        Args:
          widget: Target page widget (must already be added).
          mode: Transition mode.
          direction: Slide direction.
          duration_ms: Animation duration in milliseconds.
          easing: Easing curve.
        """
        idx = self.indexOf(widget)
        self.set_current_index_animated(
            idx,
            mode=mode,
            direction=direction,
        )

    def next_animated(
        self,
        *,
        mode: TransitionMode | None = None,
    ):
        """Animate to the next page (slide left by default)."""
        count = self.count()
        if count == 0:
            return
        base_index = self.get_active_index()
        target = (base_index + 1) % count
        self.set_current_index_animated(
            target,
            mode=mode,
            direction=Direction.LEFT,
        )

    def previous_animated(
        self,
        *,
        mode: TransitionMode | None = None,
    ):
        """Animate to the previous page (slide right by default)."""
        count = self.count()
        if count == 0:
            return
        base_index = self.get_active_index()
        target = (base_index - 1) % count
        self.set_current_index_animated(
            target,
            mode=mode,
            direction=Direction.RIGHT,
        )

    # Utility Methods
    # ---------------
    @property
    def is_animating(self) -> bool:
        """Return whether an animation is currently running."""
        return self._anim_group is not None

    # Private Methods
    # ---------------
    def _auto_direction_for(self, target_index: int) -> Direction:
        """Infer a sensible slide direction from index delta."""
        return Direction.LEFT if target_index > self.currentIndex() else Direction.RIGHT

    def _prepare_widgets_for_overlay(self):
        """Place prev/next widgets as temporary overlays for animation."""
        rect = self.rect()
        if not self._prev_widget or not self._next_widget:
            return

        # Ensure both target widgets are visible and on our coordinate space
        for w in (self._prev_widget, self._next_widget):
            w.setParent(self)
            w.setVisible(True)
            w.raise_()
            w.setGeometry(rect)

        # Disable layout effects during animation to avoid relayout jitter
        self._needs_geom_sync = True

    def _start_fade(self):
        """Start a cross-fade animation."""
        if not self._prev_widget or not self._next_widget:
            return

        self._prepare_widgets_for_overlay()

        # Graphics effects (opacity)
        self._prev_effect = QtWidgets.QGraphicsOpacityEffect(self._prev_widget)
        self._next_effect = QtWidgets.QGraphicsOpacityEffect(self._next_widget)
        self._prev_widget.setGraphicsEffect(self._prev_effect)
        self._next_widget.setGraphicsEffect(self._next_effect)

        self._prev_effect.setOpacity(1.0)
        self._next_effect.setOpacity(0.0)

        # Animations
        group = QtCore.QParallelAnimationGroup(self)

        fade_out = QtCore.QPropertyAnimation(self._prev_effect, b"opacity", self)
        fade_out.setDuration(self.duration_ms)
        fade_out.setEasingCurve(self.easing_curve)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)

        fade_in = QtCore.QPropertyAnimation(self._next_effect, b"opacity", self)
        fade_in.setDuration(self.duration_ms)
        fade_in.setEasingCurve(self.easing_curve)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)

        group.addAnimation(fade_out)
        group.addAnimation(fade_in)

        # Lifetime managed manually — do NOT use DeleteWhenStopped
        self._anim_group = group
        self._anim_group.finished.connect(self._finalize_animation)
        self._anim_group.start()

    def _start_slide(self, direction: Direction):
        """Start a slide animation in the given direction."""
        if not self._prev_widget or not self._next_widget:
            return

        self._prepare_widgets_for_overlay()
        rect = self.rect()

        # Compute start positions
        prev_start = rect.topLeft()
        if direction == Direction.LEFT:
            next_start = QtCore.QPoint(rect.width(), 0)
            delta_prev = QtCore.QPoint(-rect.width(), 0)
        elif direction == Direction.RIGHT:
            next_start = QtCore.QPoint(-rect.width(), 0)
            delta_prev = QtCore.QPoint(rect.width(), 0)
        elif direction == Direction.UP:
            next_start = QtCore.QPoint(0, rect.height())
            delta_prev = QtCore.QPoint(0, -rect.height())
        else:  # Direction.DOWN
            next_start = QtCore.QPoint(0, -rect.height())
            delta_prev = QtCore.QPoint(0, rect.height())

        self._next_widget.move(next_start)
        self._prev_widget.move(prev_start)

        # Animations (geometry.pos)
        group = QtCore.QParallelAnimationGroup(self)

        prev_anim = QtCore.QPropertyAnimation(self._prev_widget, b"pos", self)
        prev_anim.setDuration(self.duration_ms)
        prev_anim.setEasingCurve(self.easing_curve)
        prev_anim.setStartValue(prev_start)
        prev_anim.setEndValue(prev_start + delta_prev)

        next_anim = QtCore.QPropertyAnimation(self._next_widget, b"pos", self)
        next_anim.setDuration(self.duration_ms)
        next_anim.setEasingCurve(self.easing_curve)
        next_anim.setStartValue(next_start)
        next_anim.setEndValue(QtCore.QPoint(0, 0))

        group.addAnimation(prev_anim)
        group.addAnimation(next_anim)

        # Lifetime managed manually — do NOT use DeleteWhenStopped
        self._anim_group = group
        self._anim_group.finished.connect(self._finalize_animation)
        self._anim_group.start()

    def _finalize_animation(self):
        """Perform final cleanup after animation ends.
        """
        # Switch the "real" current index once the visual is done.
        self.setCurrentIndex(self._pending_set_index)
        self._pending_set_index = -1

        # Remove effects
        for widget in (self._prev_widget, self._next_widget):
            if widget is None:
                continue
            widget.setGraphicsEffect(None)
            widget = None

        # Reset pointers
        self._prev_effect = None
        self._next_effect = None
        self._needs_geom_sync = False

        # Safely dispose the current animation group
        self._anim_group.stop()
        self._anim_group.deleteLater()
        self._anim_group = None

    # Overridden Methods
    # ------------------
    @override
    def resizeEvent(self, event: QtGui.QResizeEvent):
        """Keep overlays aligned while resizing.
        """
        super().resizeEvent(event)
        if self._needs_geom_sync and (self._prev_widget or self._next_widget):
            rect = self.rect()
            if self._prev_widget:
                self._prev_widget.setFixedSize(rect.size())
            if self._next_widget:
                self._next_widget.setFixedSize(rect.size())


# Demo / Example Usage
# --------------------
class _DemoPage(QtWidgets.QWidget):
    """Simple colored page with a label and navigation buttons."""

    def __init__(self, color: QtGui.QColor, text: str, parent: QtWidgets.QWidget = None):
        """Initialize the page widget.

        Args:
          color: Background color.
          text: Title text to display.
          parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(QtGui.QPalette.Window, color)
        self.setPalette(pal)

        title = QtWidgets.QLabel(text)
        title.setStyleSheet("font-size: 28px; font-weight: 600; color: white;")
        title.setAlignment(QtCore.Qt.AlignCenter)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(title)


def main():
    """Create the application and show a demo with animated transitions."""
    import sys

    app = QtWidgets.QApplication(sys.argv)

    w = QtWidgets.QWidget()
    w.setWindowTitle("TransitionStackedWidget Demo")
    w.resize(720, 420)

    stacked = TransitionStackedWidget()

    # Pages without their own buttons
    p1 = _DemoPage(QtGui.QColor("#1e293b"), "Page 1")
    p2 = _DemoPage(QtGui.QColor("#0f766e"), "Page 2")
    p3 = _DemoPage(QtGui.QColor("#7c3aed"), "Page 3")

    stacked.addWidget(p1)
    stacked.addWidget(p2)
    stacked.addWidget(p3)

    # --- Static Control Bar (always visible) ---
    btn_prev = QtWidgets.QPushButton("◀ Prev")
    btn_next = QtWidgets.QPushButton("Next ▶")
    btn_fade_prev = QtWidgets.QPushButton("◀ Fade")
    btn_fade_next = QtWidgets.QPushButton("Fade ▶")

    control_bar = QtWidgets.QHBoxLayout()
    control_bar.addStretch(1)
    control_bar.addWidget(btn_prev)
    control_bar.addWidget(btn_fade_prev)
    control_bar.addWidget(btn_fade_next)
    control_bar.addWidget(btn_next)
    control_bar.addStretch(1)

    # Connect static buttons
    btn_prev.clicked.connect(lambda: stacked.previous_animated())
    btn_next.clicked.connect(lambda: stacked.next_animated())
    btn_fade_prev.clicked.connect(lambda: stacked.previous_animated(mode=TransitionMode.FADE))
    btn_fade_next.clicked.connect(lambda: stacked.next_animated(mode=TransitionMode.FADE))

    # --- Layout ---
    outer = QtWidgets.QVBoxLayout(w)
    outer.addWidget(stacked, stretch=1)
    outer.addLayout(control_bar)

    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
