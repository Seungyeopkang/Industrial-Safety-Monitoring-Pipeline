import unittest

from pydantic import ValidationError

from rag.danger_contract import eligible_danger_records
from vlm.analyzer import SYSTEM_INSTRUCTION, _build_user_prompt
from vlm.schema import VLMSceneAnalysis


def valid_payload():
    return {
        "workers": [{
            "worker_id": "Worker 1", "helmet": "unknown", "vest": "worn",
            "location_description": "작업 구역", "activity": "작업 중",
            "proximity_to_hazard": "가장자리 인접", "visibility": "partial", "occlusion_level": "severe",
        }],
        "scene_context": {"work_zone_type": "construction", "lighting_condition": "low-light"},
        "overall_description": "가림과 저조도로 PPE 판독이 제한됨",
        "immediate_dangers": [{
            "danger_type": "fall_risk", "worker_ids": ["Worker 1"],
            "description": "가장자리 인접 작업으로 추락 위험", "evidence": "이미지에서 가장자리와 근로자 위치가 확인됨",
            "confidence": 0.7,
        }],
        "analysis_limitations": ["부분 가림", "저조도"],
        "vlm_confidence": 0.6,
    }


class VlmContractTests(unittest.TestCase):
    def test_occlusion_and_unknown_parse(self):
        parsed = VLMSceneAnalysis.model_validate(valid_payload())
        self.assertEqual(parsed.workers[0].helmet.value, "unknown")
        self.assertEqual(parsed.workers[0].occlusion_level.value, "severe")

    def test_no_detection_and_empty_dangers_are_valid(self):
        payload = valid_payload()
        payload["workers"] = []
        payload["immediate_dangers"] = []
        VLMSceneAnalysis.model_validate(payload)

    def test_confidence_bounds_are_enforced(self):
        payload = valid_payload()
        payload["vlm_confidence"] = 1.1
        with self.assertRaises(ValidationError):
            VLMSceneAnalysis.model_validate(payload)

    def test_only_grounded_typed_dangers_cross_rag_boundary(self):
        valid = valid_payload()["immediate_dangers"][0]
        invalid = {"danger_type": "unknown", "description": "모호함", "evidence": "", "confidence": 0.9}
        self.assertEqual(eligible_danger_records(["자유 문자열", invalid, valid]), [valid])

    def test_prompt_contract_prohibits_ungrounded_dangers(self):
        for variant in ("default", "role_stepwise", "fewshot", "constraints", "role_constraints", "role_constraints_fewshot", "safety_first"):
            prompt = SYSTEM_INSTRUCTION + "\n" + _build_user_prompt(variant, "Detector metadata: (no objects detected)")
            self.assertIn("unknown", prompt)
            self.assertIn("analysis_limitations", prompt)
            self.assertIn("근거(evidence)", prompt)
            self.assertIn("추측", prompt)
            self.assertIn("missing_ppe danger", prompt)
            self.assertIn("partial/severe occlusion", prompt)


if __name__ == "__main__":
    unittest.main()
