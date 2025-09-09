from django.test import SimpleTestCase
from ai.validators import validate_role_output, SchemaError


class NegativeRoleValidatorsTests(SimpleTestCase):
    def test_planner_missing_sections(self):
        with self.assertRaises(SchemaError):
            validate_role_output('plan', {'schema_version': '1'})

    def test_writer_rejects_json_like(self):
        with self.assertRaises(SchemaError):
            validate_role_output('write', {'draft': "{\n  'a': 1\n}"})

    def test_reviser_missing_diff(self):
        with self.assertRaises(SchemaError):
            validate_role_output('revise', {'revised': 'text'})

    def test_formatter_missing_field(self):
        with self.assertRaises(SchemaError):
            validate_role_output('format', {'formatted': 'oops'})
