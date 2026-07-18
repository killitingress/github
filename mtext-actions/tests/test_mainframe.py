"""Prüft JCL-Rendering und Publish-Vorbedingungen ohne FTP."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lbs_delivery.errors import DeliveryError, Status
from lbs_delivery.mainframe import render_jcl

from tests.support import AUTOMATION_ROOT


class MainframeTests(unittest.TestCase):
    def setUp(self) -> None:
        """Lädt das produktive JCL-Template für Render-Prüfungen."""

        self.template = (
            AUTOMATION_ROOT / "templates/mainframe-upload.jcl"
        ).read_text(encoding="ascii")
        self.jcl = {
            "ISPW": "P",
            "LEVEL": "FKTE",
            "SUBSYS": "LOMS",
            "ASSIGNMENT": "LOMS000066",
        }

    def test_render_jcl_replaces_all_markers(self) -> None:
        """Ersetzt alle JCL-Platzhalter durch geprüfte Werte."""

        rendered = render_jcl(self.template, self.jcl, "FIBASISD")
        self.assertIn("MEMBER=((FIBASISD,,R))", rendered)
        self.assertNotIn("@@", rendered)

    def test_render_jcl_rejects_invalid_subsystem(self) -> None:
        """Lehnt Subsysteme außerhalb des JCL-Zeichensatzes ab."""

        invalid = {**self.jcl, "SUBSYS": "lo-ms"}
        with self.assertRaises(DeliveryError) as context:
            render_jcl(self.template, invalid, "FIBASISD")
        self.assertEqual(context.exception.status, Status.VALIDATION_FAILED)

    def test_render_jcl_rejects_unresolved_template_marker(self) -> None:
        """Lehnt Templates ab, die nach dem Rendern noch Marker enthalten."""

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        template_path = Path(temporary.name) / "broken.jcl"
        template_path.write_text("@@MEMBER@@ @@UNKNOWN@@\n", encoding="ascii")
        with self.assertRaises(DeliveryError) as context:
            render_jcl(template_path.read_text(encoding="ascii"), self.jcl, "FIBASISD")
        self.assertEqual(context.exception.status, Status.VALIDATION_FAILED)


if __name__ == "__main__":
    unittest.main()
