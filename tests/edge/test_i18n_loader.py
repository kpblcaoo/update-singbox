import os
import tempfile
import json
from sboxmgr.i18n.loader import LanguageLoader


def test_invalid_json_fallback():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Создаём невалидный JSON
        bad_path = os.path.join(tmpdir, "bad.json")
        with open(bad_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json }")
        # en.json как fallback
        en_path = os.path.join(tmpdir, "en.json")
        with open(en_path, "w", encoding="utf-8") as f:
            json.dump({"test": "ok"}, f)
        lang = LanguageLoader("bad", base_dir=tmpdir)
        assert lang.get("test") == "ok"


def test_missing_file_fallback():
    with tempfile.TemporaryDirectory() as tmpdir:
        en_path = os.path.join(tmpdir, "en.json")
        with open(en_path, "w", encoding="utf-8") as f:
            json.dump({"test": "ok"}, f)
        lang = LanguageLoader("missing", base_dir=tmpdir)
        assert lang.get("test") == "ok"


def test_ansi_escape_sanitization():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_str = "Hello\x1b[31mWorld"
        test_path = os.path.join(tmpdir, "en.json")
        with open(test_path, "w", encoding="utf-8") as f:
            json.dump({"test": test_str}, f)
        lang = LanguageLoader("en", base_dir=tmpdir)
        assert "\x1b" not in lang.get("test")
        assert lang.get("test") == "HelloWorld"


def test_too_long_string_truncated():
    with tempfile.TemporaryDirectory() as tmpdir:
        long_str = "A" * 1000
        test_path = os.path.join(tmpdir, "en.json")
        with open(test_path, "w", encoding="utf-8") as f:
            json.dump({"test": long_str}, f)
        lang = LanguageLoader("en", base_dir=tmpdir)
        assert len(lang.get("test")) == 500


def test_key_not_found_returns_key():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = os.path.join(tmpdir, "en.json")
        with open(test_path, "w", encoding="utf-8") as f:
            json.dump({"test": "ok"}, f)
        lang = LanguageLoader("en", base_dir=tmpdir)
        assert lang.get("not_found") == "not_found" 