from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QListView,
    QSpinBox,
    QStyle,
    QStyleOptionSpinBox,
    QWidget,
)


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
        track_rect = rect.adjusted(
            rect.width() - track_width,
            (rect.height() - track_height) // 2,
            0,
            -(rect.height() - track_height) // 2,
        )
        text_rect = rect.adjusted(0, 0, -(track_width + spacing), 0)

        text_color = QColor("#41586d") if self.isEnabled() else QColor("#9aa8b6")
        painter.setPen(text_color)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())

        if self.isChecked():
            track_color = QColor("#2b7fc9") if self.isEnabled() else QColor("#9dc1e2")
            border_color = QColor("#236ba8") if self.isEnabled() else QColor("#89afcf")
        else:
            track_color = QColor("#dde5ed") if self.isEnabled() else QColor("#edf1f5")
            border_color = QColor("#c7d1db") if self.isEnabled() else QColor("#dde4eb")

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
            focus_pen = QPen(QColor("#8cb9e6"), 2)
            painter.setPen(focus_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(
                track_rect.adjusted(-2, -2, 2, 2),
                (track_height + 4) / 2,
                (track_height + 4) / 2,
            )


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
        color = QColor("#4a6782") if self.isEnabled() else QColor("#a0adba")
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
        color = QColor("#4a6782") if self.isEnabled() else QColor("#a0adba")
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


def dialog_style_sheet() -> str:
    return """
        QDialog {
            background: #f3f5f7;
        }
        QLabel {
            color: #253342;
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
        QLineEdit,
        QComboBox,
        QSpinBox,
        QDoubleSpinBox,
        QPlainTextEdit,
        QTableWidget {
            background: #ffffff;
            color: #24384a;
            border: 1px solid #c9d3dd;
            border-radius: 10px;
            selection-background-color: #1565c0;
            selection-color: #ffffff;
        }
        QLineEdit,
        QPlainTextEdit {
            padding: 8px 10px;
        }
        QLineEdit:focus,
        QComboBox:focus,
        QSpinBox:focus,
        QDoubleSpinBox:focus,
        QPlainTextEdit:focus,
        QTableWidget:focus {
            border: 1px solid #4e8ccf;
        }
        QComboBox {
            padding: 8px 40px 8px 12px;
            font-weight: 600;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8fbfe);
        }
        QComboBox:hover,
        QSpinBox:hover,
        QDoubleSpinBox:hover {
            border: 1px solid #9cb9d6;
            background: #ffffff;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 34px;
            border-left: 1px solid #d7e0e8;
            background: #eef4fa;
            border-top-right-radius: 10px;
            border-bottom-right-radius: 10px;
        }
        QComboBox::down-arrow,
        QSpinBox::up-arrow,
        QDoubleSpinBox::up-arrow,
        QSpinBox::down-arrow,
        QDoubleSpinBox::down-arrow {
            image: none;
            width: 0px;
            height: 0px;
        }
        QSpinBox,
        QDoubleSpinBox {
            padding: 8px 38px 8px 12px;
            font-weight: 600;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8fbfe);
        }
        QSpinBox::up-button,
        QDoubleSpinBox::up-button {
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 28px;
            border-left: 1px solid #d7e0e8;
            border-bottom: 1px solid #d7e0e8;
            background: #eef4fa;
            border-top-right-radius: 10px;
        }
        QSpinBox::down-button,
        QDoubleSpinBox::down-button {
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 28px;
            border-left: 1px solid #d7e0e8;
            background: #eef4fa;
            border-bottom-right-radius: 10px;
        }
        QSpinBox::up-button:hover,
        QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover,
        QDoubleSpinBox::down-button:hover {
            background: #e2edf8;
        }
        QComboBox QAbstractItemView {
            background: #ffffff;
            color: #24384a;
            border: 1px solid #c9d7e3;
            border-radius: 12px;
            outline: 0;
            padding: 8px;
            selection-background-color: #dbeaf8;
            selection-color: #1f3550;
        }
        QComboBox QAbstractItemView::item {
            min-height: 30px;
            border-radius: 8px;
            padding: 4px 10px;
            margin: 2px 4px;
            color: #24384a;
            background: transparent;
        }
        QComboBox QAbstractItemView::item:hover,
        QComboBox QAbstractItemView::item:selected {
            background: #dbeaf8;
            color: #1f3550;
        }
        QCheckBox#parameterToggle {
            min-width: 82px;
            min-height: 30px;
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
        QTableWidget {
            gridline-color: #e5ebf1;
            alternate-background-color: #f8fbfe;
        }
        QTableWidget::item:selected {
            background: #1565c0;
            color: #ffffff;
        }
        QHeaderView::section {
            background: #eef3f8;
            color: #41586d;
            border: none;
            border-right: 1px solid #dbe3eb;
            border-bottom: 1px solid #dbe3eb;
            padding: 8px 10px;
            font-weight: 700;
        }
    """


def apply_dialog_chrome(dialog: QDialog) -> None:
    dialog.setStyleSheet(dialog_style_sheet())
