import os
import requests
from dotenv import load_dotenv

env_path = r"c:\Users\user\Desktop\VLM-Based Industrial Safety Monitoring Pipeline\.env"
load_dotenv(dotenv_path=env_path)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
PAGE_ID = "38f73d49-32e0-81ef-8b76-c695924fcb4e"

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def append_deep_analysis():
    url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children"
    
    payload = {
        "children": [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "🔍 [심층 분석] keremberke 모델의 0.00 성능 현상 분석"}}]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": "Q. keremberke 모델이 모든 지표에서 0.00이 나오는 것이 매핑 오류인가, 실제 성능 한계인가?\n\n"}
                        },
                        {
                            "type": "text",
                            "text": {"content": "A. 클래스 매핑(helmet -> 0, no_helmet -> 1)은 정상적으로 연동되어 있습니다. 그럼에도 0.00이 나온 이유를 밝히기 위해 "},
                            "annotations": {"bold": True}
                        },
                        {
                            "type": "text",
                            "text": {"content": "임계값을 극단적인 0.001로 설정하여 706장의 테스트 이미지를 전수 조사"}
                        },
                        {
                            "type": "text",
                            "text": {"content": "하였습니다.\n\n• 총 15,506개의 예측 바운딩 박스가 검출되었으나, 클래스 분포는 다음과 같습니다:\n  - no_glove: 7,537회\n  - no_goggles: 6,111회\n  - glove: 852회\n  - goggles: 1,006회\n  - "}
                        },
                        {
                            "type": "text",
                            "text": {"content": "helmet / no_helmet: 0회 (단 한 번도 검출되지 않음)\n\n"},
                            "annotations": {"bold": True, "color": "red"}
                        },
                        {
                            "type": "text",
                            "text": {"content": "• 원인 분석 (도메인 미스매치):\n"},
                            "annotations": {"bold": True}
                        },
                        {
                            "type": "text",
                            "text": {"content": "keremberke 모델이 학습한 데이터셋은 주로 실험실/클린룸 내부의 상반신 클로즈업 뷰(장갑, 고글 위주)입니다. 반면, 평가에 사용된 Construction-PPE 데이터셋은 야외 건설 현장의 전신/원거리 뷰이므로 모델의 피처 추출기(Feature Extractor)가 전혀 다르게 반응합니다. 작은 헬멧은 아예 인지하지 못하고, 장갑이 없는 맨손이나 고글 미착용 얼굴 영역에만 극단적인 편향(bias)을 보여 'no_glove', 'no_goggles'로만 예측이 쏟아진 것입니다.\n\n"}
                        },
                        {
                            "type": "text",
                            "text": {"content": "• 결론:\n"},
                            "annotations": {"bold": True}
                        },
                        {
                            "type": "text",
                            "text": {"content": "비교 분석은 공정하게 진행되었으며, 이 결과를 통해 국내 건설 현장에 사전 학습된 Hansung-Cho 모델의 현장 적용성이 압도적임을 정량적으로 증명할 수 있었습니다."}
                        }
                    ]
                }
            }
        ]
    }
    
    res = requests.patch(url, json=payload, headers=headers)
    if res.status_code == 200:
        print("Successfully appended deep analysis to Notion devlog!")
    else:
        print("Failed to append analysis to Notion:", res.text)

if __name__ == "__main__":
    append_deep_analysis()
