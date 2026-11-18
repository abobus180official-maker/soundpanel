from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QLinearGradient
from PySide6.QtWidgets import QWidget

from app.theme import ACCENT, BG_ALT, TEXT_DIM, BORDER, PANEL_DARK


class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(90)
        self.setMaximumHeight(140)
        self._peaks = np.zeros(0, dtype=np.float32)
        self._progress = 0.0
        self._title = ""
        self._active = False

    def set_sound(self, peaks: np.ndarray | None, title: str = "") -> None:
        self._peaks = peaks if peaks is not None else np.zeros(0, dtype=np.float32)
        self._title = title
        self._progress = 0.0
        self.update()

    def set_progress(self, value: float | None) -> None:
        self._progress = float(value or 0.0)
        self._active = value is not None
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.fillRect(rect, QColor(PANEL_DARK))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(rect)

        margin = 10
        area = QRectF(rect.left() + margin, rect.top() + margin,
                      rect.width() - 2 * margin, rect.height() - 2 * margin)
        center_y = area.center().y()

        painter.setPen(QPen(QColor(BORDER), 1, Qt.DashLine))
        painter.drawLine(int(area.left()), int(center_y), int(area.right()), int(center_y))

        peaks = self._peaks
        if peaks is None or len(peaks) == 0:
            painter.setPen(QColor(TEXT_DIM))
            painter.drawText(rect, Qt.AlignCenter, "Осциллограмма появится при воспроизведении")
            painter.end()
            return

        count = len(peaks)
        bar_width = area.width() / count
        max_peak = float(np.max(peaks)) or 1.0
        half = area.height() / 2.0
        played_x = area.left() + area.width() * min(1.0, max(0.0, self._progress))

        for index, peak in enumerate(peaks):
            value = float(min(1.0, peak / max_peak)) * half
            x = area.left() + index * bar_width
            height = max(1.0, value)
            bar = QRectF(x, center_y - height, max(1.0, bar_width - 1.0), height * 2)
            if x < played_x:
                gradient = QLinearGradient(bar.topLeft(), bar.bottomLeft())
                gradient.setColorAt(0.0, QColor(ACCENT))
                gradient.setColorAt(0.5, QColor("#7fd0f5"))
                gradient.setColorAt(1.0, QColor(ACCENT))
                painter.fillRect(bar, gradient)
            else:
                painter.fillRect(bar, QColor("#3b4145"))

        if self._active:
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.drawLine(int(played_x), int(area.top()), int(played_x), int(area.bottom()))

        if self._title:
            painter.setPen(QColor(TEXT_DIM))
            painter.drawText(area.adjusted(6, 2, -6, 0), Qt.AlignLeft | Qt.AlignTop, self._title)
        painter.end()
