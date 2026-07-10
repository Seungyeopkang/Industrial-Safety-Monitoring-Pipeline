import unittest

from llm.reporter import REPORT_OUTPUT_CONTRACT, _build_llm_prompt, generate_report
from llm.schema import SafetyReport


class _Usage:
    prompt_token_count = 1
    candidates_token_count = 1


class _Response:
    usage_metadata = _Usage()
    text = "{}"
    parsed = SafetyReport(
        date="1999-01-01", violations=[], overall_severity="NONE",
        recommended_actions=[], citations=[], summary="정상",
    )


class _Models:
    def generate_content(self, **_kwargs):
        return _Response()


class _Client:
    models = _Models()


class LlmContractTests(unittest.TestCase):
    def test_all_variants_keep_common_safety_contract(self):
        for variant in ("default", "sop_grounded", "severity_first"):
            prompt = _build_llm_prompt(variant, "{}", "") + REPORT_OUTPUT_CONTRACT
            self.assertIn("unknown PPE", prompt)
            self.assertIn("citations", prompt)
            self.assertIn("파이프라인 메타데이터", prompt)

    def test_pipeline_date_overrides_model_invented_date(self):
        result = generate_report({}, client=_Client(), report_date="2026-07-10")
        self.assertEqual(result["parsed"].date, "2026-07-10")


if __name__ == "__main__":
    unittest.main()
