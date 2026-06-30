import os
import shutil
import subprocess
import requests
from dotenv import load_dotenv

env_path = r"c:\Users\user\Desktop\VLM-Based Industrial Safety Monitoring Pipeline\.env"
load_dotenv(dotenv_path=env_path)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = "38d73d49-32e0-81c2-b71a-e4c967437e17"
PREVIOUS_PAGE_ID = "38f73d49-32e0-818c-a169-c397345b1439"

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def copy_and_push_image():
    assets_dir = r"c:\Users\user\Desktop\VLM-Based Industrial Safety Monitoring Pipeline\notion\assets"
    os.makedirs(assets_dir, exist_ok=True)
    
    src = r"c:\Users\user\Desktop\VLM-Based Industrial Safety Monitoring Pipeline\outputs\results\evaluation_comparison.png"
    dst = os.path.join(assets_dir, "evaluation_comparison.png")
    
    shutil.copy(src, dst)
    print("Copied chart to notion assets.")
    
    # Run git commands to commit and push the asset
    try:
        subprocess.run(["git", "add", "notion/assets/evaluation_comparison.png"], check=True)
        subprocess.run(["git", "commit", "-m", "assets(notion): add evaluation comparison chart for devlog embedding"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("Successfully pushed visualization image to GitHub.")
    except Exception as e:
        print("Git push failed or no changes to commit:", e)

def archive_previous_page():
    url = f"https://api.notion.com/v1/pages/{PREVIOUS_PAGE_ID}"
    payload = {"archived": True}
    res = requests.patch(url, json=payload, headers=headers)
    if res.status_code == 200:
        print("Successfully archived the previous empty page.")
    else:
        print("Failed to archive previous page (maybe already archived or ID invalid):", res.text)

def make_table_block(headers_list, rows_list):
    cells = []
    # Header row
    cells.append({
        "object": "block",
        "type": "table_row",
        "table_row": {
            "cells": [[{"type": "text", "text": {"content": h}}] for h in headers_list]
        }
    })
    # Data rows
    for row in rows_list:
        cells.append({
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": [[{"type": "text", "text": {"content": str(c)}}] for c in row]
            }
        })
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": len(headers_list),
            "has_column_header": True,
            "has_row_header": False,
            "children": cells
        }
    }

def create_detailed_devlog():
    # Raw GitHub url of the pushed image
    image_url = "https://raw.githubusercontent.com/Seungyeopkang/VLM-Based-Industrial-Safety-Monitoring-Pipeline/main/notion/assets/evaluation_comparison.png"
    
    url = "https://api.notion.com/v1/pages"
    
    # 1. Speed & Resource Metrics Rows
    speed_headers = ["Model", "Params (M)", "Load (ms)", "Inference (ms)", "FPS", "RAM (MB)"]
    speed_rows = [
        ["keremberke/yolov8m", "25.85", "81.65", "14.75", "67.8", "123.16"],
        ["Hansung-Cho/yolov8-ppe", "3.01", "23.53", "5.24", "190.72", "50.0"],
        ["Tanishjain9/yolov8n", "2.69", "21.03", "5.44", "183.77", "45.0"]
    ]
    
    # 2. Construction-PPE Rows
    cppe_headers = ["Model", "Helmet F1 (P / R)", "No-Helmet F1 (P / R)", "Vest F1 (P / R)"]
    cppe_rows = [
        ["keremberke/yolov8m", "0.00 (0.00 / 0.00)", "0.00 (0.00 / 0.00)", "0.00 (0.00 / 0.00)"],
        ["Hansung-Cho/yolov8-ppe", "0.79 (0.81 / 0.78)", "0.22 (0.21 / 0.23)", "0.70 (0.72 / 0.67)"],
        ["Tanishjain9/yolov8n", "0.18 (0.75 / 0.10)", "0.00 (0.00 / 0.00)", "0.46 (0.59 / 0.37)"]
    ]
    
    # 3. Hard Hat Workers Rows
    hh_headers = ["Model", "Helmet F1 (P / R)", "No-Helmet F1 (P / R)", "Vest F1"]
    hh_rows = [
        ["keremberke/yolov8m", "0.00 (0.00 / 0.00)", "0.00 (0.00 / 0.00)", "N/A"],
        ["Hansung-Cho/yolov8-ppe", "0.50 (0.50 / 0.50)", "0.09 (0.09 / 0.08)", "0.00"],
        ["Tanishjain9/yolov8n", "0.29 (0.91 / 0.17)", "0.00 (0.00 / 0.00)", "0.00"]
    ]

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
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": "3종 YOLOv8 모델 후보군에 대해 추론 지연속도, FPS, 메모리 사용량, 파라미터 수의 로컬 GPU 벤치마크 및 2개 데이터셋의 정밀성(Precision, Recall, F1)을 산출하고 비교 분석을 완료하였습니다."}}]
                }
            },
            
            # Speed Table
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": "1. 하드웨어 리소스 및 속도 벤치마크 결과"}}]
                }
            },
            make_table_block(speed_headers, speed_rows),
            
            # Construction-PPE Table
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": "2. Construction-PPE 데이터셋 정량 평가 결과"}}]
                }
            },
            make_table_block(cppe_headers, cppe_rows),
            
            # Hard Hat Workers Table
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": "3. Hard Hat Workers v10 데이터셋 정량 평가 결과"}}]
                }
            },
            make_table_block(hh_headers, hh_rows),
            
            # Image Visualization
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "📈 종합 시각화 자료 (3x3 Grid)"}}]
                }
            },
            {
                "object": "block",
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {
                        "url": image_url
                    }
                }
            },
            
            # Technology Decisions
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
                        {"type": "text", "text": {"content": "Hansung-Cho/yolov8-ppe-detection 모델 선정"}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "\n  - 실시간 추론 속도(190.72 FPS) 및 가벼운 리소스 소모(RAM 50MB, Params 3.01M)로 기획 방향인 실시간 파이프라인의 1차 필터에 완벽 부합.\n  - Helmet F1 0.793, Vest F1 0.698로 가장 뛰어난 감지 신뢰도를 기록함.\n  - 위반 사항(NO-Hardhat, NO-Safety Vest, NO-Mask) 클래스가 자체적으로 학습되어 있어 연계가 수월함."}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "• "}},
                        {"type": "text", "text": {"content": "신뢰도 임계값 구간을 통한 하이브리드 VLM 호출 분기 수립"}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": "\n  - 단독 탐지 모델의 미착용(no_helmet) F1 스코어가 극도로 낮음(0.08 ~ 0.22)을 발견.\n  - 1차 탐지 신뢰도가 확실히 높은 영역(예: >0.75)은 VLM 호출을 건너뛰어 비용을 절감하고, 신뢰도가 애매하게 겹치는 구간(0.3 ~ 0.75)만 선별적으로 VLM API를 호출해 최종 판단을 보정하는 설계 타당성 검증."}}
                    ]
                }
            },
            
            # Problems & Solutions
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
                        {"type": "text", "text": {"content": "\n  - 원인: 각 모델 배포처마다 상이한 PPE 라벨 스키마 및 가중치를 사용함.\n  - 해결: 모델 고유 클래스명을 표준 클래스(helmet, no_helmet, vest)로 통일해주는 매핑 딕셔너리를 구축하고, 테스트 이미지 단위로 IoU(>=0.5) 기반 매칭을 직접 연산하는 evaluate.py 코드를 작성하여 해결."}}
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
                        {"type": "text", "text": {"content": "\n  - 원인: annotations를 text 오브젝트 하위 필드로 오인해 삽입함.\n  - 해결: annotations는 text와 형제(sibling) 계층 구조에 위치해야 하므로 API 스펙에 맞게 payload 구조를 수정하여 정상 연동 성공."}}
                    ]
                }
            },
            
            # Next steps
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
        new_page_url = res.json().get("url")
        print(f"Successfully created DETAILED Dev Log page in Notion!")
        print(f"New Notion Page URL: {new_page_url}")
    else:
        print("Failed to create DETAILED Dev Log page:", res.text)

if __name__ == "__main__":
    copy_and_push_image()
    archive_previous_page()
    create_detailed_devlog()
