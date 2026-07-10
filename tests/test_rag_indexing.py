import unittest

from rag.build_index import plan_incremental
from rag.chunker import chunk_documents, parent_documents


class RagIndexingTests(unittest.TestCase):
    def test_parent_child_chunks_have_stable_hierarchy(self):
        docs = [{
            "source": "guide", "filename": "guide.txt", "doc_id": "doc-guide",
            "text": "[KOSHA] PPE\nWear a helmet and vest when required.",
        }]
        first = chunk_documents(docs)
        second = chunk_documents(docs)
        self.assertEqual([chunk["id"] for chunk in first], [chunk["id"] for chunk in second])
        self.assertEqual(first[0]["doc_id"], "doc-guide")
        self.assertEqual(first[0]["chunk_type"], "child")
        parents = parent_documents(first)
        self.assertEqual(len(parents), 1)
        self.assertIn(first[0]["parent_id"], parents)
        self.assertIn("Wear a helmet", parents[first[0]["parent_id"]]["text"])

    def test_incremental_plan_only_embeds_changed_files_and_deletes_removed(self):
        previous = {"documents": {
            "same.txt": {"doc_id": "same", "sha256": "a"},
            "removed.txt": {"doc_id": "removed", "sha256": "b"},
            "changed.txt": {"doc_id": "changed", "sha256": "old"},
        }}
        documents = [
            {"relative_path": "same.txt", "doc_id": "same", "sha256": "a", "filename": "same.txt"},
            {"relative_path": "changed.txt", "doc_id": "changed", "sha256": "new", "filename": "changed.txt"},
            {"relative_path": "new.txt", "doc_id": "new", "sha256": "c", "filename": "new.txt"},
        ]
        changed, deleted, rows = plan_incremental(documents, previous)
        self.assertEqual({doc["relative_path"] for doc in changed}, {"changed.txt", "new.txt"})
        self.assertEqual(set(deleted), {"removed", "changed"})
        self.assertEqual({row["relative_path"] for row in rows}, {"same.txt", "changed.txt", "new.txt"})


if __name__ == "__main__":
    unittest.main()
