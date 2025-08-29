from django.test import SimpleTestCase
from ai.provider import CompositeProvider, Gpt5Provider, GeminiProvider


FILE_REFS = [
    {"id": 1, "name": "budget.xlsx", "ocr_text": "Line items: laptops, training, travel."},
    {"id": 2, "name": "scope.pdf", "ocr_text": "Objectives include outreach and capacity building."},
]


class FileRefsPromptingTests(SimpleTestCase):
    def test_gpt5_write_includes_file_refs_context(self):
        p = Gpt5Provider()
        res = p.write(section_id="summary", answers={"objective": "X"}, file_refs=FILE_REFS)
        assert "[context:sources]" in res.text
        assert "budget.xlsx" in res.text
        assert "Objectives include outreach" in res.text

    def test_gemini_revise_includes_file_refs_context(self):
        p = GeminiProvider()
        res = p.revise(base_text="Base", change_request="Polish", file_refs=FILE_REFS)
        assert "[context:sources]" in res.text
        assert "scope.pdf" in res.text

    def test_composite_routes_and_includes_context(self):
        p = CompositeProvider()
        write = p.write(section_id="summary", answers={"objective": "X"}, file_refs=FILE_REFS)
        assert write.model_id == "gpt-5"
        assert "[context:sources]" in write.text
        rev = p.revise(base_text="Hi", change_request="Tighten", file_refs=FILE_REFS)
        assert rev.model_id == "gemini"
        assert "[context:sources]" in rev.text
