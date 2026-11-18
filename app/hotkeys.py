from __future__ import annotations

import threading

from pynput import keyboard


SPECIAL_NAMES = {
    "alt_l": "alt", "alt_r": "alt", "alt_gr": "alt",
    "ctrl_l": "ctrl", "ctrl_r": "ctrl",
    "shift_l": "shift", "shift_r": "shift",
    "cmd": "win", "cmd_l": "win", "cmd_r": "win",
    "caps_lock": "capslock", "page_up": "pageup", "page_down": "pagedown",
    "print_screen": "printscreen", "scroll_lock": "scrolllock",
    "num_lock": "numlock", "menu": "apps",
}

MODIFIERS = {"ctrl", "alt", "shift", "win"}


def normalize_key_name(key) -> str | None:
    if isinstance(key, keyboard.KeyCode):
        if key.vk is not None and 96 <= key.vk <= 105:
            return f"numpad{key.vk - 96}"
        if key.char:
            return key.char.lower()
        if key.vk is not None:
            return f"vk{key.vk}"
        return None
    name = getattr(key, "name", None)
    if name is None:
        return None
    return SPECIAL_NAMES.get(name, name)


class HotkeyManager:
    def __init__(self, on_hotkey, on_error=None):
        self.on_hotkey = on_hotkey
        self.on_error = on_error
        self._modifiers: set[str] = set()
        self._lock = threading.RLock()
        self._listener: keyboard.Listener | None = None
        self._suppress = False

    def start(self) -> None:
        if self._listener is not None:
            return
        try:
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self._listener.daemon = True
            self._listener.start()
        except Exception as exc:
            if self.on_error:
                self.on_error(f"Горячие клавиши недоступны: {exc}")

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def _on_press(self, key) -> None:
        name = normalize_key_name(key)
        if name is None:
            return
        with self._lock:
            if name in MODIFIERS:
                self._modifiers.add(name)
                return
            combo_parts = sorted(self._modifiers) + [name]
            combo = "+".join(combo_parts)
        if self._suppress:
            return
        try:
            self.on_hotkey(combo)
        except Exception as exc:
            if self.on_error:
                self.on_error(str(exc))

    def _on_release(self, key) -> None:
        name = normalize_key_name(key)
        if name is None:
            return
        with self._lock:
            self._modifiers.discard(name)

    def set_suppressed(self, flag: bool) -> None:
        self._suppress = flag
