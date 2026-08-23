"""Stellt Projektpakete für den M/Text-Adapter auf CIFS bereit.

Der Workflow erzeugt je betroffenem Projekt das gemeinsame F- oder D-Paket.
Er meldet dem Adapter das vollständig geschriebene Übergabeverzeichnis. Der
Adapter übernimmt die Pakete nach `serverSync` und startet die
M/Text-Synchronisation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from . import config, git
from .process import DeliveryError, NETWORK_TIMEOUT, Status
from .project_package import build_project_package


# Vom Adapter werden höchstens 1 MB Antworttext eingelesen.
_ADAPTER_RESPONSE_LIMIT = 1024 * 1024

# URL-Muster des LTOMA-Sync-Endpunktes.
_ADAPTER_SYNC_URL = "https://{umgebung}.ltoma.intern/vMtextAdapter/sync"

# Diese Umgebungsvariable bezeichnet den auf dem Runner eingehängten
# CIFS-Basispfad für vollständige Übergabeaufträge.
_CIFS_ROOT_ENVIRONMENT = "MTEXT_CIFS_ROOT"

# GitHub liefert für den ersten Push eines Branches diese Null-SHA als Vorgänger.
_EMPTY_PUSH_COMMIT = "0" * 40


def _call_adapter(url: str, payload: dict[str, object]) -> tuple[int, str]:
    """Meldet dem Adapter ein vollständig bereitgestelltes CIFS-Verzeichnis."""

    # Antwort begrenzt einlesen. Nur HTTP 200–299 bestätigt die Annahme durch LTOMA.
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:
            status = response.status
            body = response.read(_ADAPTER_RESPONSE_LIMIT).decode(errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read(_ADAPTER_RESPONSE_LIMIT).decode(errors="replace")
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP {exc.code}: {body[:1000]}") from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapter ist nicht erreichbar") from exc

    if not 200 <= status < 300:
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP {status}: {body[:1000]}")
    return status, body


def _plan_sync(
    configuration: config.Configuration,
    *,
    repository_root: str | Path,
    source_branch: str,
    event_name: str,
    previous_commit: str,
) -> tuple[str, tuple[str, ...], str | None]:
    """Leitet Releaselinie, Zielstufen und Vergleichscommit aus dem GitHub-Ereignis ab."""

    # Branch liefert Releaselinie und die zugehörige M/Text-Zielstufe.
    releaselinie, zielstufe = git.resolve_sync_branch(source_branch, configuration.releaselinie)

    # Ein manueller Lauf gleicht den ausgewählten Commit vollständig ab.
    if event_name == "workflow_dispatch":
        return releaselinie, (zielstufe,), None

    # GitHub kennt beim ersten Push eines Feature-Branches keinen Vorgänger.
    # Der gemeinsame Commit mit seinem Zielbranch grenzt die Feature-Änderungen
    # ab, damit parallele Features nicht als FULL übertragen werden.
    if previous_commit == _EMPTY_PUSH_COMMIT and zielstufe == config.MTEXT_ZIEL_ENTWICKLUNG:
        base_branch = "main" if releaselinie == configuration.releaselinie else f"release/{releaselinie}"
        previous_commit = git.run(
            repository_root,
            "merge-base",
            "HEAD",
            f"refs/remotes/origin/{base_branch}",
        ).decode("ascii").strip()
    elif not previous_commit or previous_commit == _EMPTY_PUSH_COMMIT:
        return releaselinie, (zielstufe,), None

    if event_name != "push" or source_branch != "main":
        return releaselinie, (zielstufe,), previous_commit

    # Push auf main mit Releaselinienwechsel: alle Zielstufen als FULL abgleichen.
    # Die bisherige Mandantenkonfiguration aus dem Vorgängercommit lesen. Dadurch
    # wird für den Vergleich kein zweiter Checkout benötigt.
    previous_configuration = git.run(
        repository_root,
        "show",
        f"{git.resolve(repository_root, previous_commit)}:{config.MANDANT_CONFIG_PATH}",  # Dateiinhalt aus dem Commit
    )
    document = json.loads(previous_configuration)
    if document["mandant"]["releaselinie"] == configuration.releaselinie:
        return releaselinie, (zielstufe,), previous_commit

    return releaselinie, config.MTEXT_ZIEL_REIHENFOLGE, None


def _sync_resources(
    configuration: config.Configuration,
    *,
    repository_root: str | Path,
    commit: str,
    previous_commit: str | None,
    source_branch: str,
    releaselinie: str,
    zielstufe: str,
    handoff_root: str | Path | None = None,
) -> dict[str, object]:
    """Erzeugt Projektpakete auf CIFS und meldet sie dem M/Text-Adapter.

    Ein normaler Push verwendet ausschließlich den Git-Vergleich zwischen
    `previous_commit` und `commit`. Ein Aufruf ohne Vergleichscommit erzeugt
    für jedes Projekt ein FULL.
    """

    # Geplantes Ziel und Commit-Zugehörigkeit prüfen.
    if zielstufe not in configuration.mtext_ziel_prefixe:
        raise DeliveryError(Status.VALIDATION_FAILED, "M/Text-Zielstufe ist ungültig")

    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist unbekannt")

    if git.resolve(repository_root, "HEAD") != commit:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum Commit")

    git.require_ancestor(repository_root, commit, f"refs/remotes/origin/{source_branch}")

    # Betroffene Projekte und den CIFS-Übergabepfad bestimmen.
    git_changes = [] if previous_commit is None else git.changes(repository_root, previous_commit, commit)
    projects = [
        (project, project_code)
        for project, project_code in configuration.projects.items()
        if previous_commit is None or any(git.project_changes(git_changes, project))
    ]
    if not projects:
        return {"status": Status.ADAPTER_ACCEPTED.value, "projekte": []}

    if handoff_root is None:
        handoff_root = os.environ.get(_CIFS_ROOT_ENVIRONMENT)
        if not handoff_root:
            raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "CIFS-Übergabepfad ist nicht konfiguriert")

    root = Path(handoff_root)
    if not root.is_dir():
        raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "CIFS-Übergabepfad ist nicht erreichbar")

    # M/Text-Umgebung aus Zielstufe und ETAPS-Linie ableiten.
    etaps_linie = configuration.releaselinien[releaselinie]["etaps_linie"]
    umgebung = f"{configuration.mtext_ziel_prefixe[zielstufe]}{etaps_linie}"
    environment_root = root / umgebung

    # Derselbe fachliche Auftrag erhält bei einem Wiederanlauf dieselbe ID.
    # Der Adapter verwendet sie unabhängig vom jeweils neuen CIFS-Verzeichnis
    # zur idempotenten Annahme.
    auftrag_document = {
        "mandant": configuration.kuerzel,
        "repository": configuration.repository,
        "releaselinie": releaselinie,
        "zielstufe": zielstufe,
        "branch": source_branch,
        "bis": commit,
        "projekte": [project for project, _ in projects],
    }
    if previous_commit is not None:
        auftrag_document["von"] = previous_commit
    auftrag = hashlib.sha256(
        json.dumps(auftrag_document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    request_name = f"{configuration.kuerzel}-{commit[:12]}-{uuid.uuid4().hex}"
    request_path = environment_root / request_name

    # Projektpakete in das CIFS-Übergabeverzeichnis schreiben. Bei einem Fehler
    # wird das Verzeichnis entfernt, damit derselbe Auftrag erneut bereitgestellt
    # werden kann.
    try:
        request_path.mkdir(parents=True)
        for project, project_code in projects:
            build_project_package(
                configuration,
                repository_root=repository_root,
                output_directory=request_path,
                project=project,
                project_code=project_code,
                changes=git_changes,
                base=None if previous_commit is None else (source_branch, previous_commit),
                target=(source_branch, commit),
            )
    except (OSError, DeliveryError) as exc:
        shutil.rmtree(request_path, ignore_errors=True)
        if isinstance(exc, DeliveryError):
            raise

        raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "CIFS-Übergabe ist fehlgeschlagen") from exc

    # Nach dem bereitgestellten Verzeichnis den passenden Adapter aufrufen.
    adapter_url = _ADAPTER_SYNC_URL.format(umgebung=umgebung)
    payload = {
        "auftrag": auftrag,
        **auftrag_document,
        "pfad": str(request_path),
    }
    status, body = _call_adapter(adapter_url, payload)

    return {
        "status": Status.ADAPTER_ACCEPTED.value,
        "http_status": status,
        "response_body": body,
        "pfad": str(request_path),
        "projekte": payload["projekte"],
    }


def run_command(arguments: argparse.Namespace) -> dict[str, object]:
    """Synchronisiert den Commit aus dem GitHub-Workflow-Kontext."""

    source = Path(os.environ.get("GITHUB_WORKSPACE", ".")) / "source"
    configuration = config.load_configuration(source, os.environ["GITHUB_REPOSITORY"])
    source_branch = os.environ["GITHUB_REF_NAME"]

    # Releaselinie, Zielstufen und Vergleichscommit aus dem GitHub-Ereignis ableiten.
    releaselinie, zielstufen, vergleichs_commit = _plan_sync(
        configuration,
        repository_root=source,
        source_branch=source_branch,
        event_name=os.environ["GITHUB_EVENT_NAME"],
        previous_commit=os.environ.get("MTEXT_PREVIOUS_COMMIT", ""),
    )

    # Jede Zielstufe nacheinander synchronisieren. Ein Abbruch nennt die bereits
    # erfolgreichen Stufen, damit der Betrieb den Stand nachvollziehen kann.
    results: list[dict[str, object]] = []
    for zielstufe in zielstufen:
        try:
            results.append(
                {
                    "zielstufe": zielstufe,
                    **_sync_resources(
                        configuration,
                        repository_root=source,
                        commit=arguments.commit,
                        previous_commit=vergleichs_commit,
                        source_branch=source_branch,
                        releaselinie=releaselinie,
                        zielstufe=zielstufe,
                    ),
                }
            )
        except DeliveryError as exc:
            done = [entry["zielstufe"] for entry in results]
            detail = f" Bereits erfolgreich: {', '.join(done)}." if done else ""
            raise DeliveryError(
                exc.status,
                f"Synchronisation mit dem M/Text-Ziel {zielstufe} fehlgeschlagen.{detail} {exc.args[0]}",
            ) from exc

    return {"status": Status.ADAPTER_ACCEPTED.value, "synchronisationen": results} | (
        {"warnungen": list(configuration.warnungen)} if configuration.warnungen else {}
    )
