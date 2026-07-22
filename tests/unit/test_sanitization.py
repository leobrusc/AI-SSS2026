"""Unit tests for traceai.analysis.sanitization module."""

import pytest

from traceai.analysis.sanitization import sanitize_dict, sanitize_string

pytestmark = pytest.mark.unit


class TestSanitizeString:
    """Tests for sanitize_string function."""

    def test_sanitize_windows_path(self):
        """Windows user paths are redacted."""
        text = r"C:\Users\john.doe\model.bin"
        result = sanitize_string(text)

        assert "john.doe" not in result
        assert "<REDACTED>" in result

    def test_sanitize_ip_address(self):
        """IP addresses are redacted."""
        text = "Connected to 192.168.1.100 on port 8080"
        result = sanitize_string(text)

        assert "192.168.1.100" not in result
        assert "<REDACTED_IP>" in result

    def test_sanitize_token(self):
        """Long hex tokens (40+ chars) are redacted."""
        token = "a" * 64
        text = f"Authorization: Bearer {token}"
        result = sanitize_string(text)

        assert token not in result
        assert "<REDACTED_TOKEN>" in result


class TestSanitizeDict:
    """Tests for sanitize_dict function."""

    def test_sanitize_dict_redacts_password(self):
        """Sensitive keys like 'password' are fully redacted."""
        data = {
            "username": "admin",
            "password": "super-secret-pass",
            "host": "192.168.1.1",
        }
        result = sanitize_dict(data)

        assert result["password"] == "<REDACTED>"
        assert "super-secret-pass" not in str(result)
        # IP should also be redacted
        assert "192.168.1.1" not in str(result)

    def test_sanitize_preserves_normal_data(self):
        """Non-sensitive data is preserved as-is."""
        data = {
            "model_id": "gpt2",
            "max_tokens": 100,
            "temperature": 0.7,
            "enabled": True,
        }
        result = sanitize_dict(data)

        assert result["model_id"] == "gpt2"
        assert result["max_tokens"] == 100
        assert result["temperature"] == 0.7
        assert result["enabled"] is True
