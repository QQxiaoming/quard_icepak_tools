from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
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

from .tool import (
    THICKNESS_LABEL,
    apply_pair_adjustment,
    build_adjustment_plan,
    list_block_dimensions,
    normalize_stack_axis,
    parse_block_records,
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


class PairedBlockThicknessResultDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_table_data: TableData | None = None
        self.parameters: ToolParameters = {}
        self.stack_axis = "z"
        self.highlighted_partner_name: str | None = None

        self.setWindowTitle("配对 Block 厚度调整")
        self.resize(1100, 720)

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
        self.result_table.itemSelectionChanged.connect(self.sync_combo_from_table)

        control_layout = QFormLayout()
        control_layout.setSpacing(10)

        self.block_combo = QComboBox(self)
        self.block_combo.currentIndexChanged.connect(self.sync_table_from_combo)
        self.block_combo.currentIndexChanged.connect(self.update_preview)

        self.direction_combo = QComboBox(self)
        self.direction_combo.currentIndexChanged.connect(self.update_preview)

        self.delta_spin = QDoubleSpinBox(self)
        self.delta_spin.setDecimals(6)
        self.delta_spin.setRange(-1000000.0, 1000000.0)
        self.delta_spin.setSingleStep(0.1)
        self.delta_spin.setValue(0.1)
        self.delta_spin.setSuffix(" mm")
        self.delta_spin.valueChanged.connect(self.update_preview)

        self.preview_label = QLabel(
            "输入正值表示朝所选方向增大厚度，输入负值表示朝所选方向减小厚度。",
            self,
        )
        self.preview_label.setWordWrap(True)

        control_layout.addRow("目标 block", self.block_combo)
        self.axis_label = QLabel(self)
        control_layout.addRow("厚度堆叠方向", self.axis_label)
        control_layout.addRow("调整方向", self.direction_combo)
        control_layout.addRow("厚度调整量", self.delta_spin)
        control_layout.addRow("预检结果", self.preview_label)

        controls_widget = QWidget(self)
        controls_widget.setLayout(control_layout)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.export_csv_button = QPushButton("导出当前表格为 CSV", self)
        self.export_csv_button.setEnabled(False)
        self.export_csv_button.clicked.connect(self.export_current_table_to_csv)
        self.apply_button = QPushButton("应用调整", self)
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_adjustment)
        close_button = QPushButton("关闭", self)
        close_button.clicked.connect(self.close)
        actions.addWidget(self.export_csv_button)
        actions.addWidget(self.apply_button)
        actions.addWidget(close_button)

        layout.addWidget(self.summary_label)
        layout.addWidget(self.result_table, 1)
        layout.addWidget(controls_widget)
        layout.addLayout(actions)

    def set_result(self, table_data: TableData, parameters: ToolParameters) -> None:
        self.current_table_data = table_data
        self.parameters = dict(parameters)
        self.stack_axis = normalize_stack_axis(self.parameters.get("stack_axis"))
        self.axis_label.setText(f"{self.stack_axis.upper()} 轴")
        self._rebuild_direction_options()

        records = parse_block_records(table_data)
        self.summary_label.setText(
            f"已枚举 {len(records)} 个 block 形体记录。当前厚度堆叠方向为 {self.stack_axis.upper()} 轴，可直接执行配对厚度调整。"
        )

        self.result_table.clear()
        self.result_table.setSortingEnabled(False)
        self.result_table.setColumnCount(len(table_data.columns))
        self.result_table.setHorizontalHeaderLabels(list(table_data.columns))
        self.result_table.setRowCount(len(table_data.rows))
        for row_index, row in enumerate(table_data.rows):
            for column_index, value in enumerate(row):
                self.result_table.setItem(row_index, column_index, SortableTableWidgetItem(value))
        self._apply_row_highlights()
        self.result_table.resizeColumnsToContents()
        self.result_table.setSortingEnabled(True)

        names = [record.object_name for record in records]
        current_name = self.block_combo.currentData()
        self.block_combo.blockSignals(True)
        self.block_combo.clear()
        for name in names:
            self.block_combo.addItem(name, name)
        if current_name:
            index = self.block_combo.findData(current_name)
            if index >= 0:
                self.block_combo.setCurrentIndex(index)
        self.block_combo.blockSignals(False)

        self.export_csv_button.setEnabled(True)
        self.sync_table_from_combo()
        self.update_preview()

    def current_plan(self):
        if self.current_table_data is None or self.block_combo.count() == 0:
            return None
        records = parse_block_records(self.current_table_data)
        return build_adjustment_plan(
            records,
            self.block_combo.currentData(),
            self.stack_axis,
            self.direction_combo.currentData(),
            self.delta_spin.value(),
        )

    def _rebuild_direction_options(self) -> None:
        direction = self.direction_combo.currentData()
        axis_upper = self.stack_axis.upper()
        self.direction_combo.blockSignals(True)
        self.direction_combo.clear()
        self.direction_combo.addItem(f"+{axis_upper} 方向", "+")
        self.direction_combo.addItem(f"-{axis_upper} 方向", "-")
        index = self.direction_combo.findData(direction)
        if index >= 0:
            self.direction_combo.setCurrentIndex(index)
        self.direction_combo.blockSignals(False)

    def _apply_row_highlights(self) -> None:
        partner_name = self.highlighted_partner_name
        highlight_foreground = QBrush(QColor("#ffffff"))
        highlight_background = QBrush(QColor("#c62828"))
        default_foreground = QBrush()
        default_background = QBrush()

        for row in range(self.result_table.rowCount()):
            name_item = self.result_table.item(row, 0)
            is_partner_row = name_item is not None and name_item.text() == partner_name
            for column in range(self.result_table.columnCount()):
                item = self.result_table.item(row, column)
                if item is not None:
                    item.setForeground(highlight_foreground if is_partner_row else default_foreground)
                    item.setBackground(highlight_background if is_partner_row else default_background)

    def sync_combo_from_table(self) -> None:
        selected_items = self.result_table.selectedItems()
        if not selected_items:
            return
        row = selected_items[0].row()
        item = self.result_table.item(row, 0)
        if item is None:
            return
        index = self.block_combo.findData(item.text())
        if index < 0 or index == self.block_combo.currentIndex():
            return
        self.block_combo.blockSignals(True)
        self.block_combo.setCurrentIndex(index)
        self.block_combo.blockSignals(False)
        self.update_preview()

    def sync_table_from_combo(self) -> None:
        if self.block_combo.count() == 0:
            return
        target_name = self.block_combo.currentData()
        self.result_table.blockSignals(True)
        self.result_table.clearSelection()
        for row in range(self.result_table.rowCount()):
            item = self.result_table.item(row, 0)
            if item is not None and item.text() == target_name:
                self.result_table.selectRow(row)
                break
        self.result_table.blockSignals(False)
        self.update_preview()

    def update_preview(self) -> None:
        try:
            plan = self.current_plan()
        except Exception as exc:
            self.highlighted_partner_name = None
            self._apply_row_highlights()
            self.preview_label.setText(str(exc))
            self.apply_button.setEnabled(False)
            return

        if plan is None:
            self.highlighted_partner_name = None
            self._apply_row_highlights()
            self.preview_label.setText("暂无可调整的 block。")
            self.apply_button.setEnabled(False)
            return

        self.highlighted_partner_name = plan.partner.object_name
        self._apply_row_highlights()

        self.preview_label.setText(
            "配对对象："
            f"{plan.partner.object_name}。"
            f"调整后所选 block {THICKNESS_LABEL[self.stack_axis]} = {plan.new_selected_thickness:.6f} mm，"
            f"相邻 block {THICKNESS_LABEL[self.stack_axis]} = {plan.new_partner_thickness:.6f} mm，"
            f"共享界面 {self.stack_axis} = {plan.new_shared_coordinate:.6f} mm。"
        )
        self.apply_button.setEnabled(True)

    def set_busy(self, busy: bool) -> None:
        self.apply_button.setEnabled(not busy)
        self.export_csv_button.setEnabled(not busy and self.current_table_data is not None)
        self.block_combo.setEnabled(not busy)
        self.direction_combo.setEnabled(not busy)
        self.delta_spin.setEnabled(not busy)

    def apply_adjustment(self) -> None:
        try:
            plan = self.current_plan()
        except Exception as exc:
            QMessageBox.warning(self, "无法执行调整", str(exc))
            return

        if plan is None:
            return

        self.set_busy(True)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            apply_pair_adjustment(parameters=self.parameters, plan=plan)
            refreshed = list_block_dimensions(
                input_path=self.parameters["input_path"],
                icepak_bin=self.parameters.get("icepak_bin") or None,
                env_script=self.parameters.get("env_script") or None,
            )
            if refreshed.exit_code != 0 or refreshed.table_data is None:
                raise RuntimeError("调整已执行，但重新枚举 block 结果失败。")
            self.set_result(refreshed.table_data, self.parameters)
        except Exception as exc:
            QMessageBox.critical(self, "调整失败", str(exc))
        else:
            QMessageBox.information(
                self,
                "调整完成",
                (
                    f"已完成 {plan.selected.object_name} 与 {plan.partner.object_name} 的配对厚度调整。\n"
                    f"厚度方向：{plan.direction_sign}{plan.stack_axis.upper()}，调整量：{plan.delta_mm:.6f} mm。"
                ),
            )
        finally:
            QApplication.restoreOverrideCursor()
            self.set_busy(False)
            self.update_preview()

    def export_current_table_to_csv(self) -> None:
        if self.current_table_data is None:
            return

        default_name = self.current_table_data.default_export_name
        start_path = str(Path.cwd() / default_name)
        input_path = self.parameters.get("input_path", "")
        if input_path:
            start_path = build_output_path(input_path, default_name)

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出当前 Block 表格为 CSV",
            start_path,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not output_path:
            return

        with Path(output_path).expanduser().resolve().open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(self.current_table_data.columns)
            writer.writerows(self.current_table_data.rows)

        QMessageBox.information(self, "导出完成", f"CSV 已导出到：\n{output_path}")


def show_paired_block_dz_result(
    parent: QWidget,
    result: ToolExecutionResult,
    parameters: ToolParameters,
) -> None:
    if result.table_data is None:
        return

    dialog = PairedBlockThicknessResultDialog(parent)
    setattr(parent, "_paired_block_thickness_dialog", dialog)
    dialog.destroyed.connect(lambda *_args: setattr(parent, "_paired_block_thickness_dialog", None))
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)
    dialog.set_result(result.table_data, parameters)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()