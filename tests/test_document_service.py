from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.document_service import DocumentService, _safe_filename


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


if __name__ == "__main__":
    unittest.main()
