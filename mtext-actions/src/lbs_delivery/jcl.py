"""Validiert JCL-Felder und rendert das versionierte Mainframe-Template."""

from __future__ import annotations

import re
from collections.abc import Mapping


class JclRenderError(ValueError):
    """Kennzeichnet ungültige JCL-Eingaben oder nicht aufgelöste Platzhalter."""


# Reguläre Ausdrücke für JCL-Platzhalter und JCL-Feldwerte.
# Erkennt Platzhalter wie `@@LEVEL@@` im JCL-Template.
_MARKER_RE = re.compile(r"@@([A-Z][A-Z0-9_]*)@@")

# Zulässige CodePipeline-Stages; diese Allowlist ist die fachliche Stage-Prüfung.
JCL_LEVELS = {"FKTE", "FKTF", "JURJ", "JURP", "SVTS", "VPTV"}
# Prüft das Mainframe-Subsystem auf erlaubte Zeichen und Feldlänge.
SUBSYSTEM_RE = re.compile(r"[A-Z0-9]{2,8}")
# Prüft einen Mainframe-Member auf erlaubte Zeichen und Feldlänge.
MEMBER_RE = re.compile(r"[A-Z0-9]{1,8}")
# Prüft das Assignment auf erlaubte Zeichen und Feldlänge.
ASSIGNMENT_RE = re.compile(r"[A-Z0-9]{1,12}")
# Ordnet jedem JCL-Feld seine verbindliche Wertprüfung zu.
JCL_FIELD_PATTERNS = {
    # Historischer JCL-Parameter: ausschließlich T (Test) oder P (Produktion).
    "ISPW": re.compile(r"[TP]"),
    # Historischer JCL-Feldname; fachlich enthält dieser Wert den Stage-Code.
    "LEVEL": re.compile("(?:" + "|".join(sorted(JCL_LEVELS)) + ")"),
    "SUBSYS": SUBSYSTEM_RE,
    "MEMBER": MEMBER_RE,
    "ASSIGNMENT": ASSIGNMENT_RE,
}


def validate_jcl_values(
    values: Mapping[str, str], *, include_member: bool = False
) -> dict[str, str]:
    """Prüft die fachlich erlaubten JCL-Werte aus Manifest oder Paket."""

    expected = set(JCL_FIELD_PATTERNS)
    if not include_member:
        expected.remove("MEMBER")
    supplied = set(values)
    missing = sorted(expected - supplied)
    unknown = sorted(supplied - expected)
    # Fehlende und fremde Felder werden gemeinsam gemeldet, damit ein Lauf zur
    # Korrektur genügt.
    if missing or unknown:
        details = []
        if missing:
            details.append(f"fehlende Felder: {', '.join(missing)}")
        if unknown:
            details.append(f"unbekannte Felder: {', '.join(unknown)}")
        raise JclRenderError("; ".join(details))

    normalized: dict[str, str] = {}
    for name in expected:
        pattern = JCL_FIELD_PATTERNS[name]
        value = values[name]
        if not isinstance(value, str) or pattern.fullmatch(value) is None:
            raise JclRenderError(f"ungültiger Wert für {name}")
        normalized[name] = value
    return normalized


def render_jcl(template: str, values: Mapping[str, str]) -> str:
    """Validiert den Platzhaltervertrag und rendert anschließend das Template."""

    normalized = validate_jcl_values(values, include_member=True)
    expected = set(JCL_FIELD_PATTERNS)
    markers = set(_MARKER_RE.findall(template))
    # Das Template darf weder einen benötigten Marker auslassen noch eigene einführen.
    if markers != expected:
        missing_markers = sorted(expected - markers)
        unknown_markers = sorted(markers - expected)
        details = []
        if missing_markers:
            details.append(f"fehlende Platzhalter: {', '.join(missing_markers)}")
        if unknown_markers:
            details.append(f"unbekannte Platzhalter: {', '.join(unknown_markers)}")
        raise JclRenderError("; ".join(details))

    rendered = _MARKER_RE.sub(lambda match: normalized[match.group(1)], template)
    if _MARKER_RE.search(rendered):
        raise JclRenderError("gerenderte JCL enthält nicht aufgelöste Platzhalter")
    return rendered
