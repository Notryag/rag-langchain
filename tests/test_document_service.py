from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from app.services.document_service import (
    DocumentAlreadyProcessingError,
    DocumentService,
    DocumentTooLargeError,
    DocumentUploadError,
    _safe_filename,
    _validate_upload,
)


class DocumentServiceTests(unittest.TestCase):
    def test_safe_filename_strips_paths_and_special_chars(self) -> None:
        self.assertEqual(_safe_filename("../产品 手册.pdf"), "产品_手册.pdf")
        self.assertEqual(_safe_filename(""), "upload.bin")

    def test_save_file_writes_under_user_and_kb_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = DocumentService(upload_dir=tmp_dir)

            path = service._save_file(user_id=7, kb_id=11, filename="../manual.txt", content=b"hello")

            self.assertEqual(path.read_bytes(), b"hello")
            self.assertEqual(path.parent, Path(tmp_dir) / "7" / "11")
            self.assertTrue(path.name.endswith("_manual.txt"))

    def test_save_file_stream_enforces_size_limit_and_removes_partial_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = DocumentService(upload_dir=tmp_dir)

            with self.assertRaises(DocumentTooLargeError):
                service._save_file_stream(
                    user_id=7,
                    kb_id=11,
                    filename="manual.txt",
                    source=BytesIO(b"too large"),
                    max_bytes=4,
                )

            self.assertEqual(list((Path(tmp_dir) / "7" / "11").iterdir()), [])

    def test_validate_upload_rejects_extension_and_content_type(self) -> None:
        with self.assertRaises(DocumentUploadError):
            _validate_upload(filename="payload.exe", content_type="application/octet-stream")
        with self.assertRaises(DocumentUploadError):
            _validate_upload(filename="manual.txt", content_type="application/x-msdownload")

        _validate_upload(filename="manual.PDF", content_type="application/pdf; charset=binary")

    def test_process_sync_rejects_document_already_processing(self) -> None:
        class FakeSession:
            def scalar(self, statement):
                self.statement = statement
                return type("Document", (), {"status": "processing"})()

        with self.assertRaises(DocumentAlreadyProcessingError):
            DocumentService().process_sync(FakeSession(), user_id=1, document_id=2)


if __name__ == "__main__":
    unittest.main()
