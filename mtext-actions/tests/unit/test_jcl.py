from __future__ import annotations

import unittest
from pathlib import Path

from lbs_delivery.jcl import JclRenderError, render_jcl


AUTOMATION_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = AUTOMATION_ROOT / "templates/mainframe-upload.jcl"
VALID_VALUES = {
    "ISPW": "P",
    "LEVEL": "JURP",
    "SUBSYS": "LOMS",
    "MEMBER": "FIBASISF",
    "ASSIGNMENT": "LOMS000067",
}


class JclRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template = TEMPLATE_PATH.read_text(encoding="ascii")

    def test_render_replaces_only_the_five_declared_fields(self) -> None:
        rendered = render_jcl(self.template, VALID_VALUES)
        self.assertNotIn("@@", rendered)
        self.assertIn("DSN=IEA.ISPWP.BOAS.JURP.TONICZ", rendered)
        self.assertIn("SELECT MEMBER=((FIBASISF,,R))", rendered)
        self.assertIn("APPLID=LOMS", rendered)
        self.assertIn("SUBAPPL=LOMS", rendered)
        self.assertIn("PROJNO=LOMS000067", rendered)
        self.assertIn("$DEFINE_TSI", rendered)

    def test_all_confirmed_stage_codes_are_accepted(self) -> None:
        for stage in ("FKTE", "FKTF", "JURJ", "JURP", "SVTS", "VPTV"):
            with self.subTest(stage=stage):
                rendered = render_jcl(self.template, dict(VALID_VALUES, LEVEL=stage))
                self.assertIn(f".BOAS.{stage}.TONICZ", rendered)

    def test_only_test_and_production_ispw_values_are_accepted(self) -> None:
        for ispw, expected_dataset in (("T", "IEA.ISPWT"), ("P", "IEA.ISPWP")):
            with self.subTest(ispw=ispw):
                rendered = render_jcl(self.template, dict(VALID_VALUES, ISPW=ispw))
                self.assertIn(expected_dataset, rendered)

        for ispw in ("E", "TEST", "PROD", ""):
            with self.subTest(ispw=ispw), self.assertRaisesRegex(
                JclRenderError, "invalid value for ISPW"
            ):
                render_jcl(self.template, dict(VALID_VALUES, ISPW=ispw))

    def test_missing_unknown_and_invalid_values_are_rejected(self) -> None:
        missing = dict(VALID_VALUES)
        missing.pop("MEMBER")
        with self.assertRaisesRegex(JclRenderError, "missing fields: MEMBER"):
            render_jcl(self.template, missing)

        unknown = dict(VALID_VALUES, PASSWORD="secret")
        with self.assertRaisesRegex(JclRenderError, "unknown fields: PASSWORD"):
            render_jcl(self.template, unknown)

        for name, value in {
            "ISPW": "P;",
            "LEVEL": "jurp",
            "SUBSYS": "LOMS-1",
            "MEMBER": "TOO-LONG-MEMBER",
            "ASSIGNMENT": "LOMS 000067",
        }.items():
            invalid = dict(VALID_VALUES)
            invalid[name] = value
            with self.subTest(name=name), self.assertRaisesRegex(
                JclRenderError, f"invalid value for {name}"
            ):
                render_jcl(self.template, invalid)

    def test_unknown_or_missing_template_markers_are_rejected(self) -> None:
        with self.assertRaisesRegex(JclRenderError, "template has unknown markers"):
            render_jcl(self.template + "@@PASSWORD@@\n", VALID_VALUES)

        with self.assertRaisesRegex(JclRenderError, "template missing markers"):
            render_jcl(self.template.replace("@@ASSIGNMENT@@", "FIXED"), VALID_VALUES)


if __name__ == "__main__":
    unittest.main()
