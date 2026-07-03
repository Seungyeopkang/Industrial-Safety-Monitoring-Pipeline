"""rag/loader.py - 한국 안전 규정 원문 로드.

datasets/sop_korean/raw/ 디렉토리의 원문 파일(PDF/TXT/MD)을 읽어 텍스트를 추출.
PDF는 pypdf, TXT/MD는 직접 읽기. 각 문서에 source(파일명) 메타데이터 부착.

반환: List[dict] = [{"text": str, "source": str, "filename": str, "filetype": str}]
"""
from pathlib import Path
from typing import List, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = PROJECT_ROOT / "datasets" / "sop_korean" / "raw"


def _extract_pdf(path: Path) -> str:
    """pypdf로 PDF 텍스트 추출."""
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n".join(pages).strip()


def _extract_text(path: Path) -> str:
    """TXT/MD 파일 직접 읽기."""
    return path.read_text(encoding="utf-8").strip()


def load_document(path) -> Dict:
    """단일 파일 로드. path는 str 또는 Path."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"문서를 찾을 수 없음: {p}")
    ext = p.suffix.lower()
    if ext == ".pdf":
        text = _extract_pdf(p)
        filetype = "pdf"
    elif ext in (".txt", ".md"):
        text = _extract_text(p)
        filetype = ext.lstrip(".")
    else:
        raise ValueError(f"지원하지 않는 파일 형식({ext}): {p}")
    return {
        "text": text,
        "source": p.stem,           # 확장자 제외 파일명(예: 01_산업안전보건법_핵심조문)
        "filename": p.name,
        "filetype": filetype,
    }


def load_directory(raw_dir=None) -> List[Dict]:
    """원문 디렉토리의 모든 지원 파일을 로드. 빈 디렉토리면 빈 리스트 반환."""
    d = Path(raw_dir) if raw_dir else DEFAULT_RAW_DIR
    if not d.exists():
        raise FileNotFoundError(f"원문 디렉토리 없음: {d}")
    docs = []
    for p in sorted(d.iterdir()):
        if p.is_file() and p.suffix.lower() in (".pdf", ".txt", ".md"):
            try:
                docs.append(load_document(p))
            except Exception as e:
                print(f"  [건너뜀] {p.name}: {e}")
    return docs


if __name__ == "__main__":
    docs = load_directory()
    print(f"로드된 문서: {len(docs)}개")
    for d in docs:
        print(f"  - {d['filename']} ({d['filetype']}, {len(d['text'])}자)")
