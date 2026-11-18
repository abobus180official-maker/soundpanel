from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout)

MODIFIER_KEYS = {
    Qt.Key_Control: "ctrl",
    Qt.Key_Shift: "shift",
    Qt.Key_Alt: "alt",
    Qt.Key_Meta: "win",
}

NAMED_KEYS = {
    Qt.Key_Space: "space",
    Qt.Key_Return: "enter",
    Qt.Key_Enter: "enter",
    Qt.Key_Escape: "esc",
    Qt.Key_Tab: "tab",
    Qt.Key_Backspace: "backspace",
    Qt.Key_Delete: "delete",
    Qt.Key_Insert: "insert",
    Qt.Key_Home: "home",
    Qt.Key_End: "end",
    Qt.Key_PageUp: "pageup",
    Qt.Key_PageDown: "pagedown",
    Qt.Key_Up: "up",
    Qt.Key_Down: "down",
    Qt.Key_Left: "left",
    Qt.Key_Right: "right",
    Qt.Key_Print: "printscreen",
    Qt.Key_Pause: "pause",
    Qt.Key_Menu: "apps",
    Qt.Key_NumLock: "numlock",
    Qt.Key_CapsLock: "capslock",
    Qt.Key_ScrollLock: "scrolllock",
}


def combo_from_event(event) -> str | None:
    key = event.key()
    if key in MODIFIER_KEYS:
        return None
    parts: list[str] = []
    modifiers = event.modifiers()
    if modifiers & Qt.ControlModifier:
        parts.append("ctrl")
    if modifiers & Qt.AltModifier:
        parts.append("alt")
    if modifiers & Qt.ShiftModifier:
        parts.append("shift")
    if modifiers & Qt.MetaModifier:
        parts.append("win")

    name: str | None = None
    if Qt.Key_F1 <= key <= Qt.Key_F24:
        name = f"f{key - Qt.Key_F1 + 1}"
    elif key in NAMED_KEYS:
        name = NAMED_KEYS[key]
    elif Qt.Key_0 <= key <= Qt.Key_9:
        digit = chr(ord("0") + key - Qt.Key_0)
        name = f"numpad{digit}" if modifiers & Qt.KeypadModifier else digit
    elif Qt.Key_A <= key <= Qt.Key_Z:
        name = chr(ord("a") + key - Qt.Key_A)
    elif key == Qt.Key_Plus:
        name = "+"
    elif key == Qt.Key_Minus:
        name = "-"
    elif key == Qt.Key_Asterisk:
        name = "*"
    elif key == Qt.Key_Slash:
        name = "/"

    if name is None:
        return None
    parts.append(name)
    return "+".join(parts)


class HotkeyDialog(QDialog):
    def __init__(self, current: str, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(340)
        self._combo = current
        self._captured: str | None = None

        layout = QVBoxLayout(self)
        hint = QLabel("Нажмите нужное сочетание клавиш.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.value_label = QLabel(current or "—")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet(
            "font-size: 18px; font-weight: 600; padding: 14px;"
            "background:#17191a; border:1px solid #34383b; border-radius:4px;"
        )
        layout.addWidget(self.value_label)

        buttons = QHBoxLayout()
        self.clear_button = QPushButton("Очистить")
        self.clear_button.clicked.connect(self._clear)
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        self.ok_button = QPushButton("Готово")
        self.ok_button.setObjectName("accent")
        self.ok_button.clicked.connect(self.accept)
        buttons.addWidget(self.clear_button)
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.ok_button)
        layout.addLayout(buttons)
        self.setFocusPolicy(Qt.StrongFocus)

    def _clear(self) -> None:
        self._captured = ""
        self.value_label.setText("—")

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Escape,) and not event.modifiers():
            self.reject()
            return
        combo = combo_from_event(event)
        if combo is None:
            super().keyPressEvent(event)
            return
        self._captured = combo
        self.value_label.setText(QKeySequence(combo).toString())
        self.value_label.setToolTip(combo)

    def result_hotkey(self) -> str:
        if self._captured is None:
            return self._combo
        return self._captured
