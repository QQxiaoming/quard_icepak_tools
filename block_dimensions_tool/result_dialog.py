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
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from icepak_model_tree_tool.result_dialog import ModelTreeNodeEntry, build_model_tree_entries
from tool_model import TableData, ToolExecutionResult, ToolParameters, build_output_path
from ui_components import ModernComboBox, ModernSpinBox, apply_dialog_chrome

TREE_COLUMNS = (
    "名称",
    "对象类型",
    "节点类型",
    "单位",
    "dx",
    "dy",
    "dz",
    "xmin",
    "xmax",
    "ymin",
    "ymax",
    "zmin",
    "zmax",
)
DISPLAY_MODE_TREE = "tree"
DISPLAY_MODE_FLAT = "flat"
INTERFERENCE_REQUIRED_COLUMNS = (
    "object_name",
    "length_unit",
    "xmin",
    "xmax",
    "ymin",
    "ymax",
    "zmin",
    "zmax",
)
INTERFERENCE_TOLERANCE = 1e-12


@dataclass(frozen=True)
class BlockBoundingBox:
    object_name: str
    length_unit: str
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float


def _table_row_to_dict(columns: tuple[str, ...], row: tuple[str, ...]) -> dict[str, str]:
    return {
        column: row[index] if index < len(row) else ""
        for index, column in enumerate(columns)
    }


def build_tree_row_lookup(table_data: TableData) -> dict[str, dict[str, str]]:
    if "node_id" not in table_data.columns:
        return {}

    node_id_index = table_data.columns.index("node_id")
    row_lookup: dict[str, dict[str, str]] = {}
    for row in table_data.rows:
        if node_id_index >= len(row):
            continue
        node_id = row[node_id_index].strip()
        if not node_id:
            continue
        row_lookup[node_id] = _table_row_to_dict(table_data.columns, row)
    return row_lookup


def count_tree_nodes(entries: tuple[ModelTreeNodeEntry, ...]) -> int:
    total = 0
    for node in entries:
        total += 1
        total += count_tree_nodes(node.children)
    return total


def count_block_nodes(
    entries: tuple[ModelTreeNodeEntry, ...],
    row_lookup: dict[str, dict[str, str]],
) -> int:
    total = 0
    for node in entries:
        row = row_lookup.get(node.node_id, {})
        if row.get("node_kind") == "object" and row.get("object_type") == "block":
            total += 1
        total += count_block_nodes(node.children, row_lookup)
    return total


def _node_row_values(node: ModelTreeNodeEntry, row_lookup: dict[str, dict[str, str]]) -> tuple[str, ...]:
    row = row_lookup.get(node.node_id, {})
    return (
        node.object_name,
        node.object_type,
        node.node_kind,
        row.get("length_unit", ""),
        row.get("dx", ""),
        row.get("dy", ""),
        row.get("dz", ""),
        row.get("xmin", ""),
        row.get("xmax", ""),
        row.get("ymin", ""),
        row.get("ymax", ""),
        row.get("zmin", ""),
        row.get("zmax", ""),
    )


def flatten_tree_table_data(
    entries: tuple[ModelTreeNodeEntry, ...],
    row_lookup: dict[str, dict[str, str]],
    default_export_name: str,
    indent_names: bool = True,
) -> TableData:
    rows: list[tuple[str, ...]] = []

    def append_rows(nodes: tuple[ModelTreeNodeEntry, ...], depth: int) -> None:
        for node in nodes:
            row_values = list(_node_row_values(node, row_lookup))
            if indent_names:
                row_values[0] = f"{'  ' * depth}{row_values[0]}"
            rows.append(tuple(row_values))
            append_rows(node.children, depth + 1)

    append_rows(entries, 0)
    return TableData(
        columns=TREE_COLUMNS,
        rows=tuple(rows),
        default_export_name=default_export_name,
    )


def build_flat_table_data(
    table_data: TableData,
    row_lookup: dict[str, dict[str, str]],
    filter_text: str = "",
) -> TableData:
    if "node_id" not in table_data.columns:
        return TableData(columns=TREE_COLUMNS, rows=(), default_export_name=table_data.default_export_name)

    node_id_index = table_data.columns.index("node_id")
    filtered_rows: list[tuple[str, ...]] = []
    for row in table_data.rows:
        if node_id_index >= len(row):
            continue
        node_id = row[node_id_index].strip()
        if not node_id:
            continue

        row_map = row_lookup.get(node_id, _table_row_to_dict(table_data.columns, row))
        bbox_values = (
            row_map.get("xmin", ""),
            row_map.get("xmax", ""),
            row_map.get("ymin", ""),
            row_map.get("ymax", ""),
            row_map.get("zmin", ""),
            row_map.get("zmax", ""),
        )
        if any(value == "" for value in bbox_values):
            continue

        row_values = (
            row_map.get("object_name", ""),
            row_map.get("object_type", ""),
            row_map.get("node_kind", ""),
            row_map.get("length_unit", ""),
            row_map.get("dx", ""),
            row_map.get("dy", ""),
            row_map.get("dz", ""),
            row_map.get("xmin", ""),
            row_map.get("xmax", ""),
            row_map.get("ymin", ""),
            row_map.get("ymax", ""),
            row_map.get("zmin", ""),
            row_map.get("zmax", ""),
        )
        if filter_text:
            searchable = " ".join(row_values[:4]).casefold()
            if filter_text not in searchable:
                continue
        filtered_rows.append(row_values)

    return TableData(
        columns=TREE_COLUMNS,
        rows=tuple(filtered_rows),
        default_export_name=table_data.default_export_name,
    )


def collect_block_bounding_boxes(
    table_data: TableData,
) -> tuple[list[BlockBoundingBox], list[str], set[str]]:
    index_map = {column: index for index, column in enumerate(table_data.columns)}
    missing_columns = [
        column for column in INTERFERENCE_REQUIRED_COLUMNS if column not in index_map
    ]
    if missing_columns:
        return [], [f"缺少列：{', '.join(missing_columns)}"], set()

    boxes: list[BlockBoundingBox] = []
    skipped_messages: list[str] = []
    units: set[str] = set()
    seen_names: set[str] = set()

    for row in table_data.rows:
        row_map = _table_row_to_dict(table_data.columns, row)
        if row_map.get("object_type") and row_map.get("object_type") != "block":
            continue
        if row_map.get("node_kind") and row_map.get("node_kind") != "object":
            continue

        object_name = row[index_map["object_name"]].strip()
        if not object_name or object_name in seen_names:
            continue

        try:
            box = BlockBoundingBox(
                object_name=object_name,
                length_unit=row[index_map["length_unit"]].strip(),
                xmin=float(row[index_map["xmin"]]),
                xmax=float(row[index_map["xmax"]]),
                ymin=float(row[index_map["ymin"]]),
                ymax=float(row[index_map["ymax"]]),
                zmin=float(row[index_map["zmin"]]),
                zmax=float(row[index_map["zmax"]]),
            )
        except ValueError:
            skipped_messages.append(f"{object_name}: 包围盒数据无法转换为数值")
            continue

        if box.xmax < box.xmin or box.ymax < box.ymin or box.zmax < box.zmin:
            skipped_messages.append(f"{object_name}: 包围盒范围无效")
            continue

        seen_names.add(object_name)
        boxes.append(box)
        if box.length_unit:
            units.add(box.length_unit)

    return boxes, skipped_messages, units


def axis_overlap_length(min_a: float, max_a: float, min_b: float, max_b: float) -> float:
    return max(0.0, min(max_a, max_b) - max(min_a, min_b))


def box_contains(outer: BlockBoundingBox, inner: BlockBoundingBox) -> bool:
    return (
        outer.xmin <= inner.xmin + INTERFERENCE_TOLERANCE
        and outer.xmax >= inner.xmax - INTERFERENCE_TOLERANCE
        and outer.ymin <= inner.ymin + INTERFERENCE_TOLERANCE
        and outer.ymax >= inner.ymax - INTERFERENCE_TOLERANCE
        and outer.zmin <= inner.zmin + INTERFERENCE_TOLERANCE
        and outer.zmax >= inner.zmax - INTERFERENCE_TOLERANCE
    )


def build_interference_report(table_data: TableData) -> tuple[str, str, bool]:
    boxes, skipped_messages, units = collect_block_bounding_boxes(table_data)
    if len(boxes) < 2:
        summary = f"可用于检测的 block 数量不足，当前只有 {len(boxes)} 个有效 block。"
        details = "\n".join(skipped_messages) if skipped_messages else "没有足够的 block 可供两两检测。"
        return summary, details, False

    interference_lines: list[str] = []
    containment_lines: list[str] = []
    interference_count = 0
    containment_count = 0
    unit_suffix = next(iter(units), "") if len(units) == 1 else ""
    volume_unit = f" {unit_suffix}^3" if unit_suffix else ""

    for index, left in enumerate(boxes[:-1]):
        for right in boxes[index + 1 :]:
            overlap_x = axis_overlap_length(left.xmin, left.xmax, right.xmin, right.xmax)
            overlap_y = axis_overlap_length(left.ymin, left.ymax, right.ymin, right.ymax)
            overlap_z = axis_overlap_length(left.zmin, left.zmax, right.zmin, right.zmax)

            if (
                overlap_x <= INTERFERENCE_TOLERANCE
                or overlap_y <= INTERFERENCE_TOLERANCE
                or overlap_z <= INTERFERENCE_TOLERANCE
            ):
                continue

            overlap_volume = overlap_x * overlap_y * overlap_z
            detail_lines = [
                (
                    "   重叠区间: "
                    f"x[{max(left.xmin, right.xmin):.6g}, {min(left.xmax, right.xmax):.6g}] "
                    f"y[{max(left.ymin, right.ymin):.6g}, {min(left.ymax, right.ymax):.6g}] "
                    f"z[{max(left.zmin, right.zmin):.6g}, {min(left.zmax, right.zmax):.6g}]"
                ),
                (
                    "   干涉尺寸: "
                    f"dx={overlap_x:.6g}, dy={overlap_y:.6g}, dz={overlap_z:.6g}, "
                    f"体积={overlap_volume:.6g}{volume_unit}"
                ),
            ]

            if box_contains(left, right):
                containment_count += 1
                containment_lines.append(
                    "\n".join(
                        [
                            f"{containment_count}. {right.object_name} 被 {left.object_name} 完全包裹",
                            *detail_lines,
                        ]
                    )
                )
                continue

            if box_contains(right, left):
                containment_count += 1
                containment_lines.append(
                    "\n".join(
                        [
                            f"{containment_count}. {left.object_name} 被 {right.object_name} 完全包裹",
                            *detail_lines,
                        ]
                    )
                )
                continue

            interference_count += 1
            interference_lines.append(
                "\n".join(
                    [
                        f"{interference_count}. {left.object_name} <-> {right.object_name}",
                        *detail_lines,
                    ]
                )
            )

    summary = (
        f"共检查 {len(boxes)} 个 block，发现 {interference_count} 组普通体积干涉，"
        f"另有 {containment_count} 组完全包裹情况。"
    )
    details_parts: list[str] = []
    if len(units) > 1:
        details_parts.append("检测结果包含多个长度单位，报告中的数值未做跨单位换算。")
    if skipped_messages:
        details_parts.append("以下 block 已跳过：")
        details_parts.extend(skipped_messages)
    if interference_lines:
        details_parts.append("普通干涉明细：")
        details_parts.extend(interference_lines)
    else:
        details_parts.append("未检测到需要优先处理的普通体积干涉。")

    if containment_lines:
        details_parts.append("警告：以下 block 存在完全包裹情况，这类情况有时是正常设计，请结合模型意图确认：")
        details_parts.extend(containment_lines)

    return summary, "\n\n".join(details_parts), interference_count > 0 or containment_count > 0


class SortableTreeWidgetItem(QTreeWidgetItem):
    def __init__(self, values: tuple[str, ...]) -> None:
        super().__init__(list(values))
        for index, value in enumerate(values):
            self.setData(index, Qt.UserRole, self._build_sort_value(value))

    @staticmethod
    def _build_sort_value(value: str) -> float | str:
        try:
            return float(value)
        except ValueError:
            return value.casefold()

    def __lt__(self, other: QTreeWidgetItem) -> bool:
        if isinstance(other, QTreeWidgetItem):
            tree_widget = self.treeWidget()
            column = tree_widget.sortColumn() if tree_widget is not None else 0
            left = self.data(column, Qt.UserRole)
            right = other.data(column, Qt.UserRole)
            if type(left) is type(right):
                return left < right
        return super().__lt__(other)


class SortableTableWidgetItem(QTableWidgetItem):
    def __init__(self, value: str) -> None:
        super().__init__(value)
        self.sort_value: float | str
        try:
            self.sort_value = float(value)
        except ValueError:
            self.sort_value = value.casefold()

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, SortableTableWidgetItem):
            left = self.sort_value
            right = other.sort_value
            if type(left) is type(right):
                return left < right
            return str(self.text()).casefold() < str(other.text()).casefold()
        return str(self.text()).casefold() < str(other.text()).casefold()


class InterferenceReportDialog(QDialog):
    def __init__(
        self,
        summary: str,
        details: str,
        has_interference: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        apply_dialog_chrome(self)
        self.setWindowTitle("干涉检测报告")
        self.resize(920, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        summary_label = QLabel(summary, self)
        summary_label.setWordWrap(True)

        details_view = QPlainTextEdit(self)
        details_view.setReadOnly(True)
        details_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        details_view.setPlainText(details)
        details_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        close_button = QPushButton("关闭", self)
        close_button.clicked.connect(self.accept)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(close_button)

        layout.addWidget(summary_label)
        layout.addWidget(details_view, 1)
        layout.addLayout(actions)

        if has_interference:
            self.setWindowTitle("干涉检测报告 - 检测到干涉")


class BlockDimensionsResultDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_dialog_chrome(self)
        self.current_table_data: TableData | None = None
        self.input_path = ""
        self.current_visible_entries: tuple[ModelTreeNodeEntry, ...] = ()
        self.current_visible_table_data: TableData | None = None
        self.row_lookup: dict[str, dict[str, str]] = {}
        self.display_mode = DISPLAY_MODE_TREE

        self.setWindowTitle("Block 尺寸统计结果")
        self.resize(1000, 640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.summary_label = QLabel("暂无结果。", self)
        self.summary_label.setWordWrap(True)

        self.hint_label = QLabel(
            "当前结果按 Icepak 官方模型树父子关系展示，block 节点保留包围盒统计，子 shape 节点保留尺寸信息。",
            self,
        )
        self.hint_label.setWordWrap(True)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("显示模式", self))
        self.display_mode_combo = ModernComboBox(self)
        self.display_mode_combo.addItem("树显示", DISPLAY_MODE_TREE)
        self.display_mode_combo.addItem("扁平显示", DISPLAY_MODE_FLAT)
        self.display_mode_combo.currentIndexChanged.connect(self.apply_name_filter)
        filter_row.addWidget(self.display_mode_combo)
        filter_row.addWidget(QLabel("名称过滤", self))
        self.name_filter_input = QLineEdit(self)
        self.name_filter_input.setPlaceholderText("输入对象名、对象类型或节点类型，动态过滤当前结果")
        self.name_filter_input.textChanged.connect(self.apply_name_filter)
        filter_row.addWidget(self.name_filter_input, 1)

        self.result_tree = QTreeWidget(self)
        self.result_tree.setColumnCount(len(TREE_COLUMNS))
        self.result_tree.setHeaderLabels(list(TREE_COLUMNS))
        self.result_tree.setAlternatingRowColors(True)
        self.result_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.result_tree.setSortingEnabled(True)
        self.result_tree.setRootIsDecorated(True)
        self.result_tree.setItemsExpandable(True)
        self.result_tree.setUniformRowHeights(True)

        self.result_table = QTableWidget(self)
        self.result_table.setColumnCount(len(TREE_COLUMNS))
        self.result_table.setHorizontalHeaderLabels(list(TREE_COLUMNS))
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.result_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.result_table.setSortingEnabled(True)
        self.result_table.hide()

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.export_csv_button = QPushButton("导出当前表格为 CSV", self)
        self.export_csv_button.setEnabled(False)
        self.export_csv_button.clicked.connect(self.export_current_table_to_csv)
        self.interference_report_button = QPushButton("输出干涉检测报告", self)
        self.interference_report_button.setEnabled(False)
        self.interference_report_button.clicked.connect(self.show_interference_report)
        close_button = QPushButton("关闭", self)
        close_button.clicked.connect(self.close)
        actions.addWidget(self.export_csv_button)
        actions.addWidget(self.interference_report_button)
        actions.addWidget(close_button)

        layout.addWidget(self.summary_label)
        layout.addWidget(self.hint_label)
        layout.addLayout(filter_row)
        layout.addWidget(self.result_tree, 1)
        layout.addWidget(self.result_table, 1)
        layout.addLayout(actions)

    def set_result(self, table_data: TableData, input_path: str) -> None:
        self.current_table_data = table_data
        self.row_lookup = build_tree_row_lookup(table_data)
        self.input_path = input_path
        self.name_filter_input.clear()
        self.apply_name_filter()
        self.export_csv_button.setEnabled(True)
        self.interference_report_button.setEnabled(True)

    def apply_name_filter(self) -> None:
        if self.current_table_data is None:
            return

        self.display_mode = self.display_mode_combo.currentData()
        filter_text = self.name_filter_input.text().strip().casefold()
        if self.display_mode == DISPLAY_MODE_TREE:
            total_entries = build_model_tree_entries(self.current_table_data)
            filtered_entries = build_model_tree_entries(self.current_table_data, filter_text)
            self.current_visible_entries = filtered_entries
            self.current_visible_table_data = flatten_tree_table_data(
                filtered_entries,
                self.row_lookup,
                self.current_table_data.default_export_name,
                indent_names=True,
            )
            self.summary_label.setText(
                "Block 尺寸统计完成，"
                f"当前显示 {count_tree_nodes(filtered_entries)} 个节点 / 共 {count_tree_nodes(total_entries)} 个节点，"
                f"block {count_block_nodes(filtered_entries, self.row_lookup)} 个 / 共 {count_block_nodes(total_entries, self.row_lookup)} 个。"
            )
            self.populate_result_tree(filtered_entries)
            return

        flat_table = build_flat_table_data(self.current_table_data, self.row_lookup, filter_text)
        total_flat_table = build_flat_table_data(self.current_table_data, self.row_lookup)
        self.current_visible_entries = ()
        self.current_visible_table_data = flat_table
        self.summary_label.setText(
            "Block 尺寸统计完成，"
            f"当前显示 {len(flat_table.rows)} 行 / 共 {len(total_flat_table.rows)} 行，"
            f"block {sum(1 for row in flat_table.rows if len(row) > 1 and row[1] == 'block')} 个。"
        )
        self.populate_result_table(flat_table)

    def populate_result_tree(self, entries: tuple[ModelTreeNodeEntry, ...]) -> None:
        self.result_table.hide()
        self.result_tree.show()
        self.result_tree.clear()
        self.result_tree.setSortingEnabled(False)
        self.result_tree.setRootIsDecorated(True)

        def create_item(node: ModelTreeNodeEntry) -> QTreeWidgetItem:
            item = SortableTreeWidgetItem(_node_row_values(node, self.row_lookup))
            item.setExpanded(True)
            for child in node.children:
                item.addChild(create_item(child))
            return item

        for entry in entries:
            self.result_tree.addTopLevelItem(create_item(entry))

        for column_index in range(len(TREE_COLUMNS)):
            self.result_tree.resizeColumnToContents(column_index)
        self.result_tree.setSortingEnabled(True)

    def populate_result_table(self, table_data: TableData) -> None:
        self.result_tree.hide()
        self.result_table.show()
        self.result_table.clearContents()
        self.result_table.setSortingEnabled(False)
        self.result_table.setRowCount(len(table_data.rows))

        for row_index, row in enumerate(table_data.rows):
            for column_index, value in enumerate(row):
                self.result_table.setItem(row_index, column_index, SortableTableWidgetItem(value))

        for column_index in range(len(TREE_COLUMNS)):
            self.result_table.resizeColumnToContents(column_index)
        self.result_table.setSortingEnabled(True)

    def export_current_table_to_csv(self) -> None:
        if self.current_visible_table_data is None:
            return

        visible_table_data = self.current_visible_table_data

        default_name = visible_table_data.default_export_name
        start_path = str(Path.cwd() / default_name)
        if self.input_path:
            start_path = build_output_path(self.input_path, default_name)

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 Block 尺寸统计结果为 CSV",
            start_path,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not output_path:
            return

        with Path(output_path).expanduser().resolve().open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(visible_table_data.columns)
            writer.writerows(visible_table_data.rows)

        QMessageBox.information(self, "导出完成", f"CSV 已导出到：\n{output_path}")

    def show_interference_report(self) -> None:
        if self.current_table_data is None:
            return

        summary, details, has_interference = build_interference_report(self.current_table_data)
        dialog = InterferenceReportDialog(summary, details, has_interference, self)
        dialog.setWindowModality(Qt.WindowModal)
        dialog.exec()


def show_block_dimensions_result(
    parent: QWidget,
    result: ToolExecutionResult,
    parameters: ToolParameters,
) -> None:
    if result.table_data is None:
        return

    dialog = BlockDimensionsResultDialog(parent)
    setattr(parent, "_block_dimensions_result_dialog", dialog)
    dialog.destroyed.connect(
        lambda *_args: setattr(parent, "_block_dimensions_result_dialog", None)
    )
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)
    dialog.set_result(result.table_data, parameters.get("input_path", ""))
    dialog.setWindowModality(Qt.WindowModal)
    dialog.exec()
