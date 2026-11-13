import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import speed_test


class FakeResponse:
    def __init__(self, chunks):
        self.chunks = iter(chunks)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return next(self.chunks, b"")


class FormatBytesTests(unittest.TestCase):
    def test_formats_bytes_and_decimal_kilobytes(self):
        self.assertEqual(speed_test.format_bytes(42), "42.00 B")
        self.assertEqual(speed_test.format_bytes(1500), "1.50 kB")

    def test_formats_megabytes(self):
        self.assertEqual(speed_test.format_bytes(2_000_000), "2.00 MB")


class DownloadTests(unittest.TestCase):
    @patch("speed_test.urlopen")
    def test_reads_until_complete_and_counts_all_bytes(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse([b"abc", b"defg", b""])
        duration, byte_count = speed_test.download_once("https://example.test/file", 5)
        self.assertGreaterEqual(duration, 0)
        self.assertEqual(byte_count, 7)
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.test/file")
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 5)

    @patch("speed_test.download_once", return_value=(0.5, 1000))
    def test_main_runs_exactly_ten_sequential_downloads(self, mock_download, _stdout=None):
        with patch("sys.argv", ["speed_test.py", "https://example.test/file"]):
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                result = speed_test.main()
        self.assertEqual(result, 0)
        self.assertEqual(mock_download.call_count, 10)
        self.assertIn("10,000 байт", output.getvalue())
        self.assertIn("Средняя скорость скачивания", output.getvalue())

    @patch("speed_test.download_once", side_effect=HTTPError(
        "https://example.test/file", 404, "Not Found", {}, None
    ))
    def test_http_error_returns_nonzero(self, _mock, _stdout=None):
        with patch("sys.argv", ["speed_test.py", "https://example.test/file"]):
            with patch("sys.stderr", new_callable=io.StringIO):
                result = speed_test.main()
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
