#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QSize, QThread, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
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
    QListView,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyleOptionSpinBox,
    QSpinBox,
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
from ui_components import (
    install_theme_styles,
    themed_focus_color,
    themed_glyph_color,
    themed_text_color,
    themed_toggle_colors,
    window_style_sheet,
)


@dataclass
class ExecutionRequest:
    tool: ToolSpec
    parameters: ToolParameters


class ToggleSwitch(QCheckBox):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("parameterToggle")

    def sizeHint(self) -> QSize:
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        return QSize(text_width + 68, 30)

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        track_width = 40
        track_height = 22
        knob_diameter = 16
        spacing = 10
        track_rect = rect.adjusted(rect.width() - track_width, (rect.height() - track_height) // 2, 0, -(rect.height() - track_height) // 2)
        text_rect = rect.adjusted(0, 0, -(track_width + spacing), 0)

        text_color = themed_text_color(self, self.isEnabled(), muted=True)
        painter.setPen(text_color)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())

        track_color, border_color = themed_toggle_colors(self, self.isChecked(), self.isEnabled())

        painter.setPen(QPen(border_color, 1))
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, track_height / 2, track_height / 2)

        knob_x = track_rect.right() - knob_diameter - 3 if self.isChecked() else track_rect.left() + 3
        knob_rect = track_rect.adjusted(
            knob_x - track_rect.left(),
            3,
            -(track_rect.width() - (knob_x - track_rect.left()) - knob_diameter),
            -3,
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(knob_rect)

        if self.hasFocus():
            focus_pen = QPen(themed_focus_color(self), 2)
            painter.setPen(focus_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(track_rect.adjusted(-2, -2, 2, 2), (track_height + 4) / 2, (track_height + 4) / 2)


class ModernComboBox(QComboBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(40)
        self.setView(QListView(self))

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = themed_glyph_color(self, self.isEnabled())
        pen = QPen(color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        center_x = self.width() - 21
        center_y = self.height() // 2 + 1
        size = 5
        painter.drawLine(center_x - size, center_y - 2, center_x, center_y + 3)
        painter.drawLine(center_x + size, center_y - 2, center_x, center_y + 3)


class _ModernSpinBoxMixin:
    def _init_modern_spin_box(self) -> None:
        self.setButtonSymbols(QAbstractSpinBox.UpDownArrows)
        self.setMinimumHeight(40)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        style = self.style()

        up_rect = style.subControlRect(QStyle.CC_SpinBox, option, QStyle.SC_SpinBoxUp, self)
        down_rect = style.subControlRect(QStyle.CC_SpinBox, option, QStyle.SC_SpinBoxDown, self)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = themed_glyph_color(self, self.isEnabled())
        pen = QPen(color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        self._draw_spin_chevron(painter, up_rect, True)
        self._draw_spin_chevron(painter, down_rect, False)

    def _draw_spin_chevron(self, painter: QPainter, rect, is_up: bool) -> None:
        if not rect.isValid():
            return

        center_x = rect.center().x()
        center_y = rect.center().y()
        size = 4
        if is_up:
            painter.drawLine(center_x - size, center_y + 2, center_x, center_y - 2)
            painter.drawLine(center_x + size, center_y + 2, center_x, center_y - 2)
        else:
            painter.drawLine(center_x - size, center_y - 2, center_x, center_y + 2)
            painter.drawLine(center_x + size, center_y - 2, center_x, center_y + 2)


class ModernSpinBox(_ModernSpinBoxMixin, QSpinBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_modern_spin_box()


class ModernDoubleSpinBox(_ModernSpinBoxMixin, QDoubleSpinBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_modern_spin_box()


class ParameterEditor(QWidget):
    valueChanged = Signal(str)

    def __init__(self, parameter: ParameterSpec, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.parameter = parameter
        self._line_edit: QLineEdit | None = None
        self._combo_box: QComboBox | None = None
        self._spin_box: QSpinBox | None = None
        self._double_spin_box: QDoubleSpinBox | None = None
        self._toggle_box: QCheckBox | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        if parameter.value_type == "boolean":
            combo_box = ModernComboBox(self)
            if not parameter.required:
                combo_box.addItem("未设置（沿用当前值）", "")
            combo_box.addItem("是", "1")
            combo_box.addItem("否", "0")
            combo_box.currentIndexChanged.connect(lambda _index: self.valueChanged.emit(self.text()))
            layout.addWidget(combo_box)
            self._combo_box = combo_box
        elif parameter.value_type == "choice" and parameter.choices:
            combo_box = ModernComboBox(self)
            if not parameter.required:
                combo_box.addItem("未设置", "")
            for label, option_value in parameter.choices:
                combo_box.addItem(label, option_value)
            combo_box.currentIndexChanged.connect(lambda _index: self.valueChanged.emit(self.text()))
            layout.addWidget(combo_box)
            self._combo_box = combo_box
        elif parameter.value_type == "integer":
            self._toggle_box = self._build_optional_toggle(layout)
            spin_box = ModernSpinBox(self)
            spin_box.setRange(
                int(parameter.minimum) if parameter.minimum is not None else -1_000_000_000,
                int(parameter.maximum) if parameter.maximum is not None else 1_000_000_000,
            )
            spin_box.setSingleStep(int(parameter.single_step) if parameter.single_step is not None else 1)
            spin_box.valueChanged.connect(lambda _value: self.valueChanged.emit(self.text()))
            layout.addWidget(spin_box, 1)
            self._spin_box = spin_box
            if self._toggle_box is not None:
                self._toggle_box.toggled.connect(spin_box.setEnabled)
                self._toggle_box.toggled.connect(lambda _checked: self.valueChanged.emit(self.text()))
        elif parameter.value_type == "float":
            self._toggle_box = self._build_optional_toggle(layout)
            double_spin_box = ModernDoubleSpinBox(self)
            double_spin_box.setDecimals(parameter.decimals)
            double_spin_box.setRange(
                parameter.minimum if parameter.minimum is not None else -1_000_000_000.0,
                parameter.maximum if parameter.maximum is not None else 1_000_000_000.0,
            )
            double_spin_box.setSingleStep(parameter.single_step if parameter.single_step is not None else 0.1)
            double_spin_box.valueChanged.connect(lambda _value: self.valueChanged.emit(self.text()))
            layout.addWidget(double_spin_box, 1)
            self._double_spin_box = double_spin_box
            if self._toggle_box is not None:
                self._toggle_box.toggled.connect(double_spin_box.setEnabled)
                self._toggle_box.toggled.connect(lambda _checked: self.valueChanged.emit(self.text()))
        else:
            line_edit = QLineEdit(self)
            line_edit.setClearButtonEnabled(True)
            line_edit.textChanged.connect(self.valueChanged.emit)
            layout.addWidget(line_edit)
            self._line_edit = line_edit

        self.setText(value)

    def _build_optional_toggle(self, layout: QHBoxLayout) -> QCheckBox | None:
        if self.parameter.required:
            return None

        toggle_box = ToggleSwitch("覆盖", self)
        layout.addWidget(toggle_box)
        return toggle_box

    def setPlaceholderText(self, text: str) -> None:
        if self._line_edit is not None:
            self._line_edit.setPlaceholderText(text)

    def text(self) -> str:
        if self._line_edit is not None:
            return self._line_edit.text().strip()

        if self._combo_box is not None:
            value = self._combo_box.currentData()
            return "" if value is None else str(value).strip()

        if self._spin_box is not None:
            if self._toggle_box is not None and not self._toggle_box.isChecked():
                return ""
            return str(self._spin_box.value())

        if self._double_spin_box is not None:
            if self._toggle_box is not None and not self._toggle_box.isChecked():
                return ""
            value = f"{self._double_spin_box.value():.{self.parameter.decimals}f}".rstrip("0").rstrip(".")
            return value or "0"

        return ""

    def setText(self, value: str) -> None:
        normalized = value.strip()

        if self._line_edit is not None:
            self._line_edit.setText(normalized)
            return

        if self._combo_box is not None:
            index = self._combo_box.findData(normalized)
            if index < 0 and not normalized and self._combo_box.count() > 0:
                index = 0
            if index >= 0:
                self._combo_box.setCurrentIndex(index)
            return

        if self._spin_box is not None:
            if self._toggle_box is not None:
                self._toggle_box.setChecked(bool(normalized))
                self._spin_box.setEnabled(bool(normalized))
            if normalized:
                self._spin_box.setValue(int(float(normalized)))
            return

        if self._double_spin_box is not None:
            if self._toggle_box is not None:
                self._toggle_box.setChecked(bool(normalized))
                self._double_spin_box.setEnabled(bool(normalized))
            if normalized:
                self._double_spin_box.setValue(float(normalized))

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        if self._spin_box is not None and self._toggle_box is not None:
            self._spin_box.setEnabled(enabled and self._toggle_box.isChecked())
        if self._double_spin_box is not None and self._toggle_box is not None:
            self._double_spin_box.setEnabled(enabled and self._toggle_box.isChecked())


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
        self.shared_parameter_widgets: dict[str, ParameterEditor] = {}
        self.shared_parameter_specs: dict[str, ParameterSpec] = {}
        self.tool_parameter_widgets: dict[str, ParameterEditor] = {}
        self.tool_parameter_specs: dict[str, ParameterSpec] = {}
        self.app_version = get_app_version()
        self.parameter_label_width = 192

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
        tool_layout.setHorizontalSpacing(0)
        tool_layout.setVerticalSpacing(12)

        self.tool_combo = ModernComboBox(self)
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

        tool_layout.addWidget(self.tool_summary, 0, 0, 1, 3)
        tool_layout.addWidget(
            self._build_overview_row(
                title="工具管理",
                meta="加载 / 卸载",
                content=manage_panel,
                help_text="管理当前工作区可用的内置工具和自定义工具。",
            ),
            1,
            0,
            1,
            3,
        )
        tool_layout.addWidget(
            self._build_overview_row(
                title="当前工具",
                meta="选择 / 切换",
                content=self.tool_combo,
                help_text="从已发现的工具中选择当前要执行的一项。",
            ),
            2,
            0,
            1,
            3,
        )
        tool_layout.addWidget(
            self._build_overview_row(
                title="工具详情",
                meta="说明 / 版本",
                content=detail_panel,
                help_text="查看当前工具的功能说明、版本和来源信息。",
            ),
            3,
            0,
            1,
            3,
        )

        shared_group = QGroupBox("公共配置", self)
        self.shared_form_layout = QGridLayout(shared_group)
        self.shared_form_layout.setContentsMargins(18, 18, 18, 18)
        self.shared_form_layout.setHorizontalSpacing(0)
        self.shared_form_layout.setVerticalSpacing(12)

        tool_form_group = QGroupBox("工具专用配置", self)
        self.tool_form_layout = QGridLayout(tool_form_group)
        self.tool_form_layout.setContentsMargins(18, 18, 18, 18)
        self.tool_form_layout.setHorizontalSpacing(0)
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
        install_theme_styles(self, window_style_sheet)

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
        if parameter.value_type == "boolean":
            return "选择是否覆盖当前值"
        if parameter.value_type == "choice":
            return "选择一个可用选项"
        if parameter.value_type == "integer":
            return "输入整数参数"
        if parameter.value_type == "float":
            return "输入数值参数"
        if parameter.browse_mode == "project_path":
            return "选择 .wbpj 文件或可定位到 IcepakProj 的目录"
        if parameter.browse_mode == "save_file":
            return "选择导出文件路径"
        if parameter.browse_mode == "open_file":
            return "选择文件路径"
        return "请输入参数值"

    def parameter_help_text(self, parameter: ParameterSpec) -> str:
        parts: list[str] = []
        if parameter.choices:
            parts.append("可选值：" + " / ".join(label for label, _value in parameter.choices))
        if parameter.minimum is not None or parameter.maximum is not None:
            lower = "-inf" if parameter.minimum is None else str(parameter.minimum)
            upper = "+inf" if parameter.maximum is None else str(parameter.maximum)
            parts.append(f"范围：{lower} ~ {upper}")
        if parameter.example_hint:
            parts.append(f"示例：{parameter.example_hint}")
        elif parameter.default_output_name:
            parts.append(f"会按测试用例路径自动补全为 {parameter.default_output_name}")
        elif parameter.default_value:
            parts.append(f"默认值：{self.default_parameter_value(parameter)}")
        return " | ".join(parts)

    def _build_overview_row(
        self,
        title: str,
        meta: str,
        content: QWidget,
        help_text: str,
    ) -> QFrame:
        row_frame = QFrame(self)
        row_frame.setObjectName("parameterRow")
        row_layout = QHBoxLayout(row_frame)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        title_panel = QWidget(row_frame)
        title_panel.setObjectName("parameterTitlePanel")
        title_panel.setFixedWidth(self.parameter_label_width)
        title_layout = QVBoxLayout(title_panel)
        title_layout.setContentsMargins(16, 14, 14, 14)
        title_layout.setSpacing(6)

        title_label = QLabel(title, row_frame)
        title_label.setObjectName("parameterTitle")
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        meta_label = QLabel(meta, row_frame)
        meta_label.setObjectName("parameterMeta")
        meta_label.setWordWrap(True)

        title_layout.addWidget(title_label)
        title_layout.addWidget(meta_label)
        title_layout.addStretch(1)

        content_panel = QWidget(row_frame)
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(16, 14, 16, 14)
        content_layout.setSpacing(6)

        help_label = QLabel(help_text, row_frame)
        help_label.setObjectName("fieldHelp")
        help_label.setWordWrap(True)

        content_layout.addWidget(content)
        content_layout.addWidget(help_label)

        row_layout.addWidget(title_panel, 0)
        row_layout.addWidget(content_panel, 1)
        return row_frame

    def _add_browse_row(
        self,
        layout: QGridLayout,
        widgets: dict[str, ParameterEditor],
        specs: dict[str, ParameterSpec],
        row: int,
        parameter: ParameterSpec,
        value: str,
    ) -> None:
        editor = ParameterEditor(parameter, value, self)
        editor.setPlaceholderText(self.parameter_placeholder_text(parameter))

        row_frame = QFrame(self)
        row_frame.setObjectName("parameterRow")
        row_layout = QHBoxLayout(row_frame)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        title_panel = QWidget(row_frame)
        title_panel.setObjectName("parameterTitlePanel")
        title_panel.setFixedWidth(self.parameter_label_width)
        title_layout = QVBoxLayout(title_panel)
        title_layout.setContentsMargins(16, 14, 14, 14)
        title_layout.setSpacing(6)

        label_text = parameter.label + (" *" if parameter.required else "")
        label = QLabel(label_text, row_frame)
        label.setObjectName("parameterTitle")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        meta_parts = ["必填" if parameter.required else "选填"]
        type_labels = {
            "text": "文本",
            "integer": "整数",
            "float": "数值",
            "boolean": "布尔",
            "choice": "枚举",
        }
        meta_parts.append(type_labels.get(parameter.value_type, "文本"))
        meta_label = QLabel("  ·  ".join(meta_parts), row_frame)
        meta_label.setObjectName("parameterMeta")
        meta_label.setWordWrap(True)

        title_layout.addWidget(label)
        title_layout.addWidget(meta_label)
        title_layout.addStretch(1)

        field_container = QWidget(row_frame)
        field_layout = QVBoxLayout(field_container)
        field_layout.setContentsMargins(16, 14, 16, 14)
        field_layout.setSpacing(6)

        field_help = QLabel(self.parameter_help_text(parameter), self)
        field_help.setObjectName("fieldHelp")
        field_help.setWordWrap(True)

        field_layout.addWidget(editor)
        field_layout.addWidget(field_help)

        row_layout.addWidget(title_panel, 0)
        if parameter.browse_mode == "none":
            row_layout.addWidget(field_container, 1)
        else:
            browse_button = QPushButton("浏览", self)
            browse_button.setObjectName("secondaryButton")
            browse_button.clicked.connect(
                lambda _checked=False, key=parameter.key: self.browse_parameter(key)
            )
            button_panel = QWidget(row_frame)
            button_layout = QVBoxLayout(button_panel)
            button_layout.setContentsMargins(0, 14, 16, 14)
            button_layout.setSpacing(0)
            button_layout.addWidget(browse_button)
            button_layout.addStretch(1)

            row_layout.addWidget(field_container, 1)
            row_layout.addWidget(button_panel, 0)

        layout.addWidget(row_frame, row, 0, 1, 3)

        widgets[parameter.key] = editor
        specs[parameter.key] = parameter
        editor.valueChanged.connect(self.save_settings)

        if parameter.key == "input_path":
            editor.valueChanged.connect(self.maybe_update_output_path)

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


def build_forced_palette(dark_mode: bool) -> QPalette:
    palette = QPalette()
    if dark_mode:
        palette.setColor(QPalette.Window, QColor("#1e2329"))
        palette.setColor(QPalette.WindowText, QColor("#edf2f7"))
        palette.setColor(QPalette.Base, QColor("#1f262e"))
        palette.setColor(QPalette.AlternateBase, QColor("#2d3540"))
        palette.setColor(QPalette.ToolTipBase, QColor("#262d35"))
        palette.setColor(QPalette.ToolTipText, QColor("#edf2f7"))
        palette.setColor(QPalette.Text, QColor("#edf2f7"))
        palette.setColor(QPalette.Button, QColor("#37414d"))
        palette.setColor(QPalette.ButtonText, QColor("#edf2f7"))
        palette.setColor(QPalette.BrightText, QColor("#ffffff"))
        palette.setColor(QPalette.Link, QColor("#4ea3ff"))
        palette.setColor(QPalette.Highlight, QColor("#2b7fc9"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.PlaceholderText, QColor("#95a3b3"))
    else:
        palette.setColor(QPalette.Window, QColor("#f3f5f7"))
        palette.setColor(QPalette.WindowText, QColor("#253342"))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.AlternateBase, QColor("#f8fafc"))
        palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
        palette.setColor(QPalette.ToolTipText, QColor("#253342"))
        palette.setColor(QPalette.Text, QColor("#253342"))
        palette.setColor(QPalette.Button, QColor("#eef4fa"))
        palette.setColor(QPalette.ButtonText, QColor("#253342"))
        palette.setColor(QPalette.BrightText, QColor("#ffffff"))
        palette.setColor(QPalette.Link, QColor("#1f6fb2"))
        palette.setColor(QPalette.Highlight, QColor("#2b7fc9"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.PlaceholderText, QColor("#6b7c8e"))
    return palette


def apply_forced_color_scheme(app: QApplication) -> None:
    requested_theme = os.environ.get("QUARD_UI_THEME", "system").strip().lower()
    if requested_theme not in {"system", "dark", "light"}:
        requested_theme = "system"
    if requested_theme == "system":
        return

    app.setStyle("Fusion")
    app.setPalette(build_forced_palette(dark_mode=requested_theme == "dark"))


def main() -> int:
    app = QApplication(sys.argv)
    apply_forced_color_scheme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())