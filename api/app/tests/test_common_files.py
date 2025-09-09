from django.test import SimpleTestCase
from app.common import files


class FileUtilsTests(SimpleTestCase):
    def test_safe_filename_basic(self):
        self.assertEqual(files.safe_filename('My Report.pdf'), 'My-Report.pdf')

    def test_safe_filename_unicode_and_length(self):
        name = 'Åccentuated 文件 名称 😀.txt'
        out = files.safe_filename(name, max_length=32)
        self.assertTrue(out.endswith('.txt'))
        self.assertLessEqual(len(out), 32)
        self.assertNotIn(' ', out)

    def test_checksum_equivalence_bytes_and_path(self):
        data = b'hello world' * 1000
        c1 = files.compute_checksum(data)
        # write temp file
        import tempfile
        import os

        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
            c2 = files.compute_checksum(path)
        finally:
            os.remove(path)
        self.assertEqual(c1.hex, c2.hex)

    def test_read_text_file_truncation(self):
        import tempfile
        import os

        content = ('abc' * 100).encode()
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(content)
            text = files.read_text_file(path, max_bytes=50)
        finally:
            os.remove(path)
        self.assertTrue(text.endswith('…'))

    def test_write_bytes_and_iter_chunks(self):
        import tempfile
        import os

        data = b'x' * (2 * 1024 * 1024 + 123)
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            files.write_bytes(path, data)
            with open(path, 'rb') as f:
                total = 0
                for chunk in files.iter_chunks(f, chunk_size=1_000_000):
                    total += len(chunk)
        finally:
            os.remove(path)
        self.assertEqual(total, len(data))
