"""Rendert die feste JCL-Vorlage und übergibt Releasepakete per FTP und JES.

Die Übergabe beginnt mit einem geprüften Manifest, rendert für jedes Paket eine
JCL-Datei und lädt beide Teile mit den Zugangsdaten der Workflow-Umgebung hoch.
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
# Ein Verbindungsversuch darf den Übergabeworkflow höchstens eine Minute aufhalten.
MAINFRAME_TIMEOUT = 60.0


def render_jcl(template: str, jcl: dict[str, str], member: str) -> str:
    """Prüft externe Werte und setzt sie in die JCL-Vorlage ein.

    Die Prüfung erfolgt vor der Textersetzung, weil die Werte in die Syntax der
    Jobsteuerung eingehen. Verbleibende Platzhalter kennzeichnen eine
    unvollständige oder unpassende Vorlage und führen zum Abbruch.
    """

    try:
        valid = (
            jcl["ISPW"] in {"T", "P"}
            and jcl["LEVEL"] in CODEPIPELINE_STAGES
            and _SUBSYSTEM_RE.fullmatch(jcl["SUBSYS"]) is not None
            and _ASSIGNMENT_RE.fullmatch(jcl["ASSIGNMENT"]) is not None
            and _MEMBER_RE.fullmatch(member) is not None
        )
    except (KeyError, TypeError) as exc:
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL-Werte sind ungültig") from exc
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
) -> None:
    """Lädt einen Paket-Member hoch und übergibt seine gerenderte JCL.

    Die FTP-Sitzung schreibt zunächst die binären Paketdaten in das feste
    Dataset. Anschließend wechselt sie in den JES-Modus und übergibt den
    zugehörigen Textjob.
    """

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
    *,
    manifest_path: str | Path,
    artifact_root: str | Path,
    template_path: str | Path,
    temporary_directory: str | Path,
) -> dict[str, object]:
    """Prüft eine Lieferung und übergibt alle enthaltenen Pakete an den Mainframe.

    Sämtliche JCL-Dateien werden gerendert, bevor Zugangsdaten gelesen werden oder
    ein Netzwerktransfer beginnt. Fehler in Manifest oder Vorlage werden dadurch
    erkannt, bevor eine unvollständige externe Übergabe entstehen kann.
    """

    manifest, packages = load_and_verify(manifest_path, artifact_root)
    try:
        template = Path(template_path).read_text(encoding="ascii")
        jcl_values = manifest["jcl"]
        temporary = Path(temporary_directory)
        temporary.mkdir(parents=True, exist_ok=True)
    except (OSError, UnicodeError, KeyError, TypeError) as exc:
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL kann nicht vorbereitet werden") from exc

    rendered: list[tuple[dict[str, Any], Path]] = []
    for package in packages:
        member = package["member"]
        jcl_path = temporary / f"{member}.jcl"
        jcl_path.write_text(render_jcl(template, jcl_values, member), encoding="ascii")
        rendered.append((package, jcl_path))

    try:
        host = os.environ["MAINFRAME_FTP_HOST"]
        user = os.environ["MAINFRAME_FTP_USER"]
        password = os.environ["MAINFRAME_FTP_PASSWORD"]
    except KeyError as exc:
        raise DeliveryError(Status.VALIDATION_FAILED, "Mainframe-FTP-Secrets fehlen") from exc
    for package, jcl_path in rendered:
        submit_package(
            Path(artifact_root) / package["path"],
            jcl_path,
            package["member"],
            host=host,
            user=user,
            password=password,
        )
    return {"status": Status.MAINFRAME_SUBMITTED.value}
