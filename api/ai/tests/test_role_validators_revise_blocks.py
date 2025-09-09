from django.test import SimpleTestCase
from ai.validators import validate_reviser_output, SchemaError


class ReviserValidatorBlocksTests(SimpleTestCase):
    def test_accepts_structured_blocks(self):
        data = {
            "revised": "Hello brave world",
            "diff": {
                "change_ratio": 0.25,
                "blocks": [
                    {"type": "add", "before": "", "after": "brave", "similarity": 0.0},
                    {"type": "equal", "before": "Hello", "after": "Hello", "similarity": 1.0},
                ],
            },
        }
        validate_reviser_output(data)  # should not raise

    def test_rejects_missing_fields_in_block(self):
        bad = {
            "revised": "text",
            "diff": {"blocks": [{"before": "a", "after": "b"}]},  # missing type
        }
        with self.assertRaises(SchemaError):
            validate_reviser_output(bad)

    def test_rejects_invalid_similarity_type(self):
        bad = {
            "revised": "text",
            "diff": {"blocks": [{"type": "equal", "before": "a", "after": "a", "similarity": "x"}]},
        }
        with self.assertRaises(SchemaError):
            validate_reviser_output(bad)

    def test_legacy_schema_still_valid(self):
        legacy = {"revised": "text", "diff": {"added": [], "removed": []}}
        validate_reviser_output(legacy)
