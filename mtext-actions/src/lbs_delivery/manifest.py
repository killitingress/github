"""Validiert Releasemanifeste und prüft die zugehörigen Artefakte."""

from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from .errors import DeliveryError, Status
from .paths import resolve_within


Manifest = dict[str, Any]
PackageArtifact = dict[str, Any]


def sha256_file(path: str | Path) -> str:
    """Berechnet die SHA-256-Prüfsumme einer Datei blockweise."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_validator() -> Draft202012Validator:
    """Lädt und prüft das mit dem Python-Paket ausgelieferte Manifestschema."""

    try:
        resource = files("lbs_delivery").joinpath("schemas/manifest.schema.json")
        schema = json.loads(resource.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)
    except (OSError, UnicodeError, json.JSONDecodeError, SchemaError) as exc:
        raise DeliveryError(
            Status.PACKAGE_FAILED, "manifest schema is invalid or unreadable"
        ) from exc


def _validate_manifest(document: Any) -> Manifest:
    """Prüft Struktur und fachliche Querverweise eines Manifestdokuments."""

    try:
        _manifest_validator().validate(document)
    except ValidationError as exc:
        location = ".".join(str(item) for item in exc.absolute_path) or "root"
        raise DeliveryError(
            Status.PACKAGE_FAILED,
            f"manifest does not match schema at {location}: {exc.message}",
        ) from exc
    _validate_semantics(document)
    return document


def _validate_semantics(manifest: Manifest) -> None:
    """Prüft Querverweise, die sich nicht sinnvoll im JSON-Schema ausdrücken lassen."""

    release_type = manifest["delivery_type"]
    if (
        release_type == "DELTA"
        and manifest["base_tag"] != f"{manifest['release_line']}.100"
    ):
        raise DeliveryError(Status.PACKAGE_FAILED, "invalid DELTA base tag")

    release_packages = packages(manifest)
    package_projects = [item["project"] for item in release_packages]
    information_projects = [
        item["project"]
        for item in manifest["artifacts"]
        if item["kind"] == "information"
    ]
    if (
        len(package_projects) != len(set(package_projects))
        or len(information_projects) != len(set(information_projects))
        or set(package_projects) != set(information_projects)
    ):
        raise DeliveryError(
            Status.PACKAGE_FAILED,
            "manifest must contain one package and information file per project",
        )

    for package in release_packages:
        valid = (
            package["deletion_list"] is None and package["deletion_count"] == 0
            if release_type == "FULL"
            else package["deletion_list"] is not None
        )
        if not valid:
            raise DeliveryError(
                Status.PACKAGE_FAILED, "invalid deletion-list contract"
            )


def write_manifest(path: str | Path, manifest: Manifest) -> None:
    """Validiert und schreibt ein Manifest in kanonischer JSON-Darstellung."""

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
        raise DeliveryError(Status.PACKAGE_FAILED, "manifest is unreadable") from exc
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
            subject="artifact",
            strict=True,
            reject_symlink=True,
        )
        if not resolved.is_file():
            raise DeliveryError(Status.PACKAGE_FAILED, "artifact is not a file")
        if resolved.stat().st_size != artifact["size"]:
            raise DeliveryError(Status.PACKAGE_FAILED, "artifact size mismatch")
        if sha256_file(resolved) != artifact["sha256"]:
            raise DeliveryError(Status.PACKAGE_FAILED, "artifact checksum mismatch")
