#!/usr/bin/env python3
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
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
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app_version import APP_NAME, get_app_version, get_window_title
from tool_registry import (
    SHARED_PARAMETERS,
    discover_tools,
    install_tool_zip,
    ToolLoadError,
    uninstall_tool,
)
from tool_model import (
    ParameterSpec,
    ProgressUpdate,
    ToolExecutionResult,
    ToolParameters,
    ToolSpec,
    build_output_path,
)


@dataclass
class ExecutionRequest:
    tool: ToolSpec
    parameters: ToolParameters


class ToolWorker(QObject):
    log = Signal(str)
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, request: ExecutionRequest) -> None:
        super().__init__()
        self.request = request

    def run(self) -> None:
        try:
            exit_code = self.request.tool.executor(
                self.request.parameters,
                self.log.emit,
                self.progress.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        self.finished.emit(exit_code)


class ErrorReportDialog(QDialog):
    def __init__(self, title: str, summary: str, details: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(860, 560)

        layout = QVBoxLayout(self)
        summary_label = QLabel(summary, self)
        summary_label.setWordWrap(True)

        details_view = QPlainTextEdit(self)
        details_view.setReadOnly(True)
        details_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        details_view.setPlainText(details)

        close_button = QPushButton("关闭", self)
        close_button.clicked.connect(self.accept)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(close_button)

        layout.addWidget(summary_label)
        layout.addWidget(details_view, 1)
        layout.addLayout(button_row)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.thread: QThread | None = None
        self.worker: ToolWorker | None = None
        self.settings = QSettings("QQxiaoming", APP_NAME)
        self.tool_specs = discover_tools()
        self.shared_parameter_widgets: dict[str, QLineEdit] = {}
        self.shared_parameter_specs: dict[str, ParameterSpec] = {}
        self.tool_parameter_widgets: dict[str, QLineEdit] = {}
        self.tool_parameter_specs: dict[str, ParameterSpec] = {}
        self.app_version = get_app_version()

        self.setWindowTitle(get_window_title())
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
            self.add_tool_combo_item(tool)
        self.load_tool_button = QPushButton("加载工具", self)
        self.load_tool_button.clicked.connect(self.load_custom_tool)
        self.unload_tool_button = QPushButton("卸载工具", self)
        self.unload_tool_button.clicked.connect(self.unload_current_tool)
        self.tool_description = QLabel(self)
        self.tool_description.setWordWrap(True)
        self.tool_description.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.tool_description.setTextInteractionFlags(Qt.TextSelectableByMouse)

        tool_layout.addWidget(QLabel("工具", self), 0, 0)
        tool_layout.addWidget(self.tool_combo, 0, 1)
        tool_layout.addWidget(self.load_tool_button, 0, 2)
        tool_layout.addWidget(self.unload_tool_button, 0, 3)
        tool_layout.addWidget(QLabel("说明", self), 1, 0)
        tool_layout.addWidget(self.tool_description, 1, 1, 1, 3)

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

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.status_label = QLabel("就绪", self)
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setFixedWidth(180)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        status_row.addWidget(self.status_label, 1)
        status_row.addStretch(1)
        status_row.addWidget(self.progress_bar)

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
        layout.addLayout(status_row)
        layout.addWidget(log_group, 1)

        self.tool_combo.currentIndexChanged.connect(self.on_tool_changed)
        self.rebuild_shared_parameter_form()
        self.restore_settings()

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
        line_edit.textChanged.connect(self.save_settings)

        if parameter.key == "input_path":
            line_edit.textChanged.connect(self.maybe_update_output_path)

    def shared_setting_key(self, parameter_key: str) -> str:
        return f"shared/{parameter_key}"

    def tool_setting_key(self, tool_key: str, parameter_key: str) -> str:
        return f"tools/{tool_key}/{parameter_key}"

    def saved_shared_value(self, parameter: ParameterSpec) -> str:
        saved_value = self.settings.value(self.shared_setting_key(parameter.key), "", type=str)
        return saved_value or self.default_parameter_value(parameter)

    def saved_tool_value(self, tool: ToolSpec, parameter: ParameterSpec) -> str:
        saved_value = self.settings.value(
            self.tool_setting_key(tool.key, parameter.key),
            "",
            type=str,
        )
        return saved_value or self.default_parameter_value(parameter)

    def restore_settings(self) -> None:
        self.restore_window_geometry()

        for parameter in SHARED_PARAMETERS:
            widget = self.shared_parameter_widgets.get(parameter.key)
            if widget is None:
                continue
            widget.setText(self.saved_shared_value(parameter))

        saved_tool_key = self.settings.value("ui/current_tool_key", "", type=str)
        tool_index = self.tool_combo.findData(saved_tool_key)
        if tool_index >= 0:
            self.tool_combo.setCurrentIndex(tool_index)
        else:
            self.on_tool_changed()

        self.restore_tool_parameter_values(self.current_tool())
        self.save_settings()

    def restore_tool_parameter_values(self, tool: ToolSpec) -> None:
        for parameter in tool.parameters:
            widget = self.tool_parameter_widgets.get(parameter.key)
            if widget is None:
                continue
            widget.setText(self.saved_tool_value(tool, parameter))

    def current_tool(self) -> ToolSpec:
        index = self.tool_combo.currentIndex()
        return self.tool_specs[index]

    def tool_display_name(self, tool: ToolSpec) -> str:
        source_label = "内置" if tool.is_builtin else "自定义"
        return f"{tool.name} [{source_label}]"

    def add_tool_combo_item(self, tool: ToolSpec) -> None:
        self.tool_combo.addItem(self.tool_display_name(tool), tool.key)
        item_index = self.tool_combo.count() - 1
        tooltip = tool.description
        if not tool.is_builtin and tool.source_path:
            tooltip_lines = [tool.description, f"来源：{tool.source_path}"]
            tcl_script = tool.internal_parameters.get("tcl_script", "").strip()
            if tcl_script:
                tooltip_lines.append(f"Tcl 路径：{Path(tcl_script).expanduser().resolve()}")
            tooltip = "\n".join(tooltip_lines)
        self.tool_combo.setItemData(item_index, tooltip, Qt.ToolTipRole)

    def reload_tool_specs(self, preferred_tool_key: str | None = None) -> None:
        if self.thread is not None:
            return

        selected_tool_key = preferred_tool_key or self.settings.value("ui/current_tool_key", "", type=str)
        self.tool_specs = discover_tools()

        self.tool_combo.blockSignals(True)
        self.tool_combo.clear()
        for tool in self.tool_specs:
            self.add_tool_combo_item(tool)
        self.tool_combo.blockSignals(False)

        if not self.tool_specs:
            self.tool_description.clear()
            self.unload_tool_button.setEnabled(False)
            self.run_button.setEnabled(False)
            return

        selected_index = self.tool_combo.findData(selected_tool_key)
        if selected_index < 0:
            selected_index = 0
        self.tool_combo.setCurrentIndex(selected_index)
        self.on_tool_changed()

    def on_tool_changed(self) -> None:
        tool = self.current_tool()
        self.tool_description.setText(tool.description)
        self.run_button.setText(tool.run_button_text)
        self.rebuild_parameter_form(tool)
        self.restore_tool_parameter_values(tool)
        self.unload_tool_button.setEnabled((not tool.is_builtin) and self.thread is None)
        self.load_tool_button.setEnabled(self.thread is None)
        self.clear_table_result()
        self.save_settings()

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
                self.saved_shared_value(parameter),
            )

    def rebuild_parameter_form(
        self,
        tool: ToolSpec,
    ) -> None:
        while self.tool_form_layout.count():
            item = self.tool_form_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.tool_parameter_widgets = {}
        self.tool_parameter_specs = {}

        for row, parameter in enumerate(tool.parameters):
            self._add_browse_row(
                self.tool_form_layout,
                self.tool_parameter_widgets,
                self.tool_parameter_specs,
                row,
                parameter,
                self.saved_tool_value(tool, parameter),
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

    def restore_window_geometry(self) -> None:
        saved_geometry = self.settings.value("ui/window_geometry")
        if saved_geometry is not None:
            self.restoreGeometry(saved_geometry)

    def save_settings(self) -> None:
        self.settings.setValue("ui/current_tool_key", self.current_tool().key)

        for key, widget in self.shared_parameter_widgets.items():
            self.settings.setValue(self.shared_setting_key(key), widget.text().strip())

        current_tool = self.current_tool()
        for key, widget in self.tool_parameter_widgets.items():
            self.settings.setValue(
                self.tool_setting_key(current_tool.key, key),
                widget.text().strip(),
            )

        self.settings.sync()

    def closeEvent(self, event) -> None:
        self.settings.setValue("ui/window_geometry", self.saveGeometry())
        self.save_settings()
        super().closeEvent(event)

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
        if not self.tool_specs:
            QMessageBox.warning(self, "无可用工具", "当前没有可执行的工具。")
            return False

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
        self.load_tool_button.setEnabled(not running)
        self.unload_tool_button.setEnabled((not running) and (not self.current_tool().is_builtin))
        if running:
            self.status_label.setText("运行中...")
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat("")

    def load_custom_tool(self) -> None:
        if self.thread is not None:
            QMessageBox.information(self, "正在运行", "请等待当前工具执行完成后再加载新工具。")
            return

        zip_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择工具压缩包",
            str(Path.cwd()),
            "Zip Files (*.zip)",
        )
        if not zip_path:
            return

        try:
            tool = install_tool_zip(zip_path)
        except FileExistsError as exc:
            QMessageBox.warning(self, "加载失败", str(exc))
            return
        except ToolLoadError as exc:
            self.append_log(f"自定义工具加载失败：{exc.summary}")
            ErrorReportDialog("自定义工具加载失败", exc.summary, exc.details, self).exec()
            return
        except Exception as exc:
            QMessageBox.critical(self, "加载失败", str(exc))
            return

        self.append_log(f"已加载用户工具：{tool.name}")
        self.reload_tool_specs(preferred_tool_key=tool.key)
        QMessageBox.information(self, "加载成功", f"已加载工具：{tool.name}")

    def unload_current_tool(self) -> None:
        if self.thread is not None:
            QMessageBox.information(self, "正在运行", "请等待当前工具执行完成后再卸载工具。")
            return

        tool = self.current_tool()
        if tool.is_builtin:
            QMessageBox.information(self, "不可卸载", "当前选中的是内置工具，不能卸载。")
            return

        reply = QMessageBox.question(
            self,
            "确认卸载",
            f"确定要卸载工具“{tool.name}”吗？",
        )
        if reply != QMessageBox.Yes:
            return

        removed_tool_key = tool.key
        removed_tool_name = tool.name
        try:
            uninstall_tool(tool)
        except Exception as exc:
            QMessageBox.critical(self, "卸载失败", str(exc))
            return

        self.settings.remove(f"tools/{removed_tool_key}")
        if self.settings.value("ui/current_tool_key", "", type=str) == removed_tool_key:
            self.settings.remove("ui/current_tool_key")
        self.append_log(f"已卸载用户工具：{removed_tool_name}")
        self.reload_tool_specs()
        QMessageBox.information(self, "卸载成功", f"已卸载工具：{removed_tool_name}")

    def reset_progress_display(self, status_text: str) -> None:
        self.status_label.setText(status_text)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")

    def complete_progress_display(self, status_text: str) -> None:
        self.status_label.setText(status_text)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("%p%")

    def apply_progress_update(self, update: ProgressUpdate) -> None:
        if update.message:
            self.status_label.setText(update.message)

        if update.mode == "indeterminate":
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat("")
            return

        if update.mode == "determinate":
            maximum = max(1, update.maximum)
            value = min(max(update.value, 0), maximum)
            self.progress_bar.setRange(0, maximum)
            self.progress_bar.setValue(value)
            self.progress_bar.setFormat("%p%")
            return

        if update.mode == "hidden":
            self.reset_progress_display(self.status_label.text())

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
        self.worker.progress.connect(self.apply_progress_update)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.cleanup_thread)
        self.thread.start()

    def on_finished(self, result: ToolExecutionResult) -> None:
        if result.exit_code == 0:
            self.run_button.setEnabled(True)
            self.append_log("工具执行成功。")
            tool = self.current_tool()
            parameters = self.collect_parameter_values()
            parameters.update(tool.internal_parameters)
            self.complete_progress_display("正在显示结果...")
            tool.success_handler(self, result, parameters)
            self.reset_progress_display("已完成")
            self.append_log("工具成功后的界面反馈已完成。")
            return

        self.run_button.setEnabled(True)
        self.reset_progress_display(f"执行失败，退出码 {result.exit_code}")
        self.append_log(f"工具执行失败，退出码 {result.exit_code}。")
        QMessageBox.critical(self, "失败", f"工具执行失败，退出码 {result.exit_code}。")

    def on_failed(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.reset_progress_display("失败")
        self.append_log(f"错误：{message}")
        QMessageBox.critical(self, "错误", message)

    def cleanup_thread(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
        if self.thread is not None:
            self.thread.deleteLater()
        self.worker = None
        self.thread = None
        self.load_tool_button.setEnabled(True)
        if self.tool_specs:
            self.unload_tool_button.setEnabled(not self.current_tool().is_builtin)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())