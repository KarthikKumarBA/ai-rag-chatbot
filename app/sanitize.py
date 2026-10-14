"""Remove sensitive content before anything is embedded or sent to an LLM.

1. Sections marked <!-- sensitive --> ... <!-- /sensitive --> are removed entirely.
2. Known secret / PII patterns are redacted as a safety net.
"""

import re

_SENSITIVE_BLOCK = re.compile(r"<!--\s*sensitive\s*-->.*?<!--\s*/sensitive\s*-->",
                              re.S | re.I)

# Order matters: longer / more specific patterns first
_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
     "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"\b([a-z][a-z0-9+.-]*://)[^\s:/@]+:[^\s/@]+@", re.I), r"\1[REDACTED]@"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\b(?:sk-ant-|sk-|ABSK)[A-Za-z0-9_\-+/=]{16,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), "[REDACTED_JWT]"),
    (re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key)(\s*[=:]\s*)"
                r"(\"[^\"]*\"|'[^']*'|[^\s,;]+)"), r"\1\2[REDACTED]"),
    (re.compile(r"(?<!\d)\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{4}(?!\d)"), "[REDACTED_CARD]"),
    (re.compile(r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)"), "[REDACTED_AADHAAR]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[REDACTED_PAN]"),
    (re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"), "[REDACTED_PHONE]"),
]


def sanitize_text(text: str) -> tuple[str, dict]:
    """Return (clean_text, stats)."""
    stats = {"sensitive_blocks": 0, "redactions": 0}
    text, stats["sensitive_blocks"] = _SENSITIVE_BLOCK.subn("", text)
    for pattern, replacement in _PATTERNS:
        text, count = pattern.subn(replacement, text)
        stats["redactions"] += count
    return text, stats
