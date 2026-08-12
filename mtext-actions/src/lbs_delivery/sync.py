"""Synchronisiert einen geprüften Repositorystand mit den externen M/Text-Systemen.

Der Ablauf kopiert einen vollständigen Projektstand oder einzelne Änderungen
direkt aus dem Checkout nach serverSync. Anschließend ruft er den zur
Releaselinie und Zielstufe gehörenden Adapter auf.
"""

from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .config import Configuration
from .git import changes, project_changes, require_ancestor, resolve
from .process import DeliveryError, Status


# Begrenzung der Antwortgröße des Adapters in Bytes.
ADAPTER_RESPONSE_LIMIT = 1024 * 1024  # 1 MB

# Wartezeit pro Adapteraufruf. Der Wert soll den Workflow nicht länger blockieren
# als für die FI üblich nötig.
ADAPTER_TIMEOUT = 30.0

# URL-Muster des vMtext-Synchronisationsadapters. Die technische Umgebung wird
# aus Releaselinien-Konfiguration und Zielstufe gebildet.
ADAPTER_SYNC_URL = "https://{umgebung}.ltoma.intern/vMtextAdapter/sync"

# Dieses Unterverzeichnis hält je Mandant den Commit des von LTOMA angenommenen
# serverSync-Stands fest. Es liegt außerhalb der M/Text-Projektverzeichnisse.
SYNC_MARKER_DIRECTORY = ".mtext-sync"


def _apply_server_sync_changes(
    source_root: str | Path,
    target_root: str | Path,
    operations: list[tuple[str, str]],
) -> None:
    """Wendet die vorbereiteten Dateiänderungen idempotent auf serverSync an.

    Der Vergleichsmarker wird erst nach dem Adapteraufruf fortgeschrieben. Nach
    einem Abbruch kann dieselbe Liste deshalb erneut angewendet werden.
    """

    source = Path(source_root)
    target = Path(target_root)
    try:
        target.mkdir(parents=True, exist_ok=True)
        for status, relative in operations:
            path = Path(relative)
            destination = target / path
            if status == "D":
                if destination.is_file() or destination.is_symlink():
                    destination.unlink()
                elif destination.exists():
                    raise IsADirectoryError(destination)
                parent = destination.parent
                project_root = target / path.parts[0]
                while parent != project_root and parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
                continue

            resource = source / path
            if not resource.is_file():
                raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "geänderte Ressource fehlt")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resource, destination)
    except OSError as exc:
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
    *, repository_root: str | Path, commit: str, source_branch: str,
    releaselinie: str, zielstufe: str, vollabgleich: bool = False,
    server_sync_root: str | Path | None = None,
) -> dict[str, object]:
    """Prüft den Quellstand und synchronisiert ihn mit dem zugehörigen M/Text-Ziel.

    Releaselinie und Zielstufe wurden bereits aus dem Branch und dem
    GitHub-Ereignis abgeleitet. Ein vorhandener erfolgreicher Commit begrenzt
    normale Übertragungen auf die seitdem geänderten Ressourcen.
    """

    # Geplantes Ziel und Commit-Zugehörigkeit prüfen.
    if zielstufe not in configuration.mtext_ziel_prefixe:
        raise DeliveryError(Status.VALIDATION_FAILED, "M/Text-Zielstufe ist ungültig")
    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist unbekannt")
    if resolve(repository_root, "HEAD") != commit:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum Commit")
    require_ancestor(repository_root, commit, f"refs/remotes/origin/{source_branch}")

    # Zielpfad und letzter von LTOMA angenommener Mandantenstand bestimmen.
    etaps_linie = configuration.releaselinien[releaselinie]["etaps_linie"]
    umgebung = f"{configuration.mtext_ziel_prefixe[zielstufe]}{etaps_linie}"
    target_root = Path(server_sync_root or f"/nfs/mtext/{umgebung}/serverSync")
    marker_path = target_root / SYNC_MARKER_DIRECTORY / f"{configuration.kuerzel}.json"
    incremental_sync = marker_path.exists() and not vollabgleich
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
            for project in configuration.projects.keys()
            for operation in project_changes(git_changes, project)
        ]

    # Den vollständigen Projektstand oder die ermittelten Änderungen direkt aus
    # dem Checkout nach serverSync kopieren. Bei einem Fehler bleibt der Marker
    # unverändert, sodass derselbe Commit erneut verarbeitet werden kann.
    source = Path(repository_root)
    if incremental_sync:
        _apply_server_sync_changes(source, target_root, operations)
    else:
        try:
            target_root.mkdir(parents=True, exist_ok=True)
            for project in configuration.projects:
                destination = target_root / project
                if destination.exists():
                    shutil.rmtree(destination)
                shutil.copytree(source / project, destination, copy_function=shutil.copy2)
        except (OSError, shutil.Error) as exc:
            raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "serverSync-Veröffentlichung fehlgeschlagen") from exc

    # Nach dem aktualisierten Projektstand den passenden Adapter aufrufen.
    adapter_url = ADAPTER_SYNC_URL.format(umgebung=umgebung)
    status, body = call_adapter(adapter_url, timeout=ADAPTER_TIMEOUT)

    # Erst die erfolgreiche Annahme durch LTOMA schreibt den Vergleichsstand fort.
    try:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_marker = marker_path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        temporary_marker.write_text(
            json.dumps(
                {"repository": configuration.repository, "commit": commit},
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        os.replace(temporary_marker, marker_path)
    except OSError as exc:
        raise DeliveryError(
            Status.RESOURCE_TRANSFER_FAILED,
            "Synchronisationsstand kann nicht gespeichert werden",
        ) from exc
    return {"status": Status.ADAPTER_ACCEPTED.value, "http_status": status, "response_body": body}
