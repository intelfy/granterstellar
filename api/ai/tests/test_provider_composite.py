from django.test import SimpleTestCase
from ai.provider import CompositeProvider


class CompositeProviderTests(SimpleTestCase):
    def test_write_uses_gpt5_and_does_not_format(self):
        p = CompositeProvider()
        res = p.write(section_id="summary", answers={"objective": "X"})
        assert res.model_id == "gpt-5"
        assert "[gemini:" not in res.text

    def test_format_final_uses_gemini(self):
        p = CompositeProvider()
        res = p.format_final(full_text="Hello", template_hint="std")
        assert res.model_id == "gemini"
        assert res.text.startswith("[gemini:final_format")
