"""Erzeugt reproduzierbare FULL- und kumulative DELTA-Lieferungen aus einem Release-Tag.

Der Releasebau prüft die Git-Quelle und verpackt jedes konfigurierte Projekt.
Zu jedem Paket entstehen die benötigte JCL und ein lesbarer Lieferbeleg.
"""

from __future__ import annotations

import gzip
import re
import shutil
import tarfile
import tempfile
from collections.abc import Iterable
from pathlib import Path

from .config import CODEPIPELINE_STAGES, ISPW_INSTANZEN, Configuration
from . import git
from .process import DeliveryError, Status


# Die Informationsdatei verlangt auch beim ersten Release eine Bezeichnung für
# den Vorgängertag, obwohl dafür kein entsprechender Git-Tag vorhanden ist.
LEGACY_PREVIOUS_TAG = "v001.100"

# Ein Tag mit der Endung `.100` bezeichnet den vollständigen Ausgangsstand einer
# Releaselinie und wählt deshalb den FULL- statt des kumulativen DELTA-Paketbaus.
FULL_SUFFIX = ".100"

# Der Dateiname des Lieferbelegs nennt Projekt, Lieferart und verglichene Tags,
# damit der Betrieb ihn dem zugehörigen Paket zuordnen kann.
INFORMATION_NAME = "_INFO_{mandant}-{project}-{delivery_type}-{tag}-{previous_tag}.txt"

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


def _normalize_tar_info(info: tarfile.TarInfo) -> tarfile.TarInfo:
    """Ersetzt Dateimetadaten aus dem Checkout durch feste Archivwerte.

    `tarfile` übernimmt sonst Änderungszeiten, Besitzer und Rechte vom
    Runner-Dateisystem. Feste Werte sorgen dafür, dass derselbe Repositorystand
    bei jedem Lauf dasselbe Paket ergibt.
    """

    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o755 if info.isdir() else 0o644
    return info


def _write_archive(archive_path: Path, entries: Iterable[tuple[Path, str]]) -> list[str]:
    """Schreibt vorbereitete Einträge in ein reproduzierbares gzip-komprimiertes TAR-Archiv.

    Der Aufrufer bestimmt die Reihenfolge der Einträge. TAR-Metadaten werden
    über `_normalize_tar_info` und der gzip-Zeitstempel auf null gesetzt, damit
    dieselben Dateiinhalte immer dieselben Bytes erzeugen. Die zurückgegebenen
    Namen erscheinen anschließend im Lieferbeleg.
    """

    try:
        with (
            archive_path.open("wb") as raw,
            gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped,
            tarfile.open(fileobj=zipped, mode="w", format=tarfile.GNU_FORMAT) as archive,
        ):
            for source, name in entries:
                archive.add(source, arcname=name, recursive=True, filter=_normalize_tar_info)
            names = archive.getnames()
    except (OSError, tarfile.TarError) as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "Releasearchiv kann nicht erzeugt werden") from exc

    return names


def _delta_archive(
    archive_path: Path, repository_root: Path, project: str, included: list[str], deleted: list[str],
    deletion_name: str,
) -> list[str]:
    """Bereitet geänderte Dateien und Löschliste für ein DELTA-Archiv vor.

    Ein temporärer Verzeichnisbaum bildet die repositoryrelativen Pfade ab.
    Das erzeugte Archiv kann dadurch ohne nachträgliche Rekonstruktion der
    Verzeichnisangaben eingespielt werden.
    """

    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        (staging / project).mkdir(parents=True)
        for relative in included:
            source = repository_root / relative
            if not source.is_file():
                raise DeliveryError(Status.PACKAGE_FAILED, "DELTA-Datei fehlt")
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        (staging / deletion_name).write_text("".join(f"{path}\n" for path in deleted), encoding="utf-8")
        entries = [(item, item.name) for item in sorted(staging.iterdir())]
        return _write_archive(archive_path, entries)


def _build_project_packages(
    configuration: Configuration, *, repository_root: Path, output: Path, project: str, projektcode: str,
    delivery_type: str, cumulative_changes: Iterable[git.GitChange],
) -> tuple[list[Path], list[str]]:
    """Erzeugt die für ein konfiguriertes Projekt benötigten Paketdateien.

    FULL-Lieferungen enthalten das vollständige Projekt und ein leeres
    DELTA-Paket. DELTA-Lieferungen enthalten die geänderten Dateien und eine aus
    dem kumulativen Git-Diff abgeleitete Löschliste.
    """

    package_prefix = f"{configuration.kuerzel}{projektcode}"
    delivery_code = "F" if delivery_type == "FULL" else "D"
    archive_path = output / f"{package_prefix}{delivery_code}.tgz"
    deletion_name = f"{package_prefix}D.txt"
    if delivery_type == "FULL":
        archive_names = _write_archive(archive_path, [(repository_root / project, f"./{project}")])
        delta_path = output / f"{package_prefix}D.tgz"
        # Die Mainframe-Übergabe erwartet neben jedem FULL-Paket einen
        # DELTA-Member, auch wenn dieser keine Änderungen oder Löschungen enthält.
        _delta_archive(delta_path, repository_root, project, [], [], deletion_name)
        return [archive_path, delta_path], archive_names

    included: set[str] = set()
    deleted: set[str] = set()
    for status, path in git.project_changes(cumulative_changes, project):
        if status in {"A", "M", "T"}:
            included.add(path)
        elif status == "D":
            deleted.add(path)
    archive_names = _delta_archive(
        archive_path, repository_root, project, sorted(included), sorted(deleted), deletion_name,
    )
    return [archive_path], archive_names


def _write_information(
    path: Path, *, mandant: str, project: str, delivery_type: str, tag: str, previous: str,
    git_changes: Iterable[tuple[str, str]], archive_names: Iterable[str],
) -> None:
    """Schreibt den lesbaren Lieferbeleg zu einem Projektpaket.

    Er dokumentiert die direkten Git-Änderungen seit dem vorigen Release und die
    Einträge des Archivs. Der Paketinhalt kann dadurch geprüft werden, ohne das
    Archiv zu entpacken.
    """

    diff_lines = "\n".join(
        f"{status}       VORRELEASE/{changed_path}"
        for status, changed_path in git_changes
    )
    archive_lines = "\n".join(archive_names)
    path.write_text(
        (
            f"Subject: Bereitstellung {mandant} - {project} - {delivery_type} - Release {tag}\n"
            "\n"
            f"Folgende DIFFs wurden beim Vergleich zwischen {previous} und {tag} "
            f"fuer Mandant {mandant} und das Projekt {project} in der Lieferung "
            f"vom Typ {delivery_type} erkannt:\n"
            "\n"
            f"{diff_lines}\n"
            "\n"
            "\n"
            f"Folgender Inhalt ist im TAR-Archiv fuer Mandant {mandant} und das "
            f"Projekt {project} in der Lieferung vom Typ {delivery_type} enthalten:\n"
            "\n"
            f"{archive_lines}\n"
        ),
        encoding="utf-8",
    )


# Hauptfunktion des Moduls, wird von `build_release.py` aufgerufen.
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
    releaselinie = f"R{tag_match.group(1)}"
    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist unbekannt")
    allowed_branches = (
        ("main", f"release/{releaselinie}")
        if configuration.releaselinie == releaselinie
        else (f"release/{releaselinie}",)
    )
    target_sha = git.require_release_commit(root, tag, allowed_branches)
    if trigger_sha and trigger_sha != target_sha:
        raise DeliveryError(Status.SOURCE_FAILED, "auslösender Commit stimmt nicht zum Tag")

    # FULL- oder DELTA-Lieferung und die zugehörigen Git-Vergleiche bestimmen.
    delivery_type = "FULL" if tag.endswith(FULL_SUFFIX) else "DELTA"
    base = f"v{tag_match.group(1)}{FULL_SUFFIX}" if delivery_type == "DELTA" else None
    base_sha = git.resolve(root, f"refs/tags/{base}") if base else None
    if base_sha:
        git.require_ancestor(root, base_sha, target_sha)
    previous = git.previous_tag(root, tag)
    previous_sha = git.resolve(root, f"refs/tags/{previous}") if previous else None
    cumulative = git.changes(root, base_sha, target_sha) if base_sha else []
    direct = git.changes(root, previous_sha, target_sha) if previous_sha else []

    # Neues Ausgabeverzeichnis anlegen.
    output = Path(output_directory)
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "Release-Ausgabeverzeichnis ist nicht neu") from exc

    # Das Hostprofil bestimmt die JCL-Werte für diese Releaselinie.
    hostprofil = configuration.hostprofile[configuration.releaselinien[releaselinie]["hostprofil"]]

    # Projektpakete, zugehörige JCL und Lieferbelege erzeugen.
    previous_label = previous or LEGACY_PREVIOUS_TAG
    for project, projektcode in configuration.projects.items():
        direct_project_changes = list(git.project_changes(direct, project))
        packages, archive_names = _build_project_packages(
            configuration,
            repository_root=root,
            output=output,
            project=project,
            projektcode=projektcode,
            delivery_type=delivery_type,
            cumulative_changes=cumulative,
        )

        information_path = output / INFORMATION_NAME.format(
            mandant=configuration.kuerzel,
            project=project,
            delivery_type=delivery_type,
            tag=tag,
            previous_tag=previous_label,
        )
        _write_information(
            information_path,
            mandant=configuration.kuerzel,
            project=project,
            delivery_type=delivery_type,
            tag=tag,
            previous=previous_label,
            git_changes=direct_project_changes,
            archive_names=archive_names,
        )
        for package_path in packages:
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
