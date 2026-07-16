"""Rendert das versionierte Mainframe-JCL-Template mit striktem Feldvertrag.

Der Renderer ist bewusst nebenwirkungsfrei: Er liest keine Secrets, überträgt
keine Dateien und startet keinen Job. Die Feldgrenzen stammen konservativ aus
dem untersuchten Bestand und sind vor der Produktivnutzung zu bestätigen.
"""

from __future__ import annotations

import re
from collections.abc import Mapping


class JclRenderError(ValueError):
    """Kennzeichnet ungültige JCL-Eingaben oder nicht aufgelöste Platzhalter."""


_MARKER_RE = re.compile(r"@@([A-Z][A-Z0-9_]*)@@")
_FIELD_PATTERNS = {
    # Historischer JCL-Parameter: ausschließlich T (Test) oder P (Produktion).
    "ISPW": re.compile(r"[TP]"),
    # Historischer JCL-Feldname; fachlich enthält dieser Wert den Stage-Code.
    "LEVEL": re.compile(r"(?:FKTE|FKTF|JURJ|JURP|SVTS|VPTV)"),
    "SUBSYS": re.compile(r"[A-Z0-9]{1,8}"),
    "MEMBER": re.compile(r"[A-Z0-9]{1,8}"),
    "ASSIGNMENT": re.compile(r"[A-Z0-9]{1,12}"),
}


def render_jcl(template: str, values: Mapping[str, str]) -> str:
    """Validiert den Platzhaltervertrag und rendert anschließend das Template."""

    expected = set(_FIELD_PATTERNS)
    supplied = set(values)
    missing = sorted(expected - supplied)
    unknown = sorted(supplied - expected)
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown fields: {', '.join(unknown)}")
        raise JclRenderError("; ".join(details))

    markers = set(_MARKER_RE.findall(template))
    if markers != expected:
        missing_markers = sorted(expected - markers)
        unknown_markers = sorted(markers - expected)
        details = []
        if missing_markers:
            details.append(f"template missing markers: {', '.join(missing_markers)}")
        if unknown_markers:
            details.append(f"template has unknown markers: {', '.join(unknown_markers)}")
        raise JclRenderError("; ".join(details))

    normalized: dict[str, str] = {}
    for name, pattern in _FIELD_PATTERNS.items():
        value = values[name]
        if not isinstance(value, str) or pattern.fullmatch(value) is None:
            raise JclRenderError(f"invalid value for {name}")
        normalized[name] = value

    rendered = _MARKER_RE.sub(lambda match: normalized[match.group(1)], template)
    if _MARKER_RE.search(rendered):
        raise JclRenderError("rendered JCL contains unresolved markers")
    return rendered
