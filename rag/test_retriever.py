"""rag/test_retriever.py - RAG 검색 단위/품질 검증(API 미사용).

검증 항목:
1. 단일 쿼리 검색 결과 개수/형식/스코어
2. 한국어 의미 검색 품질(헬멧/조끼/추락/위험구역/보호구미지급)
3. retrieve_for_violations 병합·중복제거
4. 인용 환각 방지 검증: 검색 결과의 (source, article)이 실제 DB에 존재
5. top-1 관련성 기대치 교차 확인
"""
from rag.retriever import retrieve, format_context, retrieve_for_violations, get_collection

QUERIES = [
    "근로자가 헬멧(안전모)을 착용하지 않고 작업 중",
    "안전조끼(반사조끼)를 입지 않은 근로자",
    "높은 곳에서 추락 위험이 있는 작업",
    "위험구역에 무단 출입한 근로자",
    "보호구를 지급하지 않은 사업주",
]

# top-1에 기대되는 article/title 키워드
EXPECTATIONS = {
    "근로자가 헬멧(안전모)을 착용하지 않고 작업 중": ("제98조", "산안규 제197조", "안전모", "보호구"),
    "안전조끼(반사조끼)를 입지 않은 근로자": ("안전조끼", "보호구", "제98조"),
    "높은 곳에서 추락 위험이 있는 작업": ("산안규 제62조", "추락"),
    "위험구역에 무단 출입한 근로자": ("위험구역", "KOSHA"),
    "보호구를 지급하지 않은 사업주": ("제98조", "보호구", "벌칙"),
}


def main():
    coll = get_collection()
    metas = coll.get(include=["metadatas"])["metadatas"]
    db_keys = {(m.get("source"), m.get("article")) for m in metas}
    print(f"DB 청크 수: {coll.count()}, 고유 (source,article) 쌍: {len(db_keys)}\n")

    print("=" * 70)
    print("1) 단일 쿼리 검색 (top_k=3)")
    print("=" * 70)
    for q in QUERIES:
        res = retrieve(q, top_k=3)
        print(f"\n쿼리: {q}")
        for r in res:
            print(f"  - {r['source']} [{r['article']}] {r['title']}  score={r['score']}")

    print("\n" + "=" * 70)
    print("2) retrieve_for_violations (복수 위반 병합·중복제거)")
    print("=" * 70)
    merged = retrieve_for_violations([
        "근로자가 헬멧(안전모)을 착용하지 않고 작업 중",
        "안전조끼를 입지 않은 근로자",
        "위험구역에 무단 출입",
    ], top_k=3)
    print(f"병합된 고유 조항: {len(merged)}건")
    for r in merged:
        print(f"  - {r['source']} [{r['article']}] {r['title']}  score={r['score']}")

    print("\n" + "=" * 70)
    print("3) format_context 출력(일부)")
    print("=" * 70)
    print(format_context(merged)[:700])

    print("\n" + "=" * 70)
    print("4) 인용 환각 방지 검증: 검색 결과 출처가 DB에 존재?")
    print("=" * 70)
    all_ok = True
    checked = 0
    for q in QUERIES:
        for r in retrieve(q, top_k=3):
            checked += 1
            key = (r["source"], r["article"])
            if key not in db_keys:
                all_ok = False
                print(f"  [경고] DB에 없음: {key}")
    print(f"  검증 건수: {checked} → 모든 출처가 DB에 존재: {all_ok}")

    print("\n" + "=" * 70)
    print("5) top-1 관련성 기대치 교차 확인")
    print("=" * 70)
    pass_n, total = 0, 0
    for q, expected in EXPECTATIONS.items():
        res = retrieve(q, top_k=1)
        top = res[0] if res else None
        if not top:
            print(f"  쿼리: {q[:30]}... → 결과 없음 ✗")
            total += 1
            continue
        blob = f"{top['article']} {top['title']} {top['source']}"
        matched = any(e in blob for e in expected)
        total += 1
        pass_n += 1 if matched else 0
        print(f"  쿼리: {q[:30]}... → top1: [{top['article']}] {top['title']} | 기대[{','.join(expected)}] {'✓' if matched else '✗'}")
    print(f"\n  top-1 관련성 통과: {pass_n}/{total}")


if __name__ == "__main__":
    main()
