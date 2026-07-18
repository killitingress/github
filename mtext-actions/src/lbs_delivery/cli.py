"""Orchestriert Validierung, Synchronisation, Releasebau und Veröffentlichung."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import (
    ADAPTER_PAYLOAD,
    MandantConfig,
    RELEASE_TAG_RE,
    Releaselinien,
    SYNC_STAGES,
    load_mandant_config,
    load_releaselinien,
    validate_releaselinie,
)
from .errors import DeliveryError, Status
from .git_refs import (
    previous_release_tag,
    require_commit_on_branch,
    require_full_sha,
    require_head,
    require_tag_on_branch,
    resolve_commit,
)
from .mainframe import FtpSettings, render_package_jcl, submit_package
from .manifest import PackageArtifact, load_manifest, packages, verify_artifacts
from .mtext_adapter import call_adapter
from .paths import resolve_within
from .release import base_tag, build_release, release_type
from .resources import publish_server_sync, stage_resources


def _common_config_arguments(parser: argparse.ArgumentParser) -> None:
    """Ergänzt gemeinsame Pfade und Repository-Angaben eines Subcommands."""

    parser.add_argument("--mandant-config", default=".config.json")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--releaselinien", required=True)
    parser.add_argument("--repository-name", required=True)


def build_parser() -> argparse.ArgumentParser:
    """Definiert die öffentliche Kommandozeilenschnittstelle der Automation."""

    parser = argparse.ArgumentParser(prog="lbs-delivery")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-config")
    _common_config_arguments(validate)

    sync = subparsers.add_parser("sync-resources")
    _common_config_arguments(sync)
    sync.add_argument("--commit", required=True)
    sync.add_argument("--source-branch", required=True)
    sync.add_argument("--environment", required=True)
    sync.add_argument("--staging-dir", required=True)
    sync.add_argument("--timeout", type=float, default=60.0)
    sync.add_argument("--execute", action="store_true")

    release = subparsers.add_parser("build-release")
    _common_config_arguments(release)
    release.add_argument("--tag", required=True)
    release.add_argument("--trigger-sha", default="")
    release.add_argument("--output", default="dist")

    publish = subparsers.add_parser("publish-mainframe")
    publish.add_argument("--manifest", required=True)
    publish.add_argument("--artifact-root", required=True)
    publish.add_argument("--template", required=True)
    publish.add_argument("--temporary-dir", required=True)
    publish.add_argument("--execute", action="store_true")

    return parser


def _load_configs(arguments: argparse.Namespace) -> tuple[MandantConfig, Releaselinien]:
    """Lädt Mandant und Releaselinien."""

    mandant = load_mandant_config(
        arguments.mandant_config,
        repository_name=arguments.repository_name,
        repository_root=arguments.repository_root,
    )
    releaselinien = load_releaselinien(arguments.releaselinien)
    konfigurierte_profile = mandant["hostprofile"]
    if any(
        item["uebergabeprofil"] not in konfigurierte_profile
        for item in releaselinien.values()
    ):
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            "Releaselinie verweist auf ein unbekanntes Hostprofil",
        )
    return mandant, releaselinien


def _validate_config(arguments: argparse.Namespace) -> Status:
    """Prüft Mandant und Releaselinien."""

    mandant, releaselinien = _load_configs(arguments)
    print(
        json.dumps(
            {
                "status": Status.CONFIG_VALIDATED.value,
                "mandanten_kuerzel": mandant["kuerzel"],
                "repository": mandant["repository"],
                "releaselinien": sorted(releaselinien),
            },
            sort_keys=True,
        )
    )
    return Status.CONFIG_VALIDATED


def _sync(arguments: argparse.Namespace) -> Status:
    """Stellt Ressourcen bereit und ruft bei Freigabe den M/Text-Adapter auf."""

    mandant, releaselinien = _load_configs(arguments)
    releaselinie, separator, stage = arguments.source_branch.partition("/")
    validate_releaselinie(releaselinien, releaselinie)
    if (
        separator != "/"
        or arguments.environment not in SYNC_STAGES
        or stage != arguments.environment
    ):
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            "Branch und Zielumgebung der Synchronisation passen nicht zusammen",
        )
    commit = require_full_sha(arguments.commit)
    require_head(arguments.repository_root, commit)
    require_commit_on_branch(arguments.repository_root, commit, arguments.source_branch)
    projects = list(mandant["projects"])
    staged = stage_resources(arguments.repository_root, arguments.staging_dir, projects)
    if not arguments.execute:
        print(json.dumps({"status": "STAGED", "projects": staged}, sort_keys=True))
        return Status.ARTIFACT_READY
    mtext_linie = releaselinien[releaselinie]["mtext_linie"]
    path_suffix, host_suffix = SYNC_STAGES[arguments.environment]
    server_sync_root = f"/nfs/mtext/{mtext_linie}{path_suffix}/serverSync"
    publish_server_sync(arguments.staging_dir, server_sync_root)
    response = call_adapter(
        f"https://{mtext_linie}{host_suffix}.ltoma.intern/vMtextAdapter/sync",
        ADAPTER_PAYLOAD,
        timeout=arguments.timeout,
    )
    print(
        json.dumps(
            {
                "status": Status.ADAPTER_ACCEPTED.value,
                "http_status": response.status,
                "response_body": response.body,
            },
            sort_keys=True,
        )
    )
    return Status.ADAPTER_ACCEPTED


def _build_release(arguments: argparse.Namespace) -> Status:
    """Prüft den Release-Tag und erzeugt das zugehörige FULL oder DELTA."""

    mandant, releaselinien = _load_configs(arguments)
    if RELEASE_TAG_RE.fullmatch(arguments.tag) is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "ungültiger Release-Tag")
    releaselinie = arguments.tag[:4]
    validate_releaselinie(releaselinien, releaselinie)
    required_branch = f"{releaselinie}/Bereitstellung"
    target_sha = require_tag_on_branch(
        arguments.repository_root, arguments.tag, required_branch
    )
    if arguments.trigger_sha and require_full_sha(arguments.trigger_sha) != target_sha:
        raise DeliveryError(
            Status.SOURCE_FAILED,
            "Tag-SHA stimmt nicht mit dem auslösenden Commit überein",
        )
    require_head(arguments.repository_root, target_sha)
    delivery = release_type(arguments.tag)
    resolved_base_tag: str | None = None
    base_sha: str | None = None
    if delivery == "DELTA":
        resolved_base_tag = base_tag(arguments.tag)
        base_sha = resolve_commit(
            arguments.repository_root, f"refs/tags/{resolved_base_tag}"
        )
    previous_tag = previous_release_tag(arguments.repository_root, arguments.tag)
    previous_sha = (
        resolve_commit(arguments.repository_root, f"refs/tags/{previous_tag}")
        if previous_tag
        else None
    )
    manifest_path = build_release(
        arguments.repository_root,
        arguments.output,
        mandant,
        repository_name=arguments.repository_name,
        release_tag=arguments.tag,
        uebergabeprofil_name=releaselinien[releaselinie]["uebergabeprofil"],
        target_sha=target_sha,
        base_sha=base_sha,
        previous_tag=previous_tag,
        previous_sha=previous_sha,
    )
    print(
        json.dumps(
            {
                "status": Status.ARTIFACT_READY.value,
                "manifest": str(manifest_path),
                "base_tag": resolved_base_tag,
                "target_sha": target_sha,
            },
            sort_keys=True,
        )
    )
    return Status.ARTIFACT_READY


def _publish(arguments: argparse.Namespace) -> Status:
    """Prüft ein Releaseartefakt und übergibt es optional an den Mainframe."""

    manifest = load_manifest(arguments.manifest)
    verify_artifacts(manifest, arguments.artifact_root)
    template = Path(arguments.template).read_text(encoding="ascii")
    temporary = Path(arguments.temporary_dir)
    temporary.mkdir(parents=True, exist_ok=True)
    rendered: list[tuple[PackageArtifact, Path]] = []
    release_packages = packages(manifest)
    for package in release_packages:
        jcl_path = temporary / f"{package['member']}.jcl"
        jcl_path.write_text(
            render_package_jcl(manifest, package, template), encoding="ascii"
        )
        rendered.append((package, jcl_path))
    if not arguments.execute:
        print(
            json.dumps(
                {
                    "status": Status.ARTIFACT_READY.value,
                    "packages": [package["member"] for package in release_packages],
                    "jcl": [str(path) for _, path in rendered],
                },
                sort_keys=True,
            )
        )
        return Status.ARTIFACT_READY
    settings = FtpSettings.from_environment()
    for package, jcl_path in rendered:
        package_path = resolve_within(
            arguments.artifact_root,
            package["path"],
            status=Status.PACKAGE_FAILED,
            subject="Artefakt",
            strict=True,
            reject_symlink=True,
        )
        submit_package(
            package_path,
            jcl_path,
            package["member"],
            settings,
        )
    print(json.dumps({"status": Status.MAINFRAME_SUBMITTED.value}))
    return Status.MAINFRAME_SUBMITTED


def run(arguments: argparse.Namespace) -> Status:
    """Leitet geparste Argumente an den passenden fachlichen Handler weiter."""

    handlers = {
        "validate-config": _validate_config,
        "sync-resources": _sync,
        "build-release": _build_release,
        "publish-mainframe": _publish,
    }
    return handlers[arguments.command](arguments)


def main(argv: list[str] | None = None) -> int:
    """Führt die CLI aus und übersetzt fachliche Fehler in Prozess-Exitcodes."""

    parser = build_parser()
    try:
        run(parser.parse_args(argv))
    except DeliveryError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except (OSError, UnicodeError) as exc:
        print(
            f"{Status.VALIDATION_FAILED.value}: lokale Dateioperation fehlgeschlagen",
            file=sys.stderr,
        )
        return DeliveryError(Status.VALIDATION_FAILED, str(exc)).exit_code
    return 0
