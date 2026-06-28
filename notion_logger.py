import os
import sys
import requests
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

if not NOTION_API_KEY or NOTION_API_KEY == "your_notion_api_key_here":
    print("Error: NOTION_API_KEY가 .env 파일에 올바르게 설정되지 않았습니다.")
    sys.exit(1)

if not NOTION_DATABASE_ID or NOTION_DATABASE_ID == "your_notion_database_id_here":
    print("Error: NOTION_DATABASE_ID가 .env 파일에 올바르게 설정되지 않았습니다.")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def convert_markdown_to_blocks(markdown_text):
    """
    간단한 마크다운 텍스트를 노션 블록 객체 배열로 변환합니다.
    """
    blocks = []
    lines = markdown_text.strip().split('\n')
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        # Headers
        if line_str.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": line_str[4:]}}]
                }
            })
        elif line_str.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": line_str[3:]}}]
                }
            })
        elif line_str.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{"type": "text", "text": {"content": line_str[2:]}}]
                }
            })
        # Bullet Lists
        elif line_str.startswith("- ") or line_str.startswith("* "):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": line_str[2:]}}]
                }
            })
        # Code block representation (simple)
        elif line_str.startswith("```"):
            # 단순화를 위해 코드 블록 마커는 일단 건너뜁니다.
            continue
        # Regular Paragraph
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": line_str}}]
                }
            })
            
    return blocks

def create_dev_log(title, content_markdown):
    url = "https://api.notion.com/v1/pages"
    
    blocks = convert_markdown_to_blocks(content_markdown)
    
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": title
                        }
                    }
                ]
            }
        },
        "children": blocks
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        print(f"성공: 노션에 '{title}' 페이지를 성공적으로 생성했습니다!")
        return True
    else:
        print(f"실패 (상태 코드: {response.status_code})")
        print("응답 메시지:", response.text)
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python notion_logger.py \"제목\" \"마크다운_내용\"")
        sys.exit(1)
        
    title_arg = sys.argv[1]
    content_arg = sys.argv[2]
    create_dev_log(title_arg, content_arg)
