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
    QVBoxLayout,
    QWidget,
)

from tool_model import TableData, ToolExecutionResult, ToolParameters, build_output_path


HIDDEN_COLUMNS = {"object_type", "shape_name"}
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


def build_visible_table_data(table_data: TableData) -> TableData:
    visible_indexes = [
        index for index, column in enumerate(table_data.columns) if column not in HIDDEN_COLUMNS
    ]
    return TableData(
        columns=tuple(table_data.columns[index] for index in visible_indexes),
        rows=tuple(
            tuple(row[index] for index in visible_indexes)
            for row in table_data.rows
        ),
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
        return super().__lt__(other)


class InterferenceReportDialog(QDialog):
    def __init__(
        self,
        summary: str,
        details: str,
        has_interference: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
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
        self.current_table_data: TableData | None = None
        self.input_path = ""
        self.current_visible_table_data: TableData | None = None

        self.setWindowTitle("Block 尺寸统计结果")
        self.resize(1000, 640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.summary_label = QLabel("暂无结果。", self)
        self.summary_label.setWordWrap(True)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("名称过滤", self))
        self.name_filter_input = QLineEdit(self)
        self.name_filter_input.setPlaceholderText("输入 object_name，动态过滤表格行")
        self.name_filter_input.textChanged.connect(self.apply_name_filter)
        filter_row.addWidget(self.name_filter_input, 1)

        self.result_table = QTableWidget(self)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.result_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.result_table.setSortingEnabled(True)
        self.result_table.horizontalHeader().setSectionsClickable(True)
        self.result_table.horizontalHeader().setSortIndicatorShown(True)

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
        layout.addLayout(filter_row)
        layout.addWidget(self.result_table, 1)
        layout.addLayout(actions)

    def set_result(self, table_data: TableData, input_path: str) -> None:
        self.current_table_data = table_data
        self.input_path = input_path
        self.name_filter_input.clear()
        self.apply_name_filter()
        self.export_csv_button.setEnabled(True)
        self.interference_report_button.setEnabled(True)

    def apply_name_filter(self) -> None:
        if self.current_table_data is None:
            return

        filter_text = self.name_filter_input.text().strip().casefold()
        filtered_table_data = self.build_filtered_visible_table_data(filter_text)
        self.current_visible_table_data = filtered_table_data

        self.summary_label.setText(
            "Block 尺寸统计完成，"
            f"当前显示 {len(filtered_table_data.rows)} 行 / 共 {len(build_visible_table_data(self.current_table_data).rows)} 行，"
            f"{len(filtered_table_data.columns)} 列。"
        )
        self.populate_result_table(filtered_table_data)

    def build_filtered_visible_table_data(self, filter_text: str) -> TableData:
        assert self.current_table_data is not None

        visible_table_data = build_visible_table_data(self.current_table_data)
        if not filter_text:
            return visible_table_data

        object_name_index = self.current_table_data.columns.index("object_name")
        filtered_rows = tuple(
            visible_row
            for source_row, visible_row in zip(
                self.current_table_data.rows,
                visible_table_data.rows,
            )
            if filter_text in source_row[object_name_index].casefold()
        )
        return TableData(
            columns=visible_table_data.columns,
            rows=filtered_rows,
            default_export_name=visible_table_data.default_export_name,
        )

    def populate_result_table(self, table_data: TableData) -> None:
        self.result_table.clear()
        self.result_table.setSortingEnabled(False)
        self.result_table.setColumnCount(len(table_data.columns))
        self.result_table.setHorizontalHeaderLabels(list(table_data.columns))
        self.result_table.setRowCount(len(table_data.rows))

        for row_index, row in enumerate(table_data.rows):
            for column_index, value in enumerate(row):
                self.result_table.setItem(row_index, column_index, SortableTableWidgetItem(value))

        self.result_table.resizeColumnsToContents()
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
