"""Rendert die feste JCL und übergibt Releasepakete per FTP an JES."""

from __future__ import annotations

import ftplib
import os
import re
from pathlib import Path
from typing import Any, Callable

from .config import CODEPIPELINE_STAGES
from .errors import DeliveryError, Status
from .manifest import load_and_verify


# Reguläre Ausdrücke für Werte im bestehenden JCL-Vertrag.
# Prüft das Mainframe-Subsystem auf erlaubte Zeichen und Feldlänge.
_SUBSYSTEM_RE = re.compile(r"[A-Z0-9]{2,8}")
# Prüft den Mainframe-Member auf erlaubte Zeichen und Feldlänge.
_MEMBER_RE = re.compile(r"[A-Z0-9]{1,8}")
# Prüft das Assignment auf erlaubte Zeichen und Feldlänge.
_ASSIGNMENT_RE = re.compile(r"[A-Z0-9]{1,12}")
# Das bestehende Dataset nimmt die erzeugten FULL- und DELTA-Pakete auf.
MAINFRAME_DATASET = "IEA.LOMS.TONICZ"
# Dieser JES-Zielknoten nimmt die gerenderte JCL entgegen.
MAINFRAME_JES_TARGET = "LIT9028A"
# Der Verbindungsaufbau darf den Workflow höchstens eine Minute blockieren.
MAINFRAME_TIMEOUT = 60.0


def render_jcl(template: str, jcl: dict[str, str], member: str) -> str:
    """Kapselt Prüfung und Ersetzung an der JCL-Vertragsgrenze."""

    try:
        valid = (
            jcl["ISPW"] in {"T", "P"}
            and jcl["LEVEL"] in CODEPIPELINE_STAGES
            and _SUBSYSTEM_RE.fullmatch(jcl["SUBSYS"]) is not None
            and _ASSIGNMENT_RE.fullmatch(jcl["ASSIGNMENT"]) is not None
            and _MEMBER_RE.fullmatch(member) is not None
        )
    except (KeyError, TypeError) as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED, "JCL-Werte sind ungültig"
        ) from exc
    if not valid:
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL-Werte sind ungültig")

    values = {**jcl, "MEMBER": member}
    rendered = template
    for name, value in values.items():
        rendered = rendered.replace(f"@@{name}@@", value)
    if "@@" in rendered:
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL-Template ist ungültig")
    return rendered


def submit_package(
    package_path: str | Path,
    jcl_path: str | Path,
    member: str,
    *,
    host: str,
    user: str,
    password: str,
    ftp_factory: Callable[[], ftplib.FTP] = ftplib.FTP,
) -> None:
    """Kapselt Paketupload und JCL-Übergabe an der FTP-Systemgrenze."""

    session = ftp_factory()
    try:
        session.connect(host, timeout=MAINFRAME_TIMEOUT)
        session.login(user, password)
        with Path(package_path).open("rb") as package:
            session.storbinary(
                f"STOR '{MAINFRAME_DATASET}({member})'", package
            )
        session.sendcmd("SITE FILETYPE=JES")
        with Path(jcl_path).open("rb") as jcl:
            session.storlines(f"STOR {MAINFRAME_JES_TARGET}", jcl)
        session.quit()
    except ftplib.all_errors as exc:
        session.close()
        raise DeliveryError(
            Status.MAINFRAME_TRANSFER_FAILED, "FTP-/JES-Übergabe fehlgeschlagen"
        ) from exc


def publish_mainframe(
    *,
    manifest_path: str | Path,
    artifact_root: str | Path,
    template_path: str | Path,
    temporary_directory: str | Path,
    execute: bool,
    ftp_factory: Callable[[], ftplib.FTP] = ftplib.FTP,
) -> dict[str, object]:
    """Prüft die Lieferung, rendert alle JCL-Dateien und übergibt sie optional."""

    manifest, packages = load_and_verify(manifest_path, artifact_root)
    try:
        template = Path(template_path).read_text(encoding="ascii")
        jcl_values = manifest["jcl"]
        temporary = Path(temporary_directory)
        temporary.mkdir(parents=True, exist_ok=True)
    except (OSError, UnicodeError, KeyError, TypeError) as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED, "JCL kann nicht vorbereitet werden"
        ) from exc

    rendered: list[tuple[dict[str, Any], Path]] = []
    for package in packages:
        member = package["member"]
        jcl_path = temporary / f"{member}.jcl"
        jcl_path.write_text(
            render_jcl(template, jcl_values, member), encoding="ascii"
        )
        rendered.append((package, jcl_path))
    if not execute:
        return {
            "status": Status.ARTIFACT_READY.value,
            "packages": [package["member"] for package in packages],
            "jcl": [str(path) for _, path in rendered],
        }

    try:
        host = os.environ["MAINFRAME_FTP_HOST"]
        user = os.environ["MAINFRAME_FTP_USER"]
        password = os.environ["MAINFRAME_FTP_PASSWORD"]
    except KeyError as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED, "Mainframe-FTP-Secrets fehlen"
        ) from exc
    for package, jcl_path in rendered:
        submit_package(
            Path(artifact_root) / package["path"],
            jcl_path,
            package["member"],
            host=host,
            user=user,
            password=password,
            ftp_factory=ftp_factory,
        )
    return {"status": Status.MAINFRAME_SUBMITTED.value}
