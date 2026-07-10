"""rag/retriever.py - 런타임 위반 쿼리 기반 SOP 조항 검색.

LLM 보고서 단계에서 위반 내용을 쿼리로 임베딩 → Chroma에서 top-k 조항 검색.
검색된 조항(출처/조문번호/제목/본문/유사도)을 LLM 프롬프트 컨텍스트로 주입하여
인용 환각을 방지(검색된 조항만 인용 허용).
"""
from typing import Any, Dict, Iterable, List, Optional
from rag.embedder import embed_query

from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VECTORSTORE_DIR = PROJECT_ROOT / "rag" / "vectorstore"
COLLECTION_NAME = "korean_safety_sop"
PARENT_STORE_PATH = VECTORSTORE_DIR / "parent_documents.json"
# 0.45/0.50/0.55 evaluation retained valid PPE/fall/danger-zone results at
# 0.55 while rejecting the observed irrelevant unknown-danger retrievals.
DEFAULT_MIN_SCORE = 0.55
DEFAULT_MAX_CONTEXT_COUNT = 8
DEFAULT_TOP_K_PER_QUERY = 3

_collection = None
_parent_store = None


def get_collection():
    """Chroma 컬렉션 싱글톤."""
    global _collection
    if _collection is None:
        import chromadb
        client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR))
        _collection = client.get_collection(COLLECTION_NAME)
    return _collection


def get_parent_store() -> Dict[str, Dict]:
    """Load parent article text written by the parent-child index builder."""
    global _parent_store
    if _parent_store is None:
        if PARENT_STORE_PATH.exists():
            import json
            _parent_store = json.loads(PARENT_STORE_PATH.read_text(encoding="utf-8"))
        else:
            _parent_store = {}
    return _parent_store


def retrieve(query: str, top_k: int = 5, min_score: Optional[float] = DEFAULT_MIN_SCORE) -> List[Dict]:
    """쿼리 → top-k 관련 조항 검색.

    반환: List[dict] = [{text, source, article, title, score}]
    score는 cosine 거리(0=동일)를 유사도(1-거리)로 환산.
    """
    coll = get_collection()
    qvec = embed_query(query)
    res = coll.query(query_embeddings=[qvec.tolist()], n_results=top_k) #가까운거 탐색
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    results = []
    for doc, meta, dist in zip(docs, metas, dists):
        score = max(0.0, 1.0 - float(dist))  # cosine distance → similarity
        if min_score is not None and score < min_score:
            continue
        parent_id = meta.get("parent_id", "")
        parent = get_parent_store().get(parent_id, {}) if parent_id else {}
        results.append({
            "text": doc,
            "source": meta.get("source", ""),
            "article": meta.get("article", ""),
            "title": meta.get("title", ""),
            "score": round(score, 4),
            "doc_id": meta.get("doc_id", ""),
            "parent_id": parent_id,
            "child_id": meta.get("child_id", ""),
            "section_path": meta.get("section_path", ""),
            "parent_text": parent.get("text", ""),
        })
    return results


def format_context(results: List[Dict]) -> str:
    """검색 결과를 LLM 프롬프트용 컨텍스트 텍스트로 포맷."""
    if not results:
        return "(검색된 관련 조항 없음)"
    lines = []
    for i, r in enumerate(results, 1):
        cite = f"{r['source']} [{r['article']}] {r['title']}"
        parent_text = r.get("parent_text", "")
        parent_block = ""
        if parent_text and parent_text != r["text"]:
            parent_block = f"\n[상위 조문 문맥]\n{parent_text[:1800]}"
        lines.append(f"[관련조항 {i}] 출처: {cite} (유사도 {r['score']})\n{r['text']}{parent_block}")
    return "\n\n".join(lines)


def retrieve_for_violations(
    violation_texts: List[str],
    top_k: int = 4,
    min_score: Optional[float] = DEFAULT_MIN_SCORE,
    max_context_count: int = DEFAULT_MAX_CONTEXT_COUNT,
) -> List[Dict]:
    """위반 설명 리스트 각각에 대해 검색 후 중복 제거하여 병합."""
    seen = set()
    merged = []
    for v in violation_texts:
        for r in retrieve(v, top_k=top_k, min_score=min_score):
            key = (r["source"], r["article"])
            if key not in seen:
                seen.add(key)
                merged.append(r)
    # 유사도 내림차순 정렬 후 상위 제한
    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged[:max_context_count]


def retrieve_for_query_records(
    query_records: Iterable[Dict[str, Any]],
    top_k_per_query: int = DEFAULT_TOP_K_PER_QUERY,
    min_score: Optional[float] = DEFAULT_MIN_SCORE,
    max_context_count: int = DEFAULT_MAX_CONTEXT_COUNT,
) -> Dict[str, Any]:
    """Retrieve canonical queries and preserve why every clause was admitted."""
    seen = set()
    merged: List[Dict[str, Any]] = []
    query_traces = []
    for record in query_records or []:
        query = str(record.get("query", "")).strip()
        if not query:
            continue
        matches = retrieve(query, top_k=top_k_per_query, min_score=min_score)
        required_terms = [str(term) for term in record.get("required_terms", []) if str(term).strip()]
        rejected_by_term_gate = 0
        if required_terms:
            filtered_matches = []
            for match in matches:
                searchable = f"{match['title']} {match['text']}"
                if any(term in searchable for term in required_terms):
                    filtered_matches.append(match)
                else:
                    rejected_by_term_gate += 1
            matches = filtered_matches
        query_traces.append({
            **record,
            "returned_count": len(matches),
            "rejected_by_term_gate": rejected_by_term_gate,
            "min_score": min_score,
            "status": "matched" if matches else "no_relevant_context",
        })
        for match in matches:
            key = (match["source"], match["article"])
            if key in seen:
                continue
            seen.add(key)
            merged.append({**match, "query_origin": record.get("origin"), "query": query})
    merged.sort(key=lambda item: item["score"], reverse=True)
    return {"clauses": merged[:max_context_count], "query_traces": query_traces}


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "근로자가 헬멧(안전모)을 착용하지 않고 작업 중"
    print(f"쿼리: {q}\n")
    results = retrieve(q, top_k=5)
    print(f"검색 결과: {len(results)}건\n")
    for r in results:
        print(f"  • {r['source']} [{r['article']}] {r['title']}  (score={r['score']})")
        print(f"    {r['text'][:90].replace(chr(10), ' ')}...")
        print()
