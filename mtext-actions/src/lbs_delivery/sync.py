"""Synchronisiert einen geprüften Repositorystand mit den externen M/Text-Systemen.

Der Ablauf bereitet einen vollständigen oder inkrementellen Ressourcenstand vor,
aktualisiert das zugehörige serverSync-Ziel und ruft den zur Releaselinie und
Umgebung des Quellbranches gehörenden Adapter auf.
"""

from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .process import DeliveryError, Status
from .config import Configuration
from .git import changes, project_changes, require_ancestor, resolve, resolve_sync_branch


# Zuordnung der M/Text-Synchronisationsumgebungen zu den Endungen für ihr
# serverSync-Verzeichnis und ihren Adapterhost.
SYNC_STAGES = {"Entwicklung": ("E", "e"), "Abnahme": ("A", "a")}

# Begrenzung der Antwortgröße des Adapters in Bytes.
ADAPTER_RESPONSE_LIMIT = 1024 * 1024  # 1 MB

# Wartezeit pro Adapteraufruf. Der Wert soll den Workflow nicht länger blockieren
# als für die FI üblich nötig.
ADAPTER_TIMEOUT = 30.0

# URL-Muster des vMtext-Synchronisationsadapters. ETAPS-Linie und Host-Suffix
# stammen aus Releaselinien-Konfiguration bzw. SYNC_STAGES.
ADAPTER_SYNC_URL = "https://{etaps_linie}{host_suffix}.ltoma.intern/vMtextAdapter/sync"

# Dieses Unterverzeichnis hält je Mandant den Commit des von LTOMA angenommenen
# serverSync-Stands fest. Es liegt außerhalb der M/Text-Projektverzeichnisse.
SYNC_MARKER_DIRECTORY = ".mtext-sync"


def publish_full_server_sync(staging_root: str | Path, target_root: str | Path) -> None:
    """Wechselt vollständig vorbereitete Projekte atomar unter serverSync ein.

    Die getrennte Funktion bildet die I/O-Grenze der Wiederherstellung ab. Jeder
    Projektstand wird neben dem Ziel aufgebaut und bei einem Fehler zurückgerollt.
    """

    staging = Path(staging_root)
    target = Path(target_root)
    try:
        target.mkdir(parents=True, exist_ok=True)
        projects = sorted(path for path in staging.iterdir() if path.is_dir())
        for project in projects:
            destination = target / project.name
            temporary = target / f".{project.name}.new-{uuid.uuid4().hex}"
            backup = target / f".{project.name}.old-{uuid.uuid4().hex}"

            # Neuen Stand neben das bisherige Ziel legen.
            shutil.copytree(project, temporary, copy_function=shutil.copy2)

            # Bisheriges Ziel zur Sicherung beiseite schieben.
            if destination.exists():
                os.replace(destination, backup)

            # Atomar einwechseln; bei Fehler die Sicherung zurücklegen.
            try:
                os.replace(temporary, destination)
            except OSError:
                if backup.exists():
                    os.replace(backup, destination)
                raise

            # Sicherung nach erfolgreichem Wechsel entfernen.
            if backup.exists():
                shutil.rmtree(backup)
    except (OSError, shutil.Error) as exc:
        raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "serverSync-Veröffentlichung fehlgeschlagen") from exc


def apply_server_sync_changes(
    staging_root: str | Path,
    target_root: str | Path,
    operations: list[tuple[str, str]],
) -> None:
    """Wendet vorbereitete Dateioperationen auf den dauerhaften serverSync-Stand an.

    Diese I/O-Grenze überträgt bei normalen Läufen ausschließlich geänderte
    Ressourcen. Löschungen räumen anschließend leer gewordene Unterverzeichnisse auf.
    """

    staging = Path(staging_root)
    target = Path(target_root)
    try:
        target.mkdir(parents=True, exist_ok=True)
        for status, relative in operations:
            path = Path(relative)
            destination = target / path
            if status == "D":
                if destination.is_file() or destination.is_symlink():
                    destination.unlink()
                parent = destination.parent
                project_root = target / path.parts[0]
                while parent != project_root and parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
                continue

            source = staging / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    except (OSError, shutil.Error) as exc:
        raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "serverSync-Veröffentlichung fehlgeschlagen") from exc


def call_adapter(url: str, *, timeout: float) -> tuple[int, str]:
    """Ruft die POST-Synchronisation auf und übersetzt Transportfehler.

    Antworttexte werden begrenzt. Nur erfolgreiche HTTP-Statuscodes bestätigen,
    dass LTOMA den unmittelbar ausgelösten Auftrag angenommen hat.
    """

    request = urllib.request.Request(
        url,
        data=json.dumps({"mandant": "MAN", "institut": "INR"}, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            body = response.read(ADAPTER_RESPONSE_LIMIT).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read(ADAPTER_RESPONSE_LIMIT).decode("utf-8", errors="replace")
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP {exc.code}: {body[:1000]}") from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapter-Transport fehlgeschlagen") from exc
    if not 200 <= status < 300:
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP {status}: {body[:1000]}")
    return status, body


def sync_resources(
    configuration: Configuration,
    *, repository_root: str | Path, commit: str, source_branch: str, staging_root: str | Path,
    full_sync: bool = False, server_sync_root: str | Path | None = None,
) -> dict[str, object]:
    """Prüft den Quellstand und synchronisiert ihn mit dem zugehörigen M/Text-Ziel.

    Feature-Branches führen nach Entwicklung, geschützte Zielbranches nach
    Abnahme. Ein vorhandener erfolgreicher Commit begrenzt die Übertragung auf
    die seitdem geänderten Ressourcen. Der erste oder ausdrücklich vollständige
    Lauf ersetzt die Projektstände vollständig.
    """

    # Quellbranch, Releaselinie und Commit-Zugehörigkeit prüfen.
    releaselinie, is_feature = resolve_sync_branch(source_branch, configuration.releaselinie)
    environment = "Entwicklung" if is_feature else "Abnahme"
    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist unbekannt")
    if resolve(repository_root, "HEAD") != commit:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum Commit")
    require_ancestor(repository_root, commit, f"refs/remotes/origin/{source_branch}")

    # Zielpfad und letzter von LTOMA angenommener Mandantenstand bestimmen.
    etaps_linie = configuration.releaselinien[releaselinie]["etaps_linie"]
    path_suffix, host_suffix = SYNC_STAGES[environment]
    target_root = Path(server_sync_root or f"/nfs/mtext/{etaps_linie}{path_suffix}/serverSync")
    marker_path = target_root / SYNC_MARKER_DIRECTORY / f"{configuration.kuerzel}.json"
    incremental_sync = marker_path.exists() and not full_sync
    operations: list[tuple[str, str]] = []
    if incremental_sync:
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            previous_commit = marker["commit"]
            if marker["repository"] != configuration.repository or not isinstance(previous_commit, str):
                raise ValueError
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise DeliveryError(
                Status.RESOURCE_TRANSFER_FAILED,
                "serverSync-Synchronisationsstand ist ungültig",
            ) from exc
        git_changes = changes(repository_root, previous_commit, commit)
        operations = [
            operation
            for project in configuration.projects
            for operation in project_changes(git_changes, project)
        ]

    # Vollstände enthalten alle Projekte. Normale Läufe bereiten nur Dateien vor,
    # die nach der zentralen Git-Projektion hinzugefügt oder geändert werden.
    source_root = Path(repository_root)
    staging = Path(staging_root)
    try:
        staging.mkdir(parents=True, exist_ok=False)
        if not incremental_sync:
            for project in configuration.projects:
                shutil.copytree(source_root / project, staging / project, copy_function=shutil.copy2)
        else:
            for status_value, relative in operations:
                if status_value == "D":
                    continue
                source = source_root / relative
                if not source.is_file():
                    raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "geänderte Ressource fehlt")
                destination = staging / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    except (OSError, shutil.Error) as exc:
        raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "Ressourcen-Staging fehlgeschlagen") from exc

    # Projektstand veröffentlichen und den passenden Adapter aufrufen.
    if incremental_sync:
        apply_server_sync_changes(staging_root, target_root, operations)
    else:
        publish_full_server_sync(staging_root, target_root)
    adapter_url = ADAPTER_SYNC_URL.format(etaps_linie=etaps_linie, host_suffix=host_suffix)
    status, body = call_adapter(adapter_url, timeout=ADAPTER_TIMEOUT)

    # Erst die erfolgreiche Annahme durch LTOMA schreibt den Vergleichsstand fort.
    try:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_marker = marker_path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        temporary_marker.write_text(
            json.dumps({"repository": configuration.repository, "commit": commit}, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary_marker, marker_path)
    except OSError as exc:
        raise DeliveryError(
            Status.RESOURCE_TRANSFER_FAILED,
            "Synchronisationsstand kann nicht gespeichert werden",
        ) from exc
    return {"status": Status.ADAPTER_ACCEPTED.value, "http_status": status, "response_body": body}
