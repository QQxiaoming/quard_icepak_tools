from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from tool_model import ToolExecutionResult, ToolParameters


def show_default_success_message(
    parent: QWidget,
    result: ToolExecutionResult,
    parameters: ToolParameters,
) -> None:
    del result
    del parameters
    QMessageBox.information(parent, "完成", "工具执行已完成。")