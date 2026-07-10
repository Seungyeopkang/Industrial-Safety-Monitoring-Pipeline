"""Build or incrementally update the Korean safety-regulation Chroma index."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from rag.chunker import chunk_documents, parent_documents
from rag.embedder import embed_texts
from rag.loader import DEFAULT_RAW_DIR, load_directory

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VECTORSTORE_DIR = PROJECT_ROOT / "rag" / "vectorstore"
COLLECTION_NAME = "korean_safety_sop"
MANIFEST_PATH = VECTORSTORE_DIR / "index_manifest.json"
PARENT_STORE_PATH = VECTORSTORE_DIR / "parent_documents.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _doc_id(relative_path: str) -> str:
    return hashlib.sha256(relative_path.replace("\\", "/").encode("utf-8")).hexdigest()[:24]


def _load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_documents(raw_dir: Path = DEFAULT_RAW_DIR) -> List[Dict]:
    docs = load_directory(raw_dir)
    for doc in docs:
        path = Path(doc["path"])
        relative = path.relative_to(raw_dir).as_posix()
        doc.update(relative_path=relative, doc_id=_doc_id(relative), sha256=_sha256(path))
    return docs


def plan_incremental(documents: Iterable[Dict], previous_manifest: Dict) -> Tuple[List[Dict], List[str], List[Dict]]:
    """Return documents to embed, removed doc ids, and new manifest rows."""
    previous = previous_manifest.get("documents", {})
    current = {doc["relative_path"]: doc for doc in documents}
    deleted = [entry["doc_id"] for path, entry in previous.items() if path not in current]
    changed, rows = [], []
    for path, doc in current.items():
        old = previous.get(path)
        if old is None or old.get("sha256") != doc["sha256"] or old.get("doc_id") != doc["doc_id"]:
            changed.append(doc)
            if old:
                deleted.append(old["doc_id"])
        rows.append({"relative_path": path, "doc_id": doc["doc_id"], "sha256": doc["sha256"], "filename": doc["filename"]})
    return changed, deleted, rows


def _metadata(chunk: Dict) -> Dict:
    return {key: str(chunk[key]) for key in (
        "source", "article", "title", "doc_id", "parent_id", "child_id", "chunk_type", "section_path"
    )}


def build(rebuild: bool = False, raw_dir: Path = DEFAULT_RAW_DIR):
    import chromadb

    raw_dir = Path(raw_dir)
    documents = prepare_documents(raw_dir)
    if not documents:
        return {"count": 0, "processed": 0, "skipped": 0, "deleted": 0, "upserted": 0}

    VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR))
    if rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        previous_manifest = {"version": 2, "documents": {}}
    else:
        previous_manifest = _load_json(MANIFEST_PATH, {"version": 2, "documents": {}})

    collection = client.get_or_create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    # Legacy c00001 ids cannot be safely incrementally deleted. Migrate once.
    if not rebuild and not MANIFEST_PATH.exists() and collection.count() > 0:
        client.delete_collection(COLLECTION_NAME)
        collection = client.get_or_create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

    changed, deleted_doc_ids, rows = plan_incremental(documents, previous_manifest)
    deleted_set = set(deleted_doc_ids)
    for doc_id in deleted_set:
        collection.delete(where={"doc_id": doc_id})

    chunks = chunk_documents(changed)
    if chunks:
        vectors = embed_texts([chunk["text"] for chunk in chunks])
        collection.upsert(
            ids=[chunk["id"] for chunk in chunks],
            embeddings=vectors.tolist(), documents=[chunk["text"] for chunk in chunks],
            metadatas=[_metadata(chunk) for chunk in chunks],
        )

    parents = _load_json(PARENT_STORE_PATH, {})
    for parent_id, parent in list(parents.items()):
        if parent.get("doc_id") in deleted_set:
            parents.pop(parent_id, None)
    parents.update(parent_documents(chunks))
    _write_json(PARENT_STORE_PATH, parents)
    _write_json(MANIFEST_PATH, {
        "version": 2, "indexed_at": datetime.now(timezone.utc).isoformat(),
        "documents": {row["relative_path"]: row for row in rows},
    })
    return {
        "count": collection.count(), "processed": len(changed),
        "skipped": len(documents) - len(changed), "deleted": len(deleted_set), "upserted": len(chunks),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Korean safety RAG index")
    parser.add_argument("--rebuild", action="store_true", help="Recreate collection and manifest")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    args = parser.parse_args()
    result = build(rebuild=args.rebuild, raw_dir=args.raw_dir)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["count"] else 1)
