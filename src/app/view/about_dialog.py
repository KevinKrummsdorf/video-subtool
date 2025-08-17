# src/app/view/about_dialog.py
from __future__ import annotations
import platform
import sys
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError

from PySide6 import QtCore, __version__ as PYSIDE_VER
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox

from app.settings import app_data_dir
from app.i18n import t
from app.service.ffmpeg_service import FfmpegService
from app import __version__ as APP_VERSION


def _base_dir() -> Path:
    # Dev vs. PyInstaller
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))

def _resources_dir() -> Path:
    return _base_dir() / "resources"


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QApplication
        self.setWindowIcon(QApplication.instance().windowIcon())
        self.setWindowTitle(t("about.title"))
        self.setModal(True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        lay = QVBoxLayout(self)

        # ---- Kopfzeile ------------------------------------------------------
        try:
            app_ver = version("video-subtool")
        except PackageNotFoundError:
            app_ver = APP_VERSION or "dev"
        except Exception:
            app_ver = APP_VERSION or "dev"

        head = QLabel(t("about.head") + f" <span style='opacity:.6'>(v{app_ver})</span>")
        f = QFont(head.font())
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        head.setFont(f)
        head.setTextFormat(Qt.RichText)
        lay.addWidget(head)

        # ---- Kurzbeschreibung ----------------------------------------------
        features = QLabel(t("about.features"))
        features.setTextFormat(Qt.RichText)
        features.setWordWrap(True)
        lay.addWidget(features)

        # ---- FFmpeg Herkunft/Infos -----------------------------------------
        ff = FfmpegService()
        ff_path = ""
        origin = "system"
        try:
            ff_path = ff.find_ffbin("ffmpeg")
            rp = _resources_dir().resolve()
            try:
                is_bundled = Path(ff_path).resolve().is_relative_to(rp)
            except AttributeError:
                is_bundled = str(Path(ff_path).resolve()).startswith(str(rp))
            origin = "bundled" if is_bundled else "system"
        except Exception:
            pass

        is_windows = (platform.system() == "Windows")
        ffmpeg_html = t("about.ffmpeg.win") if is_windows else t("about.ffmpeg.linux")

        lic_dir = (_resources_dir() / "LICENSES" / "FFmpeg").as_posix()
        licenses = (
            f"<p>{t('about.licenses')}: "
            f"<a href='file:///{lic_dir}'>resources/LICENSES/FFmpeg/</a><br>"
            "Builds: <a href='https://github.com/BtbN/FFmpeg-Builds'>BtbN/FFmpeg-Builds</a></p>"
        )

        ff_where = QLabel(
            ffmpeg_html +
            f"<p style='margin-top:2px; opacity:.85'>FFmpeg: <code>{origin}</code><br>"
            f"Path: <code>{ff_path or '–'}</code></p>" +
            licenses
        )
        ff_where.setOpenExternalLinks(True)
        ff_where.setTextFormat(Qt.RichText)
        ff_where.setWordWrap(True)
        lay.addWidget(ff_where)

        # ---- Tech-Footer (Qt/PySide, App-Daten) ----------------------------
        qt_info = QLabel(
            f"<p style='margin-top:6px; opacity:.7'>"
            f"Qt {QtCore.qVersion()} · PySide {PYSIDE_VER}</p>"
        )
        qt_info.setTextFormat(Qt.RichText)
        lay.addWidget(qt_info)

        data_dir = app_data_dir()
        data = QLabel(f"<code>{t('about.appdata')}</code> {data_dir}")
        data.setTextFormat(Qt.RichText)
        data.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(data)

        # ---- Links ----------------------------------------------------------
        links = QLabel(
            f"<p style='margin-top:4px'>{t('about.website')}: "
            "<a href='https://kev-network.de/'>kev-network.de</a><br>"
            f"{t('about.source')}: "
            "<a href='https://github.com/KevinKrummsdorf/video-subtool'>GitHub Repository</a></p>"
        )
        links.setOpenExternalLinks(True)
        links.setTextFormat(Qt.RichText)
        links.setWordWrap(True)
        lay.addWidget(links)

        # ---- OK -------------------------------------------------------------
        btns = QDialogButtonBox(QDialogButtonBox.Ok, parent=self)
        btns.accepted.connect(self.accept)
        lay.addWidget(btns)
