import os
import sys
import re
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

def parse_inline_text(text):
    """
    텍스트 내의 **굵게**, `코드`, [링크](URL) 마크다운 문법을 파싱하여
    노션 rich_text 포맷으로 변환합니다.
    """
    pattern = re.compile(
        r'(\*\*(?P<bold>[^\*]+)\*\*)|'
        r'(`(?P<code>[^`]+)`)|'
        r'(\[(?P<link_text>[^\]]+)\]\((?P<link_url>[^\)]+)\))'
    )
    
    rich_text = []
    last_idx = 0
    
    for match in pattern.finditer(text):
        # 매치 이전의 일반 텍스트 추가
        if match.start() > last_idx:
            plain_part = text[last_idx:match.start()]
            rich_text.append({
                "type": "text",
                "text": {"content": plain_part}
            })
            
        gd = match.groupdict()
        if gd.get("bold"):
            rich_text.append({
                "type": "text",
                "text": {"content": gd["bold"]},
                "annotations": {"bold": True}
            })
        elif gd.get("code"):
            rich_text.append({
                "type": "text",
                "text": {"content": gd["code"]},
                "annotations": {"code": True}
            })
        elif gd.get("link_text"):
            rich_text.append({
                "type": "text",
                "text": {
                    "content": gd["link_text"],
                    "link": {"url": gd["link_url"]}
                }
            })
            
        last_idx = match.end()
        
    if last_idx < len(text):
        rich_text.append({
            "type": "text",
            "text": {"content": text[last_idx:]}
        })
        
    return rich_text

def convert_markdown_to_blocks(markdown_text):
    """
    마크다운 텍스트를 노션 블록 객체 배열로 변환합니다.
    """
    blocks = []
    lines = markdown_text.split('\n')
    
    in_code_block = False
    code_content = []
    code_language = "plain text"
    
    for line in lines:
        stripped = line.strip()
        
        # 코드 블록 처리
        if stripped.startswith("```"):
            if in_code_block:
                # 코드 블록 종료
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": "\n".join(code_content)}}],
                        "language": code_language
                    }
                })
                code_content = []
                in_code_block = False
            else:
                # 코드 블록 시작
                in_code_block = True
                lang = stripped[3:].strip()
                # 노션 API가 허용하는 언어로 맵핑 (기본값 plain text)
                code_language = lang if lang else "plain text"
            continue
            
        if in_code_block:
            code_content.append(line)
            continue
            
        if not stripped:
            continue
            
        # Headings
        if stripped.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": parse_inline_text(stripped[4:])
                }
            })
        elif stripped.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": parse_inline_text(stripped[3:])
                }
            })
        elif stripped.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": parse_inline_text(stripped[2:])
                }
            })
        # Blockquotes
        elif stripped.startswith("> "):
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {
                    "rich_text": parse_inline_text(stripped[2:])
                }
            })
        # Bullet Lists
        elif stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("· ") or stripped.startswith("• "):
            content = stripped[2:]
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": parse_inline_text(content)
                }
            })
        # Regular Paragraph
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": parse_inline_text(line)
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
