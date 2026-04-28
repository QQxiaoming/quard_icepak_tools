from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui_components import ModernComboBox, ModernSpinBox, apply_dialog_chrome

from .preview import MeshRulePreviewResult, preview_mesh_refinement_rules
from .rules import (
    MATCH_MODE_CHOICES,
    RULE_OVERRIDE_FIELD_SPECS,
    MeshRefinementRule,
    deserialize_mesh_refinement_rules,
    serialize_mesh_refinement_rules,
)


class MeshRefinementRulesDialog(QDialog):
    def __init__(self, serialized_rules: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_dialog_chrome(self)
        self.setWindowTitle("块组细化规则编辑器")
        self.resize(1040, 680)
        self.setMinimumSize(860, 560)

        self._loading_detail = False
        self.serialized_value = serialized_rules.strip()
        try:
            self.rules = deserialize_mesh_refinement_rules(serialized_rules)
        except ValueError as exc:
            self.rules = []
            self.serialized_value = ""
            QMessageBox.warning(self, "规则格式无效", str(exc))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hint_label = QLabel(
            "按块名精确匹配、通配匹配或正则匹配，把不同块组映射到不同的局部网格参数。优先级越大，覆盖越靠后。",
            self,
        )
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(splitter, 1)

        summary_panel = QWidget(splitter)
        summary_layout = QVBoxLayout(summary_panel)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(8)

        self.rule_table = QTableWidget(summary_panel)
        self.rule_table.setColumnCount(6)
        self.rule_table.setHorizontalHeaderLabels(("启用", "规则名", "优先级", "匹配模式", "目标模式", "覆盖项"))
        self.rule_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rule_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.rule_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rule_table.setAlternatingRowColors(True)
        self.rule_table.itemSelectionChanged.connect(self._load_selected_rule)
        self.rule_table.horizontalHeader().setStretchLastSection(True)
        summary_layout.addWidget(self.rule_table, 1)

        action_layout = QHBoxLayout()
        self.add_button = QPushButton("新增规则", summary_panel)
        self.duplicate_button = QPushButton("复制规则", summary_panel)
        self.remove_button = QPushButton("删除规则", summary_panel)
        self.move_up_button = QPushButton("上移", summary_panel)
        self.move_down_button = QPushButton("下移", summary_panel)
        for button in (
            self.add_button,
            self.duplicate_button,
            self.remove_button,
            self.move_up_button,
            self.move_down_button,
        ):
            button.setObjectName("secondaryButton")
            action_layout.addWidget(button)
        action_layout.addStretch(1)
        summary_layout.addLayout(action_layout)

        detail_scroll = QScrollArea(splitter)
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QScrollArea.NoFrame)

        detail_panel = QWidget(detail_scroll)
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(12)

        basic_group = QGroupBox("规则定义", detail_panel)
        basic_form = QFormLayout(basic_group)
        basic_form.setLabelAlignment(Qt.AlignLeft)
        self.enabled_box = QCheckBox("启用当前规则", basic_group)
        self.name_edit = QLineEdit(basic_group)
        self.priority_spin = ModernSpinBox(basic_group)
        self.priority_spin.setRange(-10000, 10000)
        self.match_mode_combo = ModernComboBox(basic_group)
        for label, value in MATCH_MODE_CHOICES:
            self.match_mode_combo.addItem(label, value)
        self.patterns_edit = QPlainTextEdit(basic_group)
        self.patterns_edit.setPlaceholderText("每行一个块名模式，例如\nCPU_*\nVRM_*")
        self.patterns_edit.setFixedHeight(120)

        basic_form.addRow("启用", self.enabled_box)
        basic_form.addRow("规则名", self.name_edit)
        basic_form.addRow("优先级", self.priority_spin)
        basic_form.addRow("匹配模式", self.match_mode_combo)
        basic_form.addRow("块名模式", self.patterns_edit)
        detail_layout.addWidget(basic_group)

        override_group = QGroupBox("局部覆盖项", detail_panel)
        override_layout = QGridLayout(override_group)
        override_layout.setContentsMargins(12, 12, 12, 12)
        override_layout.setHorizontalSpacing(12)
        override_layout.setVerticalSpacing(8)
        self.override_widgets: dict[str, QWidget] = {}
        for row, field_spec in enumerate(RULE_OVERRIDE_FIELD_SPECS):
            label = QLabel(field_spec.label, override_group)
            if field_spec.value_type == "boolean":
                editor = ModernComboBox(override_group)
                editor.addItem("沿用全局值", "")
                editor.addItem("开启", "1")
                editor.addItem("关闭", "0")
                editor.currentIndexChanged.connect(self._save_current_rule)
            else:
                editor = QLineEdit(override_group)
                editor.setPlaceholderText("留空表示不覆盖")
                editor.textChanged.connect(self._save_current_rule)
            override_layout.addWidget(label, row, 0)
            override_layout.addWidget(editor, row, 1)
            self.override_widgets[field_spec.key] = editor

        clear_overrides_button = QPushButton("清空当前规则覆盖项", override_group)
        clear_overrides_button.setObjectName("secondaryButton")
        clear_overrides_button.clicked.connect(self._clear_current_overrides)
        override_layout.addWidget(clear_overrides_button, len(RULE_OVERRIDE_FIELD_SPECS), 0, 1, 2)
        detail_layout.addWidget(override_group, 1)

        detail_layout.addStretch(1)

        detail_scroll.setWidget(detail_panel)

        splitter.addWidget(summary_panel)
        splitter.addWidget(detail_scroll)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([620, 420])

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        preview_button = QPushButton("预览命中对象", self)
        preview_button.setObjectName("secondaryButton")
        preview_button.clicked.connect(self._preview_matches)
        cancel_button = QPushButton("取消", self)
        cancel_button.setObjectName("secondaryButton")
        cancel_button.clicked.connect(self.reject)
        ok_button = QPushButton("保存规则", self)
        ok_button.clicked.connect(self.accept)
        button_row.addWidget(preview_button)
        button_row.addWidget(cancel_button)
        button_row.addWidget(ok_button)
        layout.addLayout(button_row)

        self.add_button.clicked.connect(self._add_rule)
        self.duplicate_button.clicked.connect(self._duplicate_rule)
        self.remove_button.clicked.connect(self._remove_rule)
        self.move_up_button.clicked.connect(lambda: self._move_rule(-1))
        self.move_down_button.clicked.connect(lambda: self._move_rule(1))

        self.enabled_box.toggled.connect(self._save_current_rule)
        self.name_edit.textChanged.connect(self._save_current_rule)
        self.priority_spin.valueChanged.connect(self._save_current_rule)
        self.match_mode_combo.currentIndexChanged.connect(self._save_current_rule)
        self.patterns_edit.textChanged.connect(self._save_current_rule)

        self._refresh_rule_table(select_row=0 if self.rules else None)

    def selected_rule_index(self) -> int | None:
        ranges = self.rule_table.selectedRanges()
        if not ranges:
            return None
        row = ranges[0].topRow()
        if row < 0 or row >= len(self.rules):
            return None
        return row

    def _refresh_rule_table(self, select_row: int | None = None) -> None:
        self.rule_table.setRowCount(len(self.rules))
        for row_index, rule in enumerate(self.rules):
            patterns_summary = " | ".join(rule.patterns[:2])
            if len(rule.patterns) > 2:
                patterns_summary = f"{patterns_summary} | ..."
            override_summary = "，".join(
                field_spec.label for field_spec in RULE_OVERRIDE_FIELD_SPECS if field_spec.key in rule.overrides
            ) or "无"
            values = (
                "是" if rule.enabled else "否",
                rule.name,
                str(rule.priority),
                dict(MATCH_MODE_CHOICES).get(rule.match_mode, rule.match_mode),
                patterns_summary,
                override_summary,
            )
            for column_index, value in enumerate(values):
                self.rule_table.setItem(row_index, column_index, QTableWidgetItem(value))

        self.rule_table.resizeColumnsToContents()

        if not self.rules:
            self._loading_detail = True
            self.enabled_box.setChecked(True)
            self.name_edit.clear()
            self.priority_spin.setValue(100)
            self.match_mode_combo.setCurrentIndex(self.match_mode_combo.findData("wildcard"))
            self.patterns_edit.clear()
            for widget in self.override_widgets.values():
                if isinstance(widget, ModernComboBox):
                    widget.setCurrentIndex(0)
                else:
                    widget.clear()
            self._loading_detail = False
            return

        target_row = 0 if select_row is None else max(0, min(select_row, len(self.rules) - 1))
        self.rule_table.selectRow(target_row)
        self._load_selected_rule()

    def _load_selected_rule(self) -> None:
        rule_index = self.selected_rule_index()
        if rule_index is None:
            return

        rule = self.rules[rule_index]
        self._loading_detail = True
        self.enabled_box.setChecked(rule.enabled)
        self.name_edit.setText(rule.name)
        self.priority_spin.setValue(rule.priority)
        combo_index = self.match_mode_combo.findData(rule.match_mode)
        self.match_mode_combo.setCurrentIndex(0 if combo_index < 0 else combo_index)
        self.patterns_edit.setPlainText("\n".join(rule.patterns))
        for field_spec in RULE_OVERRIDE_FIELD_SPECS:
            widget = self.override_widgets[field_spec.key]
            value = rule.overrides.get(field_spec.key, "")
            if isinstance(widget, ModernComboBox):
                combo_index = widget.findData(value)
                widget.setCurrentIndex(0 if combo_index < 0 else combo_index)
            else:
                widget.setText(value)
        self._loading_detail = False

    def _current_rule_from_editors(self) -> MeshRefinementRule:
        overrides: dict[str, str] = {}
        for field_spec in RULE_OVERRIDE_FIELD_SPECS:
            widget = self.override_widgets[field_spec.key]
            if isinstance(widget, ModernComboBox):
                value = str(widget.currentData() or "").strip()
            else:
                value = widget.text().strip()
            if value:
                overrides[field_spec.key] = value

        return MeshRefinementRule(
            name=self.name_edit.text().strip(),
            enabled=self.enabled_box.isChecked(),
            priority=self.priority_spin.value(),
            match_mode=str(self.match_mode_combo.currentData() or "wildcard"),
            patterns=[line.strip() for line in self.patterns_edit.toPlainText().splitlines() if line.strip()],
            overrides=overrides,
        )

    def _save_current_rule(self) -> None:
        if self._loading_detail:
            return

        rule_index = self.selected_rule_index()
        if rule_index is None:
            return

        self.rules[rule_index] = self._current_rule_from_editors()
        self._refresh_rule_table(select_row=rule_index)

    def _add_rule(self) -> None:
        new_index = len(self.rules) + 1
        self.rules.append(
            MeshRefinementRule(
                name=f"rule_{new_index}",
                enabled=True,
                priority=100,
                match_mode="wildcard",
                patterns=["BLOCK_*"] if new_index == 1 else [],
                overrides={},
            )
        )
        self._refresh_rule_table(select_row=len(self.rules) - 1)

    def _duplicate_rule(self) -> None:
        rule_index = self.selected_rule_index()
        if rule_index is None:
            return

        source = self.rules[rule_index]
        self.rules.insert(rule_index + 1, replace(source, name=f"{source.name}_copy"))
        self._refresh_rule_table(select_row=rule_index + 1)

    def _remove_rule(self) -> None:
        rule_index = self.selected_rule_index()
        if rule_index is None:
            return

        del self.rules[rule_index]
        self._refresh_rule_table(select_row=min(rule_index, len(self.rules) - 1))

    def _move_rule(self, direction: int) -> None:
        rule_index = self.selected_rule_index()
        if rule_index is None:
            return
        target_index = rule_index + direction
        if target_index < 0 or target_index >= len(self.rules):
            return

        self.rules[rule_index], self.rules[target_index] = self.rules[target_index], self.rules[rule_index]
        self._refresh_rule_table(select_row=target_index)

    def _clear_current_overrides(self) -> None:
        for widget in self.override_widgets.values():
            if isinstance(widget, ModernComboBox):
                widget.setCurrentIndex(0)
            else:
                widget.clear()
        self._save_current_rule()

    def _collect_preview_context(self) -> tuple[str, str | None, str | None]:
        parent = self.parentWidget()
        if parent is None:
            raise ValueError("无法获取主窗口上下文，无法执行预览。")

        shared_widgets = getattr(parent, "shared_parameter_widgets", None)
        if not isinstance(shared_widgets, dict):
            raise ValueError("主窗口缺少共享参数，无法执行预览。")

        input_widget = shared_widgets.get("input_path")
        if input_widget is None:
            raise ValueError("找不到测试用例路径参数，无法执行预览。")
        input_path = input_widget.text().strip()
        if not input_path:
            raise ValueError("请先填写测试用例路径，再执行预览。")

        env_widget = shared_widgets.get("env_script")
        env_script = env_widget.text().strip() if env_widget is not None else ""

        tool_widgets = getattr(parent, "tool_parameter_widgets", None)
        icepak_bin = None
        if isinstance(tool_widgets, dict):
            icepak_widget = tool_widgets.get("icepak_bin")
            if icepak_widget is not None:
                icepak_bin = icepak_widget.text().strip() or None

        return input_path, env_script or None, icepak_bin

    def _preview_matches(self) -> None:
        try:
            serialized_rules = serialize_mesh_refinement_rules(self.rules)
            input_path, env_script, icepak_bin = self._collect_preview_context()
            preview_result = preview_mesh_refinement_rules(
                input_path=input_path,
                serialized_rules=serialized_rules,
                env_script=env_script,
                icepak_bin=icepak_bin,
            )
        except Exception as exc:
            QMessageBox.warning(self, "预览失败", str(exc))
            return

        PreviewResultDialog(preview_result, self).exec()

    def accept(self) -> None:
        try:
            self.serialized_value = serialize_mesh_refinement_rules(self.rules)
        except ValueError as exc:
            QMessageBox.warning(self, "规则配置无效", str(exc))
            return
        super().accept()


def edit_mesh_refinement_rules(serialized_rules: str, parent: QWidget | None = None) -> str | None:
    dialog = MeshRefinementRulesDialog(serialized_rules, parent)
    if dialog.exec() != QDialog.Accepted:
        return None
    return dialog.serialized_value


class PreviewResultDialog(QDialog):
    def __init__(self, preview_result: MeshRulePreviewResult, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_dialog_chrome(self)
        self.setWindowTitle("规则命中预览")
        self.resize(960, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        summary_label = QLabel(
            f"共 {len(preview_result.summaries)} 条规则，命中 {preview_result.total_matches} 个 block。",
            self,
        )
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        rule_table = QTableWidget(self)
        rule_table.setColumnCount(5)
        rule_table.setHorizontalHeaderLabels(("规则名", "优先级", "匹配模式", "块名模式", "命中数"))
        rule_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        rule_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        rule_table.setAlternatingRowColors(True)
        rule_table.setRowCount(len(preview_result.summaries))
        for row_index, summary in enumerate(preview_result.summaries):
            values = (
                summary.rule_name,
                str(summary.priority),
                summary.match_mode,
                " | ".join(summary.patterns),
                str(summary.matched_count),
            )
            for column_index, value in enumerate(values):
                rule_table.setItem(row_index, column_index, QTableWidgetItem(value))
        rule_table.resizeColumnsToContents()
        layout.addWidget(rule_table, 1)

        match_view = QPlainTextEdit(self)
        match_view.setReadOnly(True)
        if preview_result.matches:
            lines = [f"{match.rule_name}\t{match.object_name}" for match in preview_result.matches]
            match_view.setPlainText("\n".join(lines))
        else:
            match_view.setPlainText("当前规则未命中任何 block。")
        layout.addWidget(match_view, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        close_button = QPushButton("关闭", self)
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)