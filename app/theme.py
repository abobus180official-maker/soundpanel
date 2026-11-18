from __future__ import annotations

from PySide6.QtGui import QColor, QPalette


ACCENT = "#2f9bd6"
ACCENT_DIM = "#1f6d96"
BG = "#1b1d1f"
BG_ALT = "#202325"
PANEL = "#25282b"
PANEL_DARK = "#17191a"
TEXT = "#d7dbde"
TEXT_DIM = "#8b9296"
BORDER = "#34383b"
ROW_PLAYING = "#1d3a4c"


STYLESHEET = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Segoe UI", "Tahoma", sans-serif;
    font-size: 12px;
}}
QMainWindow, QDialog {{
    background-color: {BG};
}}
QToolBar {{
    background-color: {PANEL_DARK};
    border: none;
    border-bottom: 1px solid {BORDER};
    spacing: 4px;
    padding: 4px 6px;
}}
QToolButton, QPushButton {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px 10px;
    color: {TEXT};
}}
QToolButton:hover, QPushButton:hover {{
    background-color: #2d3134;
    border-color: #4a5054;
}}
QToolButton:pressed, QPushButton:pressed {{
    background-color: #35393c;
}}
QToolButton:checked, QPushButton:checked {{
    background-color: {ACCENT_DIM};
    border-color: {ACCENT};
    color: #ffffff;
}}
QPushButton#accent {{
    background-color: {ACCENT_DIM};
    border-color: {ACCENT};
    font-weight: 600;
}}
QPushButton#accent:hover {{
    background-color: {ACCENT};
}}
QTableWidget {{
    background-color: {BG_ALT};
    alternate-background-color: #24272a;
    gridline-color: {BORDER};
    border: 1px solid {BORDER};
    selection-background-color: {ROW_PLAYING};
    selection-color: #ffffff;
    outline: none;
}}
QTableWidget::item {{
    padding: 4px 6px;
    border: none;
}}
QHeaderView::section {{
    background-color: {PANEL_DARK};
    color: {TEXT_DIM};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 6px;
    font-weight: 600;
}}
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {PANEL_DARK};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 20px;
}}
QComboBox:hover, QLineEdit:hover {{
    border-color: #4a5054;
}}
QComboBox QAbstractItemView {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_DIM};
    outline: none;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: #3a3f42;
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: #e6eaec;
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 6px;
}}
QProgressBar {{
    background-color: {PANEL_DARK};
    border: 1px solid {BORDER};
    border-radius: 3px;
    height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 2px;
}}
QStatusBar {{
    background-color: {PANEL_DARK};
    color: {TEXT_DIM};
    border-top: 1px solid {BORDER};
}}
QMenu {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 18px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background-color: {ACCENT_DIM};
}}
QScrollBar:vertical {{
    background: {PANEL_DARK};
    width: 12px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #44494c;
    min-height: 24px;
    border-radius: 6px;
}}
QScrollBar::handle:vertical:hover {{
    background: #565c60;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QLabel#hint {{
    color: {TEXT_DIM};
}}
QLabel#brand {{
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
    padding-right: 10px;
}}
QFrame#panel {{
    background-color: {PANEL_DARK};
    border-top: 1px solid {BORDER};
}}
QToolTip {{
    background-color: {PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px;
}}
"""


def apply_palette(app) -> None:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG))
    palette.setColor(QPalette.WindowText, QColor(TEXT))
    palette.setColor(QPalette.Base, QColor(BG_ALT))
    palette.setColor(QPalette.AlternateBase, QColor("#24272a"))
    palette.setColor(QPalette.Text, QColor(TEXT))
    palette.setColor(QPalette.Button, QColor(PANEL))
    palette.setColor(QPalette.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipBase, QColor(PANEL))
    palette.setColor(QPalette.ToolTipText, QColor(TEXT))
    app.setPalette(palette)
