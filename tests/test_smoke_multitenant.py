from __future__ import annotations

import unittest

from scripts.smoke_multitenant import _multipart_body


class SmokeMultitenantScriptTests(unittest.TestCase):
    def test_multipart_body_contains_file_part(self) -> None:
        body = _multipart_body(
            boundary="boundary",
            field_name="file",
            filename="manual.txt",
            content=b"hello",
            content_type="text/plain",
        )

        self.assertIn(b"--boundary", body)
        self.assertIn(b'name="file"; filename="manual.txt"', body)
        self.assertIn(b"Content-Type: text/plain", body)
        self.assertIn(b"\r\n\r\nhello\r\n--boundary--", body)


if __name__ == "__main__":
    unittest.main()
