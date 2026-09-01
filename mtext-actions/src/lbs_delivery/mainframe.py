"""Erzeugt und übergibt FULL- und DELTA-Lieferungen an den Mainframe.

Der Releasebau prüft die Git-Quelle und erstellt die Archive,
JSON-Informationsdateien und JCL. Die Übergabe lädt die Archive per FTPS und
reicht ihre JCL bei JES ein.
"""

from __future__ import annotations

import ftplib
import os
import re
import ssl
from pathlib import Path

from . import config, git
from .config import Configuration, mandant_source
from .process import DeliveryError, NETWORK_TIMEOUT, Status
from .project_archives import build_project_archives, release_scope


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

    # nur Werte einsetzen, die von Vorlage und Mainframe akzeptiert werden
    if (
        _SUBSYSTEM_RE.fullmatch(subsystem) is None
        or _ASSIGNMENT_RE.fullmatch(assignment) is None
        or _MEMBER_RE.fullmatch(member) is None
    ):
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL-Werte sind ungültig")

    # geprüfte Werte in die JCL-Vorlage einsetzen
    rendered = (
        template.replace("@@ISPW@@", ispw)
        .replace("@@LEVEL@@", level)
        .replace("@@SUBSYS@@", subsystem)
        .replace("@@ASSIGNMENT@@", assignment)
        .replace("@@MEMBER@@", member)
    )

    # nicht ersetzte Platzhalter als fehlerhafte Vorlage melden
    if "@@" in rendered:
        raise DeliveryError(Status.VALIDATION_FAILED, "JCL-Template ist ungültig")

    return rendered


def _submit_archive(archive_path: Path) -> None:
    """Lädt ein Archiv-Member per FTPS hoch und übergibt die gerenderte JCL an JES."""

    # Archivname bestimmt Mainframe-Member und zugehörige JCL-Datei
    member = archive_path.stem
    jcl_path = archive_path.with_suffix(_MAINFRAME_JCL_SUFFIX)

    # Passwort als einziges geheimes Zugangsdokument aus der Umgebung lesen
    password = os.environ["MAINFRAME_FTPS_PASSWORD"]
    session = ftplib.FTP_TLS(context=ssl.create_default_context())
    try:
        # FTPS-Sitzung anmelden und auch die Datenverbindung verschlüsseln
        session.connect(_MAINFRAME_FTPS_HOST, _MAINFRAME_FTPS_PORT, timeout=NETWORK_TIMEOUT)
        session.login(_MAINFRAME_FTPS_USER, password)
        session.prot_p()

        # passive Datenverbindungen werden vom Runner aufgebaut und benötigen
        # deshalb keine eingehende Firewall-Freischaltung auf dem Runner.
        session.set_pasv(True)

        # Archiv als Member in das gemeinsame Mainframe-Dataset übertragen
        with archive_path.open("rb") as archive:
            session.storbinary(f"STOR '{_MAINFRAME_DATASET}({member})'", archive)

        # Sitzung auf JES umstellen und die zum Member gerenderte JCL einreichen
        session.sendcmd("SITE FILETYPE=JES")

        with jcl_path.open("rb") as jcl:
            session.storlines(f"STOR {_MAINFRAME_JES_TARGET}", jcl)

        # erfolgreiche Sitzung geordnet beenden
        session.quit()
    except ftplib.all_errors as exc:
        session.close()
        raise DeliveryError(Status.MAINFRAME_TRANSFER_FAILED, f"FTPS-/JES-Übergabe fehlgeschlagen: {exc}") from exc


def _submit_mainframe_files(*, release_directory: Path) -> dict[str, object]:
    """Übergibt alle vorbereiteten Archive und JCL-Dateien an den Mainframe."""

    # vollständige Paare aus Archiv und JCL im Release-Verzeichnis voraussetzen
    archives = sorted(release_directory.glob("*.tgz"))
    if not archives or any(not e.with_suffix(_MAINFRAME_JCL_SUFFIX).is_file() for e in archives):
        raise DeliveryError(Status.PACKAGE_FAILED, "Archive oder JCL fehlen")

    # jedes Archiv zusammen mit seiner JCL an den Mainframe übergeben
    for archive in archives:
        _submit_archive(archive)

    return {"status": Status.MAINFRAME_SUBMITTED.value}


def _build_mainframe_files(configuration: Configuration, *, output_directory: Path, tag: str) -> None:
    """Erzeugt Archive, Informationsdateien und JCL für den Liefer-Tag."""

    # Liefer-Tag in Releaselinie und gemeinsamen Git-Scope auflösen
    repository_root = mandant_source()
    tag_match = git.LIEFER_TAG_RE.fullmatch(tag)
    releaselinie = tag_match.group("releaselinie")
    scope = release_scope(repository_root, tag, git.resolve(repository_root, f"refs/tags/{tag}"))

    # Hostprofil und JCL-Vorlage für diese Releaselinie laden
    hostprofil = configuration.hostprofile[configuration.releaselinien[releaselinie]["hostprofil"]]
    try:
        jcl_template = _MAINFRAME_JCL_TEMPLATE.read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, f"JCL-Template kann nicht gelesen werden: {exc}") from exc

    # Archive, Informationsdateien und zugehörige Mainframe-JCL je Projekt erzeugen
    for project in configuration.projects:
        project_archives = build_project_archives(
            configuration,
            repository_root,
            project,
            scope,
            output_directory,
        )

        for archive_path in (project_archives.f_archiv, project_archives.d_archiv):
            if archive_path is None:
                continue

            # Archivname und Hostprofil in eine eigene JCL-Datei einsetzen
            member = archive_path.stem
            rendered = _render_jcl(
                jcl_template,
                ispw=configuration.ispw,
                level=hostprofil["stage"],
                subsystem=configuration.subsystem,
                assignment=hostprofil["assignment"],
                member=member,
            )
            try:
                archive_path.with_suffix(_MAINFRAME_JCL_SUFFIX).write_text(rendered, encoding="ascii")
            except OSError as exc:
                raise DeliveryError(Status.PACKAGE_FAILED, f"JCL kann nicht geschrieben werden: {exc}") from exc


def run(subcommand: str, tag: str | None = None) -> dict[str, object]:
    """Erzeugt Release-Dateien oder übergibt sie an den Mainframe."""

    # Build erzeugt die von den folgenden Workflow-Schritten verwendeten Dateien
    if subcommand == "build":
        configuration = Configuration.load(mandant_source(), os.environ["GITHUB_REPOSITORY"])
        _build_mainframe_files(
            configuration,
            output_directory=Path(os.environ["RUNNER_TEMP"]) / "dist",
            tag=tag,
        )

        return {"status": Status.ARTIFACT_READY.value} | (
            {"warnungen": list(configuration.warnungen)} if configuration.warnungen else {}
        )

    # Mainframe-Schritt übergibt das zuvor heruntergeladene Release-Verzeichnis
    return _submit_mainframe_files(release_directory=Path(os.environ["RUNNER_TEMP"]) / "release")
