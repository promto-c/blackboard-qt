# Type Checking Imports
# ---------------------
from typing import Optional, Generator, Deque, Dict, Any

# Standard Library Imports
# ------------------------
from itertools import islice
from collections import deque

# Third Party Imports
# -------------------
from qtpy import QtCore

# Local Imports
# -------------
from blackboard.utils.thread_pool import ThreadPoolManager, GeneratorWorker
from blackboard.widgets.button import DataFetchingButtons


# Class Definitions
# -----------------
class DataFetcher(QtCore.QObject):
    """A class to handle data fetching logic separately from the UI.

    Attributes:
        generator (Optional[Generator]): The data generator.
        has_more_items_to_fetch (bool): Indicates if there is more data to fetch.
    """

    DEFAULT_BATCH_SIZE = 50

    data_fetched = QtCore.Signal(dict)
    started = QtCore.Signal()
    finished = QtCore.Signal()
    loaded_all = QtCore.Signal()

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent=None):
        super().__init__(parent)

        # Initialize setup
        self.__init_attributes()

    def __init_attributes(self):
        """Initialize the attributes.
        """
        self.generator = None
        self.has_more_items_to_fetch = False
        # NOTE: A queue (using deque or list) is used instead of a single task object to store current tasks. 
        #       This approach avoids issues with concurrent task handling, ensuring each task is stopped 
        #       before starting a new one, and prevents old tasks from running after a new task begins.
        self._current_tasks: Deque[GeneratorWorker] = deque()

    # Public Methods
    # --------------
    def set_generator(self, generator: Generator):
        """Set the data generator."""
        self.stop_fetch()
        self.generator = generator
        self.has_more_items_to_fetch = True

    def fetch(self, batch_size: int):
        """Fetch more data in batches."""
        self._fetch_data(batch_size)

    def fetch_more(self):
        """Fetch more data in batches."""
        self._fetch_data(self.DEFAULT_BATCH_SIZE)

    def fetch_all(self):
        """Fetch all remaining data."""
        self._fetch_data()

    def pause_fetch(self):
        """Pause the current data fetching task."""
        while self._current_tasks:
            task = self._current_tasks.popleft()
            task.pause()

    def stop_fetch(self):
        """Stop the current data fetching task."""
        while self._current_tasks:
            task = self._current_tasks.popleft()
            task.result.disconnect()
            task.stop()

    # Private Methods
    # ---------------
    def _fetch_data(self, batch_size: Optional[int] = None):
        """Fetch more data using the generator.

        Args:
            batch_size (Optional[int]): The batch size to fetch. If None, fetch all remaining data.
        """
        if self._current_tasks or not self.has_more_items_to_fetch:
            return

        items_to_fetch = islice(self.generator, batch_size) if batch_size else self.generator

        # Create the current_task
        task = GeneratorWorker(items_to_fetch, desired_size=batch_size)
        # Connect signals
        task.result.connect(self._on_data_fetched)
        task.started.connect(self.started.emit)
        task.finished.connect(self._on_task_finished)
        task.loaded_all.connect(self._handle_no_more_items)

        # Start the task
        ThreadPoolManager.thread_pool().start(task.run)
        self._current_tasks.append(task)

    def _on_data_fetched(self, data: Dict[Any, Any]):
        # NOTE: Prevents data from stopped tasks from incorrectly triggering further actions
        if self.sender() not in self._current_tasks:
            return
        self.data_fetched.emit(data)

    def _on_task_finished(self):
        if self.sender() in self._current_tasks:
            self._current_tasks.remove(self.sender())
        self.finished.emit()

    def _handle_no_more_items(self):
        self.has_more_items_to_fetch = False
        self.loaded_all.emit()


class FetchManager(DataFetcher):
    """Handles the fetching state, actions, and data fetching logic.
    """

    THRESHOLD_TO_FETCH_MORE = 50

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent=None):
        super().__init__(parent)

        # Initialize setup
        self.__init_ui()
        self.__init_signal_connections()

    def __init_ui(self):
        """Initialize the UI of the widget.
        """
        # Create and initialize the fetch buttons
        self.data_fetching_buttons = DataFetchingButtons(self.parent())
        self.data_fetching_buttons.hide()

    def __init_signal_connections(self):
        """Initialize signal-slot connections.
        """
        # Connect DataFetcher signals
        self.started.connect(self._show_fetching_indicator)
        self.finished.connect(self._show_fetch_buttons)
        self.loaded_all.connect(self.data_fetching_buttons.hide)

        # Connect buttons to their respective methods
        self.data_fetching_buttons.fetch_more_button.clicked.connect(self.fetch_more)
        self.data_fetching_buttons.fetch_all_button.clicked.connect(self.fetch_all)
        self.data_fetching_buttons.stop_fetch_button.clicked.connect(self.pause_fetch)

    # Public Methods
    # --------------
    def set_generator(self, generator: Generator):
        """Set the data generator."""
        super().set_generator(generator)
        self.data_fetching_buttons.show()

    # Private Methods
    # ---------------
    def _show_fetching_indicator(self):
        """Show the fetching indicator."""
        self.data_fetching_buttons.fetch_more_button.hide()
        self.data_fetching_buttons.fetch_all_button.hide()
        self.data_fetching_buttons.stop_fetch_button.show()

    def _show_fetch_buttons(self):
        """Show the fetch buttons."""
        self.data_fetching_buttons.fetch_more_button.show()
        self.data_fetching_buttons.fetch_all_button.show()
        self.data_fetching_buttons.stop_fetch_button.hide()
