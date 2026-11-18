import os
import sys
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from app import config
from app.theme import STYLESHEET, apply_palette
from app.ui.main_window import MainWindow


def _install_excepthook() -> None:
    def hook(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            log_path = config.config_dir() / "error.log"
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(text + "\n")
        except OSError:
            pass
        sys.__stderr__ and sys.__stderr__.write(text)
        try:
            QMessageBox.critical(None, "SoundPanel — ошибка", text[-1500:])
        except Exception:
            pass

    sys.excepthook = hook


def main() -> int:
    _install_excepthook()
    app = QApplication(sys.argv)
    app.setApplicationName("SoundPanel")
    app.setApplicationDisplayName("SoundPanel")
    app.setOrganizationName("SoundPanel")
    apply_palette(app)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    if os.environ.get("SOUNDPANEL_SMOKE") == "1":
        QTimer.singleShot(1800, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
