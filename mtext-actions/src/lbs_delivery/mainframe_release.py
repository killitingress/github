"""Erzeugt und übergibt FULL- und DELTA-Lieferungen an den Mainframe.

Der Releasebau prüft die Git-Quelle und erstellt die Archive,
JSON-Informationsdateien und JCL. Die Übergabe lädt die Archive per FTPS und
reicht ihre JCL bei JES ein.
"""

from __future__ import annotations

import argparse
import ftplib
import os
import re
import ssl
from pathlib import Path

from . import config, git
from .config import Configuration, mandant_source
from .process import DeliveryError, NETWORK_TIMEOUT, Status
from .project_artifacts import ChangeStand, build_project_artifacts, release_scope


# F- und D-Archive werden als Member in diesem Mainframe-Dataset abgelegt.
_MAINFRAME_DATASET = "IEA.LOMS.TONICZ"

# Die erzeugte JCL wird an dieses JES-Ziel übergeben.
_MAINFRAME_JES_TARGET = "LIT9028A"

# Alle Mandanten übertragen ihre Archive an diesen zentralen Mainframe-Host.
_MAINFRAME_FTPS_HOST = "ize9.lbs-it.de"

# Explizites FTPS verwendet den FTP-Standardport des zentralen Mainframe-Zugangs.
_MAINFRAME_FTPS_PORT = 21

# Dieser technische Benutzer führt die zentrale FTPS- und JES-Übergabe aus.
_MAINFRAME_FTPS_USER = "LIT9028"

# Dateierweiterung der JCL-Datei zum jeweiligen Archiv-Member im Release-Artefakt.
_MAINFRAME_JCL_SUFFIX = ".jcl"

# Vorlage für die JCL-Übergabe eines Archiv-Members an JES.
_MAINFRAME_JCL_TEMPLATE = config.AUTOMATION_ROOT / "templates/mainframe-upload.jcl"

# Reguläre Ausdrücke
_SUBSYSTEM_RE = re.compile(r"[A-Z0-9]{2,8}")
_MEMBER_RE = re.compile(r"[A-Z0-9]{1,8}")
_ASSIGNMENT_RE = re.compile(r"[A-Z0-9]{1,12}")


def _render_jcl(template: str, *, ispw: str, level: str, subsystem: str, assignment: str, member: str) -> str:
    """Prüft die Mainframe-Werte und setzt sie in die JCL-Vorlage ein."""

    # Nur Werte einsetzen, die von der Vorlage und dem Mainframe akzeptiert werden.
    if (
        _SUBSYSTEM_RE.fullmatch(subsystem) is None
        or _ASSIGNMENT_RE.fullmatch(assignment) is None
        or _MEMBER_RE.fullmatch(member) is None
    ):
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL-Werte sind ungültig")

    # Platzhalter in der Vorlage durch die geprüften Werte ersetzen.
    rendered = (
        template.replace("@@ISPW@@", ispw)
        .replace("@@LEVEL@@", level)
        .replace("@@SUBSYS@@", subsystem)
        .replace("@@ASSIGNMENT@@", assignment)
        .replace("@@MEMBER@@", member)
    )

    # Wenn noch @@-Platzhalter im resultierenden JCL stehen, ist die Vorlage wohl ungültig.
    if "@@" in rendered:
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL-Template ist ungültig")

    return rendered


def _submit_archive(archive_path: Path) -> None:
    """Lädt ein Archiv-Member per FTPS hoch und übergibt die gerenderte JCL an JES."""

    member = archive_path.stem
    jcl_path = archive_path.with_suffix(_MAINFRAME_JCL_SUFFIX)
    # Das Passwort ist das einzige Mainframe-Zugangsdatum aus einem Secret.
    password = os.environ["MAINFRAME_FTPS_PASSWORD"]
    session = ftplib.FTP_TLS(context=ssl.create_default_context())
    try:
        session.connect(_MAINFRAME_FTPS_HOST, _MAINFRAME_FTPS_PORT, timeout=NETWORK_TIMEOUT)
        session.login(_MAINFRAME_FTPS_USER, password)
        session.prot_p()
        # Passive Datenverbindungen werden vom Runner aufgebaut und benötigen
        # deshalb keine eingehende Firewall-Freischaltung auf dem Runner.
        session.set_pasv(True)

        with archive_path.open("rb") as archive:
            session.storbinary(f"STOR '{_MAINFRAME_DATASET}({member})'", archive)

        session.sendcmd("SITE FILETYPE=JES")

        with jcl_path.open("rb") as jcl:
            session.storlines(f"STOR {_MAINFRAME_JES_TARGET}", jcl)

        session.quit()
    except ftplib.all_errors as exc:
        session.close()
        raise DeliveryError(Status.MAINFRAME_TRANSFER_FAILED, "FTPS-/JES-Übergabe fehlgeschlagen") from exc


def _publish_mainframe(*, artifact_root: Path) -> dict[str, object]:
    """Übergibt alle vorbereiteten Archive und JCL-Dateien an den Mainframe."""

    # Archive und JCL im Artefaktverzeichnis voraussetzen.
    archives = sorted(artifact_root.glob("*.tgz"))
    if not archives or any(not archive.with_suffix(_MAINFRAME_JCL_SUFFIX).is_file() for archive in archives):
        raise DeliveryError(Status.PACKAGE_FAILED, "Archive oder JCL fehlen")

    # Jedes Archiv mit seiner JCL an den Mainframe übergeben.
    for archive in archives:
        _submit_archive(archive)

    return {"status": Status.MAINFRAME_SUBMITTED.value}


# Der Releasebau wird vom gleichnamigen Workflow-Einstieg aufgerufen.
def _build_release(configuration: Configuration, *, output_directory: Path, tag: str) -> None:
    """Erzeugt Archive, Informationsdateien und JCL für den Liefer-Tag."""

    repository_root = mandant_source()
    tag_match = git.LIEFER_TAG_RE.fullmatch(tag)
    releaselinie = tag_match.group("releaselinie")
    zwischenrelease = tag_match.group("zwischenrelease")
    target_sha = git.resolve(repository_root, f"refs/tags/{tag}")

    base, cumulative = release_scope(
        repository_root,
        target_sha,
        releaselinie=releaselinie,
        zwischenrelease=zwischenrelease,
    )

    # Das Hostprofil bestimmt die JCL-Werte für diese Releaselinie.
    hostprofil = configuration.hostprofile[configuration.releaselinien[releaselinie]["hostprofil"]]
    jcl_template = _MAINFRAME_JCL_TEMPLATE.read_text(encoding="ascii")

    # Archive, Informationsdateien und die zugehörige Mainframe-JCL erzeugen.
    for project in configuration.projects:
        project_artifacts = build_project_artifacts(
            configuration,
            repository_root=repository_root,
            output_directory=output_directory,
            project=project,
            stand=ChangeStand(von=base, bis=(tag, target_sha), changes=cumulative),
            include_empty_delta=True,
        )

        for archive_path in (project_artifacts.f_archiv, project_artifacts.d_archiv):
            if archive_path is None:
                continue

            member = archive_path.stem
            archive_path.with_suffix(_MAINFRAME_JCL_SUFFIX).write_text(
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


def run(arguments: argparse.Namespace) -> dict[str, object]:
    """Erzeugt Release-Dateien oder übergibt sie an den Mainframe."""

    if arguments.release_command == "build":
        configuration = Configuration.load(mandant_source(), os.environ["GITHUB_REPOSITORY"])
        _build_release(configuration, output_directory=Path(os.environ["RUNNER_TEMP"]) / "dist", tag=arguments.tag)

        return {"status": Status.ARTIFACT_READY.value} | (
            {"warnungen": list(configuration.warnungen)} if configuration.warnungen else {}
        )

    return _publish_mainframe(artifact_root=Path(os.environ["RUNNER_TEMP"]) / "release")
