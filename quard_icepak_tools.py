#!/usr/bin/env python3
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from tool_registry import (
    SHARED_PARAMETERS,
    TOOLS,
)
from tool_model import ParameterSpec, ToolExecutionResult, ToolParameters, ToolSpec, build_output_path


@dataclass
class ExecutionRequest:
    tool: ToolSpec
    parameters: ToolParameters


class ToolWorker(QObject):
    log = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, request: ExecutionRequest) -> None:
        super().__init__()
        self.request = request

    def run(self) -> None:
        try:
            exit_code = self.request.tool.executor(self.request.parameters, self.log.emit)
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        self.finished.emit(exit_code)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.thread: QThread | None = None
        self.worker: ToolWorker | None = None
        self.tool_specs = TOOLS
        self.shared_parameter_widgets: dict[str, QLineEdit] = {}
        self.shared_parameter_specs: dict[str, ParameterSpec] = {}
        self.tool_parameter_widgets: dict[str, QLineEdit] = {}
        self.tool_parameter_specs: dict[str, ParameterSpec] = {}

        self.setWindowTitle("Quard Icepak 工具箱")
        self.resize(880, 620)

        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        tool_group = QGroupBox("工具选择", self)
        tool_layout = QGridLayout(tool_group)
        tool_layout.setHorizontalSpacing(10)
        tool_layout.setVerticalSpacing(10)

        self.tool_combo = QComboBox(self)
        for tool in self.tool_specs:
            self.tool_combo.addItem(tool.name, tool.key)
        self.tool_description = QLabel(self)
        self.tool_description.setWordWrap(True)
        self.tool_description.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.tool_description.setTextInteractionFlags(Qt.TextSelectableByMouse)

        tool_layout.addWidget(QLabel("工具", self), 0, 0)
        tool_layout.addWidget(self.tool_combo, 0, 1, 1, 2)
        tool_layout.addWidget(QLabel("说明", self), 1, 0)
        tool_layout.addWidget(self.tool_description, 1, 1, 1, 2)

        shared_group = QGroupBox("公共配置", self)
        self.shared_form_layout = QGridLayout(shared_group)
        self.shared_form_layout.setHorizontalSpacing(10)
        self.shared_form_layout.setVerticalSpacing(10)

        tool_form_group = QGroupBox("工具专用配置", self)
        self.tool_form_layout = QGridLayout(tool_form_group)
        self.tool_form_layout.setHorizontalSpacing(10)
        self.tool_form_layout.setVerticalSpacing(10)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.run_button = QPushButton("运行工具", self)
        self.run_button.clicked.connect(self.start_tool)
        self.clear_log_button = QPushButton("清空日志", self)
        self.clear_log_button.clicked.connect(self.clear_log)
        actions.addWidget(self.run_button)
        actions.addWidget(self.clear_log_button)
        actions.addStretch(1)

        self.status_label = QLabel("就绪", self)
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        log_group = QGroupBox("执行日志", self)
        log_layout = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout.addWidget(self.log_view)

        layout.addWidget(tool_group)
        layout.addWidget(shared_group)
        layout.addWidget(tool_form_group)
        layout.addLayout(actions)
        layout.addWidget(self.status_label)
        layout.addWidget(log_group, 1)

        self.tool_combo.currentIndexChanged.connect(self.on_tool_changed)
        self.rebuild_shared_parameter_form()
        self.on_tool_changed()

    def _add_browse_row(
        self,
        layout: QGridLayout,
        widgets: dict[str, QLineEdit],
        specs: dict[str, ParameterSpec],
        row: int,
        parameter: ParameterSpec,
        value: str,
    ) -> None:
        label_text = parameter.label

        label = QLabel(label_text, self)
        line_edit = QLineEdit(value, self)
        browse_button = QPushButton("浏览", self)
        browse_button.clicked.connect(
            lambda _checked=False, key=parameter.key: self.browse_parameter(key)
        )
        if parameter.browse_mode == "none":
            browse_button.setEnabled(False)
        layout.addWidget(label, row, 0)
        layout.addWidget(line_edit, row, 1)
        layout.addWidget(browse_button, row, 2)
        widgets[parameter.key] = line_edit
        specs[parameter.key] = parameter

        if parameter.key == "input_path":
            line_edit.textChanged.connect(self.maybe_update_output_path)

    def current_tool(self) -> ToolSpec:
        index = self.tool_combo.currentIndex()
        return self.tool_specs[index]

    def on_tool_changed(self) -> None:
        tool = self.current_tool()
        self.tool_description.setText(tool.description)
        self.run_button.setText(tool.run_button_text)
        previous_values = self.collect_tool_parameter_values()
        self.rebuild_parameter_form(tool, previous_values)
        self.clear_table_result()

    def collect_shared_parameter_values(self) -> ToolParameters:
        return {
            key: widget.text().strip()
            for key, widget in self.shared_parameter_widgets.items()
        }

    def collect_tool_parameter_values(self) -> ToolParameters:
        return {
            key: widget.text().strip()
            for key, widget in self.tool_parameter_widgets.items()
        }

    def collect_parameter_values(self) -> ToolParameters:
        values = self.collect_shared_parameter_values()
        values.update(self.collect_tool_parameter_values())
        return values

    def rebuild_shared_parameter_form(self) -> None:
        while self.shared_form_layout.count():
            item = self.shared_form_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.shared_parameter_widgets = {}
        self.shared_parameter_specs = {}

        for row, parameter in enumerate(SHARED_PARAMETERS):
            self._add_browse_row(
                self.shared_form_layout,
                self.shared_parameter_widgets,
                self.shared_parameter_specs,
                row,
                parameter,
                self.default_parameter_value(parameter),
            )

    def rebuild_parameter_form(
        self,
        tool: ToolSpec,
        previous_values: ToolParameters,
    ) -> None:
        while self.tool_form_layout.count():
            item = self.tool_form_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.tool_parameter_widgets = {}
        self.tool_parameter_specs = {}

        for row, parameter in enumerate(tool.parameters):
            if parameter.default_output_name:
                value = self.default_parameter_value(parameter)
            else:
                value = previous_values.get(parameter.key) or self.default_parameter_value(parameter)
            self._add_browse_row(
                self.tool_form_layout,
                self.tool_parameter_widgets,
                self.tool_parameter_specs,
                row,
                parameter,
                value,
            )

        self.maybe_update_output_path()

    def default_parameter_value(self, parameter: ParameterSpec) -> str:
        if parameter.default_output_name:
            input_path = self.shared_parameter_widgets.get("input_path")
            input_value = input_path.text().strip() if input_path is not None else ""
            if not input_value:
                input_value = str(Path.cwd())
            return build_output_path(input_value, parameter.default_output_name)

        if not parameter.default_value:
            return ""

        default_path = Path(parameter.default_value).expanduser()
        if default_path.is_absolute():
            return str(default_path)

        if default_path.suffix:
            return str(Path(__file__).resolve().with_name(parameter.default_value))

        return parameter.default_value

    def append_log(self, message: str) -> None:
        if not message:
            return
        self.log_view.appendPlainText(message)
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_log(self) -> None:
        self.log_view.clear()

    def clear_table_result(self) -> None:
        return

    def maybe_update_output_path(self) -> None:
        output_spec = self.tool_parameter_specs.get("output_path")
        output_widget = self.tool_parameter_widgets.get("output_path")
        input_widget = self.shared_parameter_widgets.get("input_path")
        if output_spec is None or output_widget is None or input_widget is None:
            return

        if output_spec.default_output_name:
            current_output_text = output_widget.text().strip()
            if current_output_text:
                current_output = Path(current_output_text).expanduser()
                if current_output.name != output_spec.default_output_name:
                    return

        input_text = input_widget.text().strip()
        if not input_text or not output_spec.default_output_name:
            return

        output_widget.setText(build_output_path(input_text, output_spec.default_output_name))

    def browse_parameter(self, parameter_key: str) -> None:
        if parameter_key in self.shared_parameter_specs:
            parameter = self.shared_parameter_specs[parameter_key]
            widget = self.shared_parameter_widgets[parameter_key]
        else:
            parameter = self.tool_parameter_specs[parameter_key]
            widget = self.tool_parameter_widgets[parameter_key]
        start_path = widget.text() or str(Path.cwd())

        if parameter.browse_mode == "project_path":
            path, _ = QFileDialog.getOpenFileName(
                self,
                "选择 Workbench 工程",
                start_path,
                parameter.file_filter,
            )
            if path:
                widget.setText(path)
                return

            directory = QFileDialog.getExistingDirectory(
                self,
                "或选择工程目录",
                start_path,
            )
            if directory:
                widget.setText(directory)
            return

        if parameter.browse_mode == "save_file":
            path, _ = QFileDialog.getSaveFileName(
                self,
                "选择输出文件",
                widget.text() or self.default_parameter_value(parameter),
                parameter.file_filter,
            )
        else:
            path, _ = QFileDialog.getOpenFileName(
                self,
                f"选择{parameter.label}",
                start_path,
                parameter.file_filter,
            )

        if path:
            widget.setText(path)

    def validate_inputs(self) -> bool:
        required = {}
        for parameter in SHARED_PARAMETERS:
            if parameter.required:
                required[parameter.label] = self.shared_parameter_widgets[parameter.key].text().strip()

        for parameter in self.current_tool().parameters:
            if parameter.required:
                required[parameter.label] = self.tool_parameter_widgets[parameter.key].text().strip()

        missing = [name for name, value in required.items() if not value]
        if missing:
            QMessageBox.warning(self, "缺少必填项", "请填写：" + "、".join(missing))
            return False
        return True

    def set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.status_label.setText("运行中..." if running else "就绪")

    def start_tool(self) -> None:
        if self.thread is not None:
            QMessageBox.information(self, "正在运行", "已有工具正在运行。")
            return

        if not self.validate_inputs():
            return

        self.clear_log()
        self.clear_table_result()
        tool = self.current_tool()
        self.append_log(f"开始执行工具：{tool.name}")
        self.set_running(True)

        self.thread = QThread(self)
        parameters = self.collect_parameter_values()
        parameters.update(tool.internal_parameters)
        self.worker = ToolWorker(
            ExecutionRequest(
                tool=tool,
                parameters=parameters,
            )
        )
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.cleanup_thread)
        self.thread.start()

    def on_finished(self, result: ToolExecutionResult) -> None:
        self.set_running(False)
        if result.exit_code == 0:
            self.status_label.setText("已完成")
            self.append_log("工具执行成功。")
            tool = self.current_tool()
            parameters = self.collect_parameter_values()
            parameters.update(tool.internal_parameters)
            tool.success_handler(self, result, parameters)
            self.append_log("工具成功后的界面反馈已完成。")
            return

        self.status_label.setText(f"执行失败，退出码 {result.exit_code}")
        self.append_log(f"工具执行失败，退出码 {result.exit_code}。")
        QMessageBox.critical(self, "失败", f"工具执行失败，退出码 {result.exit_code}。")

    def on_failed(self, message: str) -> None:
        self.set_running(False)
        self.status_label.setText("失败")
        self.append_log(f"错误：{message}")
        QMessageBox.critical(self, "错误", message)

    def cleanup_thread(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
        if self.thread is not None:
            self.thread.deleteLater()
        self.worker = None
        self.thread = None


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())