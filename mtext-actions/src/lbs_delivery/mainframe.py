"""Implementiert die bestehende FTP-/JES-Übergabe bewusst ohne Job-Polling."""

from __future__ import annotations

import ftplib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .errors import DeliveryError, Status
from .jcl import JclRenderError, MEMBER_RE, render_jcl
from .manifest import Manifest, PackageArtifact


# Fehlerklassen, die während FTP-Verbindung, Upload oder JES-Submit auftreten können.
_FTP_ERRORS = (OSError, ValueError) + ftplib.all_errors
# Festes Dataset für die hochgeladenen Releasepakete.
MAINFRAME_DATASET = "IEA.LOMS.TONICZ"
# Fester JES-Zielknoten für das gerenderte JCL.
MAINFRAME_JES_TARGET = "LIT9028A"
# Maximale Dauer des FTP-Verbindungsaufbaus in Sekunden.
MAINFRAME_FTP_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class FtpSettings:
    """Bündelt die Zugangsdaten der FTP-/JES-Übergabe."""

    host: str
    user: str
    password: str

    @classmethod
    def from_environment(cls) -> "FtpSettings":
        """Liest die erforderlichen Secrets aus der Prozessumgebung."""

        required = {
            "host": os.environ.get("MAINFRAME_FTP_HOST", ""),
            "user": os.environ.get("MAINFRAME_FTP_USER", ""),
            "password": os.environ.get("MAINFRAME_FTP_PASSWORD", ""),
        }
        if not all(required.values()):
            raise DeliveryError(
                Status.VALIDATION_FAILED, "erforderliche Mainframe-FTP-Secrets fehlen"
            )
        return cls(**required)


def render_package_jcl(
    manifest: Manifest, package: PackageArtifact, template: str
) -> str:
    """Rendert die JCL für genau ein im Manifest beschriebenes Paket."""

    try:
        values = dict(manifest["jcl"])
        values["MEMBER"] = package["member"]
        return render_jcl(template, values)
    except JclRenderError as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED, f"JCL-Rendering fehlgeschlagen: {exc}"
        ) from exc


def _accepted(reply: str) -> bool:
    """Bewertet unmittelbare FTP-Antworten der 2xx-Klasse als akzeptiert."""

    return len(reply) >= 3 and reply[:3].isdigit() and 200 <= int(reply[:3]) < 300


def submit_package(
    package_path: str | Path,
    jcl_path: str | Path,
    member: str,
    settings: FtpSettings,
    *,
    ftp_factory: Callable[[], ftplib.FTP] = ftplib.FTP,
) -> None:
    """Überträgt ein Paket und reicht die zugehörige JCL unmittelbar bei JES ein."""

    if MEMBER_RE.fullmatch(member) is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "ungültiger Mainframe-Member")
    package = Path(package_path)
    jcl = Path(jcl_path)
    if not package.is_file() or not jcl.is_file():
        raise DeliveryError(Status.MAINFRAME_TRANSFER_FAILED, "Übergabedatei fehlt")
    session = ftp_factory()
    # Paketupload und JES-Submit gehören zu einer gemeinsamen FTP-Sitzung.
    try:
        session.connect(settings.host, timeout=MAINFRAME_FTP_TIMEOUT_SECONDS)
        login_reply = session.login(settings.user, settings.password)
        if login_reply and not _accepted(login_reply):
            raise ftplib.Error(login_reply)
        with package.open("rb") as source:
            reply = session.storbinary(
                f"STOR '{MAINFRAME_DATASET}({member})'", source
            )
        if not _accepted(reply):
            raise ftplib.Error(reply)
        site_reply = session.sendcmd("SITE FILETYPE=JES")
        if not _accepted(site_reply):
            raise ftplib.Error(site_reply)
        with jcl.open("rb") as source:
            jes_reply = session.storlines(f"STOR {MAINFRAME_JES_TARGET}", source)
        if not _accepted(jes_reply):
            raise ftplib.Error(jes_reply)
        session.quit()
    except _FTP_ERRORS as exc:
        # close() ist nach Transportfehlern nur noch eine bestmögliche Bereinigung.
        try:
            session.close()
        except Exception:
            pass
        raise DeliveryError(
            Status.MAINFRAME_TRANSFER_FAILED, "FTP-/JES-Übergabe fehlgeschlagen"
        ) from exc
