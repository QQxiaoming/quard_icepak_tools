from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tool_model import TableData, ToolExecutionResult, ToolParameters
from ui_components import apply_dialog_chrome


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


class MeshQualityResultDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_dialog_chrome(self)
        self.setWindowTitle("网格质量评估结果")
        self.resize(980, 760)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.summary_label = QLabel("暂无结果。", self)
        self.summary_label.setWordWrap(True)

        self.hint_label = QLabel(
            "说明：Quality 和 Face alignment 一般越大越好，Skewness 一般越小越好，Cell volume 应保持正值。",
            self,
        )
        self.hint_label.setWordWrap(True)
        self.hint_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.result_table = QTableWidget(self)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.result_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.result_table.setSortingEnabled(True)
        self.result_table.horizontalHeader().setSectionsClickable(True)
        self.result_table.horizontalHeader().setSortIndicatorShown(True)

        self.report_view = QPlainTextEdit(self)
        self.report_view.setReadOnly(True)
        self.report_view.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.report_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        actions = QHBoxLayout()
        actions.addStretch(1)
        close_button = QPushButton("关闭", self)
        close_button.clicked.connect(self.close)
        actions.addWidget(close_button)

        layout.addWidget(self.summary_label)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.result_table, 1)
        layout.addWidget(self.report_view, 1)
        layout.addLayout(actions)

    def set_result(self, table_data: TableData, report_text: str | None) -> None:
        self.summary_label.setText(
            f"网格生成完成，已统计 {len(table_data.rows)} 项质量指标。"
        )
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
        self.report_view.setPlainText(report_text or "未生成诊断建议。")


def show_mesh_quality_result(
    parent: QWidget,
    result: ToolExecutionResult,
    parameters: ToolParameters,
) -> None:
    del parameters
    if result.table_data is None:
        return

    dialog = MeshQualityResultDialog(parent)
    setattr(parent, "_mesh_quality_result_dialog", dialog)
    dialog.destroyed.connect(
        lambda *_args: setattr(parent, "_mesh_quality_result_dialog", None)
    )
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)
    dialog.set_result(result.table_data, result.report_text)
    dialog.setWindowModality(Qt.WindowModal)
    dialog.exec()
