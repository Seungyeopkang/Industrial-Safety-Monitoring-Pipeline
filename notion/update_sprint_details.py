import os
import sys
import requests
from dotenv import load_dotenv

# 프로젝트 루트 기준 .env 로드 (하드코딩된 절대경로 제거)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

NOTION_API_KEY = os.getenv("NOTION_API_KEY")

if not NOTION_API_KEY or NOTION_API_KEY == "your_notion_api_key":
    print("Error: NOTION_API_KEY가 .env 파일에 올바르게 설정되지 않았습니다.")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# 일회성 태스크명 변경 매핑 (page_id -> 새 제목).
# 본 스크립트는 단발성 마이그레이션 유틸리티이므로 매핑 테이블 자체는 데이터로 유지.
UPDATES = {
    "38e73d49-32e0-81b1-8a50-f7f2a9ac61aa": "Pydantic 데이터 모델링 정의 및 VLM/LLM Structured Outputs 연동",
    "38e73d49-32e0-8139-9159-e962701b80ce": "FastAPI BackgroundTasks 기반 비동기 파이프라인 처리 및 비차단(Non-blocking) API 설계",
    "38e73d49-32e0-81fd-a05a-d4b313295e69": "정적 결과 화면 대시보드 UI 개발 (바운딩박스 오버레이 이미지 뷰어 + 리포트 세부 정보 카드)",
    "38e73d49-32e0-814c-97c3-fe27b2cfd16b": "Pydantic 구조화 데이터를 노션 블록(Heading, Table, Paragraph) 구조로 변환하는 모듈 개발"
}

def update_titles():
    for page_id, new_title in UPDATES.items():
        url = f"https://api.notion.com/v1/pages/{page_id}"
        payload = {
            "properties": {
                "Name": {
                    "title": [
                        {
                            "text": {
                                "content": new_title
                            }
                        }
                    ]
                }
            }
        }
        res = requests.patch(url, json=payload, headers=headers)
        if res.status_code == 200:
            print(f"Updated page {page_id} title to: {new_title}")
        else:
            print(f"Failed to update page {page_id}: {res.text}")

if __name__ == "__main__":
    update_titles()
