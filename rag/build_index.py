"""rag/build_index.py - 한국 안전 규정 벡터DB 일회성 빌드.

datasets/sop_korean/raw/ 원문 → loader → chunker → bge-m3 임베딩 → Chroma 영속 저장.
실행: python -m rag.build_index [--rebuild]

인덱스 위치: rag/vectorstore/ (Chroma PersistentClient)
컬렉션명: korean_safety_sop (cosine 거리)
"""
import argparse
import sys
from pathlib import Path
from rag.loader import load_directory
from rag.chunker import chunk_documents
from rag.embedder import embed_texts

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VECTORSTORE_DIR = PROJECT_ROOT / "rag" / "vectorstore"
COLLECTION_NAME = "korean_safety_sop"


def build(rebuild: bool = False):
    import chromadb
    print("[build] 1/4 원문 로드")
    docs = load_directory()
    if not docs:
        print("  원문이 없습니다. datasets/sop_korean/raw/ 에 파일을 넣으세요.")
        return 0
    print(f"  문서 {len(docs)}개")

    print("[build] 2/4 청킹")
    chunks = chunk_documents(docs)
    print(f"  청크 {len(chunks)}개")
    if not chunks:
        print("  청크가 생성되지 않았습니다.")
        return 0

    print("[build] 3/4 임베딩 (bge-m3, 첫 실행 시 모델 다운로드)")
    texts = [c["text"] for c in chunks]
    vecs = embed_texts(texts)
    print(f"  임베딩 shape={vecs.shape}")

    print("[build] 4/4 Chroma 저장")
    client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR))
    if rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"  기존 컬렉션 삭제: {COLLECTION_NAME}")
        except Exception:
            pass
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    ids = [c["id"] for c in chunks]
    metadatas = [
        {"source": c["source"], "article": c["article"], "title": c["title"]}
        for c in chunks
    ]
    # Chroma는 리스트의 리스트 float 임베딩 사용
    collection.add(
        ids=ids,
        embeddings=vecs.tolist(),
        documents=texts,
        metadatas=metadatas,
    )
    print(f"  저장 완료: 컬렉션 '{COLLECTION_NAME}' / {collection.count()}건")
    print(f"  위치: {VECTORSTORE_DIR}")
    return collection.count()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="한국 안전 규정 RAG 인덱스 빌드")
    parser.add_argument("--rebuild", action="store_true", help="기존 컬렉션 삭제 후 재구축")
    args = parser.parse_args()
    n = build(rebuild=args.rebuild)
    sys.exit(0 if n else 1)
