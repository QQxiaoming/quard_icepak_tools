from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tool_model import TableData, ToolExecutionResult, ToolParameters, build_output_path
from ui_components import apply_dialog_chrome


MODEL_TREE_COLUMNS = (
    "名称",
    "对象类型",
    "说明",
)


@dataclass(frozen=True)
class ModelTreeObjectEntry:
    object_name: str
    object_type: str


@dataclass(frozen=True)
class ModelTreeGroupEntry:
    object_type: str
    objects: tuple[ModelTreeObjectEntry, ...]

    def count_label(self) -> str:
        return f"{len(self.objects)} 个对象"


def build_model_tree_groups(
    table_data: TableData,
    filter_text: str = "",
) -> tuple[ModelTreeGroupEntry, ...]:
    index_map = {column: index for index, column in enumerate(table_data.columns)}
    required = ("object_type", "object_name")
    missing = [column for column in required if column not in index_map]
    if missing:
        return ()

    normalized_filter = filter_text.casefold()
    grouped: dict[str, list[ModelTreeObjectEntry]] = {}
    order: list[str] = []

    for row in table_data.rows:
        object_type = row[index_map["object_type"]].strip() or "unknown"
        object_name = row[index_map["object_name"]].strip()
        if not object_name:
            continue

        if normalized_filter:
            searchable = f"{object_type} {object_name}".casefold()
            if normalized_filter not in searchable:
                continue

        if object_type not in grouped:
            grouped[object_type] = []
            order.append(object_type)

        grouped[object_type].append(
            ModelTreeObjectEntry(object_name=object_name, object_type=object_type)
        )

    return tuple(
        ModelTreeGroupEntry(object_type=object_type, objects=tuple(grouped[object_type]))
        for object_type in order
    )


def flatten_model_tree_groups(groups: tuple[ModelTreeGroupEntry, ...]) -> TableData:
    rows: list[tuple[str, ...]] = []
    for group in groups:
        rows.append((group.object_type, "分组", group.count_label()))
        for entry in group.objects:
            rows.append((entry.object_name, entry.object_type, ""))
    return TableData(
        columns=MODEL_TREE_COLUMNS,
        rows=tuple(rows),
        default_export_name="icepak_model_tree.csv",
    )


class SortableTreeWidgetItem(QTreeWidgetItem):
    def __init__(self, value: str) -> None:
        super().__init__([value])

    def __lt__(self, other: QTreeWidgetItem) -> bool:
        if isinstance(other, QTreeWidgetItem):
            column = self.treeWidget().sortColumn() if self.treeWidget() is not None else 0
            return self.text(column).casefold() < other.text(column).casefold()
        return super().__lt__(other)


class IcepakModelTreeResultDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_dialog_chrome(self)
        self.current_table_data: TableData | None = None
        self.current_visible_groups: tuple[ModelTreeGroupEntry, ...] = ()
        self.input_path = ""

        self.setWindowTitle("Icepak 模型树预览")
        self.resize(960, 640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.hint_label = QLabel(
            "该工具基于 Icepak Tcl 当前可用的平铺对象枚举，按对象类型分组展示，便于快速核对模型内容。",
            self,
        )
        self.hint_label.setWordWrap(True)

        self.summary_label = QLabel("暂无结果。", self)
        self.summary_label.setWordWrap(True)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("对象过滤", self))
        self.name_filter_input = QLineEdit(self)
        self.name_filter_input.setPlaceholderText("输入对象名或对象类型，动态过滤预览树")
        self.name_filter_input.textChanged.connect(self.apply_name_filter)
        filter_row.addWidget(self.name_filter_input, 1)

        self.result_tree = QTreeWidget(self)
        self.result_tree.setColumnCount(len(MODEL_TREE_COLUMNS))
        self.result_tree.setHeaderLabels(list(MODEL_TREE_COLUMNS))
        self.result_tree.setAlternatingRowColors(True)
        self.result_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.result_tree.setSortingEnabled(True)
        self.result_tree.setRootIsDecorated(True)
        self.result_tree.setItemsExpandable(True)
        self.result_tree.setUniformRowHeights(True)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.export_csv_button = QPushButton("导出当前表格为 CSV", self)
        self.export_csv_button.setEnabled(False)
        self.export_csv_button.clicked.connect(self.export_current_table_to_csv)
        close_button = QPushButton("关闭", self)
        close_button.clicked.connect(self.close)
        actions.addWidget(self.export_csv_button)
        actions.addWidget(close_button)

        layout.addWidget(self.hint_label)
        layout.addWidget(self.summary_label)
        layout.addLayout(filter_row)
        layout.addWidget(self.result_tree, 1)
        layout.addLayout(actions)

    def set_result(self, table_data: TableData, input_path: str) -> None:
        self.current_table_data = table_data
        self.input_path = input_path
        self.name_filter_input.clear()
        self.apply_name_filter()
        self.export_csv_button.setEnabled(True)

    def apply_name_filter(self) -> None:
        if self.current_table_data is None:
            return

        filter_text = self.name_filter_input.text().strip().casefold()
        filtered_groups = build_model_tree_groups(self.current_table_data, filter_text)
        total_groups = build_model_tree_groups(self.current_table_data)
        visible_object_count = sum(len(group.objects) for group in filtered_groups)
        total_object_count = sum(len(group.objects) for group in total_groups)
        self.current_visible_groups = filtered_groups
        self.summary_label.setText(
            "Icepak 模型树预览已加载，"
            f"当前显示 {len(filtered_groups)} 个类型分组 / 共 {len(total_groups)} 个类型分组，"
            f"{visible_object_count} 个对象 / 共 {total_object_count} 个对象。"
        )
        self.populate_result_tree(filtered_groups)

    def populate_result_tree(self, groups: tuple[ModelTreeGroupEntry, ...]) -> None:
        self.result_tree.clear()
        self.result_tree.setSortingEnabled(False)

        for group in groups:
            group_item = SortableTreeWidgetItem(group.object_type)
            group_item.setText(0, group.object_type)
            group_item.setText(1, "分组")
            group_item.setText(2, group.count_label())
            group_item.setExpanded(True)
            self.result_tree.addTopLevelItem(group_item)

            for entry in group.objects:
                object_item = SortableTreeWidgetItem(entry.object_name)
                object_item.setText(0, entry.object_name)
                object_item.setText(1, entry.object_type)
                object_item.setText(2, "")
                group_item.addChild(object_item)

        self.result_tree.resizeColumnToContents(0)
        self.result_tree.resizeColumnToContents(1)
        self.result_tree.resizeColumnToContents(2)
        self.result_tree.setSortingEnabled(True)

    def export_current_table_to_csv(self) -> None:
        if not self.current_visible_groups:
            return

        visible_table_data = flatten_model_tree_groups(self.current_visible_groups)
        default_name = visible_table_data.default_export_name
        start_path = str(Path.cwd() / default_name)
        if self.input_path:
            start_path = build_output_path(self.input_path, default_name)

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 Icepak 模型树预览为 CSV",
            start_path,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not output_path:
            return

        with Path(output_path).expanduser().resolve().open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(visible_table_data.columns)
            writer.writerows(visible_table_data.rows)


def show_model_tree_result(
    parent: QWidget,
    result: ToolExecutionResult,
    parameters: ToolParameters,
) -> None:
    if result.table_data is None:
        return

    dialog = IcepakModelTreeResultDialog(parent)
    setattr(parent, "_icepak_model_tree_result_dialog", dialog)
    dialog.destroyed.connect(
        lambda *_args: setattr(parent, "_icepak_model_tree_result_dialog", None)
    )
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)
    dialog.set_result(result.table_data, parameters.get("input_path", ""))
    dialog.setWindowModality(Qt.WindowModal)
    dialog.exec()