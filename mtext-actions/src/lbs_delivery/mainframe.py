"""Implementiert die bestehende FTP-/JES-Übergabe bewusst ohne Job-Polling."""

from __future__ import annotations

import ftplib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .errors import DeliveryError, Status
from .jcl import JclRenderError, render_jcl
from .manifest import Manifest, PackageArtifact


_MEMBER_RE = re.compile(r"[A-Z0-9]{1,8}")
_DATASET_RE = re.compile(r"[A-Z0-9@$#.-]{1,44}")
_FTP_ERRORS = (OSError, ValueError) + ftplib.all_errors


@dataclass(frozen=True)
class FtpSettings:
    """Bündelt Zugang und technische Zielparameter der FTP-/JES-Übergabe."""

    host: str
    user: str
    password: str
    dataset: str = "IEA.LOMS.TONICZ"
    jes_target: str = "LIT9028A"
    timeout: float = 60.0

    @classmethod
    def from_environment(cls) -> "FtpSettings":
        """Liest Secrets und optionale Zielwerte aus der Prozessumgebung."""

        required = {
            "host": os.environ.get("MAINFRAME_FTP_HOST", ""),
            "user": os.environ.get("MAINFRAME_FTP_USER", ""),
            "password": os.environ.get("MAINFRAME_FTP_PASSWORD", ""),
        }
        if not all(required.values()):
            raise DeliveryError(
                Status.VALIDATION_FAILED, "required Mainframe FTP secrets are missing"
            )
        return cls(
            **required,
            dataset=os.environ.get("MAINFRAME_DATASET") or "IEA.LOMS.TONICZ",
            jes_target=os.environ.get("MAINFRAME_JES_TARGET") or "LIT9028A",
            timeout=float(os.environ.get("MAINFRAME_FTP_TIMEOUT") or "60"),
        )


def render_package_jcl(
    manifest: Manifest, package: PackageArtifact, template: str
) -> str:
    """Rendert die JCL für genau ein im Manifest beschriebenes Paket."""

    try:
        values = dict(manifest["jcl"])
        values["MEMBER"] = package["member"]
        return render_jcl(template, values)
    except JclRenderError as exc:
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL rendering failed") from exc


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

    if _MEMBER_RE.fullmatch(member) is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "invalid Mainframe member")
    if _DATASET_RE.fullmatch(settings.dataset) is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "invalid Mainframe dataset")
    package = Path(package_path)
    jcl = Path(jcl_path)
    if not package.is_file() or not jcl.is_file():
        raise DeliveryError(Status.MAINFRAME_TRANSFER_FAILED, "publish input is missing")
    session = ftp_factory()
    try:
        session.connect(settings.host, timeout=settings.timeout)
        login_reply = session.login(settings.user, settings.password)
        if login_reply and not _accepted(login_reply):
            raise ftplib.Error(login_reply)
        with package.open("rb") as source:
            reply = session.storbinary(
                f"STOR '{settings.dataset}({member})'", source
            )
        if not _accepted(reply):
            raise ftplib.Error(reply)
        site_reply = session.sendcmd("SITE FILETYPE=JES")
        if not _accepted(site_reply):
            raise ftplib.Error(site_reply)
        with jcl.open("rb") as source:
            jes_reply = session.storlines(f"STOR {settings.jes_target}", source)
        if not _accepted(jes_reply):
            raise ftplib.Error(jes_reply)
        session.quit()
    except _FTP_ERRORS as exc:
        try:
            session.close()
        except Exception:
            pass
        raise DeliveryError(
            Status.MAINFRAME_TRANSFER_FAILED, "FTP/JES hand-over failed"
        ) from exc
