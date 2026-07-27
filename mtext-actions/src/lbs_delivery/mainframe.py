"""Rendert die feste JCL-Vorlage und übergibt Releasepakete per FTP und JES.

Die Übergabe prüft zuerst Manifest und Vorlage vollständig, rendert für jedes
Paket eine eigene JCL-Datei und startet erst danach die externe Übertragung.
"""

from __future__ import annotations

import ftplib
import os
import re
from pathlib import Path
from typing import Any

from .config import CODEPIPELINE_STAGES
from .process import DeliveryError, Status
from .manifest import load_and_verify


# Reguläre Ausdrücke für Werte, die in den JCL-Vertrag eingesetzt werden.
# Prüft ein Mainframe-Subsystem anhand des Zeichenvorrats und der Feldlänge,
# die Vorlage und Zielsystem akzeptieren.
_SUBSYSTEM_RE = re.compile(r"[A-Z0-9]{2,8}")
# Prüft den erzeugten Dataset-Member nach den Namensregeln des Mainframes.
_MEMBER_RE = re.compile(r"[A-Z0-9]{1,8}")
# Prüft das CodePipeline-Assignment, bevor es in die JCL eingesetzt wird.
_ASSIGNMENT_RE = re.compile(r"[A-Z0-9]{1,12}")
# Die Bytes der FULL- und DELTA-Pakete werden als Member dieses bestehenden
# Mainframe-Datasets abgelegt.
MAINFRAME_DATASET = "IEA.LOMS.TONICZ"
# Die gerenderte Jobsteuerung wird an dieses bestehende JES-Ziel übergeben.
MAINFRAME_JES_TARGET = "LIT9028A"
# Wartezeit pro FTP-Verbindungsaufbau. Der Wert soll den Workflow nicht länger
# blockieren als für die FI üblich nötig.
MAINFRAME_TIMEOUT = 30.0


def render_jcl(template: str, jcl: dict[str, str], member: str) -> str:
    """Prüft externe Werte und setzt sie in die JCL-Vorlage ein."""

    try:
        ispw = jcl["ISPW"]
        level = jcl["LEVEL"]
        subsys = jcl["SUBSYS"]
        assignment = jcl["ASSIGNMENT"]
    except (KeyError, TypeError) as exc:
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL-Werte sind ungültig") from exc

    # Manifest-Werte müssen den JCL-Vertrag erfüllen, bevor Platzhalter ersetzt werden.
    if (
        ispw not in {"T", "P"}
        or level not in CODEPIPELINE_STAGES
        or _SUBSYSTEM_RE.fullmatch(subsys) is None
        or _ASSIGNMENT_RE.fullmatch(assignment) is None
        or _MEMBER_RE.fullmatch(member) is None
    ):
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL-Werte sind ungültig")

    # Platzhalter in der Vorlage durch die geprüften Werte ersetzen.
    values = {**jcl, "MEMBER": member}
    rendered = template
    for name, value in values.items():
        rendered = rendered.replace(f"@@{name}@@", value)

    # Verbleibende Platzhalter zeigen eine unpassende oder unvollständige Vorlage.
    if "@@" in rendered:
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL-Template ist ungültig")

    return rendered


def submit_package(
    package_path: str | Path, jcl_path: str | Path, member: str, *, host: str, user: str, password: str,
) -> None:
    """Lädt ein Paket-Member per FTP hoch und übergibt die gerenderte JCL an JES."""

    session = ftplib.FTP()
    try:
        session.connect(host, timeout=MAINFRAME_TIMEOUT)
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
    *, manifest_path: str | Path, artifact_root: str | Path, template_path: str | Path, temporary_directory: str | Path,
) -> dict[str, object]:
    """Prüft eine Lieferung und übergibt alle enthaltenen Pakete an den Mainframe."""

    # Manifest und Pakete laden und prüfen.
    manifest, packages = load_and_verify(manifest_path, artifact_root)

    # JCL-Vorlage und Manifestwerte für die spätere Erzeugung bereitstellen.
    try:
        template = Path(template_path).read_text(encoding="ascii")
        jcl_values = manifest["jcl"]
        if not isinstance(jcl_values, dict):
            raise TypeError
    except (OSError, UnicodeError) as exc:
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL kann nicht vorbereitet werden") from exc
    except (KeyError, TypeError) as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "Manifest ist unvollständig") from exc

    temporary = Path(temporary_directory)
    temporary.mkdir(parents=True, exist_ok=True)

    # Alle JCL-Dateien erzeugen, bevor Zugangsdaten gelesen oder übertragen werden.
    prepared: list[tuple[dict[str, Any], Path]] = []
    for package in packages:
        member = package["member"]
        jcl_path = temporary / f"{member}.jcl"
        jcl_path.write_text(render_jcl(template, jcl_values, member), encoding="ascii")
        prepared.append((package, jcl_path))

    # FTP-Secrets einmal lesen; danach folgt nur noch die externe Übergabe.
    try:
        host = os.environ["MAINFRAME_FTP_HOST"]
        user = os.environ["MAINFRAME_FTP_USER"]
        password = os.environ["MAINFRAME_FTP_PASSWORD"]
    except KeyError as exc:
        raise DeliveryError(Status.VALIDATION_FAILED, "Mainframe-FTP-Secrets fehlen") from exc

    for package, jcl_path in prepared:
        submit_package(
            Path(artifact_root) / package["path"],
            jcl_path,
            package["member"],
            host=host,
            user=user,
            password=password,
        )

    return {"status": Status.MAINFRAME_SUBMITTED.value}
