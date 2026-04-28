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
class ModelTreeNodeEntry:
    node_id: str
    parent_id: str
    node_kind: str
    object_name: str
    object_type: str
    detail: str = ""
    children: tuple["ModelTreeNodeEntry", ...] = ()


def _prune_tree(nodes: tuple[ModelTreeNodeEntry, ...], filter_text: str) -> tuple[ModelTreeNodeEntry, ...]:
    if not filter_text:
        return nodes

    pruned_nodes: list[ModelTreeNodeEntry] = []
    for node in nodes:
        pruned_children = _prune_tree(node.children, filter_text)
        searchable = f"{node.node_kind} {node.object_type} {node.object_name} {node.detail}".casefold()
        if filter_text in searchable or pruned_children:
            pruned_nodes.append(
                ModelTreeNodeEntry(
                    node_id=node.node_id,
                    parent_id=node.parent_id,
                    node_kind=node.node_kind,
                    object_name=node.object_name,
                    object_type=node.object_type,
                    detail=node.detail,
                    children=pruned_children,
                )
            )
    return tuple(pruned_nodes)


def build_model_tree_entries(
    table_data: TableData,
    filter_text: str = "",
) -> tuple[ModelTreeNodeEntry, ...]:
    index_map = {column: index for index, column in enumerate(table_data.columns)}
    required = ("node_id", "parent_id", "node_kind", "object_type", "object_name", "detail")
    missing = [column for column in required if column not in index_map]
    if missing:
        return ()

    ordered_nodes: list[ModelTreeNodeEntry] = []
    seen_node_ids: set[str] = set()
    for row in table_data.rows:
        node_id = row[index_map["node_id"]].strip()
        parent_id = row[index_map["parent_id"]].strip() or "__root__"
        node_kind = row[index_map["node_kind"]].strip() or "object"
        object_type = row[index_map["object_type"]].strip() or "unknown"
        object_name = row[index_map["object_name"]].strip()
        detail = row[index_map["detail"]].strip()
        if not node_id or not object_name or node_id in seen_node_ids:
            continue

        seen_node_ids.add(node_id)
        ordered_nodes.append(
            ModelTreeNodeEntry(
                node_id=node_id,
                parent_id=parent_id,
                node_kind=node_kind,
                object_name=object_name,
                object_type=object_type,
                detail=detail,
            )
        )

    children_by_parent: dict[str, list[ModelTreeNodeEntry]] = {}
    for node in ordered_nodes:
        children_by_parent.setdefault(node.parent_id, []).append(node)

    node_by_id = {node.node_id: node for node in ordered_nodes}

    def build_node(node: ModelTreeNodeEntry) -> ModelTreeNodeEntry:
        child_nodes = tuple(build_node(child) for child in children_by_parent.get(node.node_id, []))
        detail = node.detail
        if node.node_kind in {"object", "shape"} and child_nodes:
            detail = detail or f"{len(child_nodes)} 个子节点"
        return ModelTreeNodeEntry(
            node_id=node.node_id,
            parent_id=node.parent_id,
            node_kind=node.node_kind,
            object_name=node.object_name,
            object_type=node.object_type,
            detail=detail,
            children=child_nodes,
        )

    root_nodes: list[ModelTreeNodeEntry] = []
    for node in ordered_nodes:
        if node.parent_id == "__root__" or node.parent_id not in node_by_id:
            root_nodes.append(build_node(node))

    return _prune_tree(tuple(root_nodes), filter_text.casefold())


def flatten_model_tree_entries(entries: tuple[ModelTreeNodeEntry, ...]) -> TableData:
    rows: list[tuple[str, ...]] = []

    def append_rows(nodes: tuple[ModelTreeNodeEntry, ...], depth: int) -> None:
        indent = "  " * depth
        for node in nodes:
            rows.append((f"{indent}{node.object_name}", node.object_type, node.detail))
            append_rows(node.children, depth + 1)

    append_rows(entries, 0)
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
        self.current_visible_entries: tuple[ModelTreeNodeEntry, ...] = ()
        self.input_path = ""

        self.setWindowTitle("Icepak 模型树预览")
        self.resize(960, 640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.hint_label = QLabel(
            "该工具按 Icepak 官方树的父子关系导出：节点层级来自对象的 model_container，而不是名称推断。",
            self,
        )
        self.hint_label.setWordWrap(True)

        self.summary_label = QLabel("暂无结果。", self)
        self.summary_label.setWordWrap(True)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("对象过滤", self))
        self.name_filter_input = QLineEdit(self)
        self.name_filter_input.setPlaceholderText("输入对象名、对象类型或节点类型，动态过滤预览树")
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
        filtered_entries = build_model_tree_entries(self.current_table_data, filter_text)
        total_entries = build_model_tree_entries(self.current_table_data)

        def count_nodes(nodes: tuple[ModelTreeNodeEntry, ...]) -> int:
            total = 0
            for node in nodes:
                if node.node_kind in {"object", "shape"}:
                    total += 1
                total += count_nodes(node.children)
            return total

        self.current_visible_entries = filtered_entries
        self.summary_label.setText(
            "Icepak 模型树预览已加载，"
            f"当前显示 {count_nodes(filtered_entries)} 个节点 / 共 {count_nodes(total_entries)} 个节点，"
            f"顶层节点 {len(filtered_entries)} 个 / 共 {len(total_entries)} 个。"
        )
        self.populate_result_tree(filtered_entries)

    def populate_result_tree(self, entries: tuple[ModelTreeNodeEntry, ...]) -> None:
        self.result_tree.clear()
        self.result_tree.setSortingEnabled(False)

        def create_item(node: ModelTreeNodeEntry) -> QTreeWidgetItem:
            item = SortableTreeWidgetItem(node.object_name)
            item.setText(0, node.object_name)
            item.setText(1, node.object_type)
            item.setText(2, node.detail)
            item.setExpanded(True)
            for child in node.children:
                item.addChild(create_item(child))
            return item

        for entry in entries:
            self.result_tree.addTopLevelItem(create_item(entry))

        self.result_tree.resizeColumnToContents(0)
        self.result_tree.resizeColumnToContents(1)
        self.result_tree.resizeColumnToContents(2)
        self.result_tree.setSortingEnabled(True)

    def export_current_table_to_csv(self) -> None:
        if not self.current_visible_entries:
            return

        visible_table_data = flatten_model_tree_entries(self.current_visible_entries)
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
