from typing import List, Dict, Any, Union, Optional
from PyQt5 import QtCore, QtGui, QtWidgets
from collections import defaultdict


# NOTE: WIP
class GroupedTreeModel(QtGui.QStandardItemModel):
    def __init__(self, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self.grouped_columns: List[int] = []
        self.original_data: List[List[Any]] = []
        self.header_labels: List[str] = []

    def group_by_column(self, column: int):
        if column in self.grouped_columns:
            return

        self.grouped_columns.append(column)
        self.rebuild_model()

    def ungroup_columns(self):
        self.grouped_columns.clear()
        self.rebuild_model()

    def set_data(self, data: List[List[Any]]):
        self.original_data = data
        self.rebuild_model()

    def set_header_labels(self, labels: List[str]):
        self.header_labels = labels

    def rebuild_model(self):
        self.clear()
        self.setHorizontalHeaderLabels(self.header_labels)

        if self.grouped_columns:
            grouped_data = self.group_data(self.original_data, self.grouped_columns)
            self.add_grouped_items(grouped_data, self.invisibleRootItem())
        else:
            self.add_items(self.original_data, self.invisibleRootItem())

    def group_data(self, data: List[List[Any]], columns: List[int]) -> Union[List[List[Any]], Dict[Any, Any]]:
        if not columns:
            return data

        grouped_data: Dict[Any, List[List[Any]]] = defaultdict(list)
        current_column = columns[0]

        for row in data:
            key = row[current_column]
            grouped_data[key].append(row)

        for key, rows in grouped_data.items():
            grouped_data[key] = self.group_data(rows, columns[1:])

        return grouped_data

    def add_grouped_items(self, grouped_data: Union[Dict[Any, Any], List[List[Any]]], parent_item: QtGui.QStandardItem):
        for key, value in grouped_data.items():
            group_item = QtGui.QStandardItem(str(key))
            parent_item.appendRow([group_item])
            if isinstance(value, dict):
                self.add_grouped_items(value, group_item)
            else:
                self.add_items(value, group_item)

    def add_items(self, data: List[List[Any]], parent_item: QtGui.QStandardItem):
        for row in data:
            items = [QtGui.QStandardItem(str(v)) for v in row]
            parent_item.appendRow(items)


class TreeView(QtWidgets.QTreeView):
    def __init__(self, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self.header().setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.header().customContextMenuRequested.connect(self.show_header_context_menu)
        self.model = GroupedTreeModel(self)
        self.setModel(self.model)
        self.create_context_menu()
        self._current_column_index: Optional[int] = None

    def create_context_menu(self):
        self.menu = QtWidgets.QMenu()
        self.group_action = self.menu.addAction("Group by this column")
        self.ungroup_action = self.menu.addAction("Ungroup columns")

        self.group_action.triggered.connect(self.group_by_column)
        self.ungroup_action.triggered.connect(self.model.ungroup_columns)

    def show_header_context_menu(self, position: QtCore.QPoint):
        header = self.header()
        self._current_column_index = header.logicalIndexAt(position)

        if self._current_column_index in self.model.grouped_columns:
            self.group_action.setEnabled(False)
            self.group_action.setToolTip("This column is already being used for grouping.")
        else:
            self.group_action.setEnabled(True)
            self.group_action.setToolTip("")

        self.menu.exec_(header.mapToGlobal(position))

    def group_by_column(self):
        self.model.group_by_column(self._current_column_index)
        self.expandAll()


import random
import string

def generate_test_data(num_rows: int = 1000, num_cols: int = 5) -> List[List[str]]:
    """Generate test data with repeating patterns for grouping.

    Args:
        num_rows (int): The number of rows to generate. Defaults to 1000.
        num_cols (int): The number of columns to generate. Defaults to 7.

    Returns:
        List[List[str]]: A list of lists containing the generated test data.
    """
    data: List[List[str]] = []
    # Generate dynamic repeating patterns for each column
    patterns: List[List[str]] = [
        [f'{chr(65 + j % 26)}{i % (5 * (j + 1))}' for i in range(num_rows)] for j in range(num_cols - 1)
    ]
    patterns.append([''.join(random.choices(string.ascii_uppercase + string.digits, k=5)) for _ in range(num_rows)])  # Random for the last column

    for i in range(num_rows):
        row = [patterns[j][i] for j in range(num_cols)]
        data.append(row)
    
    return data

if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QMainWindow()
    tree_view = TreeView()

    num_columns = 5
    num_rows = 1000
    header_labels = [f'Column {i+1}' for i in range(num_columns)]
    data = generate_test_data(num_rows, num_columns)

    tree_view.model.set_header_labels(header_labels)
    tree_view.model.set_data(data)

    window.setCentralWidget(tree_view)
    window.show()
    sys.exit(app.exec_())
