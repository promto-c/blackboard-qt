import pytest
from qtpy import QtCore, QtGui
from blackboard.utils.proxy_model import FlatProxyModel, CheckableProxyModel

class TestFlatProxyModel:
    @pytest.fixture
    def source_model(self):
        # Creates a simple source model for testing
        model = QtGui.QStandardItemModel()
        items = [QtGui.QStandardItem(f"Item {i}") for i in range(5)]
        for item in items:
            model.appendRow(item)
        return model

    @pytest.fixture
    def proxy_model(self, source_model):
        # Initialize your FlatProxyModel with the provided source model
        return FlatProxyModel(source_model=source_model)

    def test_initialization(self, proxy_model):
        assert proxy_model.rowCount() == 5
        assert not proxy_model.show_only_checked
        assert not proxy_model.show_only_leaves

    def test_set_source_model(self, proxy_model, source_model):
        new_model = QtGui.QStandardItemModel()
        new_model.appendRow(QtGui.QStandardItem("New Item"))
        proxy_model.setSourceModel(new_model)

        assert proxy_model.rowCount() == 1
        assert proxy_model.sourceModel() == new_model
        assert proxy_model.mapToSource(proxy_model.index(0, 0)).data() == "New Item"

    def test_model_changes(self, proxy_model, source_model):
        # Test adding items
        source_model.appendRow(QtGui.QStandardItem("New Item"))
        assert proxy_model.rowCount() == 6
        
        # Test removing items
        source_model.removeRow(0)
        assert proxy_model.rowCount() == 5

    @pytest.mark.parametrize("show_only_checked, expected_count", [(True, 0), (False, 5)])
    def test_filter_checked_items(self, proxy_model, source_model, show_only_checked, expected_count):
        if show_only_checked:
            for i in range(source_model.rowCount()):
                item = source_model.item(i)
                item.setCheckable(True)
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)
        
        proxy_model.set_filter_checked_items(show_only_checked)
        assert proxy_model.rowCount() == expected_count

        if show_only_checked:
            source_model.item(0).setCheckState(QtCore.Qt.CheckState.Checked)
            assert proxy_model.rowCount() == 1

    def test_mapping_functions(self, proxy_model, source_model):
        source_index = source_model.index(0, 0)
        proxy_index = proxy_model.mapFromSource(source_index)
        assert proxy_index.row() == 0

        back_to_source_index = proxy_model.mapToSource(proxy_index)
        assert back_to_source_index == source_index

    def test_invalid_indices(self, proxy_model):
        invalid_proxy_index = proxy_model.index(-1, 0)
        assert not invalid_proxy_index.isValid()

        invalid_source_index = QtCore.QModelIndex()
        assert not proxy_model.mapFromSource(invalid_source_index).isValid()

class TestCheckableProxyModel:
    @pytest.fixture
    def source_model(self):
        # Creates a simple source model with checkable items for testing
        model = QtGui.QStandardItemModel()
        for i in range(3):  # Adding parent items
            parent_item = QtGui.QStandardItem(f"Parent {i}")
            model.appendRow(parent_item)
            for j in range(2):  # Adding child items
                child_item = QtGui.QStandardItem(f"Child {i}.{j}")
                child_item.setCheckable(True)
                parent_item.appendRow(child_item)
        return model

    @pytest.fixture
    def checkable_proxy_model(self, source_model):
        # Initialize your CheckableProxyModel with the provided source model
        return CheckableProxyModel(source_model=source_model)

    def test_initialization(self, checkable_proxy_model):
        # Verify the model starts with the correct setup
        assert checkable_proxy_model.rowCount() == 3  # Assuming the top-level rows are visible by default

    def test_data_and_set_data(self, checkable_proxy_model):
        parent_index = checkable_proxy_model.index(0, 0)  # Access the first parent
        child_index = checkable_proxy_model.index(0, 0, parent_index)  # First child of the first parent

        # Set data for child, expect parent updates
        assert checkable_proxy_model.setData(child_index, QtCore.Qt.CheckState.Checked, QtCore.Qt.ItemDataRole.CheckStateRole)
        assert checkable_proxy_model.data(child_index, QtCore.Qt.ItemDataRole.CheckStateRole) == QtCore.Qt.CheckState.Checked

        # Ensure the parent's state reflects a partial check due to one child being checked
        assert checkable_proxy_model.data(parent_index, QtCore.Qt.ItemDataRole.CheckStateRole) == QtCore.Qt.CheckState.PartiallyChecked

    def test_update_parent_and_children(self, checkable_proxy_model):
        parent_index = checkable_proxy_model.index(0, 0)  # Access the first parent
        first_child = checkable_proxy_model.index(0, 0, parent_index)
        second_child = checkable_proxy_model.index(1, 0, parent_index)

        # Initially set first child as checked
        checkable_proxy_model.setData(first_child, QtCore.Qt.CheckState.Checked, QtCore.Qt.ItemDataRole.CheckStateRole)

        # Now set the parent, expecting children to match parent state
        checkable_proxy_model.setData(parent_index, QtCore.Qt.CheckState.Unchecked, QtCore.Qt.ItemDataRole.CheckStateRole)
        assert checkable_proxy_model.data(first_child, QtCore.Qt.ItemDataRole.CheckStateRole) == QtCore.Qt.CheckState.Unchecked
        assert checkable_proxy_model.data(second_child, QtCore.Qt.ItemDataRole.CheckStateRole) == QtCore.Qt.CheckState.Unchecked

    def test_item_flags(self, checkable_proxy_model):
        index = checkable_proxy_model.index(0, 0)  # Access any index
        flags = checkable_proxy_model.flags(index)
        assert flags & QtCore.Qt.ItemFlag.ItemIsUserCheckable
