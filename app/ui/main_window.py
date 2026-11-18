from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QDragEnterEvent, QDropEvent, QFont, QIcon, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog,
                               QFrame, QHBoxLayout, QHeaderView, QLabel, QMainWindow,
                               QMenu, QMessageBox, QProgressBar, QPushButton, QSizePolicy,
                               QSlider, QStatusBar, QTableWidget, QTableWidgetItem, QToolBar,
                               QVBoxLayout, QWidget, QInputDialog)

from app import config, resources
from app.audio import AUDIO_EXTENSIONS, AudioEngine, Sound
from app.hotkeys import HotkeyManager
from app.theme import ACCENT, ROW_PLAYING, TEXT_DIM
from app.ui.hotkey_dialog import HotkeyDialog
from app.ui.waveform import WaveformWidget

DEFAULT_HOTKEYS = ["ctrl+1", "ctrl+2", "ctrl+3", "ctrl+4", "ctrl+5",
                   "ctrl+6", "ctrl+7", "ctrl+8", "ctrl+9", "ctrl+0"]

FILE_FILTER = "Аудио (" + " ".join(f"*{ext}" for ext in AUDIO_EXTENSIONS) + ");;Все файлы (*.*)"


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def humanize_hotkey(combo: str) -> str:
    if not combo:
        return "—"
    parts = combo.split("+")
    names = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}
    pretty = [names.get(part, part.upper()) for part in parts]
    return "+".join(pretty)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Звуковая панель")
        self.resize(1080, 700)
        self.setMinimumSize(820, 520)
        self.setAcceptDrops(True)

        self.cfg = config.load_config()
        self.engine = AudioEngine()
        self.sounds: dict[int, Sound] = {}
        self.order: list[int] = []
        self._next_id = 1
        self._last_played: int | None = None
        self._playing_cache: set[int] = set()
        self._suppress_hotkeys = False
        self._hotkey_map: dict[str, int] = {}
        self._ready = False

        self.hotkeys = HotkeyManager(self._on_global_hotkey, self._on_hotkey_error)

        self._build_ui()
        self._restore_devices()
        self._start_audio()
        self._load_library()
        self._apply_volumes()
        self._update_hotkey_index()
        self._ready = True
        self.hotkeys.start()

        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _build_ui(self) -> None:
        self.setWindowIcon(QIcon(resources.asset("appicon.png")))

        toolbar = QToolBar("Главная")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(toolbar)

        brand = QLabel("SOUNDPANEL")
        brand.setObjectName("brand")
        brand.setContentsMargins(4, 0, 10, 0)
        toolbar.addWidget(brand)
        toolbar.addSeparator()

        self.add_button = QPushButton(QIcon(resources.asset("addfile.png")), " Файлы")
        self.add_button.setIconSize(QSize(18, 18))
        self.add_button.setToolTip("Добавить аудиофайлы (Ctrl+O)")
        self.add_button.clicked.connect(self.add_files)
        toolbar.addWidget(self.add_button)

        self.add_folder_button = QPushButton(QIcon(resources.asset("file.png")), " Папка")
        self.add_folder_button.setIconSize(QSize(18, 18))
        self.add_folder_button.setToolTip("Добавить все звуки из папки")
        self.add_folder_button.clicked.connect(self.add_folder)
        toolbar.addWidget(self.add_folder_button)

        self.remove_button = QPushButton("✕ Удалить")
        self.remove_button.clicked.connect(self.remove_selected)
        toolbar.addWidget(self.remove_button)

        self.up_button = QPushButton()
        self.up_button.setIcon(QIcon(resources.asset("up.png")))
        self.up_button.setIconSize(QSize(18, 18))
        self.up_button.setFixedWidth(36)
        self.up_button.setToolTip("Переместить выше")
        self.up_button.clicked.connect(lambda: self.move_selected(-1))
        toolbar.addWidget(self.up_button)

        self.down_button = QPushButton()
        self.down_button.setIcon(QIcon(resources.asset("down.png")))
        self.down_button.setIconSize(QSize(18, 18))
        self.down_button.setFixedWidth(36)
        self.down_button.setToolTip("Переместить ниже")
        self.down_button.clicked.connect(lambda: self.move_selected(1))
        toolbar.addWidget(self.down_button)

        toolbar.addSeparator()
        self.stop_button = QPushButton("■ Стоп")
        self.stop_button.setToolTip("Остановить все звуки")
        self.stop_button.clicked.connect(self.stop_all)
        toolbar.addWidget(self.stop_button)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        self.exclusive_box = QCheckBox("Только один звук")
        self.exclusive_box.setToolTip("Останавливать предыдущий звук при запуске нового")
        self.exclusive_box.toggled.connect(self._toggle_exclusive)
        toolbar.addWidget(self.exclusive_box)

        device_bar = QToolBar("Устройства")
        device_bar.setMovable(False)
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBar(Qt.TopToolBarArea, device_bar)

        device_bar.addWidget(self._toolbar_label("Выход"))
        self.out_combo = QComboBox()
        self.out_combo.setMinimumWidth(340)
        self.out_combo.setToolTip("Куда играть звук. Для микрофона в Discord выберите CABLE Input")
        self.out_combo.currentIndexChanged.connect(self._on_out_device_changed)
        device_bar.addWidget(self.out_combo)

        device_bar.addWidget(self._toolbar_label("Микрофон"))
        self.mic_combo = QComboBox()
        self.mic_combo.setMinimumWidth(340)
        self.mic_combo.setToolTip("Ваш микрофон: его звук подмешивается в выбранный выход")
        self.mic_combo.currentIndexChanged.connect(self._on_mic_device_changed)
        device_bar.addWidget(self.mic_combo)

        device_bar.addWidget(self._toolbar_label("Для голосового чата: выход = CABLE Input, микрофон = ваш микрофон"))

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["№", "Клавиша", "Название", "Длительность"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 52)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(3, 100)
        layout.addWidget(self.table, 1)

        self.waveform = WaveformWidget()
        layout.addWidget(self.waveform)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QHBoxLayout(panel)
        panel_layout.setContentsMargins(12, 8, 12, 8)
        panel_layout.setSpacing(14)

        panel_layout.addWidget(QLabel("Громкость"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 200)
        self.volume_slider.setFixedWidth(200)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        panel_layout.addWidget(self.volume_slider)
        self.volume_label = QLabel("85%")
        self.volume_label.setFixedWidth(44)
        panel_layout.addWidget(self.volume_label)

        panel_layout.addWidget(QLabel("Микрофон"))
        self.mic_slider = QSlider(Qt.Horizontal)
        self.mic_slider.setRange(0, 200)
        self.mic_slider.setFixedWidth(150)
        self.mic_slider.valueChanged.connect(self._on_mic_volume_changed)
        panel_layout.addWidget(self.mic_slider)
        self.mic_label = QLabel("100%")
        self.mic_label.setFixedWidth(44)
        panel_layout.addWidget(self.mic_label)

        self.mic_button = QPushButton("Микрофон вкл")
        self.mic_button.setCheckable(True)
        self.mic_button.setChecked(True)
        self.mic_button.toggled.connect(self._toggle_mic)
        panel_layout.addWidget(self.mic_button)

        panel_layout.addStretch(1)

        panel_layout.addWidget(QLabel("Выход"))
        self.out_meter = QProgressBar()
        self.out_meter.setRange(0, 100)
        self.out_meter.setValue(0)
        self.out_meter.setTextVisible(False)
        self.out_meter.setFixedWidth(120)
        panel_layout.addWidget(self.out_meter)

        panel_layout.addWidget(QLabel("Мик."))
        self.mic_meter = QProgressBar()
        self.mic_meter.setRange(0, 100)
        self.mic_meter.setValue(0)
        self.mic_meter.setTextVisible(False)
        self.mic_meter.setFixedWidth(120)
        panel_layout.addWidget(self.mic_meter)

        layout.addWidget(panel)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Готово")

        open_action = QAction(self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.add_files)
        self.addAction(open_action)

        delete_action = QAction(self)
        delete_action.setShortcut(QKeySequence.Delete)
        delete_action.triggered.connect(self.remove_selected)
        self.addAction(delete_action)

        self._apply_saved_state()

    def _toolbar_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("hint")
        label.setContentsMargins(8, 0, 4, 0)
        return label

    def _apply_saved_state(self) -> None:
        self.volume_slider.setValue(int(self.cfg.get("sfx_volume", 85)))
        self.mic_slider.setValue(int(self.cfg.get("mic_volume", 100)))
        self.mic_button.setChecked(bool(self.cfg.get("mic_enabled", True)))
        self.exclusive_box.setChecked(bool(self.cfg.get("exclusive_play", False)))
        size = self.cfg.get("window") or {}
        if size.get("width") and size.get("height"):
            self.resize(int(size["width"]), int(size["height"]))

    def _restore_devices(self) -> None:
        self.out_combo.blockSignals(True)
        self.out_combo.clear()
        self.out_combo.addItem("Системное устройство по умолчанию", None)
        for index, name in AudioEngine.output_devices():
            self.out_combo.addItem(f"{index}: {name}", index)
        self._select_device(self.out_combo, self.cfg.get("out_device"))

        self.mic_combo.blockSignals(True)
        self.mic_combo.clear()
        self.mic_combo.addItem("Без микрофона", None)
        for index, name in AudioEngine.input_devices():
            self.mic_combo.addItem(f"{index}: {name}", index)
        self._select_device(self.mic_combo, self.cfg.get("mic_device"))
        self.mic_combo.blockSignals(False)
        self.out_combo.blockSignals(False)

    def _select_device(self, combo: QComboBox, saved) -> None:
        if saved is None:
            combo.setCurrentIndex(0)
            return
        for position in range(combo.count()):
            if combo.itemData(position) == saved:
                combo.setCurrentIndex(position)
                return
        if isinstance(saved, str):
            for position in range(combo.count()):
                if saved and saved in combo.itemText(position):
                    combo.setCurrentIndex(position)
                    return
        combo.setCurrentIndex(0)

    def _start_audio(self) -> None:
        out_device = self.out_combo.currentData()
        mic_device = self.mic_combo.currentData()
        ok = self.engine.start(out_device, mic_device)
        self._update_device_titles()
        if not ok:
            self.statusBar().showMessage(self.engine.last_error or "Аудиоустройство недоступно")
        self._reload_sounds()

    def _update_device_titles(self) -> None:
        self.out_combo.setToolTip(
            f"Выход: {self.out_combo.currentText()}\n"
            "Для передачи в голосовой чат выберите CABLE Input (VB-Audio Virtual Cable)"
        )
        self.mic_combo.setToolTip(
            f"Микрофон: {self.mic_combo.currentText()}\n"
            "Голос подмешивается в выход, чтобы собеседники слышали и вас, и звуки"
        )

    def _on_out_device_changed(self, _index: int) -> None:
        self.cfg["out_device"] = self.out_combo.currentData()
        config.save_config(self.cfg)
        self._start_audio()

    def _on_mic_device_changed(self, _index: int) -> None:
        self.cfg["mic_device"] = self.mic_combo.currentData()
        config.save_config(self.cfg)
        self._start_audio()

    def _reload_sounds(self) -> None:
        for sound_id, sound in list(self.sounds.items()):
            try:
                refreshed = self.engine.load_sound(sound.path, sound.name, sound_id,
                                                   sound.hotkey, sound.volume)
                self.sounds[sound_id] = refreshed
            except Exception:
                pass
        self._refresh_table()

    def _load_library(self) -> None:
        entries = self.cfg.get("sounds") or []
        loaded = 0
        for entry in entries:
            path = entry.get("path") or ""
            if not path or not os.path.isfile(path):
                continue
            try:
                sound = self.engine.load_sound(
                    path,
                    entry.get("name") or Path(path).stem,
                    self._next_id,
                    entry.get("hotkey") or "",
                    float(entry.get("volume", 1.0)),
                )
            except Exception:
                continue
            self.sounds[sound.id] = sound
            self.order.append(sound.id)
            self._next_id += 1
            loaded += 1
        self._refresh_table()
        if loaded:
            self.statusBar().showMessage(f"Загружено звуков: {loaded}")

    def _persist(self) -> None:
        if not self._ready:
            return
        self.cfg["sounds"] = [
            {
                "path": self.sounds[sound_id].path,
                "name": self.sounds[sound_id].name,
                "hotkey": self.sounds[sound_id].hotkey,
                "volume": self.sounds[sound_id].volume,
            }
            for sound_id in self.order
            if sound_id in self.sounds
        ]
        self.cfg["sfx_volume"] = self.volume_slider.value()
        self.cfg["mic_volume"] = self.mic_slider.value()
        self.cfg["mic_enabled"] = self.mic_button.isChecked()
        self.cfg["exclusive_play"] = self.exclusive_box.isChecked()
        self.cfg["window"] = {"width": self.width(), "height": self.height()}
        config.save_config(self.cfg)

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self.order))
        for row, sound_id in enumerate(self.order):
            sound = self.sounds.get(sound_id)
            if sound is None:
                continue
            index_item = QTableWidgetItem(str(row + 1))
            index_item.setTextAlignment(Qt.AlignCenter)
            hotkey_item = QTableWidgetItem(humanize_hotkey(sound.hotkey))
            hotkey_item.setTextAlignment(Qt.AlignCenter)
            name_item = QTableWidgetItem(sound.name)
            duration_item = QTableWidgetItem(format_duration(sound.duration))
            duration_item.setTextAlignment(Qt.AlignCenter)
            for column, item in enumerate((index_item, hotkey_item, name_item, duration_item)):
                item.setData(Qt.UserRole, sound_id)
                if column == 3:
                    item.setForeground(QColor(TEXT_DIM))
                self.table.setItem(row, column, item)
        self._playing_cache = set()
        self._apply_playing_styles(set())

    def _apply_playing_styles(self, playing: set[int]) -> None:
        bold = QFont()
        bold.setBold(True)
        for row, sound_id in enumerate(self.order):
            active = sound_id in playing
            for column in range(4):
                item = self.table.item(row, column)
                if item is None:
                    continue
                item.setBackground(QColor(ROW_PLAYING) if active else QColor(0, 0, 0, 0))
                if column == 2:
                    font = QFont()
                    font.setBold(active)
                    item.setFont(font)
                    item.setForeground(QColor("#ffffff") if active else QColor("#d7dbde"))
        self.table.viewport().update()

    def _row_sound_id(self, row: int) -> int | None:
        item = self.table.item(row, 0)
        if item is None:
            return None
        sound_id = item.data(Qt.UserRole)
        return int(sound_id) if sound_id is not None else None

    def _selected_sound_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        return self._row_sound_id(rows[0].row())

    def _on_cell_clicked(self, row: int, column: int) -> None:
        sound_id = self._row_sound_id(row)
        if sound_id is None:
            return
        if column == 1:
            self.assign_hotkey(sound_id)
            return
        self.play_sound(sound_id)

    def _on_cell_double_clicked(self, row: int, _column: int) -> None:
        sound_id = self._row_sound_id(row)
        if sound_id is not None:
            self.rename_sound(sound_id)

    def play_sound(self, sound_id: int) -> None:
        sound = self.sounds.get(sound_id)
        if sound is None:
            return
        if sound_id in self.engine.playing_ids():
            self.engine.stop_sound(sound_id)
        else:
            self.engine.play(sound, exclusive=self.exclusive_box.isChecked())
        self._last_played = sound_id
        self.waveform.set_sound(sound.peaks, sound.name)

    def stop_all(self) -> None:
        self.engine.stop_all()
        self.statusBar().showMessage("Воспроизведение остановлено")

    def add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Добавить звуки", "", FILE_FILTER)
        if paths:
            self._add_paths(paths)

    def add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Добавить папку со звуками")
        if not folder:
            return
        found: list[str] = []
        for root, _dirs, files in os.walk(folder):
            for name in sorted(files):
                if name.lower().endswith(AUDIO_EXTENSIONS):
                    found.append(os.path.join(root, name))
        if not found:
            QMessageBox.information(self, "SoundPanel", "В папке не найдено поддерживаемых аудиофайлов.")
            return
        self._add_paths(found)

    def _next_free_hotkey(self) -> str:
        used = {sound.hotkey for sound in self.sounds.values() if sound.hotkey}
        row = 1
        while True:
            for candidate in DEFAULT_HOTKEYS:
                if candidate not in used:
                    return candidate
            candidate = f"ctrl+alt+{row}"
            if candidate not in used:
                return candidate
            row += 1

    def _add_paths(self, paths: list[str]) -> None:
        added = 0
        failed: list[str] = []
        for path in paths:
            if not os.path.isfile(path) or not path.lower().endswith(AUDIO_EXTENSIONS):
                continue
            try:
                hotkey = self._next_free_hotkey()
                sound = self.engine.load_sound(path, Path(path).stem, self._next_id, hotkey)
            except Exception:
                failed.append(Path(path).name)
                continue
            self.sounds[sound.id] = sound
            self.order.append(sound.id)
            self._next_id += 1
            added += 1
        if added:
            self._refresh_table()
            self._update_hotkey_index()
            self._persist()
            self.statusBar().showMessage(f"Добавлено звуков: {added}")
        if failed:
            QMessageBox.warning(self, "SoundPanel",
                                "Не удалось прочитать файлы:\n" + "\n".join(failed[:12]))

    def remove_selected(self) -> None:
        sound_id = self._selected_sound_id()
        if sound_id is None:
            return
        self.engine.stop_sound(sound_id)
        self.sounds.pop(sound_id, None)
        if sound_id in self.order:
            self.order.remove(sound_id)
        if self._last_played == sound_id:
            self._last_played = None
            self.waveform.set_sound(None)
        self._refresh_table()
        self._update_hotkey_index()
        self._persist()

    def move_selected(self, delta: int) -> None:
        sound_id = self._selected_sound_id()
        if sound_id is None:
            return
        position = self.order.index(sound_id)
        target = position + delta
        if 0 <= target < len(self.order):
            self.order[position], self.order[target] = self.order[target], self.order[position]
            self._refresh_table()
            self.table.selectRow(target)
            self._persist()

    def rename_sound(self, sound_id: int) -> None:
        sound = self.sounds.get(sound_id)
        if sound is None:
            return
        name, ok = QInputDialog.getText(self, "Переименовать", "Название:", text=sound.name)
        if ok and name.strip():
            sound.name = name.strip()
            self._refresh_table()
            self._persist()

    def change_volume(self, sound_id: int) -> None:
        sound = self.sounds.get(sound_id)
        if sound is None:
            return
        value, ok = QInputDialog.getDouble(self, "Громкость звука", "Процент громкости:",
                                           sound.volume * 100.0, 0.0, 200.0, 0)
        if ok:
            sound.volume = value / 100.0
            self._persist()

    def assign_hotkey(self, sound_id: int) -> None:
        sound = self.sounds.get(sound_id)
        if sound is None:
            return
        self._suppress_hotkeys = True
        self.hotkeys.set_suppressed(True)
        try:
            dialog = HotkeyDialog(sound.hotkey, f"Клавиша для «{sound.name}»", self)
            if dialog.exec():
                combo = dialog.result_hotkey()
                for other in self.sounds.values():
                    if other.id != sound_id and other.hotkey == combo:
                        other.hotkey = ""
                sound.hotkey = combo
                self._refresh_table()
                self._update_hotkey_index()
                self._persist()
        finally:
            self._suppress_hotkeys = False
            self.hotkeys.set_suppressed(False)

    def _show_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        self.table.selectRow(index.row())
        sound_id = self._row_sound_id(index.row())
        if sound_id is None:
            return
        sound = self.sounds.get(sound_id)
        menu = QMenu(self)
        play_action = menu.addAction("Воспроизвести")
        stop_action = menu.addAction("Остановить")
        menu.addSeparator()
        hotkey_action = menu.addAction("Назначить клавишу…")
        rename_action = menu.addAction("Переименовать…")
        volume_action = menu.addAction("Громкость…")
        menu.addSeparator()
        up_action = menu.addAction("Выше")
        down_action = menu.addAction("Ниже")
        menu.addSeparator()
        remove_action = menu.addAction("Удалить из списка")

        chosen = menu.exec(self.table.viewport().mapToGlobal(position))
        if chosen is play_action:
            self.play_sound(sound_id)
        elif chosen is stop_action:
            self.engine.stop_sound(sound_id)
        elif chosen is hotkey_action:
            self.assign_hotkey(sound_id)
        elif chosen is rename_action:
            self.rename_sound(sound_id)
        elif chosen is volume_action:
            self.change_volume(sound_id)
        elif chosen is up_action:
            self.move_selected(-1)
        elif chosen is down_action:
            self.move_selected(1)
        elif chosen is remove_action:
            self.remove_selected()

    def _on_volume_changed(self, value: int) -> None:
        self.volume_label.setText(f"{value}%")
        self.engine.set_sfx_gain(value / 100.0)
        self._persist()

    def _on_mic_volume_changed(self, value: int) -> None:
        self.mic_label.setText(f"{value}%")
        self.engine.set_mic_gain(value / 100.0)
        self._persist()

    def _apply_volumes(self) -> None:
        self.engine.set_sfx_gain(self.volume_slider.value() / 100.0)
        self.engine.set_mic_gain(self.mic_slider.value() / 100.0)

    def _toggle_mic(self, checked: bool) -> None:
        self.engine.mic_enabled = checked
        self.mic_button.setText("Микрофон вкл" if checked else "Микрофон выкл")
        self._persist()

    def _toggle_exclusive(self, checked: bool) -> None:
        self.cfg["exclusive_play"] = checked
        self._persist()

    def _on_hotkey_error(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _update_hotkey_index(self) -> None:
        self._hotkey_map = {
            sound.hotkey.lower(): sound.id
            for sound in self.sounds.values()
            if sound.hotkey
        }

    def _on_global_hotkey(self, combo: str) -> None:
        if self._suppress_hotkeys:
            return
        sound_id = self._hotkey_map.get(combo.lower())
        if sound_id is None:
            return
        sound = self.sounds.get(sound_id)
        if sound is None:
            return
        if sound_id in self.engine.playing_ids():
            self.engine.stop_sound(sound_id)
        else:
            self.engine.play(sound, exclusive=self.exclusive_box.isChecked())
        self._last_played = sound_id

    def _tick(self) -> None:
        playing = self.engine.playing_ids()
        if playing != self._playing_cache:
            self._playing_cache = playing
            self._apply_playing_styles(playing)
        if self._last_played is not None:
            progress = self.engine.voice_progress(self._last_played)
            self.waveform.set_progress(progress)
        self.out_meter.setValue(min(100, int(self.engine.out_level * 180)))
        self.mic_meter.setValue(min(100, int(self.engine.mic_level * 180)))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        files: list[str] = []
        for path in paths:
            if os.path.isdir(path):
                for root, _dirs, names in os.walk(path):
                    for name in names:
                        if name.lower().endswith(AUDIO_EXTENSIONS):
                            files.append(os.path.join(root, name))
            elif path.lower().endswith(AUDIO_EXTENSIONS):
                files.append(path)
        if files:
            self._add_paths(files)
        event.acceptProposedAction()

    def closeEvent(self, event) -> None:
        self._persist()
        self.timer.stop()
        self.hotkeys.stop()
        self.engine.stop()
        super().closeEvent(event)
