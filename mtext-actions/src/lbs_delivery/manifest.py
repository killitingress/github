"""Validiert Releasemanifeste und prüft die zugehörigen Artefakte."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .errors import DeliveryError, Status
from .jcl import JclRenderError, validate_jcl_values
from .paths import resolve_within, safe_relative_path


Manifest = dict[str, Any]
PackageArtifact = dict[str, Any]

_RELEASE_TAG_RE = re.compile(r"R[0-9]{3}\.[0-9]{3}")
_RELEASE_LINE_RE = re.compile(r"R[0-9]{3}")
_SHA_RE = re.compile(r"[0-9a-f]{40}")
_CHECKSUM_RE = re.compile(r"[0-9a-f]{64}")
_MANDANT_RE = re.compile(r"[A-Z]{2}")
_MEMBER_RE = re.compile(r"[A-Z0-9]{1,8}")
_PROJECT_CODE_RE = re.compile(r"[A-Z0-9]{1,5}")
_ROOT_KEYS = {
    "repository",
    "mandant",
    "release_tag",
    "release_line",
    "delivery_type",
    "base_tag",
    "base_sha",
    "target_sha",
    "previous_tag",
    "previous_sha",
    "artifacts",
    "jcl",
}
_ARTIFACT_KEYS = {"kind", "path", "project", "size", "sha256"}
_PACKAGE_KEYS = _ARTIFACT_KEYS | {
    "member",
    "project_code",
    "deletion_list",
    "deletion_count",
}


def _invalid(message: str) -> None:
    raise DeliveryError(Status.PACKAGE_FAILED, message)


def _object(value: Any, keys: set[str], subject: str) -> Manifest:
    if not isinstance(value, dict) or set(value) != keys:
        _invalid(f"invalid {subject}")
    return value


def _string(
    value: Any,
    subject: str,
    *,
    pattern: re.Pattern[str] | None = None,
    maximum: int | None = None,
) -> str:
    valid = isinstance(value, str) and bool(value)
    valid = valid and (maximum is None or len(value) <= maximum)
    valid = valid and (pattern is None or pattern.fullmatch(value) is not None)
    if not valid:
        _invalid(f"invalid {subject}")
    return value


def _optional(value: Any, subject: str, pattern: re.Pattern[str]) -> None:
    if value is not None:
        _string(value, subject, pattern=pattern)


def _artifact_path(value: Any) -> str:
    path = _string(value, "artifact path", maximum=256)
    if "\x00" in path:
        _invalid("invalid artifact path")
    safe_relative_path(
        path, status=Status.PACKAGE_FAILED, subject="artifact"
    )
    return path


def sha256_file(path: str | Path) -> str:
    """Berechnet die SHA-256-Prüfsumme einer Datei blockweise."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_manifest(document: Any) -> Manifest:
    """Prüft ausschließlich den verwendeten Manifestvertrag."""

    manifest = _object(document, _ROOT_KEYS, "manifest")
    _string(manifest["repository"], "repository", maximum=128)
    _string(manifest["mandant"], "mandant", pattern=_MANDANT_RE)
    release_tag = _string(
        manifest["release_tag"], "release tag", pattern=_RELEASE_TAG_RE
    )
    release_line = _string(
        manifest["release_line"], "release line", pattern=_RELEASE_LINE_RE
    )
    if release_line != release_tag[:4]:
        _invalid("release line does not match release tag")
    if (
        not isinstance(manifest["delivery_type"], str)
        or manifest["delivery_type"] not in {"FULL", "DELTA"}
    ):
        _invalid("invalid delivery type")
    _optional(manifest["base_tag"], "base tag", _RELEASE_TAG_RE)
    _optional(manifest["base_sha"], "base SHA", _SHA_RE)
    _string(manifest["target_sha"], "target SHA", pattern=_SHA_RE)
    _optional(manifest["previous_tag"], "previous tag", _RELEASE_TAG_RE)
    _optional(manifest["previous_sha"], "previous SHA", _SHA_RE)
    if (manifest["previous_tag"] is None) != (manifest["previous_sha"] is None):
        _invalid("previous tag and SHA must be set together")

    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, list) or len(artifacts) < 2:
        _invalid("invalid artifacts")
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            _invalid("invalid artifact")
        kind = artifact.get("kind")
        expected_keys = _PACKAGE_KEYS if kind == "package" else _ARTIFACT_KEYS
        artifact = _object(artifact, expected_keys, "artifact")
        if kind not in {"package", "information"}:
            _invalid("invalid artifact kind")
        _artifact_path(artifact["path"])
        _string(artifact["project"], "artifact project", maximum=128)
        if type(artifact["size"]) is not int or artifact["size"] < 0:
            _invalid("invalid artifact size")
        _string(artifact["sha256"], "artifact checksum", pattern=_CHECKSUM_RE)
        if kind == "package":
            _string(artifact["member"], "package member", pattern=_MEMBER_RE)
            _string(
                artifact["project_code"],
                "package project code",
                pattern=_PROJECT_CODE_RE,
            )
            if artifact["deletion_list"] is not None:
                _string(
                    artifact["deletion_list"], "deletion list", maximum=128
                )
            if (
                type(artifact["deletion_count"]) is not int
                or artifact["deletion_count"] < 0
            ):
                _invalid("invalid deletion count")

    try:
        validate_jcl_values(manifest["jcl"])
    except (AttributeError, TypeError, JclRenderError) as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "invalid manifest JCL") from exc
    _validate_semantics(manifest)
    return manifest


def _validate_semantics(manifest: Manifest) -> None:
    """Prüft die fachlichen Querverweise des Manifests."""

    release_type = manifest["delivery_type"]
    if release_type == "FULL":
        if manifest["base_tag"] is not None or manifest["base_sha"] is not None:
            _invalid("FULL must not have a base")
    elif (
        manifest["base_tag"] != f"{manifest['release_line']}.100"
        or manifest["base_sha"] is None
    ):
        _invalid("invalid DELTA base")

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
        _invalid("manifest must contain one package and information file per project")

    for package in release_packages:
        valid = (
            package["deletion_list"] is None and package["deletion_count"] == 0
            if release_type == "FULL"
            else package["deletion_list"] is not None
        )
        if not valid:
            _invalid("invalid deletion-list contract")


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
