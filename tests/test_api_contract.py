import unittest

from api.main import app
from api.schemas import public_job_status, public_pipeline_result


def _pipeline_result():
    return {
        "job_id": "job-1",
        "media": {"type": "image", "representative_frame_path": "C:/private/frame.jpg"},
        "detection": {"model": "model.pt", "summary": [], "detections": [{
            "class_name": "Person", "confidence": 0.9, "bbox": [0, 0, 10, 10],
            "vlm_trigger": False, "trigger_reason": "high_confidence_skip",
        }]},
        "vlm_dispatch": {"should_dispatch": True, "reason": "image_trigger_policy"},
        "vlm": {"parsed": {
            "workers": [{"worker_id": "Worker 1", "helmet": "unknown", "vest": "unknown",
                         "mask": "unknown", "gloves": "unknown", "location_description": "x",
                         "activity": "x", "proximity_to_hazard": "none", "visibility": "partial",
                         "occlusion_level": "partial"}],
            "scene_context": {"work_zone_type": "site", "machinery_present": [],
                              "environmental_hazards": [], "lighting_condition": "good"},
            "overall_description": "x", "immediate_dangers": [], "analysis_limitations": [],
            "vlm_confidence": 0.8,
        }, "latency_ms": 10, "prompt_tokens": 1, "output_tokens": 1, "provider_debug": "secret"},
        "rag": {"status": "complete", "retrieved_count": 1, "clauses": [{
            "source": "law", "article": "art. 1", "title": "title", "score": 0.9,
            "text": "raw legal text", "parent_text": "large internal parent", "doc_id": "internal",
        }], "canonical_queries": [{"query": "internal"}]},
        "llm": {"latency_ms": 10, "prompt_tokens": 1, "output_tokens": 1, "retrieved_count": 1},
        "report": {"date": "2026-07-10", "violations": [], "overall_severity": "NONE",
                   "recommended_actions": [], "citations": [], "summary": "clear"},
        "notion": {"success": True, "page_url": "https://example.test/page", "page_id": "secret"},
        "metrics": {"total_ms": 25, "stages_ms": {"detection": 5, "vlm": 10, "rag": 1, "llm": 9, "notion": 0}},
    }


class APIContractTests(unittest.TestCase):
    def test_result_allow_list_hides_internal_paths_and_rag_bodies(self):
        result = public_pipeline_result(_pipeline_result()).model_dump()
        self.assertNotIn("representative_frame_path", result["media"])
        self.assertEqual(set(result["rag"]["clauses"][0]), {"source", "article", "title", "score"})
        self.assertNotIn("page_id", result["notion"])

    def test_status_allow_list_hides_traceback_and_paths(self):
        result = public_job_status("job-1", {
            "status": "failed", "stage": "error", "message": "safe message", "updated_at": 1,
            "result_path": "C:/private/result.json", "traceback": "secret trace",
        }).model_dump()
        self.assertNotIn("result_path", result)
        self.assertNotIn("traceback", result)

    def test_openapi_declares_result_and_status_contracts(self):
        schema = app.openapi()
        self.assertIn("PipelineResultResponse", schema["components"]["schemas"])
        self.assertIn("JobStatusResponse", schema["components"]["schemas"])
        self.assertIn("200", schema["paths"]["/results/{job_id}"]["get"]["responses"])
