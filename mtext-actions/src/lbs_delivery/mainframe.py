"""Übergibt vorbereitete Releasepakete per FTP und JES an den Mainframe."""

from __future__ import annotations

import ftplib
import os
from pathlib import Path

from .process import DeliveryError, NETWORK_TIMEOUT, Status


# FULL- und DELTA-Pakete werden als Member in diesem Mainframe-Dataset abgelegt.
MAINFRAME_DATASET = "IEA.LOMS.TONICZ"

# Die erzeugte JCL wird an dieses JES-Ziel übergeben.
MAINFRAME_JES_TARGET = "LIT9028A"


def submit_package(
    package_path: str | Path, jcl_path: str | Path, member: str, *, host: str, user: str, password: str,
) -> None:
    """Lädt ein Paket-Member per FTP hoch und übergibt die gerenderte JCL an JES."""

    session = ftplib.FTP()
    try:
        session.connect(host, timeout=NETWORK_TIMEOUT)
        session.login(user, password)

        with Path(package_path).open("rb") as package:
            session.storbinary(f"STOR '{MAINFRAME_DATASET}({member})'", package)

        session.sendcmd("SITE FILETYPE=JES")

        with Path(jcl_path).open("rb") as jcl:
            session.storlines(f"STOR {MAINFRAME_JES_TARGET}", jcl)

        session.quit()
    except ftplib.all_errors as exc:
        session.close()
        raise DeliveryError(Status.MAINFRAME_TRANSFER_FAILED, "FTP-/JES-Übergabe fehlgeschlagen") from exc


def publish_mainframe(
    *,
    artifact_root: str | Path,
) -> dict[str, object]:
    """Übergibt alle vorbereiteten Pakete und JCL-Dateien an den Mainframe."""

    root = Path(artifact_root)
    packages = sorted(root.glob("*.tgz"))
    if not packages or any(not package.with_suffix(".jcl").is_file() for package in packages):
        raise DeliveryError(Status.PACKAGE_FAILED, "Releasepakete oder JCL fehlen")

    host = os.environ["MAINFRAME_FTP_HOST"]
    user = os.environ["MAINFRAME_FTP_USER"]
    password = os.environ["MAINFRAME_FTP_PASSWORD"]

    for package in packages:
        submit_package(
            package,
            package.with_suffix(".jcl"),
            package.stem,
            host=host,
            user=user,
            password=password,
        )

    return {"status": Status.MAINFRAME_SUBMITTED.value}
