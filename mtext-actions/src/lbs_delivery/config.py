"""Lädt Konfigurationen und wendet Schema- sowie Deploymentregeln an."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from .delivery_names import project_code_for_name
from .errors import DeliveryError, Status


JsonObject = dict[str, Any]
MandantConfig = JsonObject
DeploymentsConfig = JsonObject
EnvironmentConfig = JsonObject

_RELEASE_LINE_RE = re.compile(r"R[0-9]{3}")
_RELEASE_TAG_RE = re.compile(r"R[0-9]{3}\.[0-9]{3}")
_STAGE_BRANCH_RE = re.compile(
    r"(?P<release_line>R[0-9]{3})/(?P<stage>[A-Za-z][A-Za-z0-9_-]*)"
)
_SECRET_KEY_RE = re.compile(r"(?:password|passwd|secret|credential|token)", re.I)


def load_document(path: str | Path) -> JsonObject:
    """Liest ein JSON-Dokument und stellt ein Objekt als Wurzel sicher."""

    config_path = Path(path)
    try:
        document = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            f"cannot read structured configuration {config_path.name}",
        ) from exc
    if not isinstance(document, dict):
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            f"configuration {config_path.name} must contain an object",
        )
    return document


def validate_schema(document: JsonObject, schema_path: str | Path) -> None:
    """Validiert ein Konfigurationsdokument gegen das angegebene JSON-Schema."""

    try:
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(document)
    except (OSError, UnicodeError, json.JSONDecodeError, SchemaError) as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED, "configuration schema is invalid or unreadable"
        ) from exc
    except ValidationError as exc:
        location = ".".join(str(item) for item in exc.absolute_path) or "root"
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            f"configuration does not match schema at {location}: {exc.message}",
        ) from exc


def _reject_secret_keys(value: Any, location: str = "root") -> None:
    """Verhindert versehentlich versionierte Schlüssel mit Geheimnischarakter."""

    if isinstance(value, dict):
        for key, nested in value.items():
            if _SECRET_KEY_RE.search(str(key)):
                raise DeliveryError(
                    Status.VALIDATION_FAILED,
                    f"secret-like configuration key is not allowed at {location}.{key}",
                )
            _reject_secret_keys(nested, f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_secret_keys(nested, f"{location}[{index}]")


def load_mandant_config(
    config_path: str | Path,
    schema_path: str | Path,
    *,
    repository_name: str,
) -> MandantConfig:
    """Lädt die Mandantenkonfiguration und prüft ihre Repository-Identität."""

    document = load_document(config_path)
    validate_schema(document, schema_path)
    _reject_secret_keys(document)
    mandant = document["mandant"]
    if mandant["repository"] != repository_name:
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            "mandant repository does not match the triggering repository",
        )
    for field in ("name", "source_path"):
        values = [project[field] for project in mandant["projects"]]
        if len(values) != len(set(values)):
            raise DeliveryError(
                Status.VALIDATION_FAILED, f"project field {field} must be unique"
            )
    project_codes = [
        project_code_for_name(project["name"]) for project in mandant["projects"]
    ]
    if len(project_codes) != len(set(project_codes)):
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            "regular projects must have unique approved delivery name mappings",
        )
    return mandant


def load_deployments_config(
    config_path: str | Path, schema_path: str | Path
) -> DeploymentsConfig:
    """Lädt gemeinsame Ziele und prüft fachliche Querverweise der Konfiguration."""

    deployments = load_document(config_path)
    validate_schema(deployments, schema_path)
    _reject_secret_keys(deployments)
    branches = [
        environment["logical_branch"]
        for environment in deployments["environments"].values()
    ]
    if len(branches) != len(set(branches)):
        raise DeliveryError(
            Status.VALIDATION_FAILED, "logical branch mappings must be unique"
        )
    line_codes = {
        release_line["line"] for release_line in deployments["release_lines"].values()
    }
    if line_codes != set(deployments["adapter"]["targets"]):
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            "adapter target lines must match configured release lines",
        )
    release_environments = [
        environment
        for environment in deployments["environments"].values()
        if environment.get("release_on_tag", False)
    ]
    if len(release_environments) != 1:
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            "exactly one release environment must be configured",
        )
    return deployments


def validate_release_line(deployments: DeploymentsConfig, release_line: str) -> None:
    """Prüft Format und Bekanntheit einer Releaselinie."""

    if _RELEASE_LINE_RE.fullmatch(release_line) is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "invalid release line format")
    if release_line not in deployments["release_lines"]:
        raise DeliveryError(Status.VALIDATION_FAILED, "unknown release line")


def validate_release_tag(deployments: DeploymentsConfig, tag: str) -> None:
    """Prüft Format und konfigurierte Releaselinie eines Release-Tags."""

    if _RELEASE_TAG_RE.fullmatch(tag) is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "invalid release tag")
    validate_release_line(deployments, tag[:4])


def resolve_environment(
    deployments: DeploymentsConfig, environment: str
) -> EnvironmentConfig:
    """Löst eine für Ressourcensynchronisation freigegebene Umgebung auf."""

    try:
        resolved = deployments["environments"][environment]
    except KeyError as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED, "unknown target environment"
        ) from exc
    if not (
        resolved["deploy_on_push"]
        and resolved.get("code") is not None
        and resolved.get("mtext_target_key") is not None
    ):
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            "resource synchronization is not enabled for this environment",
        )
    return resolved


def _environment_for_branch(
    deployments: DeploymentsConfig, logical_branch: str
) -> EnvironmentConfig:
    """Ermittelt die eindeutig konfigurierte Umgebung eines logischen Branches."""

    matches = [
        environment
        for environment in deployments["environments"].values()
        if environment["logical_branch"] == logical_branch
    ]
    if len(matches) != 1:
        raise DeliveryError(Status.VALIDATION_FAILED, "unknown logical stage branch")
    return matches[0]


def release_branch(deployments: DeploymentsConfig, release_line: str) -> str:
    """Leitet den Bereitstellungsbranch einer Releaselinie aus der Konfiguration ab."""

    validate_release_line(deployments, release_line)
    environment = next(
        environment
        for environment in deployments["environments"].values()
        if environment.get("release_on_tag", False)
    )
    return f"{release_line}/{environment['logical_branch']}"


def resolve_adapter_url(
    deployments: DeploymentsConfig, release_line: str, environment: str
) -> str:
    """Erzeugt die Adapter-URL aus Releaselinie und Zielumgebung."""

    validate_release_line(deployments, release_line)
    resolved_environment = resolve_environment(deployments, environment)
    line = deployments["release_lines"][release_line]["line"]
    key = resolved_environment["mtext_target_key"]
    base = deployments["adapter"]["targets"][line][key]
    path = deployments["adapter"]["path"]
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def resolve_server_sync_root(
    deployments: DeploymentsConfig,
    release_line: str,
    environment: EnvironmentConfig,
) -> str:
    """Erzeugt den serverSync-Zielpfad aus Linie und Umgebungscode."""

    line = deployments["release_lines"][release_line]["line"]
    return deployments["adapter"]["server_sync_path_template"].format(
        line=line, environment_code=environment["code"]
    )


def resolve_stage_branch(
    deployments: DeploymentsConfig, branch: str
) -> tuple[str, EnvironmentConfig]:
    """Zerlegt einen Stufenbranch und löst seine konfigurierte Umgebung auf."""

    match = _STAGE_BRANCH_RE.fullmatch(branch)
    if match is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "invalid stage branch")
    release_line = match.group("release_line")
    validate_release_line(deployments, release_line)
    return release_line, _environment_for_branch(deployments, match.group("stage"))


def resolve_sync_branch(
    deployments: DeploymentsConfig, branch: str, environment: str
) -> str:
    """Prüft, dass Branchstufe und angeforderte Sync-Umgebung übereinstimmen."""

    release_line, stage_environment = resolve_stage_branch(deployments, branch)
    target_environment = resolve_environment(deployments, environment)
    if stage_environment["logical_branch"] != target_environment["logical_branch"]:
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            "source branch stage does not match target environment",
        )
    return release_line
