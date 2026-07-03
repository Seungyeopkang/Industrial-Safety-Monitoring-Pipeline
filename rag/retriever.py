"""rag/retriever.py - 런타임 위반 쿼리 기반 SOP 조항 검색.

LLM 보고서 단계에서 위반 내용을 쿼리로 임베딩 → Chroma에서 top-k 조항 검색.
검색된 조항(출처/조문번호/제목/본문/유사도)을 LLM 프롬프트 컨텍스트로 주입하여
인용 환각을 방지(검색된 조항만 인용 허용).
"""
from typing import List, Dict, Optional
from rag.embedder import embed_query

from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VECTORSTORE_DIR = PROJECT_ROOT / "rag" / "vectorstore"
COLLECTION_NAME = "korean_safety_sop"

_collection = None


def get_collection():
    """Chroma 컬렉션 싱글톤."""
    global _collection
    if _collection is None:
        import chromadb
        client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR))
        _collection = client.get_collection(COLLECTION_NAME)
    return _collection


def retrieve(query: str, top_k: int = 5) -> List[Dict]:
    """쿼리 → top-k 관련 조항 검색.

    반환: List[dict] = [{text, source, article, title, score}]
    score는 cosine 거리(0=동일)를 유사도(1-거리)로 환산.
    """
    coll = get_collection()
    qvec = embed_query(query)
    res = coll.query(query_embeddings=[qvec.tolist()], n_results=top_k)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    results = []
    for doc, meta, dist in zip(docs, metas, dists):
        score = max(0.0, 1.0 - float(dist))  # cosine distance → similarity
        results.append({
            "text": doc,
            "source": meta.get("source", ""),
            "article": meta.get("article", ""),
            "title": meta.get("title", ""),
            "score": round(score, 4),
        })
    return results


def format_context(results: List[Dict]) -> str:
    """검색 결과를 LLM 프롬프트용 컨텍스트 텍스트로 포맷."""
    if not results:
        return "(검색된 관련 조항 없음)"
    lines = []
    for i, r in enumerate(results, 1):
        cite = f"{r['source']} [{r['article']}] {r['title']}"
        lines.append(f"[관련조항 {i}] 출처: {cite} (유사도 {r['score']})\n{r['text']}")
    return "\n\n".join(lines)


def retrieve_for_violations(violation_texts: List[str], top_k: int = 4) -> List[Dict]:
    """위반 설명 리스트 각각에 대해 검색 후 중복 제거하여 병합."""
    seen = set()
    merged = []
    for v in violation_texts:
        for r in retrieve(v, top_k=top_k):
            key = (r["source"], r["article"])
            if key not in seen:
                seen.add(key)
                merged.append(r)
    # 유사도 내림차순 정렬 후 상위 제한
    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged[:8]


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
