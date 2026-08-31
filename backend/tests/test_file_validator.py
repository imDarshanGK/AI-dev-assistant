"""
Regression tests for file validator service (v2).

Tests for file validation including:
- File extension validation
- Double extension detection
- MIME type validation
"""

import pytest

from app.utils.file_validator import (
    get_file_extension,
    has_double_extension,
    validate_file_extension,
    detect_mime_type,
    validate_mime_type,
    validate_file,
)
from app.utils.upload_config import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    BLOCKED_EXTENSIONS,
    UPLOAD_ERROR_MESSAGES,
    max_file_size,
)


class TestGetFileExtension:
    """Tests for file extension extraction."""

    def test_simple_extension(self):
        """Should extract extension from simple filename."""
        assert get_file_extension("file.py") == ".py"
        assert get_file_extension("script.js") == ".js"
        assert get_file_extension("data.txt") == ".txt"

    def test_uppercase_extension(self):
        """Should return lowercase extension for uppercase filenames."""
        assert get_file_extension("FILE.PY") == ".py"
        assert get_file_extension("Script.JS") == ".js"

    def test_no_extension(self):
        """Should return empty string for files without extension."""
        assert get_file_extension("Makefile") == ""
        assert get_file_extension("README") == ""

    def test_hidden_file(self):
        """Should handle hidden files correctly."""
        assert get_file_extension(".gitignore") == ".gitignore"
        assert get_file_extension(".env") == ".env"

    def test_double_extension(self):
        """Should return only the final extension."""
        assert get_file_extension("archive.tar.gz") == ".gz"
        assert get_file_extension("backup.tar.bz2") == ".bz2"


class TestHasDoubleExtension:
    """Tests for double extension detection."""

    def test_single_extension_returns_false(self):
        """Should return False for files with single extension."""
        assert not has_double_extension("file.py")
        assert not has_double_extension("script.js")
        assert not has_double_extension("data.txt")

    def test_double_allowed_extension_returns_false(self):
        """Should return False if all extensions are allowed."""
        assert not has_double_extension("file.py.py")
        assert not has_double_extension("script.js.js")

    def test_double_blocked_extension_returns_true(self):
        """Should return True if any intermediate extension is blocked."""
        assert has_double_extension("file.exe.py")
        assert has_double_extension("malware.bat.txt")
        assert has_double_extension("script.ps1.js")

    def test_triple_extension_blocked(self):
        """Should detect blocked extensions in triple extensions."""
        assert has_double_extension("archive.exe.tar.gz")
        assert has_double_extension("data.bat.json.py")

    def test_no_extension(self):
        """Should return False for files without extension."""
        assert not has_double_extension("Makefile")
        assert not has_double_extension("README")


class TestValidateFileExtension:
    """Tests for file extension validation."""

    def test_valid_extension(self):
        """Should accept valid file extensions."""
        for ext in ALLOWED_EXTENSIONS:
            filename = f"file{ext}"
            result = validate_file_extension(filename)
            assert result == ext

    def test_invalid_extension(self):
        """Should raise ValueError for unsupported extensions."""
        with pytest.raises(ValueError, match=UPLOAD_ERROR_MESSAGES["invalid_extension"]):
            validate_file_extension("file.pdf")

        with pytest.raises(ValueError, match=UPLOAD_ERROR_MESSAGES["invalid_extension"]):
            validate_file_extension("image.png")

    def test_no_extension(self):
        """Should raise ValueError for files without extension."""
        with pytest.raises(ValueError, match=UPLOAD_ERROR_MESSAGES["invalid_extension"]):
            validate_file_extension("Makefile")

    def test_blocked_extension(self):
        """Should raise ValueError for blocked executable extensions."""
        for blocked_ext in BLOCKED_EXTENSIONS:
            filename = f"malware{blocked_ext}"
            with pytest.raises(ValueError, match=UPLOAD_ERROR_MESSAGES["blocked_file"]):
                validate_file_extension(filename)

    def test_double_extension_with_blocked(self):
        """Should raise ValueError for double extensions with blocked file."""
        with pytest.raises(ValueError, match=UPLOAD_ERROR_MESSAGES["blocked_file"]):
            validate_file_extension("exploit.exe.py")

        with pytest.raises(ValueError, match=UPLOAD_ERROR_MESSAGES["blocked_file"]):
            validate_file_extension("virus.bat.txt")

    def test_case_insensitive_validation(self):
        """Should validate extensions case-insensitively."""
        result = validate_file_extension("FILE.PY")
        assert result == ".py"

        result = validate_file_extension("Script.JS")
        assert result == ".js"


class TestDetectMimeType:
    """Tests for MIME type detection."""

    def test_detect_python_mime_type(self):
        """Should detect Python file MIME type."""
        content = b"print('hello')"
        mime = detect_mime_type(content)
        assert mime is not None
        # Python files may be detected as various text types
        assert mime in ALLOWED_MIME_TYPES[".py"]

    def test_detect_javascript_mime_type(self):
        """Should detect JavaScript file MIME type."""
        content = b"console.log('hello');"
        mime = detect_mime_type(content)
        assert mime is not None
        # JS files may be detected as text/plain or application/javascript
        assert mime in ALLOWED_MIME_TYPES[".js"]

    def test_detect_text_mime_type(self):
        """Should detect plain text MIME type."""
        content = b"This is plain text"
        mime = detect_mime_type(content)
        assert mime is not None
        # Text files should be detected as text/plain
        assert mime in ALLOWED_MIME_TYPES[".txt"]

    def test_detect_java_mime_type(self):
        """Should detect Java file MIME type."""
        content = b"public class Hello { public static void main(String[] args) {} }"
        mime = detect_mime_type(content)
        assert mime is not None
        # Java files may be detected as various types
        assert mime in ALLOWED_MIME_TYPES[".java"]

    def test_detect_cpp_mime_type(self):
        """Should detect C++ file MIME type."""
        content = b"#include <iostream>\nint main() { return 0; }"
        mime = detect_mime_type(content)
        assert mime is not None
        # C++ files may be detected as various types
        assert mime in ALLOWED_MIME_TYPES[".cpp"]

    def test_detect_empty_file(self):
        """Should handle empty files."""
        content = b""
        mime = detect_mime_type(content)
        assert mime is not None


class TestValidateMimeType:
    """Tests for MIME type validation against extension."""

    def test_valid_python_mime_type(self):
        """Should accept valid Python MIME types."""
        ext = ".py"
        content = b"print('test')"
        result = validate_mime_type(ext=ext, filecontent=content)
        assert result is not None
        assert result in ALLOWED_MIME_TYPES[ext]

    def test_valid_javascript_mime_type(self):
        """Should accept valid JavaScript MIME types."""
        ext = ".js"
        content = b"console.log('test');"
        result = validate_mime_type(ext=ext, filecontent=content)
        assert result is not None
        assert result in ALLOWED_MIME_TYPES[ext]

    def test_valid_text_mime_type(self):
        """Should accept text MIME type for .txt files."""
        ext = ".txt"
        content = b"This is text content"
        result = validate_mime_type(ext=ext, filecontent=content)
        assert result is not None
        assert result in ALLOWED_MIME_TYPES[ext]

    def test_valid_typescript_mime_type(self):
        """Should accept valid TypeScript MIME types."""
        ext = ".ts"
        content = b"const hello: string = 'world';"
        result = validate_mime_type(ext=ext, filecontent=content)
        assert result is not None
        assert result in ALLOWED_MIME_TYPES[ext]

    def test_invalid_mime_type_for_extension(self):
        """Should raise ValueError for mismatched MIME types."""
        ext = ".py"
        # Binary content that won't match Python MIME types
        content = b"\x89PNG\r\n\x1a\n"  # PNG file header
        with pytest.raises(ValueError, match=UPLOAD_ERROR_MESSAGES["invalid_mime"]):
            validate_mime_type(ext=ext, filecontent=content)


class TestValidateFile:
    """Tests for complete file validation."""

    def test_valid_python_file(self):
        """Should validate a valid Python file."""
        filename = "script.py"
        content = b"def hello():\n    print('world')\n"
        result = validate_file(filename=filename, filecontent=content)
        assert result is not None

    def test_valid_javascript_file(self):
        """Should validate a valid JavaScript file."""
        filename = "app.js"
        content = b"function hello() { console.log('world'); }"
        result = validate_file(filename=filename, filecontent=content)
        assert result is not None

    def test_valid_text_file(self):
        """Should validate a valid text file."""
        filename = "readme.txt"
        content = b"This is a readme file"
        result = validate_file(filename=filename, filecontent=content)
        assert result is not None

    def test_valid_typescript_file(self):
        """Should validate a valid TypeScript file."""
        filename = "app.ts"
        content = b"const greeting: string = 'hello';"
        result = validate_file(filename=filename, filecontent=content)
        assert result is not None

    def test_valid_java_file(self):
        """Should validate a valid Java file."""
        filename = "HelloWorld.java"
        content = b"public class HelloWorld { public static void main(String[] args) {} }"
        result = validate_file(filename=filename, filecontent=content)
        assert result is not None

    def test_valid_cpp_file(self):
        """Should validate a valid C++ file."""
        filename = "main.cpp"
        content = b"#include <iostream>\nint main() { return 0; }"
        result = validate_file(filename=filename, filecontent=content)
        assert result is not None

    def test_invalid_extension_fails(self):
        """Should fail validation for invalid extensions."""
        with pytest.raises(ValueError, match=UPLOAD_ERROR_MESSAGES["invalid_extension"]):
            validate_file(filename="image.png", filecontent=b"fake content")

    def test_blocked_extension_fails(self):
        """Should fail validation for blocked extensions."""
        with pytest.raises(ValueError, match=UPLOAD_ERROR_MESSAGES["blocked_file"]):
            validate_file(filename="malware.exe", filecontent=b"fake content")

    def test_double_extension_with_blocked_fails(self):
        """Should fail validation for double extensions with blocked files."""
        with pytest.raises(ValueError, match=UPLOAD_ERROR_MESSAGES["blocked_file"]):
            validate_file(filename="exploit.exe.py", filecontent=b"fake content")

    def test_no_extension_fails(self):
        """Should fail validation for files without extension."""
        with pytest.raises(ValueError, match=UPLOAD_ERROR_MESSAGES["invalid_extension"]):
            validate_file(filename="Makefile", filecontent=b"fake content")

    def test_case_insensitive_validation(self):
        """Should handle filenames case-insensitively."""
        filename = "SCRIPT.PY"
        content = b"print('hello')"
        result = validate_file(filename=filename, filecontent=content)
        assert result is not None


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_long_filename(self):
        """Should handle very long filenames."""
        long_name = "a" * 200 + ".py"
        content = b"print('test')"
        result = validate_file(filename=long_name, filecontent=content)
        assert result is not None

    def test_filename_with_spaces(self):
        """Should handle filenames with spaces."""
        filename = "my file name.py"
        content = b"print('test')"
        result = validate_file(filename=filename, filecontent=content)
        assert result is not None

    def test_filename_with_special_characters(self):
        """Should handle filenames with special characters."""
        filename = "file-name_2024.py"
        content = b"print('test')"
        result = validate_file(filename=filename, filecontent=content)
        assert result is not None

    def test_filename_with_unicode(self):
        """Should handle filenames with unicode characters."""
        filename = "файл.py"  # Russian characters
        content = b"print('test')"
        result = validate_file(filename=filename, filecontent=content)
        assert result is not None

    def test_empty_content(self):
        """Should handle files with empty content."""
        filename = "empty.py"
        content = b""
        result = validate_file(filename=filename, filecontent=content)
        assert result is not None

    def test_large_content_within_limit(self):
        """Should handle files with large content within limits."""
        filename = "large.py"
        # Create content just under the file size limit
        content = b"x = " + b"1" * (max_file_size - 100)
        result = validate_file(filename=filename, filecontent=content)
        assert result is not None

    def test_path_traversal_attempt(self):
        """Should handle filenames with path traversal attempts."""
        filename = "../../etc/passwd.py"
        content = b"test content"
        result = validate_file(filename=filename, filecontent=content)
        assert result is not None