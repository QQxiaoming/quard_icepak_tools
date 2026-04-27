from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
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


@dataclass(frozen=True)
class ThemeColors:
    window: str
    surface: str
    surface_alt: str
    section: str
    input_bg: str
    input_hover: str
    chrome: str
    chrome_hover: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_soft: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_text: str
    accent_soft: str
    accent_soft_text: str
    success_bg: str
    success_text: str
    error_bg: str
    error_text: str
    idle_bg: str
    idle_text: str
    selection: str
    selection_text: str
    progress_bg: str
    progress_chunk: str
    disabled_text: str
    toggle_off: str
    toggle_off_border: str
    toggle_on_disabled: str
    focus: str


def _blend(color: QColor, other: QColor, amount: float) -> QColor:
    ratio = max(0.0, min(1.0, amount))
    inverse = 1.0 - ratio
    return QColor(
        round(color.red() * inverse + other.red() * ratio),
        round(color.green() * inverse + other.green() * ratio),
        round(color.blue() * inverse + other.blue() * ratio),
    )


def _css(color: QColor) -> str:
    return color.name()


def _is_dark_palette(palette: QPalette) -> bool:
    window = palette.color(QPalette.Window)
    text = palette.color(QPalette.WindowText)
    return window.lightnessF() < text.lightnessF()


def _resolved_palette(widget: QWidget | None = None) -> QPalette:
    if widget is not None:
        return widget.palette()
    app = QApplication.instance()
    return app.palette() if app is not None else QPalette()


def theme_colors(widget: QWidget | None = None) -> ThemeColors:
    palette = _resolved_palette(widget)
    accent = palette.color(QPalette.Highlight)
    accent_text = palette.color(QPalette.HighlightedText)
    if not accent.isValid():
        accent = QColor("#2b7fc9")
    if not accent_text.isValid():
        accent_text = QColor("#ffffff")

    if _is_dark_palette(palette):
        window = QColor("#1e2329")
        surface = QColor("#262d35")
        surface_alt = QColor("#2d3540")
        section = QColor("#303946")
        input_bg = QColor("#1f262e")
        input_hover = QColor("#252d37")
        chrome = QColor("#37414d")
        chrome_hover = QColor("#424d5b")
        border = QColor("#495463")
        border_strong = QColor("#5d6a7b")
        text = QColor("#edf2f7")
        text_muted = QColor("#c2ccd6")
        text_soft = QColor("#95a3b3")
        disabled_text = QColor("#768393")
        idle_bg = QColor("#323b46")
        idle_text = QColor("#d5dde6")
        success_bg = QColor("#1d4736")
        success_text = QColor("#bfe9d4")
        error_bg = QColor("#5a2626")
        error_text = QColor("#ffd4d4")
        progress_bg = QColor("#222931")
        toggle_off = QColor("#566170")
        toggle_off_border = QColor("#697687")
        toggle_on_disabled = QColor("#56708b")
        focus = _blend(accent, QColor("#ffffff"), 0.28)
        accent_soft = _blend(accent, surface, 0.72)
        accent_soft_text = _blend(accent_text, text, 0.35)
    else:
        window = QColor("#f3f5f7")
        surface = QColor("#ffffff")
        surface_alt = QColor("#f8fafc")
        section = QColor("#eef3f8")
        input_bg = QColor("#ffffff")
        input_hover = QColor("#ffffff")
        chrome = QColor("#eef4fa")
        chrome_hover = QColor("#e2edf8")
        border = QColor("#d7dde5")
        border_strong = QColor("#c9d3dd")
        text = QColor("#253342")
        text_muted = QColor("#41586d")
        text_soft = QColor("#6b7c8e")
        disabled_text = QColor("#8a98a8")
        idle_bg = QColor("#e8edf2")
        idle_text = QColor("#415466")
        success_bg = QColor("#dff3ea")
        success_text = QColor("#1f6a49")
        error_bg = QColor("#fde8e8")
        error_text = QColor("#9a2d2d")
        progress_bg = QColor("#e9edf2")
        toggle_off = QColor("#dde5ed")
        toggle_off_border = QColor("#c7d1db")
        toggle_on_disabled = QColor("#9dc1e2")
        focus = _blend(accent, QColor("#ffffff"), 0.5)
        accent_soft = QColor("#dbeaf8")
        accent_soft_text = QColor("#1f3550")

    accent_hover = accent.lighter(112) if _is_dark_palette(palette) else accent.darker(108)
    accent_pressed = accent.darker(118)
    selection = _blend(accent, surface, 0.2 if _is_dark_palette(palette) else 0.1)

    return ThemeColors(
        window=_css(window),
        surface=_css(surface),
        surface_alt=_css(surface_alt),
        section=_css(section),
        input_bg=_css(input_bg),
        input_hover=_css(input_hover),
        chrome=_css(chrome),
        chrome_hover=_css(chrome_hover),
        border=_css(border),
        border_strong=_css(border_strong),
        text=_css(text),
        text_muted=_css(text_muted),
        text_soft=_css(text_soft),
        accent=_css(accent),
        accent_hover=_css(accent_hover),
        accent_pressed=_css(accent_pressed),
        accent_text=_css(accent_text),
        accent_soft=_css(accent_soft),
        accent_soft_text=_css(accent_soft_text),
        success_bg=_css(success_bg),
        success_text=_css(success_text),
        error_bg=_css(error_bg),
        error_text=_css(error_text),
        idle_bg=_css(idle_bg),
        idle_text=_css(idle_text),
        selection=_css(selection),
        selection_text=_css(accent_text),
        progress_bg=_css(progress_bg),
        progress_chunk=_css(accent),
        disabled_text=_css(disabled_text),
        toggle_off=_css(toggle_off),
        toggle_off_border=_css(toggle_off_border),
        toggle_on_disabled=_css(toggle_on_disabled),
        focus=_css(focus),
    )


def themed_text_color(widget: QWidget, enabled: bool = True, muted: bool = False) -> QColor:
    colors = theme_colors(widget)
    color = colors.text_muted if muted else colors.text
    if not enabled:
        color = colors.disabled_text
    return QColor(color)


def themed_glyph_color(widget: QWidget, enabled: bool = True) -> QColor:
    colors = theme_colors(widget)
    return QColor(colors.text_muted if enabled else colors.disabled_text)


def themed_toggle_colors(widget: QWidget, checked: bool, enabled: bool) -> tuple[QColor, QColor]:
    colors = theme_colors(widget)
    if checked:
        track = colors.accent if enabled else colors.toggle_on_disabled
        border = colors.accent_hover if enabled else colors.toggle_on_disabled
        return QColor(track), QColor(border)
    if enabled:
        return QColor(colors.toggle_off), QColor(colors.toggle_off_border)
    return QColor(colors.surface_alt), QColor(colors.border)


def themed_focus_color(widget: QWidget) -> QColor:
    return QColor(theme_colors(widget).focus)


class _ThemeStyleFilter(QObject):
    def __init__(self, widget: QWidget, stylesheet_factory) -> None:
        super().__init__(widget)
        self._widget = widget
        self._stylesheet_factory = stylesheet_factory
        self._is_applying = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if not self._is_applying and watched is self._widget and event.type() in {
            QEvent.ApplicationPaletteChange,
            QEvent.PaletteChange,
            QEvent.StyleChange,
            QEvent.ThemeChange,
        }:
            self._is_applying = True
            try:
                self._widget.setStyleSheet(self._stylesheet_factory(self._widget))
            finally:
                self._is_applying = False
        return super().eventFilter(watched, event)


def install_theme_styles(widget: QWidget, stylesheet_factory) -> None:
    widget.setStyleSheet(stylesheet_factory(widget))
    style_filter = getattr(widget, "_theme_style_filter", None)
    if style_filter is None:
        style_filter = _ThemeStyleFilter(widget, stylesheet_factory)
        widget.installEventFilter(style_filter)
        widget._theme_style_filter = style_filter


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


def dialog_style_sheet(widget: QWidget | None = None) -> str:
    colors = theme_colors(widget)
    return f"""
        QDialog {{
            background: {colors.window};
        }}
        QLabel {{
            color: {colors.text};
        }}
        QGroupBox {{
            background: {colors.surface};
            border: 1px solid {colors.border};
            border-radius: 14px;
            font-weight: 600;
            margin-top: 12px;
            padding-top: 8px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 16px;
            padding: 0 6px;
            color: {colors.text};
        }}
        QLineEdit,
        QComboBox,
        QSpinBox,
        QDoubleSpinBox,
        QPlainTextEdit,
        QTableWidget {{
            background: {colors.input_bg};
            color: {colors.text};
            border: 1px solid {colors.border_strong};
            border-radius: 10px;
            selection-background-color: {colors.selection};
            selection-color: {colors.selection_text};
        }}
        QLineEdit,
        QPlainTextEdit {{
            padding: 8px 10px;
        }}
        QLineEdit:focus,
        QComboBox:focus,
        QSpinBox:focus,
        QDoubleSpinBox:focus,
        QPlainTextEdit:focus,
        QTableWidget:focus {{
            border: 1px solid {colors.accent};
        }}
        QComboBox {{
            padding: 8px 40px 8px 12px;
            font-weight: 600;
            background: {colors.input_bg};
        }}
        QComboBox:hover,
        QSpinBox:hover,
        QDoubleSpinBox:hover {{
            border: 1px solid {colors.accent};
            background: {colors.input_hover};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 34px;
            border-left: 1px solid {colors.border};
            background: {colors.chrome};
            border-top-right-radius: 10px;
            border-bottom-right-radius: 10px;
        }}
        QComboBox::down-arrow,
        QSpinBox::up-arrow,
        QDoubleSpinBox::up-arrow,
        QSpinBox::down-arrow,
        QDoubleSpinBox::down-arrow {{
            image: none;
            width: 0px;
            height: 0px;
        }}
        QSpinBox,
        QDoubleSpinBox {{
            padding: 8px 38px 8px 12px;
            font-weight: 600;
            background: {colors.input_bg};
        }}
        QSpinBox::up-button,
        QDoubleSpinBox::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 28px;
            border-left: 1px solid {colors.border};
            border-bottom: 1px solid {colors.border};
            background: {colors.chrome};
            border-top-right-radius: 10px;
        }}
        QSpinBox::down-button,
        QDoubleSpinBox::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 28px;
            border-left: 1px solid {colors.border};
            background: {colors.chrome};
            border-bottom-right-radius: 10px;
        }}
        QSpinBox::up-button:hover,
        QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover,
        QDoubleSpinBox::down-button:hover {{
            background: {colors.chrome_hover};
        }}
        QComboBox QAbstractItemView {{
            background: {colors.surface};
            color: {colors.text};
            border: 1px solid {colors.border_strong};
            border-radius: 12px;
            outline: 0;
            padding: 8px;
            selection-background-color: {colors.accent_soft};
            selection-color: {colors.accent_soft_text};
        }}
        QComboBox QAbstractItemView::item {{
            min-height: 30px;
            border-radius: 8px;
            padding: 4px 10px;
            margin: 2px 4px;
            color: {colors.text};
            background: transparent;
        }}
        QComboBox QAbstractItemView::item:hover,
        QComboBox QAbstractItemView::item:selected {{
            background: {colors.accent_soft};
            color: {colors.accent_soft_text};
        }}
        QCheckBox#parameterToggle {{
            min-width: 82px;
            min-height: 30px;
        }}
        QPushButton {{
            background: {colors.chrome};
            color: {colors.text};
            border: 1px solid {colors.border};
            border-radius: 10px;
            padding: 9px 14px;
        }}
        QPushButton:hover {{
            background: {colors.chrome_hover};
        }}
        QPushButton:disabled {{
            color: {colors.disabled_text};
            background: {colors.surface_alt};
        }}
        QPushButton#primaryButton {{
            background: {colors.accent};
            color: {colors.accent_text};
            border: 1px solid {colors.accent_pressed};
            font-weight: 600;
            min-height: 38px;
        }}
        QPushButton#primaryButton:hover {{
            background: {colors.accent_hover};
        }}
        QTableWidget {{
            gridline-color: {colors.border};
            alternate-background-color: {colors.surface_alt};
        }}
        QTableWidget::item:selected {{
            background: {colors.selection};
            color: {colors.selection_text};
        }}
        QHeaderView::section {{
            background: {colors.section};
            color: {colors.text_muted};
            border: none;
            border-right: 1px solid {colors.border};
            border-bottom: 1px solid {colors.border};
            padding: 8px 10px;
            font-weight: 700;
        }}
    """


def window_style_sheet(widget: QWidget | None = None) -> str:
    colors = theme_colors(widget)
    return f"""
        QMainWindow {{
            background: {colors.window};
        }}
        QGroupBox {{
            background: {colors.surface};
            border: 1px solid {colors.border};
            border-radius: 14px;
            font-weight: 600;
            margin-top: 12px;
            padding-top: 8px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 16px;
            padding: 0 6px;
            color: {colors.text};
        }}
        QLabel {{
            color: {colors.text};
        }}
        QLabel#sectionHint {{
            color: {colors.text_soft};
        }}
        QLabel#toolTitle {{
            color: {colors.text};
            font-size: 18px;
            font-weight: 700;
        }}
        QLabel#toolBadge {{
            color: {colors.text_muted};
            font-size: 12px;
            background: {colors.surface_alt};
            border: 1px solid {colors.border};
            border-radius: 999px;
            padding: 4px 10px;
            font-weight: 600;
        }}
        QLabel#toolDescription {{
            background: {colors.surface_alt};
            border: 1px solid {colors.border};
            border-radius: 10px;
            padding: 10px 12px;
            color: {colors.text_muted};
        }}
        QLabel#statusBadge {{
            border-radius: 999px;
            padding: 6px 14px;
            font-weight: 600;
            min-width: 72px;
        }}
        QLabel#statusBadge[tone="idle"] {{
            background: {colors.idle_bg};
            color: {colors.idle_text};
        }}
        QLabel#statusBadge[tone="running"] {{
            background: {colors.success_bg};
            color: {colors.success_text};
        }}
        QLabel#statusBadge[tone="success"] {{
            background: {colors.accent_soft};
            color: {colors.accent_soft_text};
        }}
        QLabel#statusBadge[tone="error"] {{
            background: {colors.error_bg};
            color: {colors.error_text};
        }}
        QLabel#fieldHelp {{
            color: {colors.text_soft};
            font-size: 12px;
        }}
        QLabel#parameterTitle {{
            color: {colors.text};
            font-size: 13px;
            font-weight: 700;
        }}
        QLabel#parameterMeta {{
            color: {colors.text_soft};
            font-size: 11px;
        }}
        QLabel#emptyStateLabel {{
            color: {colors.text_muted};
            background: {colors.surface_alt};
            border: 1px dashed {colors.border};
            border-radius: 10px;
            padding: 12px;
        }}
        QFrame#parameterRow {{
            background: {colors.surface_alt};
            border: 1px solid {colors.border};
            border-radius: 14px;
        }}
        QWidget#parameterTitlePanel {{
            background: {colors.section};
            border-right: 1px solid {colors.border};
            border-top-left-radius: 13px;
            border-bottom-left-radius: 13px;
        }}
        QLineEdit,
        QComboBox,
        QSpinBox,
        QDoubleSpinBox,
        QPlainTextEdit {{
            background: {colors.input_bg};
            color: {colors.text};
            border: 1px solid {colors.border_strong};
            border-radius: 10px;
            padding: 8px 10px;
            selection-background-color: {colors.selection};
            selection-color: {colors.selection_text};
        }}
        QLineEdit:focus,
        QComboBox:focus,
        QSpinBox:focus,
        QDoubleSpinBox:focus,
        QPlainTextEdit:focus {{
            border: 1px solid {colors.accent};
        }}
        QComboBox {{
            padding: 8px 40px 8px 12px;
            font-weight: 600;
            color: {colors.text};
            background: {colors.input_bg};
        }}
        QComboBox:hover {{
            border: 1px solid {colors.accent};
            background: {colors.input_hover};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 34px;
            border-left: 1px solid {colors.border};
            background: {colors.chrome};
            border-top-right-radius: 10px;
            border-bottom-right-radius: 10px;
        }}
        QComboBox::down-arrow {{
            image: none;
            width: 0px;
            height: 0px;
        }}
        QComboBox:on {{
            background: {colors.input_hover};
        }}
        QSpinBox,
        QDoubleSpinBox {{
            padding: 8px 38px 8px 12px;
            font-weight: 600;
            color: {colors.text};
            background: {colors.input_bg};
        }}
        QSpinBox:hover,
        QDoubleSpinBox:hover {{
            border: 1px solid {colors.accent};
            background: {colors.input_hover};
        }}
        QSpinBox::up-button,
        QDoubleSpinBox::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 28px;
            border-left: 1px solid {colors.border};
            border-bottom: 1px solid {colors.border};
            background: {colors.chrome};
            border-top-right-radius: 10px;
        }}
        QSpinBox::down-button,
        QDoubleSpinBox::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 28px;
            border-left: 1px solid {colors.border};
            background: {colors.chrome};
            border-bottom-right-radius: 10px;
        }}
        QSpinBox::up-button:hover,
        QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover,
        QDoubleSpinBox::down-button:hover {{
            background: {colors.chrome_hover};
        }}
        QSpinBox::up-arrow,
        QDoubleSpinBox::up-arrow,
        QSpinBox::down-arrow,
        QDoubleSpinBox::down-arrow {{
            image: none;
            width: 0px;
            height: 0px;
        }}
        QComboBox QAbstractItemView {{
            background: {colors.surface};
            color: {colors.text};
            border: 1px solid {colors.border_strong};
            border-radius: 12px;
            outline: 0;
            padding: 8px;
            selection-background-color: {colors.accent_soft};
            selection-color: {colors.accent_soft_text};
        }}
        QComboBox QAbstractItemView::item {{
            min-height: 30px;
            border-radius: 8px;
            padding: 4px 10px;
            margin: 2px 4px;
            color: {colors.text};
            background: transparent;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background: {colors.accent_soft};
            color: {colors.accent_soft_text};
        }}
        QComboBox QAbstractItemView::item:selected {{
            background: {colors.accent_soft};
            color: {colors.accent_soft_text};
        }}
        QCheckBox#parameterToggle {{
            min-width: 82px;
            min-height: 30px;
        }}
        QPushButton {{
            background: {colors.chrome};
            color: {colors.text};
            border: 1px solid {colors.border};
            border-radius: 10px;
            padding: 9px 14px;
        }}
        QPushButton:hover {{
            background: {colors.chrome_hover};
        }}
        QPushButton:disabled {{
            color: {colors.disabled_text};
            background: {colors.surface_alt};
        }}
        QPushButton#primaryButton {{
            background: {colors.accent};
            color: {colors.accent_text};
            border: 1px solid {colors.accent_pressed};
            font-weight: 600;
            min-height: 38px;
        }}
        QPushButton#primaryButton:hover {{
            background: {colors.accent_hover};
        }}
        QPushButton#toolManageButton {{
            padding: 7px 12px;
            min-height: 0px;
        }}
        QProgressBar {{
            min-height: 12px;
            border-radius: 6px;
            background: {colors.progress_bg};
            border: 1px solid {colors.border};
            color: {colors.text};
            text-align: center;
        }}
        QProgressBar::chunk {{
            border-radius: 5px;
            background: {colors.progress_chunk};
        }}
        QTableWidget::item:selected {{
            background: {colors.selection};
            color: {colors.selection_text};
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
    """


def apply_dialog_chrome(dialog: QDialog) -> None:
    install_theme_styles(dialog, dialog_style_sheet)
