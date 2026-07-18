"""Validiert Releasemanifeste und prüft die zugehörigen Artefakte."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from .config import (
    MANDANTEN_KUERZEL,
    RELEASELINIE_RE,
    RELEASE_TAG_RE,
)
from .delivery_names import DELIVERY_CODES
from .errors import DeliveryError, Status
from .git_refs import FULL_SHA_RE
from .jcl import JclRenderError, MEMBER_RE, validate_jcl_values
from .paths import resolve_within, safe_relative_path, sha256_file


class ArtifactData(TypedDict):
    """Bündelt die gemeinsamen Felder aller Lieferartefakte."""

    path: str
    project: str
    size: int
    sha256: str


class PackageArtifact(ArtifactData):
    """Beschreibt ein Paketartefakt einschließlich Mainframe-Zuordnung."""

    kind: Literal["package"]
    member: str
    project_code: str
    deletion_list: str | None
    deletion_count: int


class InformationArtifact(ArtifactData):
    """Beschreibt die lesbare Informationsdatei eines Projektpakets."""

    kind: Literal["information"]


class JclValues(TypedDict):
    """Beschreibt die validierten JCL-Werte eines Manifests."""

    ISPW: str
    LEVEL: str
    SUBSYS: str
    ASSIGNMENT: str


# Erlaubte Artefaktformen innerhalb eines validierten Manifests.
Artifact = PackageArtifact | InformationArtifact


class Manifest(TypedDict):
    """Beschreibt den vollständigen Vertrag an der Build-Publish-Grenze."""

    repository: str
    mandant: str
    release_tag: str
    releaselinie: str
    delivery_type: str
    base_tag: str | None
    base_sha: str | None
    target_sha: str
    previous_tag: str | None
    previous_sha: str | None
    artifacts: list[Artifact]
    jcl: JclValues

# Reguläre Ausdrücke für manifest-spezifische Werte.
# Prüft eine kleingeschriebene hexadezimale SHA-256-Prüfsumme.
_CHECKSUM_RE = re.compile(r"[0-9a-f]{64}")
# Vollständige Feldmenge des Manifestwurzelobjekts.
_ROOT_KEYS = {
    "repository",
    "mandant",
    "release_tag",
    "releaselinie",
    "delivery_type",
    "base_tag",
    "base_sha",
    "target_sha",
    "previous_tag",
    "previous_sha",
    "artifacts",
    "jcl",
}
# Gemeinsame Feldmenge von Paket- und Informationsartefakten.
_ARTIFACT_KEYS = {"kind", "path", "project", "size", "sha256"}
# Zusätzliche Felder eines Paketartefakts.
_PACKAGE_KEYS = _ARTIFACT_KEYS | {
    "member",
    "project_code",
    "deletion_list",
    "deletion_count",
}


def _invalid(message: str) -> None:
    """Bricht eine Manifestprüfung mit stabilem Paketstatus ab."""

    raise DeliveryError(Status.PACKAGE_FAILED, message)


def _object(value: Any, keys: set[str], subject: str) -> dict[str, Any]:
    """Prüft die vollständige Feldmenge eines Manifestobjekts."""

    if not isinstance(value, dict) or set(value) != keys:
        _invalid(f"ungültig: {subject}")
    return value


def _string(
    value: Any,
    subject: str,
    *,
    pattern: re.Pattern[str] | None = None,
    maximum: int | None = None,
) -> str:
    """Prüft ein nicht leeres Manifestfeld auf Länge und Format."""

    valid = isinstance(value, str) and bool(value)
    valid = valid and (maximum is None or len(value) <= maximum)
    valid = valid and (pattern is None or pattern.fullmatch(value) is not None)
    if not valid:
        _invalid(f"ungültig: {subject}")
    return value


def _optional(value: Any, subject: str, pattern: re.Pattern[str]) -> None:
    """Prüft ein optionales formatiertes Feld, wenn es gesetzt ist."""

    if value is not None:
        _string(value, subject, pattern=pattern)


def _artifact_path(value: Any) -> str:
    """Prüft einen Artefaktpfad vor späteren Dateisystemzugriffen."""

    path = _string(value, "Artefaktpfad", maximum=256)
    if "\x00" in path:
        _invalid("ungültiger Artefaktpfad")
    safe_relative_path(
        path, status=Status.PACKAGE_FAILED, subject="Artefakt"
    )
    return path


def _validate_manifest(document: Any) -> Manifest:
    """Prüft ausschließlich den verwendeten Manifestvertrag."""

    manifest = _object(document, _ROOT_KEYS, "Manifest")
    _string(manifest["repository"], "Repository", maximum=128)
    if (
        not isinstance(manifest["mandant"], str)
        or manifest["mandant"] not in MANDANTEN_KUERZEL
    ):
        _invalid("ungültiges Mandanten-Kürzel")
    release_tag = _string(
        manifest["release_tag"], "Release-Tag", pattern=RELEASE_TAG_RE
    )
    releaselinie = _string(
        manifest["releaselinie"], "Releaselinie", pattern=RELEASELINIE_RE
    )
    # Das separate Linienfeld verhindert mehrdeutige Releasebezüge im Manifest.
    if releaselinie != release_tag[:4]:
        _invalid("Releaselinie passt nicht zum Release-Tag")
    if (
        not isinstance(manifest["delivery_type"], str)
        or manifest["delivery_type"] not in {"FULL", "DELTA"}
    ):
        _invalid("ungültige Lieferart")
    _optional(manifest["base_tag"], "Basis-Tag", RELEASE_TAG_RE)
    _optional(manifest["base_sha"], "Basis-SHA", FULL_SHA_RE)
    _string(manifest["target_sha"], "Ziel-SHA", pattern=FULL_SHA_RE)
    _optional(manifest["previous_tag"], "Vorgänger-Tag", RELEASE_TAG_RE)
    _optional(manifest["previous_sha"], "Vorgänger-SHA", FULL_SHA_RE)
    # Tag und SHA beschreiben gemeinsam genau einen Vorgängerstand.
    if (manifest["previous_tag"] is None) != (manifest["previous_sha"] is None):
        _invalid("Vorgänger-Tag und Vorgänger-SHA müssen gemeinsam gesetzt sein")

    artifacts = manifest["artifacts"]
    # Jede Lieferung enthält mindestens ein Paket und seine Informationsdatei.
    if not isinstance(artifacts, list) or len(artifacts) < 2:
        _invalid("ungültige Artefaktliste")
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            _invalid("ungültiges Artefakt")
        kind = artifact.get("kind")
        expected_keys = _PACKAGE_KEYS if kind == "package" else _ARTIFACT_KEYS
        artifact = _object(artifact, expected_keys, "Artefakt")
        if kind not in {"package", "information"}:
            _invalid("ungültige Artefaktart")
        _artifact_path(artifact["path"])
        _string(artifact["project"], "Artefaktprojekt", maximum=128)
        if type(artifact["size"]) is not int or artifact["size"] < 0:
            _invalid("ungültige Artefaktgröße")
        _string(artifact["sha256"], "Artefaktprüfsumme", pattern=_CHECKSUM_RE)
        if kind == "package":
            _string(artifact["member"], "Paket-Member", pattern=MEMBER_RE)
            if (
                not isinstance(artifact["project_code"], str)
                or artifact["project_code"] not in DELIVERY_CODES
            ):
                _invalid("ungültiger Projektcode des Pakets")
            if artifact["deletion_list"] is not None:
                _string(
                    artifact["deletion_list"], "Löschliste", maximum=128
                )
            if (
                type(artifact["deletion_count"]) is not int
                or artifact["deletion_count"] < 0
            ):
                _invalid("ungültige Löschanzahl")

    try:
        # JCL-Struktur und JCL-Werte werden ausschließlich im JCL-Modul definiert.
        validate_jcl_values(manifest["jcl"])
    except (AttributeError, TypeError, JclRenderError) as exc:
        raise DeliveryError(
            Status.PACKAGE_FAILED, "ungültige JCL im Manifest"
        ) from exc
    _validate_semantics(manifest)
    return cast(Manifest, manifest)


def _validate_semantics(manifest: Manifest) -> None:
    """Prüft die fachlichen Querverweise des Manifests."""

    release_type = manifest["delivery_type"]
    # FULL besitzt keine Basis; DELTA bezieht sich immer auf den .100-Stand der Linie.
    if release_type == "FULL":
        if manifest["base_tag"] is not None or manifest["base_sha"] is not None:
            _invalid("FULL darf keine Basis besitzen")
    elif (
        manifest["base_tag"] != f"{manifest['releaselinie']}.100"
        or manifest["base_sha"] is None
    ):
        _invalid("ungültige DELTA-Basis")

    release_packages = packages(manifest)
    package_projects = [item["project"] for item in release_packages]
    information_projects = [
        item["project"]
        for item in manifest["artifacts"]
        if item["kind"] == "information"
    ]
    # Pro Projekt bilden Paket und Information eine eindeutige Einheit.
    if (
        len(package_projects) != len(set(package_projects))
        or len(information_projects) != len(set(information_projects))
        or set(package_projects) != set(information_projects)
    ):
        _invalid("Manifest benötigt je Projekt genau ein Paket und eine Information")

    for package in release_packages:
        # Nur DELTA-Lieferungen tragen eine Löschliste; FULL weist stets null
        # Löschungen aus.
        valid = (
            package["deletion_list"] is None and package["deletion_count"] == 0
            if release_type == "FULL"
            else package["deletion_list"] is not None
        )
        if not valid:
            _invalid("ungültige Zuordnung der Löschliste")


def write_manifest(path: str | Path, manifest: Manifest) -> None:
    """Validiert und schreibt ein Manifest in kanonischer JSON-Darstellung."""

    # Ungeprüfte Daten dürfen die Build-Publish-Grenze nicht überschreiten.
    _validate_manifest(manifest)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_manifest(path: str | Path) -> Manifest:
    """Liest und validiert ein Manifest an der Build-Publish-Grenze."""

    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(
            Status.PACKAGE_FAILED, "Manifest kann nicht gelesen werden"
        ) from exc
    return _validate_manifest(document)


def packages(manifest: Manifest) -> list[PackageArtifact]:
    """Extrahiert die paketierbaren Artefakte aus einem validierten Manifest."""

    return [
        artifact
        for artifact in manifest["artifacts"]
        if artifact["kind"] == "package"
    ]


def verify_artifacts(manifest: Manifest, artifact_root: str | Path) -> None:
    """Prüft Pfad, Dateigröße und SHA-256 aller manifestierten Dateien."""

    root = Path(artifact_root).resolve()
    for artifact in manifest["artifacts"]:
        resolved = resolve_within(
            root,
            artifact["path"],
            status=Status.PACKAGE_FAILED,
            subject="Artefakt",
            strict=True,
            reject_symlink=True,
        )
        if not resolved.is_file():
            raise DeliveryError(Status.PACKAGE_FAILED, "Artefakt ist keine Datei")
        if resolved.stat().st_size != artifact["size"]:
            raise DeliveryError(
                Status.PACKAGE_FAILED, "Artefaktgröße stimmt nicht überein"
            )
        # Größe allein erkennt gleich lange Manipulationen nicht; daher
        # zusätzlich SHA-256.
        if sha256_file(resolved) != artifact["sha256"]:
            raise DeliveryError(
                Status.PACKAGE_FAILED, "Artefaktprüfsumme stimmt nicht überein"
            )
