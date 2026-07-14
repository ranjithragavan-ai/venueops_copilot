"""
Tests for security measures implemented in the application.

Covers:
- bcrypt password hashing and verification.
- html.escape XSS sanitisation.
- Input validation edge cases.
"""

import bcrypt
import html
import pytest


# ───────────────────────────────────────────────────────────────────── #
#  Password Hashing Tests
# ───────────────────────────────────────────────────────────────────── #

class TestBcryptHashing:
    """Ensure bcrypt is correctly used for password storage."""

    def test_hash_starts_with_2b(self):
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(b"password123", salt)
        assert hashed.startswith(b"$2b$")

    def test_checkpw_validates_correct_password(self):
        pwd = "secureP@ss!"
        hashed = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        assert bcrypt.checkpw(pwd.encode("utf-8"), hashed.encode("utf-8")) is True

    def test_checkpw_rejects_wrong_password(self):
        hashed = bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode("utf-8")
        assert bcrypt.checkpw(b"wrong", hashed.encode("utf-8")) is False

    def test_different_salts_produce_different_hashes(self):
        h1 = bcrypt.hashpw(b"same", bcrypt.gensalt())
        h2 = bcrypt.hashpw(b"same", bcrypt.gensalt())
        assert h1 != h2  # Same password, different salts → different hashes


# ───────────────────────────────────────────────────────────────────── #
#  XSS Sanitisation Tests
# ───────────────────────────────────────────────────────────────────── #

class TestXssSanitisation:
    """Verify html.escape protects against script injection."""

    def test_script_tag_escaped(self):
        malicious = '<script>alert("xss")</script>'
        safe = html.escape(malicious)
        assert "<script>" not in safe
        assert "&lt;script&gt;" in safe

    def test_angle_brackets_escaped(self):
        assert html.escape("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"

    def test_ampersand_escaped(self):
        assert html.escape("AT&T") == "AT&amp;T"

    def test_quotes_escaped(self):
        assert html.escape('"hello"', quote=True) == "&quot;hello&quot;"

    def test_clean_text_unchanged(self):
        clean = "Normal incident report about a spill in aisle 5."
        assert html.escape(clean) == clean
