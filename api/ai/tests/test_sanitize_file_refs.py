from django.test import SimpleTestCase
from ai.sanitize import sanitize_file_refs


class SanitizeFileRefsTests(SimpleTestCase):
    def test_sanitize_file_refs_keeps_known_fields_and_trims(self):
        refs = [
            {
                'id': '12',
                'url': 'https://example.com/x' * 200,  # will be trimmed
                'name': 'a' * 300,  # will be trimmed to 256
                'content_type': 'application/pdf',
                'size': '1000',
                'ocr_text': 'Hello\nworld' + ('!' * 50000),  # trimmed to 20000
                'extra': 'ignore me',
            }
        ]
        out = sanitize_file_refs(refs)
        assert len(out) == 1
        item = out[0]
        assert item['id'] == 12
        assert item['url'].startswith('https://example.com/')
        assert len(item['name']) == 256
        assert item['content_type'] == 'application/pdf'
        assert item['size'] == 1000
        assert len(item['ocr_text']) == 20000
        assert 'extra' not in item

    def test_non_list_returns_empty(self):
        assert sanitize_file_refs(None) == []
        assert sanitize_file_refs(123) == []

    def test_invalid_items_are_skipped(self):
        out = sanitize_file_refs([{'id': 'x'}, 'bad', None])
        # 'id' invalid will skip that item; others invalid too
        assert out == []
