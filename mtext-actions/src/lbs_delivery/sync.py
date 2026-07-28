"""Synchronisiert einen geprüften Repositorystand mit den externen M/Text-Systemen.

Der Ablauf stellt die Projektverzeichnisse bereit, ersetzt ihre serverSync-Ziele
mit Rückfallmöglichkeit und ruft den zur Releaselinie und Umgebung des
Quellbranches gehörenden Adapter auf.
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
from .git import require_ancestor, resolve


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


def publish_server_sync(staging_root: str | Path, target_root: str | Path) -> None:
    """Ersetzt bereitgestellte Projekte unter serverSync mit Rückfallmöglichkeit.

    Jeder neue Verzeichnisbaum wird neben sein Ziel kopiert und anschließend
    eingewechselt. Scheitert dieser Wechsel nach dem Verschieben des alten
    Verzeichnisses, wird dessen Sicherung vor der Fehlermeldung wiederhergestellt.
    """

    staging = Path(staging_root)
    target = Path(target_root)
    try:
        target.mkdir(parents=True, exist_ok=True)

        # Jedes gestagte Projekt einzeln atomar unter serverSync einwechseln.
        for project in sorted(path for path in staging.iterdir() if path.is_dir()):
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


def _send_adapter_request(request: urllib.request.Request, *, timeout: float) -> tuple[int, str]:
    """Führt einen vorbereiteten Adapteraufruf aus und wertet seine Antwort aus.

    Die gemeinsame HTTP-Grenze begrenzt Antworttexte und übersetzt
    Transportfehler sowie nicht erfolgreiche Statuscodes in das
    Lieferfehlermodell.
    """

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


def call_adapter(url: str, *, timeout: float) -> tuple[int, str]:
    """Ruft die bestehende POST-Synchronisation des M/Text-Adapters auf."""

    request = urllib.request.Request(
        url,
        data=json.dumps({"mandant": "MAN", "institut": "INR"}, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _send_adapter_request(request, timeout=timeout)


def put_server_sync(package_path: str | Path, url: str, *, timeout: float) -> tuple[int, str]:
    """Dient als Vorlage für einen späteren PUT-Transportweg.

    Die Funktion ist nicht an `sync_resources` angebunden. Sie liest ein
    vorbereitetes ZIP-Transportpaket und baut den PUT-Aufruf auf.
    """

    try:
        package = Path(package_path).read_bytes()
    except OSError as exc:
        raise DeliveryError(
            Status.RESOURCE_TRANSFER_FAILED,
            "ZIP-Transportpaket konnte nicht gelesen werden",
        ) from exc

    request = urllib.request.Request(
        url,
        data=package,
        headers={"Content-Type": "application/zip"},
        method="PUT",
    )
    return _send_adapter_request(request, timeout=timeout)


def sync_resources(
    configuration: Configuration,
    *, repository_root: str | Path, commit: str, source_branch: str, staging_root: str | Path,
) -> dict[str, object]:
    """Prüft den angeforderten Quellstand und führt die vollständige Synchronisation aus.

    Die Branchstruktur bestimmt eine konfigurierte Releaselinie und Umgebung.
    Erst nach dem Nachweis der Branch-Zugehörigkeit werden die Projektverzeichnisse
    bereitgestellt, veröffentlicht und dem zugehörigen Adapter gemeldet.
    """

    # Quellbranch, Releaselinie und Commit-Zugehörigkeit prüfen.
    releaselinie, _, environment = source_branch.partition("/")
    if environment not in SYNC_STAGES:
        raise DeliveryError(Status.VALIDATION_FAILED, "Zielumgebung ist ungültig")
    if source_branch != f"{releaselinie}/{environment}":
        raise DeliveryError(Status.VALIDATION_FAILED, "Branch passt nicht zur Zielumgebung")
    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist unbekannt")
    if resolve(repository_root, "HEAD") != commit:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum Commit")
    require_ancestor(repository_root, commit, f"refs/remotes/origin/{source_branch}")

    # Konfigurierte Projekte in ein separates Staging-Verzeichnis kopieren.
    source_root = Path(repository_root)
    staging = Path(staging_root)
    try:
        staging.mkdir(parents=True, exist_ok=False)
        for project in configuration.projects:
            shutil.copytree(source_root / project, staging / project, copy_function=shutil.copy2)
    except (OSError, shutil.Error) as exc:
        raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "Ressourcen-Staging fehlgeschlagen") from exc

    # Gestagte Projekte veröffentlichen und den passenden Adapter aufrufen.
    etaps_linie = configuration.releaselinien[releaselinie]["etaps_linie"]
    path_suffix, host_suffix = SYNC_STAGES[environment]
    publish_server_sync(staging_root, f"/nfs/mtext/{etaps_linie}{path_suffix}/serverSync")
    adapter_url = ADAPTER_SYNC_URL.format(etaps_linie=etaps_linie, host_suffix=host_suffix)
    status, body = call_adapter(adapter_url, timeout=ADAPTER_TIMEOUT)
    return {"status": Status.ADAPTER_ACCEPTED.value, "http_status": status, "response_body": body}
