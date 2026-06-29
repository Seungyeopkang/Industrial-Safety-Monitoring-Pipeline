import os
import requests
from dotenv import load_dotenv

env_path = r"c:\Users\user\Desktop\VLM-Based Industrial Safety Monitoring Pipeline\.env"
load_dotenv(dotenv_path=env_path)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID")

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# 1. Delete existing README child page and obsolete dashboard blocks
url = f"https://api.notion.com/v1/blocks/{NOTION_PAGE_ID}/children"
response = requests.get(url, headers=headers)
if response.status_code == 200:
    blocks = response.json().get("results", [])
    for block in blocks:
        # README child page 삭제
        if block["type"] == "child_page" and block["child_page"]["title"] == "README (프로젝트 개요)":
            requests.delete(f"https://api.notion.com/v1/blocks/{block['id']}", headers=headers)
        
        # 이전 대시보드 가이드 블록 삭제
        if block["type"] == "heading_2":
            text = block["heading_2"]["rich_text"][0]["text"]["content"] if block["heading_2"]["rich_text"] else ""
            if "대시보드 활용 및 구성 요소" in text:
                requests.delete(f"https://api.notion.com/v1/blocks/{block['id']}", headers=headers)
        if block["type"] == "bulleted_list_item":
            text = block["bulleted_list_item"]["rich_text"][0]["text"]["content"] if block["bulleted_list_item"]["rich_text"] else ""
            if "README" in text or "Sprint 계획" in text or "Dev Log" in text:
                requests.delete(f"https://api.notion.com/v1/blocks/{block['id']}", headers=headers)

# 2. Append README content to the parent page directly
payload = {
    "children": [
        {
            "object": "block",
            "type": "divider",
            "divider": {}
        },
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "📖 프로젝트 개요"}}]
            }
        },
        {
            "object": "block",
            "type": "quote",
            "quote": {
                "rich_text": [{"type": "text", "text": {"content": "실무형 AI 파이프라인: YOLO의 정교한 객체 탐지와 Vision-Language Model(VLM)의 고도의 맥락 분석력을 결합하여 완성도 높은 작업장 안전 관리 체계를 시각적으로 증명하는 프로젝트"}}]
            }
        },
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": "1. 프로젝트 배경 및 필요성"}}]
            }
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": "기존의 컴퓨터 비전 기반 산업 안전 시스템은 "}},
                    {"type": "text", "text": {"content": "YOLO"}, "annotations": {"code": True}},
                    {"type": "text", "text": {"content": " 등 객체 탐지 모델만을 사용하여 특정 객체(예: 헬멧)의 유무만을 판별해 왔습니다. 그러나 이는 다음과 같은 한계가 존재합니다:\n"}},
                    {"type": "text", "text": {"content": "- **맥락(Context) 부재**: 안전 장비를 왜 착용하지 않았는지, 현재 작업자가 처한 환경이 얼마나 위험한 환경(고공 작업, 지상 작업 등)인지 파악 불가\n- **보고서 작성의 비효율성**: 단순 탐지 결과를 현장 관리자가 해석해 수동으로 보고서를 작성해야 하는 번거로움\n\n본 프로젝트는 이러한 문제를 해결하기 위해 "}},
                    {"type": "text", "text": {"content": "Detection → VLM → LLM → Notion"}, "annotations": {"bold": True}},
                    {"type": "text", "text": {"content": "으로 연결되는 다단계 파이프라인을 구축하여 의사결정과 아카이빙을 완전 자동화합니다."}}
                ]
            }
        },
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": "2. 기술적 차별성 및 아키텍처"}}]
            }
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": "본 아키텍처는 AI 스타트업(예: Nota AI) 등의 실무 서비스 파이프라인을 모방하여 다음과 같이 역할을 분리 설계했습니다.\n\n"}},
                    {"type": "text", "text": {"content": "1단계: YOLOv8 PPE 탐지 (Detection)\n"}, "annotations": {"bold": True}},
                    {"type": "text", "text": {"content": "- 실시간성에 최적화된 경량 객체 탐지 모델을 활용하여 인물 및 PPE(헬멧, 조끼, 장갑 등)의 위치(Bounding Box) 신속 검출.\n\n"}},
                    {"type": "text", "text": {"content": "2단계: Vision-Language Model 분석 (VLM)\n"}, "annotations": {"bold": True}},
                    {"type": "text", "text": {"content": "- 이미지 데이터와 1단계 YOLO 검출 메타데이터를 프롬프트와 조합해 VLM(Gemini/Claude 등)에 입력. 주변 환경과 사람 간의 논리적 관계와 위험 맥락을 자연어로 상세 도출.\n\n"}},
                    {"type": "text", "text": {"content": "3단계: Large Language Model 리포트 변환 (LLM)\n"}, "annotations": {"bold": True}},
                    {"type": "text", "text": {"content": "- 비정형 VLM 상세 묘사를 입력받아 표준 작업 절차서(SOP)와 비교 분석하여 위반 건수, 위험도(Low/Medium/High) 판정 및 긴급 대응 방안을 규격화된 마크다운 보고서로 변환.\n\n"}},
                    {"type": "text", "text": {"content": "4단계: 자동 아카이빙 (Notion API)\n"}, "annotations": {"bold": True}},
                    {"type": "text", "text": {"content": "- 백엔드에서 API를 호출해 점검 결과를 노션 데이터베이스에 실시간 적재하여 즉각적인 현장 대시보드로 활용 가능하게 설계."}}
                ]
            }
        },
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": "3. 기술 스택 및 선택 이유 (Why)"}}]
            }
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": "- **YOLOv8**: 뛰어난 실시간 성능과 쉬운 파이프라인 연계성\n- **FastAPI**: 비동기 처리에 최적화되어 VLM/LLM API 호출 시 발생할 수 있는 병목(I/O Bound)의 효율적 관리 지원\n- **Notion API**: DB 인프라 구축 리소스를 최소화하면서도, 포트폴리오 평가관에게 풍부한 시각적 로그 및 아카이빙 결과물을 링크 하나로 투명하게 보여줄 수 있는 최적의 스토리지 솔루션"}}
                ]
            }
        }
    ]
}

requests.patch(url, json=payload, headers=headers)
print("Successfully moved README to main page.")
