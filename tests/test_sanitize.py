"""Sensitive sections and secret/PII patterns never reach the index."""

from app.sanitize import sanitize_text


def test_sensitive_block_is_removed():
    text = ("Public intro.\n<!-- sensitive -->\nAdmin creds: root / hunter2\n"
            "<!-- /sensitive -->\nPublic outro.")
    clean, stats = sanitize_text(text)

    assert "hunter2" not in clean
    assert "Public intro." in clean and "Public outro." in clean
    assert stats["sensitive_blocks"] == 1


def test_patterns_are_redacted():
    text = (
        "Call +91 98450 12345 or 9845012345. PAN ABCDE1234F. Aadhaar 1234 5678 9012. "
        "Card 4111 1111 1111 1111. Key AKIAABCDEFGHIJKLMNOP and sk-abcdefghijklmnopqrstuv. "
        "DB postgres://admin:S3cret!@db.internal:5432/app and password = hunter2"
    )
    clean, stats = sanitize_text(text)

    for secret in ["98450", "9845012345", "ABCDE1234F", "1234 5678 9012", "4111 1111",
                   "AKIAABCDEFGHIJKLMNOP", "sk-abcdefghijklmnopqrstuv", "S3cret!", "hunter2"]:
        assert secret not in clean, secret
    assert "postgres://[REDACTED]@db.internal" in clean
    assert stats["redactions"] >= 8


def test_normal_text_is_unchanged():
    text = "Employees get 24 days of leave. Deploys stop on Friday after 15:00 IST on 2026-12-24."
    clean, stats = sanitize_text(text)
    assert clean == text
    assert stats == {"sensitive_blocks": 0, "redactions": 0}
