"""Erzeugt und übergibt FULL- und DELTA-Lieferungen an den Mainframe.

Der Paketbau prüft die Git-Quelle und erstellt Archive und JCL. Die Übergabe
lädt die Archive per FTPS, reicht ihre JCL bei JES ein oder endet im Dry Run
nach der Dateiprüfung.
"""

from __future__ import annotations

import ftplib
import os
import re
import ssl
from pathlib import Path

from . import config, git
from .process import DeliveryError, NETWORK_TIMEOUT, Status
from .project_packages import (
    build_delta_archive,
    build_project_archive,
    project_archive_path,
    lieferumfang,
)


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

# Dateierweiterung der JCL-Datei zum jeweiligen Archiv-Member im Lieferartefakt.
_MAINFRAME_JCL_SUFFIX = ".jcl"

# Vorlage für die JCL-Übergabe eines Archiv-Members an JES.
_MAINFRAME_JCL_TEMPLATE = config.ACTION_ROOT / "templates/mainframe-upload.jcl"

# Reguläre Ausdrücke
_SUBSYSTEM_RE = re.compile(r"[A-Z0-9]{2,8}")
_MEMBER_RE = re.compile(r"[A-Z0-9]{1,8}")
_ASSIGNMENT_RE = re.compile(r"[A-Z0-9]{1,12}")


def _render_jcl(template: str, ispw: str, level: str, subsystem: str, assignment: str, member: str) -> str:
    """Prüft die Mainframe-Werte und setzt sie in die JCL-Vorlage ein."""

    # nur Werte einsetzen, die von Vorlage und Mainframe akzeptiert werden
    for value, pattern in (
        (subsystem, _SUBSYSTEM_RE),
        (assignment, _ASSIGNMENT_RE),
        (member, _MEMBER_RE),
    ):
        if pattern.fullmatch(value) is None:
            raise DeliveryError(Status.VALIDATION_FAILED, "JCL-Werte sind ungültig")

    # geprüfte Werte in die JCL-Vorlage einsetzen
    rendered = (
        template.replace("@@ISPW@@", ispw)
        .replace("@@LEVEL@@", level)
        .replace("@@SUBSYS@@", subsystem)
        .replace("@@ASSIGNMENT@@", assignment)
        .replace("@@MEMBER@@", member)
    )

    return rendered


def _submit_archive(archive_path: Path) -> None:
    """Lädt ein Archiv-Member per FTPS hoch und übergibt die gerenderte JCL an JES."""

    member = archive_path.stem
    jcl_path = archive_path.with_suffix(_MAINFRAME_JCL_SUFFIX)

    # IZE9 ohne Prüfung des Serverzertifikats über TLS erreichen
    password = os.environ["IZE9_FTPS_PASSWORD_MTEXT"]
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    session = ftplib.FTP_TLS(context=context)
    try:
        session.connect(_MAINFRAME_FTPS_HOST, _MAINFRAME_FTPS_PORT, timeout=NETWORK_TIMEOUT)
        session.login(_MAINFRAME_FTPS_USER, password)
        session.prot_p()
        session.set_pasv(True)

        # Archiv als Member in das Mainframe-Dataset übertragen
        with archive_path.open("rb") as archive:
            session.storbinary(f"STOR '{_MAINFRAME_DATASET}({member})'", archive)

        # Sitzung auf JES umstellen und die zum Member gerenderte JCL einreichen
        session.sendcmd("SITE FILETYPE=JES")

        with jcl_path.open("rb") as jcl:
            session.storlines(f"STOR {_MAINFRAME_JES_TARGET}", jcl)

        # FTPS-Sitzung beenden
        session.quit()

    except ftplib.all_errors as exc:
        session.close()
        raise DeliveryError(Status.MAINFRAME_TRANSFER_FAILED, f"FTPS-/JES-Übergabe fehlgeschlagen: {exc}") from exc


def _submit_mainframe_files(*, lieferung_directory: Path, dry_run: bool) -> dict[str, object]:
    """Übergibt alle vorbereiteten Archive und JCL-Dateien an den Mainframe."""

    # vollständige Paare aus Archiv und JCL im Release-Verzeichnis voraussetzen
    archives = sorted(lieferung_directory.glob("*.tgz"))
    if not archives:
        raise DeliveryError(Status.PACKAGE_FAILED, "Archive fehlen")
    for archive in archives:
        jcl = archive.with_suffix(_MAINFRAME_JCL_SUFFIX)
        if not jcl.is_file():
            raise DeliveryError(Status.PACKAGE_FAILED, f"JCL fehlt: {jcl.name}")

    # ein Dry Run endet hier, ohne FTPS- und JES-Übergabe
    if dry_run:
        return {"status": Status.MAINFRAME_SKIPPED}

    # zuerst alle F-Archive übertragen, danach die D-Archive ersetzen
    for archive in archives:
        if archive.stem.endswith("F"):
            _submit_archive(archive)
    for archive in archives:
        if archive.stem.endswith("D"):
            _submit_archive(archive)

    return {"status": Status.MAINFRAME_SUBMITTED}


def _build_mainframe_files(configuration: config.Configuration, *, output_directory: Path, tag: git.LieferTag) -> None:
    """Erzeugt Archive und JCL für den Liefer-Tag."""

    # Paketumfang aus dem vorbereiteten Commit ableiten
    repository_root = config.mandant_source()
    scope = lieferumfang(repository_root, tag, git.resolve(repository_root, "HEAD"))

    # Hostprofil und JCL-Vorlage für diese Releaselinie laden
    host_profile = configuration.hostprofile[configuration.releaselinien[tag.releaselinie]["hostprofil"]]
    try:
        jcl_template = _MAINFRAME_JCL_TEMPLATE.read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, f"JCL-Template kann nicht gelesen werden: {exc}") from exc

    # Projektarchive erstellen und je Archiv-Member eine JCL-Datei generieren
    for project in configuration.projects:
        archive = build_project_archive(configuration, repository_root, project, output_directory, scope)

        # leeres D-Archiv verhindert, dass der Folgejob ein früheres DELTA einspielt
        archive_paths = [archive]
        if scope.von is None:
            delta_archive = project_archive_path(configuration, project, output_directory, "D")
            build_delta_archive(repository_root, project, delta_archive, [])
            archive_paths.append(delta_archive)

        for archive_path in archive_paths:
            # Archivname und Hostprofil in eine JCL-Datei rendern
            member = archive_path.stem
            rendered = _render_jcl(jcl_template, configuration.ispw, host_profile["stage"], configuration.subsystem, host_profile["assignment"], member)

            try:
                # JCL-Datei für das Archiv-Member erstellen
                archive_path.with_suffix(_MAINFRAME_JCL_SUFFIX).write_text(rendered, encoding="ascii")
            except OSError as exc:
                raise DeliveryError(Status.PACKAGE_FAILED, f"JCL kann nicht geschrieben werden: {exc}") from exc


def run(subcommand: str, tag: str | None = None) -> dict[str, object]:
    """Erzeugt Lieferdateien oder übergibt sie an den Mainframe."""

    # Build-Schritt erzeugt die Lieferdateien
    if subcommand == "build":
        try:
            tag = git.LieferTag.parse(tag)
        except ValueError as exc:
            raise DeliveryError(Status.VALIDATION_FAILED, str(exc)) from exc

        configuration = config.Configuration.load(config.mandant_source(), os.environ["GITHUB_REPOSITORY"])
        _build_mainframe_files(configuration, output_directory=Path(os.environ["RUNNER_TEMP"]) / "dist", tag=tag)

        return {
            "status": Status.ARTIFACT_READY,
            "outputs": {"dry_run": str(configuration.dry_run).lower()},
        }

    # Mainframe-Schritt übergibt das zuvor heruntergeladene Release-Verzeichnis
    if subcommand == "mainframe":
        return _submit_mainframe_files(
            lieferung_directory=Path(os.environ["RUNNER_TEMP"]) / "release",
            dry_run=os.environ.get("DRY_RUN") == "true",
        )

    raise DeliveryError(Status.VALIDATION_FAILED, "unbekannter Lieferbefehl")
