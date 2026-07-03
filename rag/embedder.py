"""rag/embedder.py - bge-m3 다국어 임베딩(로컬).

BAAI/bge-m3 모델로 한국어+영어 dense 임베딩 생성. GPU(cuda) 우선, 실패 시 cpu.
sentence-transformers의 SentenceTransformer로 로드(dense 임베딩 경로).
임베딩은 L2 정규화하여 코사인 유사도 기반 검색에 사용.

첫 호출 시 모델 다운로드(~2.3GB, HuggingFace 캐시). 이후 캐시 재사용.
"""
import os
from typing import List, Optional
import numpy as np

DEFAULT_MODEL = "BAAI/bge-m3"

_embedder = None  # 싱글톤 캐시


def _pick_device(preferred: Optional[str] = None) -> str:
    """CUDA 사용 가능 여부에 따라 device 선택."""
    if preferred:
        return preferred
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def get_embedder(model_name: str = DEFAULT_MODEL, device: Optional[str] = None):
    """SentenceTransformer 싱글톤 인스턴스 반환."""
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        dev = _pick_device(device)
        print(f"[embedder] 로드: {model_name} (device={dev})")
        _embedder = SentenceTransformer(model_name, device=dev)
    return _embedder


def embed_texts(texts: List[str], model_name: str = DEFAULT_MODEL,
                device: Optional[str] = None, normalize: bool = True) -> np.ndarray:
    """텍스트 리스트 → 정규화된 임베딩 배열 (N, dim)."""
    model = get_embedder(model_name, device)
    vecs = model.encode(
        texts,
        batch_size=16,
        show_progress_bar=False,
        normalize_embeddings=normalize,
        convert_to_numpy=True,
    )
    return vecs


def embed_query(query: str, model_name: str = DEFAULT_MODEL,
                device: Optional[str] = None) -> np.ndarray:
    """단일 쿼리 → 정규화된 임베딩 (dim,)."""
    return embed_texts([query], model_name, device)[0]


def embedding_dim(model_name: str = DEFAULT_MODEL) -> int:
    """모델 임베딩 차원 반환."""
    return int(embed_texts(["dimprobe"]).shape[1])


if __name__ == "__main__":
    import time
    t0 = time.time()
    v = embed_texts(["헬멧 미착용", "안전모를 쓰지 않은 근로자"])
    print(f"shape={v.shape} dim={v.shape[1]} load+encode={time.time()-t0:.1f}s")
    # 코사인 유사도(정규화됨 → 내적)
    sim = float(v[0] @ v[1])
    print(f"cos_sim(헬멧미착용 vs 안전모미착용)={sim:.3f}")
