"""RAG module - 한국 안전 규정 기반 SOP 검색/증강.

구성:
- loader.py   : 원문 파일(PDF/TXT/MD) 로드 및 텍스트 추출
- chunker.py  : 조문 단위 청킹 + 메타데이터(출처/조문번호/제목) 부착
- embedder.py : bge-m3 다국어 임베딩(로컬, GPU 가속)
- build_index.py : Chroma 벡터DB 인덱스 일회성 빌드 스크립트
- retriever.py : 런타임 위반 쿼리 → top-k 조항 검색
"""
