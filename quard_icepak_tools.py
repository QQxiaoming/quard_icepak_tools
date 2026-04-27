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
    QFrame,
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
    QScrollArea,
    QSizePolicy,
    QSplitter,
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
        self.resize(1180, 760)
        self.setMinimumSize(1020, 680)
        self.apply_window_style()

        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal, root)
        splitter.setChildrenCollapsible(False)

        left_scroll = QScrollArea(self)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)

        left_content = QWidget(self)
        left_scroll.setWidget(left_content)

        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(16)

        tool_group = QGroupBox("工具概览", self)
        tool_layout = QGridLayout(tool_group)
        tool_layout.setContentsMargins(18, 18, 18, 18)
        tool_layout.setHorizontalSpacing(12)
        tool_layout.setVerticalSpacing(12)

        self.tool_combo = QComboBox(self)
        self.tool_combo.setMinimumWidth(360)
        for tool in self.tool_specs:
            self.add_tool_combo_item(tool)

        self.load_tool_button = QPushButton("加载工具", self)
        self.load_tool_button.setObjectName("toolManageButton")
        self.load_tool_button.clicked.connect(self.load_custom_tool)
        self.unload_tool_button = QPushButton("卸载工具", self)
        self.unload_tool_button.setObjectName("toolManageButton")
        self.unload_tool_button.clicked.connect(self.unload_current_tool)
        self.tool_summary = QLabel(self)
        self.tool_summary.setObjectName("sectionHint")
        self.tool_summary.setWordWrap(True)
        self.tool_title = QLabel(self)
        self.tool_title.setObjectName("toolTitle")
        self.tool_title.setWordWrap(True)
        self.tool_version_badge = QLabel(self)
        self.tool_version_badge.setObjectName("toolBadge")
        self.tool_source_badge = QLabel(self)
        self.tool_source_badge.setObjectName("toolBadge")
        self.tool_description = QLabel(self)
        self.tool_description.setWordWrap(True)
        self.tool_description.setObjectName("toolDescription")
        self.tool_description.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.tool_description.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.tool_description.setMinimumHeight(86)

        manage_label = QLabel("工具管理", self)
        manage_label.setObjectName("fieldHelp")

        manage_panel = QWidget(self)
        manage_layout = QHBoxLayout(manage_panel)
        manage_layout.setContentsMargins(0, 0, 0, 0)
        manage_layout.setSpacing(8)
        manage_layout.addWidget(manage_label)
        manage_layout.addStretch(1)
        manage_layout.addWidget(self.load_tool_button)
        manage_layout.addWidget(self.unload_tool_button)

        meta_panel = QWidget(self)
        meta_layout = QHBoxLayout(meta_panel)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(8)
        meta_layout.addWidget(self.tool_version_badge)
        meta_layout.addWidget(self.tool_source_badge)
        meta_layout.addStretch(1)

        detail_panel = QWidget(self)
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)
        detail_layout.addWidget(self.tool_title)
        detail_layout.addWidget(meta_panel)
        detail_layout.addWidget(self.tool_description)

        tool_layout.addWidget(self.tool_summary, 0, 0, 1, 4)
        tool_layout.addWidget(manage_panel, 1, 0, 1, 4)
        tool_layout.addWidget(QLabel("当前工具", self), 2, 0)
        tool_layout.addWidget(self.tool_combo, 2, 1, 1, 3)
        tool_layout.addWidget(QLabel("工具详情", self), 3, 0, Qt.AlignTop)
        tool_layout.addWidget(detail_panel, 3, 1, 1, 3)

        shared_group = QGroupBox("公共配置", self)
        self.shared_form_layout = QGridLayout(shared_group)
        self.shared_form_layout.setContentsMargins(18, 18, 18, 18)
        self.shared_form_layout.setHorizontalSpacing(12)
        self.shared_form_layout.setVerticalSpacing(12)

        tool_form_group = QGroupBox("工具专用配置", self)
        self.tool_form_layout = QGridLayout(tool_form_group)
        self.tool_form_layout.setContentsMargins(18, 18, 18, 18)
        self.tool_form_layout.setHorizontalSpacing(12)
        self.tool_form_layout.setVerticalSpacing(12)

        left_layout.addWidget(tool_group)
        left_layout.addWidget(shared_group)
        left_layout.addWidget(tool_form_group)
        left_layout.addStretch(1)

        right_panel = QWidget(self)
        right_panel.setObjectName("sidePanel")
        right_panel.setMinimumWidth(360)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(16)

        execution_group = QGroupBox("执行控制", self)
        execution_layout = QVBoxLayout(execution_group)
        execution_layout.setContentsMargins(18, 18, 18, 18)
        execution_layout.setSpacing(14)

        self.run_hint_label = QLabel("先在左侧完成工具选择与参数配置，再开始执行。", self)
        self.run_hint_label.setObjectName("sectionHint")
        self.run_hint_label.setWordWrap(True)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.run_button = QPushButton("运行工具", self)
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self.start_tool)
        self.clear_log_button = QPushButton("清空日志", self)
        self.clear_log_button.clicked.connect(self.clear_log)
        actions.addWidget(self.run_button, 1)
        actions.addWidget(self.clear_log_button)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.status_label = QLabel("就绪", self)
        self.status_label.setObjectName("statusBadge")
        self.status_label.setProperty("tone", "idle")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        status_row.addWidget(self.status_label)
        status_row.addWidget(self.progress_bar, 1)

        execution_layout.addWidget(self.run_hint_label)
        execution_layout.addLayout(actions)
        execution_layout.addLayout(status_row)

        log_group = QGroupBox("执行日志", self)
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(18, 18, 18, 18)
        log_layout.setSpacing(12)
        log_hint = QLabel("执行过程、异常信息和结果反馈会持续写入这里。", self)
        log_hint.setObjectName("sectionHint")
        log_hint.setWordWrap(True)
        self.log_view = QPlainTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log_view.setPlaceholderText("执行日志会显示在这里。")
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout.addWidget(log_hint)
        log_layout.addWidget(self.log_view, 1)

        right_layout.addWidget(execution_group)
        right_layout.addWidget(log_group, 1)

        splitter.addWidget(left_scroll)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter, 1)

        self.tool_combo.currentIndexChanged.connect(self.on_tool_changed)
        self.rebuild_shared_parameter_form()
        self.restore_settings()
        self.on_tool_changed()

    def apply_window_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f3f5f7;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d7dde5;
                border-radius: 14px;
                font-weight: 600;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 6px;
                color: #243447;
            }
            QLabel {
                color: #253342;
            }
            QLabel#sectionHint {
                color: #607284;
            }
            QLabel#toolTitle {
                color: #1f2f3d;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#toolBadge {
                color: #506273;
                font-size: 12px;
                background: #f2f5f8;
                border: 1px solid #e0e6ed;
                border-radius: 999px;
                padding: 4px 10px;
                font-weight: 600;
            }
            QLabel#toolDescription {
                background: #f7f9fb;
                border: 1px solid #e0e6ed;
                border-radius: 10px;
                padding: 10px 12px;
                color: #33485c;
            }
            QLabel#statusBadge {
                border-radius: 999px;
                padding: 6px 14px;
                font-weight: 600;
                min-width: 72px;
            }
            QLabel#statusBadge[tone="idle"] {
                background: #e8edf2;
                color: #415466;
            }
            QLabel#statusBadge[tone="running"] {
                background: #dff3ea;
                color: #1f6a49;
            }
            QLabel#statusBadge[tone="success"] {
                background: #deefff;
                color: #16507b;
            }
            QLabel#statusBadge[tone="error"] {
                background: #fde8e8;
                color: #9a2d2d;
            }
            QLabel#fieldHelp {
                color: #6b7c8e;
                font-size: 12px;
            }
            QLabel#emptyStateLabel {
                color: #5f7285;
                background: #f7f9fb;
                border: 1px dashed #cfd8e3;
                border-radius: 10px;
                padding: 12px;
            }
            QLineEdit,
            QComboBox,
            QPlainTextEdit {
                background: #ffffff;
                border: 1px solid #c9d3dd;
                border-radius: 10px;
                padding: 8px 10px;
                selection-background-color: #bfd8f2;
            }
            QLineEdit:focus,
            QComboBox:focus,
            QPlainTextEdit:focus {
                border: 1px solid #4e8ccf;
            }
            QPushButton {
                background: #edf1f5;
                color: #243447;
                border: 1px solid #d0d8e1;
                border-radius: 10px;
                padding: 9px 14px;
            }
            QPushButton:hover {
                background: #e3eaf1;
            }
            QPushButton:disabled {
                color: #8a98a8;
                background: #f3f5f7;
            }
            QPushButton#primaryButton {
                background: #1f6fb2;
                color: #ffffff;
                border: 1px solid #185a91;
                font-weight: 600;
                min-height: 38px;
            }
            QPushButton#primaryButton:hover {
                background: #185f99;
            }
            QPushButton#toolManageButton {
                padding: 7px 12px;
                min-height: 0px;
            }
            QProgressBar {
                min-height: 12px;
                border-radius: 6px;
                background: #e9edf2;
                border: 1px solid #d7dde5;
                text-align: center;
            }
            QProgressBar::chunk {
                border-radius: 5px;
                background: #2f88d6;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            """
        )

    def refresh_status_badge(self, text: str, tone: str) -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("tone", tone)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def parameter_placeholder_text(self, parameter: ParameterSpec) -> str:
        if parameter.example_hint:
            return parameter.example_hint
        if parameter.default_output_name:
            return f"默认自动生成 {parameter.default_output_name}"
        if parameter.browse_mode == "project_path":
            return "选择 .wbpj 文件或可定位到 IcepakProj 的目录"
        if parameter.browse_mode == "save_file":
            return "选择导出文件路径"
        if parameter.browse_mode == "open_file":
            return "选择文件路径"
        return "请输入参数值"

    def parameter_help_text(self, parameter: ParameterSpec) -> str:
        parts: list[str] = []
        parts.append("必填" if parameter.required else "选填")
        if parameter.example_hint:
            parts.append(f"示例：{parameter.example_hint}")
        elif parameter.default_output_name:
            parts.append(f"会按测试用例路径自动补全为 {parameter.default_output_name}")
        elif parameter.default_value:
            parts.append(f"默认值：{self.default_parameter_value(parameter)}")
        return " | ".join(parts)

    def _add_browse_row(
        self,
        layout: QGridLayout,
        widgets: dict[str, QLineEdit],
        specs: dict[str, ParameterSpec],
        row: int,
        parameter: ParameterSpec,
        value: str,
    ) -> None:
        label_text = parameter.label + (" *" if parameter.required else "")

        label = QLabel(label_text, self)
        label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        line_edit = QLineEdit(value, self)
        line_edit.setClearButtonEnabled(True)
        line_edit.setPlaceholderText(self.parameter_placeholder_text(parameter))

        field_container = QWidget(self)
        field_layout = QVBoxLayout(field_container)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(4)

        field_help = QLabel(self.parameter_help_text(parameter), self)
        field_help.setObjectName("fieldHelp")
        field_help.setWordWrap(True)

        field_layout.addWidget(line_edit)
        field_layout.addWidget(field_help)

        browse_button = QPushButton("浏览", self)
        browse_button.clicked.connect(
            lambda _checked=False, key=parameter.key: self.browse_parameter(key)
        )
        if parameter.browse_mode == "none":
            browse_button.setEnabled(False)

        layout.addWidget(label, row, 0)
        layout.addWidget(field_container, row, 1)
        layout.addWidget(browse_button, row, 2, Qt.AlignTop)

        widgets[parameter.key] = line_edit
        specs[parameter.key] = parameter
        line_edit.textChanged.connect(self.save_settings)

        if parameter.key == "input_path":
            line_edit.textChanged.connect(self.maybe_update_output_path)

    def shared_setting_key(self, parameter_key: str) -> str:
        return f"shared/{parameter_key}"

    def tool_setting_key(self, tool_id: str, parameter_key: str) -> str:
        return f"tools/{tool_id}/{parameter_key}"

    def find_tool_by_saved_id(self, saved_tool_id: str) -> ToolSpec | None:
        if not saved_tool_id:
            return None

        for tool in self.tool_specs:
            if tool.identifier == saved_tool_id:
                return tool

        matches = [tool for tool in self.tool_specs if tool.key == saved_tool_id]
        if len(matches) == 1:
            return matches[0]

        return None

    def setting_value_or_default(self, key: str, default_value: str) -> str:
        if not self.settings.contains(key):
            return default_value
        return self.settings.value(key, "", type=str)

    def saved_shared_value(self, parameter: ParameterSpec) -> str:
        return self.setting_value_or_default(
            self.shared_setting_key(parameter.key),
            self.default_parameter_value(parameter),
        )

    def saved_tool_value(self, tool: ToolSpec, parameter: ParameterSpec) -> str:
        identifier_key = self.tool_setting_key(tool.identifier, parameter.key)
        if self.settings.contains(identifier_key):
            return self.settings.value(identifier_key, "", type=str)

        legacy_key = self.tool_setting_key(tool.key, parameter.key)
        if self.settings.contains(legacy_key):
            return self.settings.value(legacy_key, "", type=str)

        return self.default_parameter_value(parameter)

    def restore_settings(self) -> None:
        self.restore_window_geometry()

        for parameter in SHARED_PARAMETERS:
            widget = self.shared_parameter_widgets.get(parameter.key)
            if widget is None:
                continue
            widget.setText(self.saved_shared_value(parameter))

        saved_tool_id = self.settings.value("ui/current_tool_id", "", type=str)
        if not saved_tool_id:
            saved_tool_id = self.settings.value("ui/current_tool_key", "", type=str)

        tool_index = self.tool_combo.findData(saved_tool_id)
        if tool_index < 0:
            saved_tool = self.find_tool_by_saved_id(saved_tool_id)
            if saved_tool is not None:
                tool_index = self.tool_combo.findData(saved_tool.identifier)

        if not self.tool_specs:
            self.tool_description.setText("未发现可用工具。")
            self.run_button.setEnabled(False)
            self.unload_tool_button.setEnabled(False)
            return
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
        if not self.tool_specs:
            raise IndexError("No tools available")
        index = self.tool_combo.currentIndex()
        return self.tool_specs[index]

    def tool_display_name(self, tool: ToolSpec) -> str:
        source_label = "内置" if tool.is_builtin else "自定义"
        return f"{tool.name} v{tool.version} [{source_label}]"

    def add_tool_combo_item(self, tool: ToolSpec) -> None:
        self.tool_combo.addItem(self.tool_display_name(tool), tool.identifier)
        item_index = self.tool_combo.count() - 1
        tooltip_lines = [f"版本：v{tool.version}", tool.description]
        if not tool.is_builtin and tool.source_path:
            tooltip_lines.append(f"来源：{tool.source_path}")
            tcl_script = tool.internal_parameters.get("tcl_script", "").strip()
            if tcl_script:
                tooltip_lines.append(f"Tcl 路径：{Path(tcl_script).expanduser().resolve()}")
        tooltip = "\n".join(tooltip_lines)
        self.tool_combo.setItemData(item_index, tooltip, Qt.ToolTipRole)

    def reload_tool_specs(self, preferred_tool_id: str | None = None) -> None:
        if self.thread is not None:
            return

        selected_tool_id = preferred_tool_id or self.settings.value("ui/current_tool_id", "", type=str)
        if not selected_tool_id:
            selected_tool_id = self.settings.value("ui/current_tool_key", "", type=str)
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

        selected_index = self.tool_combo.findData(selected_tool_id)
        if selected_index < 0:
            selected_tool = self.find_tool_by_saved_id(selected_tool_id)
            if selected_tool is not None:
                selected_index = self.tool_combo.findData(selected_tool.identifier)
        if selected_index < 0:
            selected_index = 0
        self.tool_combo.setCurrentIndex(selected_index)
        self.on_tool_changed()

    def on_tool_changed(self) -> None:
        if not self.tool_specs:
            self.tool_title.setText("未发现可用工具")
            self.tool_version_badge.clear()
            self.tool_source_badge.clear()
            self.tool_description.setText("未发现可用工具。")
            self.tool_summary.setText("当前工作区没有可用工具，无法开始执行。")
            self.run_hint_label.setText("请先加载一个工具压缩包，或在工作区内添加内置工具目录。")
            self.run_button.setEnabled(False)
            self.unload_tool_button.setEnabled(False)
            self.load_tool_button.setEnabled(self.thread is None)
            return

        tool = self.current_tool()
        source_label = "内置工具" if tool.is_builtin else "自定义工具"
        self.tool_summary.setText(
            f"当前已发现 {len(self.tool_specs)} 个工具。先选择工具，再检查参数，最后在右侧执行并查看日志。"
        )
        self.tool_title.setText(tool.name)
        self.tool_version_badge.setText(f"版本 v{tool.version}")
        self.tool_source_badge.setText(source_label)
        self.tool_description.setText(tool.description)
        self.run_hint_label.setText(f"当前操作：{tool.run_button_text}。完成左侧配置后，可直接在这里执行。")
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

        if not tool.parameters:
            empty_label = QLabel("当前工具没有额外配置项，确认公共配置无误后即可运行。", self)
            empty_label.setObjectName("emptyStateLabel")
            empty_label.setWordWrap(True)
            self.tool_form_layout.addWidget(empty_label, 0, 0, 1, 3)
            return

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
        for key, widget in self.shared_parameter_widgets.items():
            self.settings.setValue(self.shared_setting_key(key), widget.text().strip())

        if self.tool_specs:
            current_tool = self.current_tool()
            self.settings.setValue("ui/current_tool_id", current_tool.identifier)
            self.settings.setValue("ui/current_tool_key", current_tool.key)

            for key, widget in self.tool_parameter_widgets.items():
                self.settings.setValue(
                    self.tool_setting_key(current_tool.identifier, key),
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
            self.refresh_status_badge("运行中", "running")
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat("")
            self.run_hint_label.setText("工具正在执行，日志会持续更新。")

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
        self.reload_tool_specs(preferred_tool_id=tool.identifier)
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

        removed_tool_id = tool.identifier
        removed_tool_key = tool.key
        removed_tool_name = tool.name
        try:
            uninstall_tool(tool)
        except Exception as exc:
            QMessageBox.critical(self, "卸载失败", str(exc))
            return

        self.settings.remove(f"tools/{removed_tool_id}")
        if self.settings.value("ui/current_tool_id", "", type=str) == removed_tool_id:
            self.settings.remove("ui/current_tool_id")
        if self.settings.value("ui/current_tool_key", "", type=str) == removed_tool_key:
            self.settings.remove("ui/current_tool_key")
        self.append_log(f"已卸载用户工具：{removed_tool_name}")
        self.reload_tool_specs()
        QMessageBox.information(self, "卸载成功", f"已卸载工具：{removed_tool_name}")

    def reset_progress_display(self, status_text: str) -> None:
        self.refresh_status_badge(status_text, "idle")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")

    def complete_progress_display(self, status_text: str) -> None:
        self.refresh_status_badge(status_text, "success")
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
        self.refresh_status_badge("执行失败", "error")
        self.append_log(f"工具执行失败，退出码 {result.exit_code}。")
        QMessageBox.critical(self, "失败", f"工具执行失败，退出码 {result.exit_code}。")

    def on_failed(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.refresh_status_badge("失败", "error")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
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