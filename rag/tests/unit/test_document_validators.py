"""Unit tests for document validators and the DocValidators factory."""
from unittest.mock import MagicMock, patch

import pytest

from core.data_sources.types.document.validators.extension_validator import ExtensionValidator
from core.data_sources.types.document.validators.size_validator import SizeValidator, DEFAULT_MAX_FILE_SIZE_BYTES
from core.data_sources.types.document.validators.duplicate_validator import DuplicateValidator
from core.data_sources.types.document.validators.name_duplicate_validator import NameDuplicateValidator
from core.data_sources.types.document.validators.factory import DocValidators


SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".md", ".txt"]


# ═══════════════════════════════════════════════════════════════════════════════
# ExtensionValidator
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.document
class TestExtensionValidator:
    """Validates that only files with allowed extensions are accepted for upload."""

    @pytest.fixture
    def validator(self):
        return ExtensionValidator(supported_extensions=SUPPORTED_EXTENSIONS)

    @pytest.mark.parametrize("filename", [
        "report.pdf",
        "REPORT.PDF",
        "notes.docx",
        "slide.pptx",
        "readme.md",
        "log.txt",
    ])
    def test_valid_extensions_pass(self, validator, filename):
        """Files with supported extensions (.pdf, .docx, .pptx, .md, .txt) must be accepted.

        Expected: ok=True, issue=None.
        Logs: No warnings or errors.
        """
        ok, issue = validator.validate(source_name=filename)
        assert ok is True
        assert issue is None

    @pytest.mark.parametrize("filename,expected_ext", [
        ("malware.exe", ".exe"),
        ("image.zip", ".zip"),
        ("data.csv", ".csv"),
    ])
    def test_unsupported_extensions_rejected(self, validator, filename, expected_ext):
        """Files with unsupported extensions must be rejected with a descriptive error.

        Expected: ok=False, issue message contains the rejected extension.
        Logs: No warnings or errors.
        """
        ok, issue = validator.validate(source_name=filename)
        assert ok is False
        assert issue is not None
        assert "not supported" in issue["message"]
        assert expected_ext in issue["message"]

    def test_no_extension_rejected(self, validator):
        """A filename without any extension must be rejected.

        Expected: ok=False, issue is not None.
        Logs: No warnings or errors.
        """
        ok, issue = validator.validate(source_name="readme")
        assert ok is False
        assert issue is not None

    def test_empty_filename_passes(self, validator):
        """An empty filename bypasses extension validation (defensive guard).

        Expected: ok=True, issue=None.
        Logs: No warnings or errors.
        """
        ok, issue = validator.validate(source_name="")
        assert ok is True
        assert issue is None

    def test_issue_contains_supported_types(self, validator):
        """The rejection message must list all supported extensions so the user knows what is allowed.

        Expected: ok=False, every supported extension appears in the error message.
        Logs: No warnings or errors.
        """
        ok, issue = validator.validate(source_name="image.zip")
        assert ok is False
        for ext in SUPPORTED_EXTENSIONS:
            assert ext in issue["message"]


# ═══════════════════════════════════════════════════════════════════════════════
# SizeValidator
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.document
class TestSizeValidator:
    """Validates that uploaded files do not exceed the configured size limit."""

    @pytest.fixture
    def validator(self):
        return SizeValidator()

    def test_file_under_limit_passes(self, tmp_path, validator):
        """A file well under the size limit must be accepted.

        Expected: ok=True, issue=None.
        Logs: No warnings or errors.
        """
        f = tmp_path / "small.pdf"
        f.write_bytes(b"x" * 1024)
        ok, issue = validator.validate(doc_path=str(f))
        assert ok is True
        assert issue is None

    @pytest.mark.parametrize("file_size,max_bytes,expected_ok", [
        (1025, 1024, False),
        (2048, 2048, True),
        (600, 500, False),
    ])
    def test_size_boundary(self, tmp_path, file_size, max_bytes, expected_ok):
        """Boundary conditions: 1 byte over rejects, exactly at limit accepts, custom limit enforced.

        Expected: ok matches expected_ok; rejection message contains 'exceeds'.
        Logs: No warnings or errors.
        """
        validator = SizeValidator(max_file_size_bytes=max_bytes)
        f = tmp_path / "boundary.pdf"
        f.write_bytes(b"x" * file_size)
        ok, issue = validator.validate(doc_path=str(f))
        assert ok is expected_ok
        if not expected_ok:
            assert issue is not None
            assert "exceeds" in issue["message"]

    def test_nonexistent_file_passes(self, validator):
        """A file that does not exist on disk must be allowed (fail-open design).

        Expected: ok=True, issue=None.
        Logs: No warnings or errors.
        """
        ok, issue = validator.validate(doc_path="/no/such/file.pdf")
        assert ok is True
        assert issue is None

    @patch("os.path.getsize", side_effect=OSError("disk error"))
    @patch("os.path.exists", return_value=True)
    def test_os_error_passes_gracefully(self, _mock_exists, _mock_size, validator):
        """When os.path.getsize raises an OSError, the validator fails open.

        Expected: ok=True, issue=None (upload allowed despite disk error).
        Logs: WARNING 'Size validation failed for /some/path.pdf, allowing upload: disk error'
        """
        ok, issue = validator.validate(doc_path="/some/path.pdf")
        assert ok is True
        assert issue is None


# ═══════════════════════════════════════════════════════════════════════════════
# DuplicateValidator
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.document
class TestDuplicateValidator:
    """Validates that file content (MD5 hash) is not a duplicate of an already-processed file."""

    def _make_validator(self, is_dup=False, raises=None):
        checker = MagicMock()
        if raises:
            checker.is_duplicate.side_effect = raises
        else:
            checker.is_duplicate.return_value = is_dup
        return DuplicateValidator(duplicate_checker=checker)

    def test_not_duplicate_passes(self):
        """A file whose MD5 has never been seen before must be accepted.

        Expected: ok=True, issue=None.
        Logs: No warnings or errors.
        """
        validator = self._make_validator(is_dup=False)
        ok, issue = validator.validate(source_name="report.pdf")
        assert ok is True
        assert issue is None

    def test_duplicate_rejected(self):
        """A file whose MD5 already exists must be rejected with an error referencing the filename.

        Expected: ok=False, issue message contains 'report.pdf'.
        Logs: No warnings or errors (this is a normal rejection, not an infrastructure failure).
        """
        validator = self._make_validator(is_dup=True)
        ok, issue = validator.validate(source_name="report.pdf")
        assert ok is False
        assert issue is not None
        assert "report.pdf" in issue["message"]

    def test_checker_exception_passes_gracefully(self):
        """When the duplicate-checker raises an exception (e.g. DB down), the validator fails open.

        Expected: ok=True, issue=None (upload allowed despite the error).
        Logs: WARNING 'Duplicate check failed for report.pdf, allowing upload: db down'
        """
        validator = self._make_validator(raises=RuntimeError("db down"))
        ok, issue = validator.validate(source_name="report.pdf")
        assert ok is True
        assert issue is None


# ═══════════════════════════════════════════════════════════════════════════════
# NameDuplicateValidator
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.document
class TestNameDuplicateValidator:
    """Validates that no other source with the same filename exists for this user."""

    def _make_validator(self, is_dup=False, status=None):
        checker = MagicMock()
        checker.is_duplicate_name.return_value = (is_dup, status)
        return NameDuplicateValidator(name_duplicate_checker=checker)

    def test_no_duplicate_passes(self):
        """A filename that has never been uploaded by this user must be accepted.

        Expected: ok=True, issue=None.
        Logs: No warnings or errors.
        """
        validator = self._make_validator(is_dup=False, status=None)
        ok, issue = validator.validate(source_name="new_doc.pdf", upload_by="alice")
        assert ok is True
        assert issue is None

    def test_duplicate_name_rejected(self):
        """A filename that already exists (with pipeline status DONE) must be rejected.

        Expected: ok=False, issue message contains the filename and the existing pipeline status.
        Logs: No warnings or errors.
        """
        validator = self._make_validator(is_dup=True, status="DONE")
        ok, issue = validator.validate(source_name="existing.pdf", upload_by="alice")
        assert ok is False
        assert "existing.pdf" in issue["message"]
        assert "DONE" in issue["message"]

    def test_empty_source_name_passes(self):
        """An empty source name bypasses duplicate-name checking (defensive guard).

        Expected: ok=True, issue=None.
        Logs: No warnings or errors.
        """
        validator = self._make_validator(is_dup=True)
        ok, issue = validator.validate(source_name="", upload_by="alice")
        assert ok is True
        assert issue is None


# ═══════════════════════════════════════════════════════════════════════════════
# DocValidators factory
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.document
class TestDocValidatorsFactory:
    """Validates the DocValidators factory that assembles the validator chain."""

    @pytest.fixture
    def dup_mock(self):
        return MagicMock(spec=DuplicateValidator)

    @pytest.fixture
    def factory(self, dup_mock):
        return DocValidators(
            duplicate_validator=dup_mock,
            extension_validator=MagicMock(spec=ExtensionValidator),
            size_validator=MagicMock(spec=SizeValidator),
            name_duplicate_validator=MagicMock(spec=NameDuplicateValidator),
        )

    def test_full_validation_returns_all_four(self, factory):
        """Normal mode must return all four validators in the chain.

        Expected: len(validators) == 4.
        Logs: No warnings or errors.
        """
        validators = factory.create_validators(skip_validation=False)
        assert len(validators) == 4

    def test_skip_validation_returns_only_duplicate(self, factory, dup_mock):
        """Skip-validation mode must return only the DuplicateValidator (content-hash check).

        Expected: len(validators) == 1, and the single validator is the DuplicateValidator instance.
        Logs: No warnings or errors.
        """
        validators = factory.create_validators(skip_validation=True)
        assert len(validators) == 1
        assert validators[0] is dup_mock
