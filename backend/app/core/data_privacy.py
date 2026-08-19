from __future__ import annotations

import re

REDACTION_MARKER = "[已脱敏]"

# These patterns intentionally target high-confidence contact/identifier shapes
# only.  Names and postal addresses cannot be identified reliably without
# over-redacting ordinary career answers, so the UI must still warn students not
# to enter them in free text.
_CONTACT_PATTERNS = (
    re.compile(
        r"(?i)(?<![\w.+-])[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
        r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}(?![\w.-])"
    ),
    re.compile(r"(?<!\d)(?:(?:\+?86)[ -]?)?1[3-9]\d(?:[ -]?\d){8}(?!\d)"),
    re.compile(r"(?<![a-zA-Z0-9])(?:[a-zA-Z]{1,6}[-_]?)?\d{8,20}(?![a-zA-Z0-9])"),
)


def redact_obvious_contact_details(text: str) -> str:
    redacted = text
    for pattern in _CONTACT_PATTERNS:
        redacted = pattern.sub(REDACTION_MARKER, redacted)
    return redacted


def contains_obvious_contact_details(text: str) -> bool:
    return any(pattern.search(text) for pattern in _CONTACT_PATTERNS)
