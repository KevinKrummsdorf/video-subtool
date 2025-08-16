# src/app/main.py
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import QTimer, QPropertyAnimation, QEasingCurve

from app.view.splash import SplashScreen
from app.i18n import t

# ---- Timings ----
MIN_SPLASH_MS   = 1000   # Splash mindestens so lange stehen lassen
FADE_MS         = 600    # Dauer des Fade-Out
EXTRA_DELAY_MS  = 2000   # Zusatzwartezeit NACH Fade, bevor MainWindow kommt


# -------- Pfade (PyInstaller vs. Dev) --------
def get_base_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):  # type: ignore[attr-defined]
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


BASE_DIR = get_base_dir()
os.chdir(BASE_DIR)
RESOURCES_DIR = BASE_DIR / "resources"


# -------- Windows: Taskleisten-Icon stabil --------
def set_app_user_model_id(id_str: str) -> None:
    if sys.platform.startswith("win"):
        try:
            import ctypes  # noqa: PLC0415
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(id_str)
        except Exception:
            pass


# -------- Exceptions sichtbar --------
def excepthook(exc_type, exc_value, exc_tb):
    print("\n=== UNCAUGHT EXCEPTION ===", file=sys.stderr)
    print(f"{exc_type.__name__}: {exc_value}", file=sys.stderr)
    traceback.print_tb(exc_tb)
    try:
        QMessageBox.critical(None, "VideoSubTool – Fehler",
                             f"{exc_type.__name__}: {exc_value}")
    except Exception:
        pass


sys.excepthook = excepthook


# -------- Main --------
def main() -> int:
    set_app_user_model_id("KevNetwork.VideoSubTool")

    app = QApplication(sys.argv)

    # App-Icon
    ico = RESOURCES_DIR / "icon.ico"
    if ico.exists():
        app.setWindowIcon(QIcon(str(ico)))

    # --- Splash sofort anzeigen ---
    brand_img = RESOURCES_DIR / "branding" / "kevnet-logo.png"
    splash_source = brand_img if brand_img.exists() else ico
    splash = SplashScreen(image_path=splash_source, title=t("app.title"))
    splash.center_on_screen()
    splash.setWindowOpacity(1.0)
    splash.show()
    app.processEvents()  # sofort sichtbar

    # --- Sequenz: Mindestzeit -> Fade -> +Delay -> MainWindow ---
    def start_fade_and_delay():
        anim = QPropertyAnimation(splash, b"windowOpacity", splash)
        anim.setDuration(FADE_MS)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.InOutQuad)

        # WICHTIG: Referenz halten, sonst kann Animation vorzeitig GC'd werden
        splash._fade_anim = anim  # type: ignore[attr-defined]

        def after_fade():
            # Verhindere App-Exit, solange noch kein Fenster offen ist
            app.setQuitOnLastWindowClosed(False)
            splash.close()

            def show_main_window():
                from app.view.main_window import MainWindow

                win = MainWindow()

                # WICHTIG: Starke Referenz halten (sonst schließt es sofort)
                app._main_window = win  # type: ignore[attr-defined]

                if ico.exists():
                    win.setWindowIcon(QIcon(str(ico)))
                win.setWindowTitle(t("app.title"))
                win.show()

                # Ab jetzt wieder normales Verhalten
                app.setQuitOnLastWindowClosed(True)

            QTimer.singleShot(EXTRA_DELAY_MS, show_main_window)

        anim.finished.connect(after_fade)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    QTimer.singleShot(MIN_SPLASH_MS, start_fade_and_delay)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
