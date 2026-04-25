from __future__ import annotations

import csv
from pathlib import Path

import math

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QBrush, QMouseEvent, QPainter, QPen, QPolygonF, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
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


class BlockModelPreviewWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.records = ()
        self.selected_name: str | None = None
        self.partner_name: str | None = None
        self.show_focus_only = False
        self.fill_enabled = True
        self.yaw_degrees = 45.0
        self.pitch_degrees = 30.0
        self.zoom_factor = 0.9
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self._last_mouse_position: QPoint | None = None
        self._drag_mode: str | None = None
        self.setMinimumWidth(320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

    def set_records(self, records) -> None:
        self.records = tuple(records)
        self.update()

    def set_highlight_names(self, selected_name: str | None, partner_name: str | None) -> None:
        self.selected_name = selected_name
        self.partner_name = partner_name
        self.update()

    def set_show_focus_only(self, show_focus_only: bool) -> None:
        self.show_focus_only = show_focus_only
        self.update()

    def set_fill_enabled(self, fill_enabled: bool) -> None:
        self.fill_enabled = fill_enabled
        self.update()

    def reset_view(self) -> None:
        self.yaw_degrees = 45.0
        self.pitch_degrees = 30.0
        self.zoom_factor = 0.9
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self._last_mouse_position = None
        self._drag_mode = None
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#f7f9fc"))

        if not self.records:
            painter.setPen(QColor("#5f6b7a"))
            painter.drawText(self.rect(), Qt.AlignCenter, "暂无可预览的 3D 模型")
            return

        visible_records = self._visible_records()
        if not visible_records:
            painter.setPen(QColor("#5f6b7a"))
            painter.drawText(self.rect(), Qt.AlignCenter, "当前筛选条件下没有可预览的 block")
            return

        projected_blocks = []
        all_points: list[QPointF] = []

        for record in visible_records:
            points_3d = self._build_box_points(record)
            projected = [self._project_point(*point) for point in points_3d]
            projected_blocks.append((record, projected))
            all_points.extend(point for point, _depth in projected)

        if not all_points:
            return

        min_x = min(point.x() for point in all_points)
        max_x = max(point.x() for point in all_points)
        min_y = min(point.y() for point in all_points)
        max_y = max(point.y() for point in all_points)
        span_x = max(max_x - min_x, 1.0)
        span_y = max(max_y - min_y, 1.0)

        viewport = QRectF(self.rect()).adjusted(18.0, 18.0, -18.0, -18.0)
        scale = min(viewport.width() / span_x, viewport.height() / span_y) * self.zoom_factor
        offset_x = viewport.center().x() - ((min_x + max_x) / 2.0) * scale + self.pan_offset_x
        offset_y = viewport.center().y() - ((min_y + max_y) / 2.0) * scale + self.pan_offset_y

        def map_point(point: QPointF) -> QPointF:
            return QPointF(point.x() * scale + offset_x, point.y() * scale + offset_y)

        projected_blocks.sort(
            key=lambda item: sum(depth for _point, depth in item[1]) / max(len(item[1]), 1)
        )

        for record, projected in projected_blocks:
            mapped_points = [map_point(point) for point, _depth in projected]
            if record.object_name == self.selected_name:
                color = QColor("#1565c0")
                width = 2.4
            elif record.object_name == self.partner_name:
                color = QColor("#c62828")
                width = 2.4
            else:
                color = QColor("#90a4ae")
                width = 1.2

            self._draw_faces(painter, record.object_name, mapped_points, projected)

            painter.setPen(QPen(color, width))
            for start_index, end_index in self._box_edges():
                painter.drawLine(mapped_points[start_index], mapped_points[end_index])

        self._draw_axis_marker(painter)
        self._draw_legend(painter)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._is_rotate_press(event):
            self._last_mouse_position = event.position().toPoint()
            self._drag_mode = "rotate"
            self.grabMouse()
            event.accept()
            return
        if self._is_pan_press(event):
            self._last_mouse_position = event.position().toPoint()
            self._drag_mode = "pan"
            self.grabMouse()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._last_mouse_position is None or self._drag_mode is None:
            super().mouseMoveEvent(event)
            return

        if self._drag_mode == "rotate" and not self._is_rotate_drag(event):
            super().mouseMoveEvent(event)
            return
        if self._drag_mode == "pan" and not self._is_pan_drag(event):
            super().mouseMoveEvent(event)
            return

        current_position = event.position().toPoint()
        delta = current_position - self._last_mouse_position
        self._last_mouse_position = current_position

        if self._drag_mode == "rotate":
            self.yaw_degrees += delta.x() * 0.6
            self.pitch_degrees = max(-89.0, min(89.0, self.pitch_degrees - delta.y() * 0.4))
        elif self._drag_mode == "pan":
            self.pan_offset_x += delta.x()
            self.pan_offset_y += delta.y()

        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._is_rotate_press(event) or self._is_pan_press(event):
            self._last_mouse_position = None
            self._drag_mode = None
            self.releaseMouse()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta_steps = event.angleDelta().y() / 120.0
        if delta_steps == 0:
            super().wheelEvent(event)
            return

        self.zoom_factor = max(0.2, min(12.0, self.zoom_factor * (1.12 ** delta_steps)))
        self.update()
        event.accept()

    def _left_button_flag(self):
        return getattr(Qt, "LeftButton", Qt.MouseButton.LeftButton)

    def _right_button_flag(self):
        return getattr(Qt, "RightButton", Qt.MouseButton.RightButton)

    def _button_value(self, button) -> int:
        try:
            return int(button)
        except TypeError:
            return int(button.value)

    def _buttons_value(self, buttons) -> int:
        try:
            return int(buttons)
        except TypeError:
            return int(buttons.value)

    def _is_rotate_press(self, event: QMouseEvent) -> bool:
        return self._button_value(event.button()) == self._button_value(self._right_button_flag())

    def _is_pan_press(self, event: QMouseEvent) -> bool:
        return self._button_value(event.button()) == self._button_value(self._left_button_flag())

    def _is_rotate_drag(self, event: QMouseEvent) -> bool:
        return bool(self._buttons_value(event.buttons()) & self._button_value(self._right_button_flag()))

    def _is_pan_drag(self, event: QMouseEvent) -> bool:
        return bool(self._buttons_value(event.buttons()) & self._button_value(self._left_button_flag()))

    def _draw_legend(self, painter: QPainter) -> None:
        entries = [
            (QColor("#1565c0"), "当前选中 block"),
            (QColor("#c62828"), "配对 block"),
            (QColor("#90a4ae"), "其他 block"),
        ]
        x = 18
        y = 18
        for color, label in entries:
            painter.fillRect(x, y, 12, 12, color)
            painter.setPen(QColor("#334155"))
            painter.drawText(x + 18, y - 1, 120, 16, Qt.AlignLeft | Qt.AlignVCenter, label)
            y += 20

    def _project_point(self, x: float, y: float, z: float) -> tuple[QPointF, float]:
        yaw = math.radians(self.yaw_degrees)
        pitch = math.radians(self.pitch_degrees)

        x1 = x * math.cos(yaw) - y * math.sin(yaw)
        y1 = x * math.sin(yaw) + y * math.cos(yaw)
        z1 = z

        y2 = y1 * math.cos(pitch) - z1 * math.sin(pitch)
        z2 = y1 * math.sin(pitch) + z1 * math.cos(pitch)
        return QPointF(x1, -y2), z2

    def _build_box_points(self, record) -> tuple[tuple[float, float, float], ...]:
        return (
            (record.xmin, record.ymin, record.zmin),
            (record.xmax, record.ymin, record.zmin),
            (record.xmax, record.ymax, record.zmin),
            (record.xmin, record.ymax, record.zmin),
            (record.xmin, record.ymin, record.zmax),
            (record.xmax, record.ymin, record.zmax),
            (record.xmax, record.ymax, record.zmax),
            (record.xmin, record.ymax, record.zmax),
        )

    def _box_edges(self) -> tuple[tuple[int, int], ...]:
        return (
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 0),
            (4, 5),
            (5, 6),
            (6, 7),
            (7, 4),
            (0, 4),
            (1, 5),
            (2, 6),
            (3, 7),
        )

    def _box_faces(self) -> tuple[tuple[int, int, int, int], ...]:
        return (
            (0, 1, 2, 3),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        )

    def _draw_faces(
        self,
        painter: QPainter,
        object_name: str,
        mapped_points: list[QPointF],
        projected: list[tuple[QPointF, float]],
    ) -> None:
        if not self.fill_enabled:
            return

        if object_name == self.selected_name:
            fill_color = QColor(21, 101, 192, 70)
        elif object_name == self.partner_name:
            fill_color = QColor(198, 40, 40, 70)
        else:
            return

        face_order = []
        for face in self._box_faces():
            face_depth = sum(projected[index][1] for index in face) / len(face)
            area = self._polygon_signed_area([mapped_points[index] for index in face])
            if abs(area) <= 1.0e-6:
                continue
            face_order.append((face_depth, face, area))

        if not face_order:
            return

        visible_area_sign = 1.0 if max(face_order, key=lambda item: item[0])[2] > 0 else -1.0

        visible_faces = [
            (face_depth, face)
            for face_depth, face, area in face_order
            if area * visible_area_sign > 0
        ]

        if not visible_faces:
            return

        visible_faces.sort()

        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(fill_color))
        for _depth, face in visible_faces:
            polygon = QPolygonF([mapped_points[index] for index in face])
            painter.drawPolygon(polygon)
        painter.restore()

    def _polygon_signed_area(self, points: list[QPointF]) -> float:
        area = 0.0
        for index, point in enumerate(points):
            next_point = points[(index + 1) % len(points)]
            area += point.x() * next_point.y() - next_point.x() * point.y()
        return area * 0.5

    def _draw_axis_marker(self, painter: QPainter) -> None:
        origin = QPointF(30.0, self.height() - 30.0)
        axis_length = 24.0
        axis_specs = (
            ("X", QColor("#d32f2f"), self._project_direction(1.0, 0.0, 0.0)),
            ("Y", QColor("#2e7d32"), self._project_direction(0.0, 1.0, 0.0)),
            ("Z", QColor("#1565c0"), self._project_direction(0.0, 0.0, 1.0)),
        )

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        for label, color, direction in axis_specs:
            end_point = QPointF(
                origin.x() + direction.x() * axis_length,
                origin.y() + direction.y() * axis_length,
            )
            painter.setPen(QPen(color, 2.2))
            painter.drawLine(origin, end_point)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(self._build_arrowhead(origin, end_point, 6.0, 4.0))
            painter.setPen(QPen(color, 1.0))
            painter.drawText(QRectF(end_point.x() + 3.0, end_point.y() - 8.0, 14.0, 14.0), Qt.AlignLeft | Qt.AlignVCenter, label)

        painter.setBrush(QBrush(QColor("#475569")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(origin, 2.2, 2.2)
        painter.restore()

    def _build_arrowhead(
        self,
        start_point: QPointF,
        end_point: QPointF,
        arrow_length: float,
        arrow_width: float,
    ) -> QPolygonF:
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = math.hypot(dx, dy)
        if length <= 1.0e-9:
            return QPolygonF([end_point, end_point, end_point])

        ux = dx / length
        uy = dy / length
        base_x = end_point.x() - ux * arrow_length
        base_y = end_point.y() - uy * arrow_length
        px = -uy
        py = ux

        return QPolygonF(
            [
                end_point,
                QPointF(base_x + px * arrow_width, base_y + py * arrow_width),
                QPointF(base_x - px * arrow_width, base_y - py * arrow_width),
            ]
        )

    def _project_direction(self, x: float, y: float, z: float) -> QPointF:
        projected, _depth = self._project_point(x, y, z)
        length = math.hypot(projected.x(), projected.y())
        if length <= 1.0e-9:
            return QPointF(0.0, 0.0)
        return QPointF(projected.x() / length, projected.y() / length)

    def _visible_records(self):
        if not self.show_focus_only:
            return self.records

        focus_names = {name for name in (self.selected_name, self.partner_name) if name}
        if not focus_names:
            return self.records

        return tuple(record for record in self.records if record.object_name in focus_names)


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

        self.preview_widget = BlockModelPreviewWidget(self)
        self.preview_hint_label = QLabel("右侧显示 block 的 3D 包围盒预览，支持左键平移、右键旋转、滚轮缩放。", self)
        self.preview_hint_label.setWordWrap(True)

        self.reset_view_button = QPushButton("重置视角", self)
        self.reset_view_button.clicked.connect(self.preview_widget.reset_view)
        self.fill_checkbox = QCheckBox("启用面填充", self)
        self.fill_checkbox.setChecked(True)
        self.fill_checkbox.toggled.connect(self.preview_widget.set_fill_enabled)
        self.focus_only_checkbox = QCheckBox("仅显示当前与配对 block", self)
        self.focus_only_checkbox.toggled.connect(self.preview_widget.set_show_focus_only)

        preview_actions = QHBoxLayout()
        preview_actions.setContentsMargins(0, 0, 0, 0)
        preview_actions.addWidget(self.reset_view_button)
        preview_actions.addWidget(self.fill_checkbox)
        preview_actions.addWidget(self.focus_only_checkbox)
        preview_actions.addStretch(1)

        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(8)
        preview_layout.addWidget(QLabel("3D 模型预览", self))
        preview_layout.addLayout(preview_actions)
        preview_layout.addWidget(self.preview_widget, 1)
        preview_layout.addWidget(self.preview_hint_label)

        preview_container = QWidget(self)
        preview_container.setLayout(preview_layout)
        preview_container.setMinimumWidth(340)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)
        content_layout.addWidget(self.result_table, 2)
        content_layout.addWidget(preview_container, 1)

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
        layout.addLayout(content_layout, 1)
        layout.addWidget(controls_widget)
        layout.addLayout(actions)

    def set_result(self, table_data: TableData, parameters: ToolParameters) -> None:
        self.current_table_data = table_data
        self.parameters = dict(parameters)
        self.stack_axis = normalize_stack_axis(self.parameters.get("stack_axis"))
        self.axis_label.setText(f"{self.stack_axis.upper()} 轴")
        self._rebuild_direction_options()

        records = parse_block_records(table_data)
        visible_table_data = build_visible_table_data(table_data)
        self.preview_widget.set_records(records)
        self.summary_label.setText(
            f"已枚举 {len(records)} 个 block 形体记录。当前厚度堆叠方向为 {self.stack_axis.upper()} 轴，可直接执行配对厚度调整。"
        )

        self.result_table.clear()
        self.result_table.setSortingEnabled(False)
        self.result_table.setColumnCount(len(visible_table_data.columns))
        self.result_table.setHorizontalHeaderLabels(list(visible_table_data.columns))
        self.result_table.setRowCount(len(visible_table_data.rows))
        for row_index, row in enumerate(visible_table_data.rows):
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
        selected_name = self.block_combo.currentData() if self.block_combo.count() > 0 else None
        try:
            plan = self.current_plan()
        except Exception as exc:
            self.highlighted_partner_name = None
            self._apply_row_highlights()
            self.preview_widget.set_highlight_names(selected_name, None)
            self.preview_label.setText(str(exc))
            self.apply_button.setEnabled(False)
            return

        if plan is None:
            self.highlighted_partner_name = None
            self._apply_row_highlights()
            self.preview_widget.set_highlight_names(selected_name, None)
            self.preview_label.setText("暂无可调整的 block。")
            self.apply_button.setEnabled(False)
            return

        self.highlighted_partner_name = plan.partner.object_name
        self._apply_row_highlights()
        self.preview_widget.set_highlight_names(plan.selected.object_name, plan.partner.object_name)

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

        visible_table_data = build_visible_table_data(self.current_table_data)

        default_name = visible_table_data.default_export_name
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
            writer.writerow(visible_table_data.columns)
            writer.writerows(visible_table_data.rows)

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