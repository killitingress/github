"""Erzeugt und übergibt FULL- und DELTA-Lieferungen an den Mainframe.

Der Releasebau prüft die Git-Quelle und verpackt jedes konfigurierte Projekt.
Zu jedem Paket entstehen die benötigte JCL und eine JSON-Informationsdatei.
Die Übergabe lädt die vorbereiteten Pakete per FTPS und reicht ihre JCL bei JES
ein.
"""

from __future__ import annotations

import ftplib
import os
import re
import ssl
from pathlib import Path

from . import git
from .config import (
    CODEPIPELINE_STAGES,
    ISPW_INSTANZEN,
    RELEASEFREIGABE_PULL_REQUEST,
    Configuration,
    release_branches,
)
from .process import DeliveryError, NETWORK_TIMEOUT, Status
from .project_package import build_project_package, release_scope
from .release_approval import require_release_approval


# FULL- und DELTA-Pakete werden als Member in diesem Mainframe-Dataset abgelegt.
MAINFRAME_DATASET = "IEA.LOMS.TONICZ"

# Die erzeugte JCL wird an dieses JES-Ziel übergeben.
MAINFRAME_JES_TARGET = "LIT9028A"

# Prüft ein Mainframe-Subsystem anhand des Zeichenvorrats und der Feldlänge,
# die Vorlage und Zielsystem akzeptieren.
_SUBSYSTEM_RE = re.compile(r"[A-Z0-9]{2,8}")

# Prüft den erzeugten Dataset-Member nach den Namensregeln des Mainframes.
_MEMBER_RE = re.compile(r"[A-Z0-9]{1,8}")

# Prüft das CodePipeline-Assignment, bevor es in die JCL eingesetzt wird.
_ASSIGNMENT_RE = re.compile(r"[A-Z0-9]{1,12}")


def _render_jcl(
    template: str, *, ispw: str, level: str, subsystem: str, assignment: str, member: str,
) -> str:
    """Prüft die Mainframe-Werte und setzt sie in die JCL-Vorlage ein."""

    # Nur Werte einsetzen, die von der Vorlage und dem Mainframe akzeptiert werden.
    if (
        ispw not in ISPW_INSTANZEN
        or level not in CODEPIPELINE_STAGES
        or _SUBSYSTEM_RE.fullmatch(subsystem) is None
        or _ASSIGNMENT_RE.fullmatch(assignment) is None
        or _MEMBER_RE.fullmatch(member) is None
    ):
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL-Werte sind ungültig")

    # Platzhalter in der Vorlage durch die geprüften Werte ersetzen.
    values = {
        "ISPW": ispw,
        "LEVEL": level,
        "SUBSYS": subsystem,
        "ASSIGNMENT": assignment,
        "MEMBER": member,
    }
    rendered = template
    for name, value in values.items():
        rendered = rendered.replace(f"@@{name}@@", value)

    # Wenn noch @@-Platzhalter im resultierenden JCL stehen, ist die Vorlage wohl ungültig.
    if "@@" in rendered:
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL-Template ist ungültig")

    return rendered


def _submit_package(
    package_path: str | Path, jcl_path: str | Path, member: str, *, host: str, port: int, user: str,
    password: str,
) -> None:
    """Lädt ein Paket-Member per FTPS hoch und übergibt die gerenderte JCL an JES."""

    session = ftplib.FTP_TLS(context=ssl.create_default_context())
    try:
        session.connect(host, port, timeout=NETWORK_TIMEOUT)
        session.login(user, password)
        session.prot_p()
        # Passive Datenverbindungen werden vom Runner aufgebaut und benötigen
        # deshalb keine eingehende Firewall-Freischaltung auf dem Runner.
        session.set_pasv(True)

        with Path(package_path).open("rb") as package:
            session.storbinary(f"STOR '{MAINFRAME_DATASET}({member})'", package)

        session.sendcmd("SITE FILETYPE=JES")

        with Path(jcl_path).open("rb") as jcl:
            session.storlines(f"STOR {MAINFRAME_JES_TARGET}", jcl)

        session.quit()
    except ftplib.all_errors as exc:
        session.close()
        raise DeliveryError(Status.MAINFRAME_TRANSFER_FAILED, "FTPS-/JES-Übergabe fehlgeschlagen") from exc


def _publish_mainframe(*, artifact_root: str | Path) -> dict[str, object]:
    """Übergibt alle vorbereiteten Pakete und JCL-Dateien an den Mainframe."""

    root = Path(artifact_root)
    packages = sorted(root.glob("*.tgz"))
    if not packages or any(not package.with_suffix(".jcl").is_file() for package in packages):
        raise DeliveryError(Status.PACKAGE_FAILED, "Releasepakete oder JCL fehlen")

    host = os.environ["MAINFRAME_FTPS_HOST"]
    user = os.environ["MAINFRAME_FTPS_USER"]
    password = os.environ["MAINFRAME_FTPS_PASSWORD"]
    try:
        port = int(os.environ["MAINFRAME_FTPS_PORT"])
    except ValueError as exc:
        raise DeliveryError(Status.VALIDATION_FAILED, "FTPS-Port ist ungültig") from exc
    if not 1 <= port <= 65_535:
        raise DeliveryError(Status.VALIDATION_FAILED, "FTPS-Port ist ungültig")

    for package in packages:
        _submit_package(
            package,
            package.with_suffix(".jcl"),
            package.stem,
            host=host,
            port=port,
            user=user,
            password=password,
        )

    return {"status": Status.MAINFRAME_SUBMITTED.value}


# Der Paketbau wird vom gleichnamigen Workflow-Einstieg aufgerufen.
def build_release(
    configuration: Configuration,
    *, repository_root: str | Path, output_directory: str | Path, jcl_template: str, tag: str,
    trigger_sha: str,
) -> None:
    """Prüft den Release-Tag und erzeugt Pakete, JCL und Informationsdateien.

    Die Funktion bindet den Tag an einen geschützten Branch, wählt FULL- oder
    DELTA-Verarbeitung und schreibt Projektpakete, JCL und Informationsdateien.
    """

    root = Path(repository_root)

    # Release-Tag, Releaselinie und optional auslösenden Commit prüfen.
    tag_match = git.RELEASE_TAG_RE.fullmatch(tag)
    if tag_match is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "ungültiger Release-Tag")
    releaselinie = f"R{tag_match.group('releaselinie')}"
    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist unbekannt")
    allowed_branches = release_branches(configuration, releaselinie)
    target_sha = git.require_release_commit(root, tag, allowed_branches)
    if trigger_sha and trigger_sha != target_sha:
        raise DeliveryError(Status.SOURCE_FAILED, "auslösender Commit stimmt nicht zum Tag")

    # Reguläre Tags im Standardverfahren müssen den Freigabenachweis des
    # zusammengeführten Pull Requests im getaggten Stand enthalten.
    if configuration.releasefreigabe == RELEASEFREIGABE_PULL_REQUEST and not tag_match.group("beta_suffix"):
        require_release_approval(
            configuration,
            repository_root=root,
            tag=tag,
            target_sha=target_sha,
            branches=allowed_branches,
        )

    # FULL- oder DELTA-Lieferung und ihren tatsächlichen Paketvergleich bestimmen.
    base, cumulative = release_scope(root, tag, target_sha)

    # Neues Ausgabeverzeichnis anlegen.
    output = Path(output_directory)
    try:
        output.mkdir(parents=True)
    except OSError as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "Release-Ausgabeverzeichnis ist nicht neu") from exc

    # Das Hostprofil bestimmt die JCL-Werte für diese Releaselinie.
    hostprofil = configuration.hostprofile[configuration.releaselinien[releaselinie]["hostprofil"]]

    # Gemeinsame Projektpakete und die zugehörige Mainframe-JCL erzeugen.
    for project, projektcode in configuration.projects.items():
        archives = build_project_package(
            configuration,
            repository_root=root,
            output_directory=output,
            project=project,
            project_code=projektcode,
            changes=cumulative,
            base=base,
            target=(tag, target_sha),
        )
        for package_path in archives:
            member = package_path.stem
            package_path.with_suffix(".jcl").write_text(
                _render_jcl(
                    jcl_template,
                    ispw=configuration.ispw,
                    level=hostprofil["stage"],
                    subsystem=configuration.subsystem,
                    assignment=hostprofil["assignment"],
                    member=member,
                ),
                encoding="ascii",
            )
