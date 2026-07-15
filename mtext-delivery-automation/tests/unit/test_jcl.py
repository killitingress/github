from __future__ import annotations

import unittest
import re
from pathlib import Path

from lbs_delivery.jcl import JclRenderError, render_jcl


AUTOMATION_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = AUTOMATION_ROOT.parent
TEMPLATE_PATH = AUTOMATION_ROOT / "templates/mainframe-upload.jcl"
FIXTURE_PATH = AUTOMATION_ROOT / "tests/fixtures/mainframe-upload.rendered.jcl"
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

    def test_rendered_jcl_matches_review_fixture(self) -> None:
        expected = FIXTURE_PATH.read_text(encoding="ascii")
        self.assertEqual(render_jcl(self.template, VALID_VALUES), expected)

    def test_template_is_normalized_read_only_extraction_from_bash(self) -> None:
        source_lines = (
            (WORKSPACE_ROOT / "LBS_SVN_Hook_v0.4.bash")
            .read_text(encoding="utf-8")
            .splitlines()[67:132]
        )
        extracted = []
        for line in source_lines:
            if not line.strip():
                continue
            match = re.match(
                r'^\s*echo "(.*)"\s+(?:>|>>)\s+\$WORKSPACE/add\.jcl\s*$',
                line,
            )
            self.assertIsNotNone(match, line)
            normalized = match.group(1).rstrip().replace(r"\$", "$")
            for historical, marker in {
                "${ISPW}": "@@ISPW@@",
                "${LEVEL}": "@@LEVEL@@",
                "${SUBSYS}": "@@SUBSYS@@",
                "${ASSIGNMENT}": "@@ASSIGNMENT@@",
                "$2": "@@MEMBER@@",
            }.items():
                normalized = normalized.replace(historical, marker)
            extracted.append(normalized)

        self.assertEqual("\n".join(extracted) + "\n", self.template)

    def test_render_replaces_only_the_five_declared_fields(self) -> None:
        rendered = render_jcl(self.template, VALID_VALUES)
        self.assertNotIn("@@", rendered)
        self.assertIn("DSN=IEA.ISPWP.BOAS.JURP.TONICZ", rendered)
        self.assertIn("SELECT MEMBER=((FIBASISF,,R))", rendered)
        self.assertIn("APPLID=LOMS", rendered)
        self.assertIn("SUBAPPL=LOMS", rendered)
        self.assertIn("PROJNO=LOMS000067", rendered)
        self.assertIn("$DEFINE_TSI", rendered)

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
