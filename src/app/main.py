# src/app/main.py
from __future__ import annotations

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
def base_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


RESOURCES_DIR = base_dir() / "resources"


# -------- Icon laden --------
def load_app_icon() -> QIcon:
    ico = RESOURCES_DIR / "branding" / "icon.ico"
    if ico.exists():
        return QIcon(str(ico))
    png = RESOURCES_DIR / "branding" / "icon.png"
    if png.exists():
        return QIcon(str(png))
    return QIcon()


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

    icon = load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    # --- Splash sofort anzeigen ---
    brand_img = RESOURCES_DIR / "branding" / "kevnet-logo.png"
    ico_file = RESOURCES_DIR / "branding" / "icon.ico"
    png_file = RESOURCES_DIR / "branding" / "icon.png"
    fallback_img = ico_file if ico_file.exists() else png_file
    splash_source = brand_img if brand_img.exists() else fallback_img
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

                if not icon.isNull():
                    win.setWindowIcon(icon)
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
