"""Strict renderer for the versioned mainframe JCL template.

The renderer is intentionally side-effect free: it reads no secrets, performs
no transfer and submits no job. Field limits are conservative draft parameters
derived from the observed inventory and must be approved before production use.
"""

from __future__ import annotations

import re
from collections.abc import Mapping


class JclRenderError(ValueError):
    """Raised when JCL inputs or the rendered template are invalid."""


_MARKER_RE = re.compile(r"@@([A-Z][A-Z0-9_]*)@@")
_FIELD_PATTERNS = {
    "ISPW": re.compile(r"[TP]"),
    "LEVEL": re.compile(r"[A-Z0-9]{1,8}"),
    "SUBSYS": re.compile(r"[A-Z0-9]{1,8}"),
    "MEMBER": re.compile(r"[A-Z0-9]{1,8}"),
    "ASSIGNMENT": re.compile(r"[A-Z0-9]{1,12}"),
}


def render_jcl(template: str, values: Mapping[str, str]) -> str:
    """Render *template* after validating the exact placeholder contract."""

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
