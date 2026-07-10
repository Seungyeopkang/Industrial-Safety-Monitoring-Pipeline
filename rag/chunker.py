"""rag/chunker.py - 한국 규정 문서 청킹.

조문 단위 의미 청킹. 원문이 다음 형태를 가정:
  [제NN조] 조문제목
  본문...
  [산안규 제NN조] 조문제목
  [KOSHA 가이드] 항목제목

정규식으로 섹션 헤더를 인식해 각 조/항목을 하나의 청크로 분할.
본문이 너무 길면 문단 단위로 추가 분할(최대 chunk_size, overlap 적용).
각 청크에 메타데이터(source, article, title) 부착 → 인용·검색에 사용.

반환: List[dict] = [{"id": str, "text": str, "source": str, "article": str, "title": str}]
"""
import re
import hashlib
from typing import List, Dict

# 섹션 헤더 패턴 1: [제98조] / [산안규 제62조] / [KOSHA 가이드] 등 (샘플 TXT 형식)
HEADER_RE = re.compile(r"^\[(.+?)\]\s*(.*)$")
# 섹션 헤더 패턴 2: 제98조(보호구) / 제197조(전조등의 설치) 등 (공식 PDF 형식)
# 제NN조 또는 제NN조의M 형식 지원
LAW_HEADER_RE = re.compile(r"^(제\d+조(?:의\d+)?)\((.+?)\)(.*)$")
# PDF 페이지 헤더 노이즈: "법제처", "법제처 1"(페이지번호 포함), 단독 숫자
NOISE_RE = re.compile(r"^(법제처\s*\d*|\d+)$")
MAX_CHUNK_CHARS = 900
OVERLAP_CHARS = 120


def _split_long(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> List[str]:
    """텍스트가 max_chars 초과 시 문단/문장 단위로 분할. overlap 적용."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    parts = []
    # 우선 문단(\n\n) 단위, 부족하면 문장 단위
    units = re.split(r"(?<=[\n。])\s+", text) if "\n" in text else re.split(r"(?<=[.。!?\n])\s+", text)
    units = [u for u in units if u.strip()]
    buf = ""
    for u in units:
        if len(buf) + len(u) + 1 <= max_chars:
            buf = (buf + "\n" + u) if buf else u
        else:
            if buf:
                parts.append(buf)
            # overlap: 이전 buf 끝부분 일부를 다음 버퍼 시작에 이어붙임
            tail = buf[-overlap:] if buf and overlap > 0 else ""
            buf = (tail + "\n" + u).strip() if tail else u
    if buf:
        parts.append(buf)
    return parts


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()[:24]


def chunk_document(doc: Dict) -> List[Dict]:
    """단일 문서를 조문 단위 청크로 분할."""
    text = doc["text"]
    source = doc["source"]
    chunks = []
    lines = text.splitlines()

    current_header = None      # 예: "제98조"
    current_title = ""         # 예: "보호구"
    current_body = []

    def flush():
        if current_header is None and not current_body:
            return
        body = "\n".join(current_body).strip()
        if not body:
            return
        article = current_header or "서문"
        title = current_title or (doc.get("filename", source))
        doc_id = str(doc.get("doc_id") or _stable_id(source))
        parent_id = _stable_id(doc_id, article, title)
        parent_text = (f"[{article}] {title}\n{body}").strip()
        for i, piece in enumerate(_split_long(body)):
            cid = _stable_id(doc_id, parent_id, str(i), piece)
            head = f"[{article}] {title}\n" if current_header else ""
            chunks.append({
                "id": cid,
                "text": (head + piece).strip(),
                "source": source,
                "article": article,
                "title": title,
                "doc_id": doc_id,
                "parent_id": parent_id,
                "child_id": cid,
                "chunk_type": "child",
                "section_path": f"{source} > {article} > {title}",
                "child_index": i,
                "parent_text": parent_text,
            })

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            if current_body:
                current_body.append("")
            continue
        # PDF 페이지 헤더 노이즈 필터 (법제처, 단독 페이지 번호)
        if NOISE_RE.match(stripped):
            continue
        # 주석 라인(#)은 청크 본문에서 제외
        if stripped.startswith("#"):
            continue
        # 패턴 1: [헤더] 제목 (샘플 TXT 형식)
        m = HEADER_RE.match(stripped)
        if m:
            flush()
            current_header = m.group(1).strip()        # "제98조" 또는 "산안규 제62조" 등
            current_title = m.group(2).strip()         # 조문 제목
            current_body = []
            continue
        # 패턴 2: 제NN조(제목) 본문시작... (공식 PDF 형식)
        m2 = LAW_HEADER_RE.match(stripped)
        if m2:
            flush()
            current_header = m2.group(1).strip()       # "제98조"
            current_title = m2.group(2).strip()        # "보호구"
            rest = m2.group(3).strip()                 # 같은 줄의 본문 시작
            current_body = [rest] if rest else []
            continue
        current_body.append(line)
    flush()
    return chunks


def chunk_documents(docs: List[Dict]) -> List[Dict]:
    """문서 리스트 전체 청킹. ID 충돌 방지를 위해 전역 카운터로 고유 ID 재할당."""
    all_chunks = []
    for d in docs:
        all_chunks.extend(chunk_document(d))
    # 전역 카운터로 고유 ID 재할당 (조문 번호 중복으로 인한 해시 충돌 방지)
    return all_chunks


def parent_documents(chunks: List[Dict]) -> Dict[str, Dict]:
    """Deduplicate full article text for citation and context expansion."""
    parents = {}
    for chunk in chunks:
        parents.setdefault(chunk["parent_id"], {
            "doc_id": chunk["doc_id"], "parent_id": chunk["parent_id"],
            "source": chunk["source"], "article": chunk["article"],
            "title": chunk["title"], "section_path": chunk["section_path"],
            "text": chunk["parent_text"],
        })
    return parents


if __name__ == "__main__":
    from rag.loader import load_directory
    docs = load_directory()
    chunks = chunk_documents(docs)
    print(f"총 청크: {len(chunks)}개")
    for c in chunks[:6]:
        print(f"\n--- {c['source']} | {c['article']} | {c['title']} ---")
        print(c["text"][:160])
