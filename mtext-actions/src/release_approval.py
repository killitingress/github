"""Kommandozeileneinstieg für den Release-Freigabe-Pull-Request.

`prepare` erzeugt die Freigabeanforderung für den ausgewählten Branchstand.
`finalize` prüft den zusammengeführten Pull Request und liefert den Release-Tag
für die anschließende Git-Operation des Workflows.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from lbs_delivery import config, process, release_approval


def build_parser() -> argparse.ArgumentParser:
    """Definiert die beiden Schritte einer Release-Freigabe."""

    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--tag", required=True)
    prepare.add_argument("--branch", required=True)
    prepare.add_argument("--source-sha", required=True)
    prepare.add_argument("--run-reference", required=True)

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--approval-branch", required=True)
    finalize.add_argument("--branch", required=True)
    finalize.add_argument("--merge-sha", required=True)
    finalize.add_argument("--pull-request-number", type=int, required=True)
    finalize.add_argument("--api-url", required=True)
    return parser


def _write_outputs(values: dict[str, str]) -> None:
    """Stellt geprüfte Werte für die folgenden Workflow-Schritte bereit."""

    output = Path(os.environ["GITHUB_OUTPUT"])
    with output.open("a", encoding="utf-8") as stream:
        for name, value in values.items():
            stream.write(f"{name}={value}\n")


def run() -> dict[str, object]:
    """Führt den gewählten Freigabeschritt im Mandanten-Checkout aus."""

    arguments = build_parser().parse_args()
    source = Path(os.environ["GITHUB_WORKSPACE"]) / "source"
    repository = os.environ["SOURCE_REPOSITORY"]
    configuration = config.load_configuration(source, repository)

    if arguments.command == "prepare":
        approval_branch, path = release_approval.prepare_release_approval(
            configuration,
            repository_root=source,
            tag=arguments.tag,
            branch=arguments.branch,
            source_sha=arguments.source_sha,
            run_reference=arguments.run_reference,
        )
        _write_outputs(
            {
                "approval_branch": approval_branch,
                "approval_path": path.relative_to(source).as_posix(),
            }
        )
        return {"status": process.Status.RELEASE_APPROVAL_READY.value}

    pull_request = release_approval.read_pull_request(
        api_url=arguments.api_url,
        repository=repository,
        number=arguments.pull_request_number,
        token=os.environ["WORKFLOW_CONFIGURATION_TOKEN"],
    )
    tag = release_approval.finalize_release_approval(
        configuration,
        repository_root=source,
        approval_branch=arguments.approval_branch,
        branch=arguments.branch,
        merge_sha=arguments.merge_sha,
        pull_request=pull_request,
    )
    _write_outputs({"release_tag": tag})
    return {"status": process.Status.RELEASE_APPROVAL_VALIDATED.value}


if __name__ == "__main__":
    raise SystemExit(process.execute(run))
