from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tool_model import TableData, ToolExecutionResult, ToolParameters, build_output_path


HIDDEN_COLUMNS = {"object_type", "shape_name"}


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


class BlockDimensionsResultDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_table_data: TableData | None = None
        self.input_path = ""

        self.setWindowTitle("Block 尺寸统计结果")
        self.resize(1000, 640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.summary_label = QLabel("暂无结果。", self)
        self.summary_label.setWordWrap(True)

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
        close_button = QPushButton("关闭", self)
        close_button.clicked.connect(self.close)
        actions.addWidget(self.export_csv_button)
        actions.addWidget(close_button)

        layout.addWidget(self.summary_label)
        layout.addWidget(self.result_table, 1)
        layout.addLayout(actions)

    def set_result(self, table_data: TableData, input_path: str) -> None:
        self.current_table_data = table_data
        self.input_path = input_path
        visible_table_data = build_visible_table_data(table_data)

        self.summary_label.setText(
            f"Block 尺寸统计完成，共 {len(visible_table_data.rows)} 行，{len(visible_table_data.columns)} 列。"
        )
        self.result_table.clear()
        self.result_table.setSortingEnabled(False)
        self.result_table.setColumnCount(len(visible_table_data.columns))
        self.result_table.setHorizontalHeaderLabels(list(visible_table_data.columns))
        self.result_table.setRowCount(len(visible_table_data.rows))

        for row_index, row in enumerate(visible_table_data.rows):
            for column_index, value in enumerate(row):
                self.result_table.setItem(row_index, column_index, SortableTableWidgetItem(value))

        self.result_table.resizeColumnsToContents()
        self.result_table.setSortingEnabled(True)
        self.export_csv_button.setEnabled(True)

    def export_current_table_to_csv(self) -> None:
        if self.current_table_data is None:
            return

        visible_table_data = build_visible_table_data(self.current_table_data)

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
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
