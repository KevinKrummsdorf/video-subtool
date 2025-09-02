# src/app/main.py
from __future__ import annotations

import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QTimer, QPropertyAnimation, QEasingCurve

from app.view.splash import SplashScreen
from app.i18n import t

# ---- Timings ----
MIN_SPLASH_MS   = 1000   # Splash mindestens so lange stehen lassen
FADE_MS         = 600    # Dauer des Fade-Out
EXTRA_DELAY_MS  = 2000   # Zusatzwartezeit NACH Fade, bevor MainWindow kommt


# -------- Pfade (PyInstaller vs. Dev) --------
def base_dir() -> Path:
    # _MEIPASS = PyInstaller-Tempdir, sonst Projektwurzel (video-subtool/)
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))

RESOURCES_DIR = base_dir() / "resources"
BRANDING_DIR  = RESOURCES_DIR / "branding"    # <— neu


# -------- Hilfen für Branding --------
def _first_existing(*candidates: Path) -> Path | None:
    for p in candidates:
        if p and p.exists():
            return p
    return None

def _find_brand_asset(preferred_names: list[str], exts: tuple[str, ...] = (".png", ".ico", ".svg")) -> Path | None:
    """
    Sucht im branding/ nach der ersten existierenden Datei.
    Beispiel: preferred_names=["app_icon", "icon"] prüft app_icon.png/.ico/.svg, dann icon.png/.ico/.svg.
    """
    for stem in preferred_names:
        for ext in exts:
            p = BRANDING_DIR / f"{stem}{ext}"
            if p.exists():
                return p
    return None


# -------- Icon laden --------
def load_app_icon() -> QIcon:
    # Priorität: app_icon.* > icon.*  (png/ico/svg)
    icon_path = _find_brand_asset(["logo", "icon"], exts=(".ico", ".png", ".svg"))
    if icon_path:
        # QIcon kann png/ico/svg laden, svg braucht ggf. QtSvg — probieren wir einfach.
        return QIcon(str(icon_path))
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
    # Priorität für Splash: splash.* > logo_splash.* > logo.* > brand.* > kevnet-logo.* > icon.*
    splash_path = (
        _find_brand_asset(["splash", "logo_splash", "logo", "brand", "kevnet-logo"], exts=(".png", ".svg"))
        or _find_brand_asset(["app_icon", "icon"], exts=(".png", ".ico", ".svg"))
    )

    if splash_path is None:
        # Harte Fallbacks wie bisher
        ico_file = BRANDING_DIR / "icon.ico"
        png_file = BRANDING_DIR / "icon.png"
        splash_path = _first_existing(ico_file, png_file)

    splash = SplashScreen(image_path=splash_path, title=t("app.title"))
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
