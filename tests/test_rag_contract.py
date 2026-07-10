import unittest
from unittest.mock import patch

import numpy as np

from rag.danger_contract import eligible_danger_records
from rag.query_builder import build_canonical_queries
from rag.retriever import retrieve, retrieve_for_query_records


class FakeCollection:
    def query(self, **_kwargs):
        return {
            "documents": [["high relevance", "low relevance"]],
            "metadatas": [[
                {"source": "law", "article": "A", "title": "high"},
                {"source": "law", "article": "B", "title": "low"},
            ]],
            "distances": [[0.30, 0.72]],
        }


class RagContractTests(unittest.TestCase):
    def test_builder_uses_controlled_templates_and_skips_unknown(self):
        workers = [{
            "worker_id": "Worker 1", "helmet": "missing", "vest": "unknown",
            "mask": "worn", "gloves": "missing",
        }]
        dangers = eligible_danger_records([
            {"danger_type": "fall_risk", "worker_ids": ["Worker 1"],
             "description": "free text must not become a query", "evidence": "panel edge", "confidence": 0.8},
            {"danger_type": "missing_ppe", "worker_ids": ["Worker 1"],
             "description": "unknown PPE kind", "evidence": "metadata", "confidence": 0.8},
            {"danger_type": "unknown", "worker_ids": [], "description": "skip", "evidence": "?", "confidence": 0.9},
        ])

        records = build_canonical_queries(workers, dangers)
        queries = {record["query"] for record in records}
        self.assertIn("안전모 보호구 착용 기준", queries)
        self.assertIn("보호장갑 착용 기준", queries)
        self.assertIn("고소 작업 추락 방지 조치", queries)
        self.assertNotIn("free text must not become a query", queries)
        self.assertEqual(sum(record["danger_type"] == "fall_risk" for record in records), 1)

    @patch("rag.retriever.embed_query", return_value=np.array([0.1, 0.2]))
    @patch("rag.retriever.get_collection", return_value=FakeCollection())
    def test_min_score_filters_forced_top_k_results(self, _collection, _embedding):
        results = retrieve("irrelevant query", top_k=2, min_score=0.5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["article"], "A")

    @patch("rag.retriever.embed_query", return_value=np.array([0.1, 0.2]))
    @patch("rag.retriever.get_collection", return_value=FakeCollection())
    def test_query_traces_explain_empty_or_accepted_context(self, _collection, _embedding):
        output = retrieve_for_query_records(
            [{"query": "safe query", "origin": "detector_ppe", "worker_ids": ["Worker 1"],
              "required_terms": ["not-present"]}],
            min_score=0.5,
        )
        self.assertEqual(output["clauses"], [])
        self.assertEqual(output["query_traces"][0]["status"], "no_relevant_context")
        self.assertEqual(output["query_traces"][0]["rejected_by_term_gate"], 1)


if __name__ == "__main__":
    unittest.main()
