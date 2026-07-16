from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from lbs_delivery.cli import build_parser, run
from lbs_delivery.errors import Status


ROOT = Path(__file__).resolve().parents[2]


class CliTests(unittest.TestCase):
    def test_validate_config_reports_validated_configuration(self) -> None:
        arguments = build_parser().parse_args(
            [
                "validate-config",
                "--mandant-config",
                str(ROOT / "tests/fixtures/mandant.json"),
                "--mandant-schema",
                str(ROOT / "config/mandant.schema.json"),
                "--deployments-config",
                str(ROOT / "config/deployments.json"),
                "--deployments-schema",
                str(ROOT / "config/deployments.schema.json"),
                "--repository-name",
                "mtext-fi",
            ]
        )

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = run(arguments)

        self.assertEqual(status, Status.CONFIG_VALIDATED)
        self.assertEqual(
            json.loads(output.getvalue()),
            {
                "mandant": "FI",
                "release_lines": ["R260", "R261", "R270"],
                "repository": "mtext-fi",
                "status": "CONFIG_VALIDATED",
            },
        )


if __name__ == "__main__":
    unittest.main()
