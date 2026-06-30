import os
import requests
from dotenv import load_dotenv

env_path = r"c:\Users\user\Desktop\VLM-Based Industrial Safety Monitoring Pipeline\.env"
load_dotenv(dotenv_path=env_path)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = "38d73d49-32e0-81c2-b71a-e4c967437e17"

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def create_devlog():
    url = "https://api.notion.com/v1/pages"
    
    payload = {
        "parent": {
            "database_id": DATABASE_ID
        },
        "properties": {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": "2026-06-30 | 1차 객체 탐지 모델 로컬 벤치마크 및 데이터셋 교정 평가 완료"
                        }
                    }
                ]
            },
            "Date": {
                "date": {
                    "start": "2026-06-30"
                }
            },
            "Sprint": {
                "select": {
                    "name": "Sprint 1"
                }
            },
            "Category": {
                "multi_select": [
                    {"name": "분석"},
                    {"name": "코드/구현"}
                ]
            }
        },
        "children": [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "📌 진행 상황"}}]
                }
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "모델 벤치마크 수행: "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "YOLOv8 사전 학습 가중치 3종에 대한 추론 속도(FPS), 메모리 사용량, 로드 속도 벤치마크 비교 완료."}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "데이터셋 테스트 셋 분석: "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "Construction-PPE 및 Hard Hat Workers v10 데이터셋 스펙 확인 및 Test split 이미지/라벨 맵 분석 완료."}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "표준화 평가 스크립트 개발: "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "3종 모델의 상이한 클래스 구성을 단일 표준 클래스(helmet, no_helmet, vest)로 치환해주는 매핑 평가 코드(evaluate.py) 개발 완료."}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "정량 지표 산출: "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "141장/176장 테스트 데이터에 대해 모델별 Precision, Recall, F1-Score 정량 평가 연산 완료."}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "종합 시각화 및 리포팅: "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "측정된 하드웨어 및 정확도 지표 9종을 3x3 종합 바 차트 시각화(evaluation_comparison.png) 및 JSON 리포트 생성 완료."}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "💡 기술 결정 사항"}}]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "• "}},
                        {"type": "text", "text": {"content": "Hansung-Cho/yolov8-ppe-detection 모델 채택"}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "\n- 실시간 추론 속도(190.7 FPS), 뛰어난 리소스 효율성(파라미터 3.01 M, RAM 50MB), 그리고 Construction-PPE 기준 가장 높은 정확도(Helmet F1: 0.793, Vest F1: 0.698)를 기록함.\n- NO-Hardhat, NO-Safety Vest, NO-Mask와 같은 미착용(위반) 클래스가 자체 탑재되어 있어, 복잡한 룰 엔지니어링 없이 직관적으로 VLM 분기 트리거 신뢰도를 얻을 수 있어 채택함."}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "• "}},
                        {"type": "text", "text": {"content": "신뢰도 기반 하이브리드 VLM 트리거 설계 확정"}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "\n- 단독 탐지 모델의 미착용(no_helmet) 감지 F1 스코어가 상대적으로 저조(0.08 ~ 0.21)함을 파악함.\n- 1차 탐지 신뢰도가 확실히 높은 정상 상태는 VLM을 건너뛰어 비용을 아끼고, 신뢰도가 애매한 경계 구간(0.3 ~ 0.75)만 VLM에 정밀 재판단을 위임함으로써 비용 효율과 신뢰성 두 마리 토끼를 잡음."}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "🛠️ 문제 & 해결"}}]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "1. "}},
                        {"type": "text", "text": {"content": "YOLO 모델간 클래스 구조 불일치 문제"}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "\n- 원인: 각 모델 배포처마다 상이한 PPE 라벨 스키마 및 가중치를 사용함.\n- 해결: 모델 고유 클래스명을 표준 클래스(helmet, no_helmet, vest)로 통일해주는 매핑 딕셔너리를 구축하고, 테스트 이미지 단위로 IoU(>=0.5) 기반 매칭을 직접 연산하는 evaluate.py 코드를 작성하여 해결."}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "2. "}},
                        {"type": "text", "text": {"content": "Notion API Block Appending 오류"}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "\n- 원인: annotations를 text 오브젝트 하위 필드로 오인해 삽입함.\n- 해결: annotations는 text와 형제(sibling) 계층 구조에 위치해야 하므로 API 스펙에 맞게 payload 구조를 수정하여 정상 연동 성공."}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "📅 다음 할 일"}}]
                }
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "[우선순위: 높음] "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "Hansung-Cho 모델 기반 1차 탐지 및 신뢰도 분기 처리 파이프라인(detection/detector.py) 스크립트 작성."}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "[우선순위: 보통] "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "OpenCV 기반 실시간 바운딩 박스 시각화 및 위반 프레임 캡처 모듈 연동."}}
                    ]
                }
            }
        ]
    }
    
    res = requests.post(url, json=payload, headers=headers)
    if res.status_code == 200:
        page_id = res.json().get("id")
        page_url = res.json().get("url")
        print(f"Successfully created Dev Log page in Notion! Page ID: {page_id}")
        print(f"Notion Page URL: {page_url}")
    else:
        print("Failed to create Dev Log page:", res.text)

if __name__ == "__main__":
    create_devlog()
