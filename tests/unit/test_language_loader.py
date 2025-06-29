
from sboxmgr.i18n.loader import LanguageLoader


def test_get_with_source():
    loader = LanguageLoader(lang="en")
    text, src = loader.get_with_source("cli.help")
    assert isinstance(text, str)
    assert src in {"local", "en", "fallback"}
    # ensure fallback returns key for nonexistent string
    missing, src2 = loader.get_with_source("nonexistent.key")
    assert missing == "nonexistent.key"
    assert src2 == "fallback"


def test_sanitize_ansi_sequences():
    """Test comprehensive ANSI escape sequence sanitization."""
    loader = LanguageLoader(lang="en")
    
    # Test various ANSI sequences
    test_cases = [
        # Basic color codes
        ("\x1b[31mRed text\x1b[0m", "Red text"),
        ("\x1b[1;33mBold yellow\x1b[0m", "Bold yellow"),
        # Multiple sequences
        ("\x1b[32mGreen\x1b[0m and \x1b[34mBlue\x1b[0m", "Green and Blue"),
        # Other ANSI sequences
        ("\x1b(BText\x1b)B", "BTextB"),
        ("\x1bPText\x1b\\", "Text\\"),
        # Mixed content
        ("Normal \x1b[31mcolored\x1b[0m text", "Normal colored text"),
        # Malformed sequences (should be cleaned)
        ("\x1b[31", ""),  # Incomplete sequence
        ("\x1b[", ""),    # Very incomplete
        # No ANSI sequences
        ("Plain text", "Plain text"),
        ("", ""),
    ]
    
    for input_text, expected in test_cases:
        sanitized = loader.sanitize({"test": input_text})["test"]
        assert sanitized == expected, f"Failed for input: {repr(input_text)}"


def test_sanitize_length_limit():
    """Test that sanitization respects length limits."""
    loader = LanguageLoader(lang="en")
    
    # Test key length limit
    long_key = "a" * 150
    result = loader.sanitize({long_key: "value"})
    assert long_key not in result
    
    # Test value length limit
    long_value = "x" * 600
    result = loader.sanitize({"test": long_value})
    assert len(result["test"]) == 500 